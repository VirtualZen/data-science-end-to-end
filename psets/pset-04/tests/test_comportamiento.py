"""Comportamiento de negocio de la decision (regla del PSet 1) y respaldo."""
from __future__ import annotations

import json
import os

import numpy as np


def _respuesta(cliente, peticion):
    r = cliente.post("/predecir", json=peticion)
    assert r.status_code == 200, r.text
    return r.json()


def test_diez_incluidas_y_pesos_suman_uno(cliente, peticion):
    """Con un universo completo se incluyen exactamente 10 acciones y el capital se reparte entero."""
    c = _respuesta(cliente, peticion)
    pesos = [a["peso"] for a in c["acciones"] if a["decision"] == "incluir"]
    assert c["n_incluidas"] == 10 == len(pesos)
    assert abs(sum(pesos) - 1) < 1e-9
    assert all(a["peso"] == 0 for a in c["acciones"] if a["decision"] == "no incluir")


def test_tope_de_volatilidad(cliente, peticion):
    """Ninguna accion por encima del percentil 80 de vol_63d del mes entra, aunque tenga el mejor retorno."""
    vols = np.array([a["vol_63d"] for a in peticion["acciones"]])
    tope = np.quantile(vols, 0.80)
    c = _respuesta(cliente, peticion)
    vol = {a["accion_key"]: a["vol_63d"] for a in peticion["acciones"]}
    assert all(vol[a["accion_key"]] <= tope for a in c["acciones"] if a["decision"] == "incluir")


def test_menos_volatil_pesa_mas(cliente, peticion):
    """Pesos inversos a la volatilidad: entre las incluidas, la de menor vol_63d recibe el mayor peso."""
    c = _respuesta(cliente, peticion)
    vol = {a["accion_key"]: a["vol_63d"] for a in peticion["acciones"]}
    inc = [(vol[a["accion_key"]], a["peso"]) for a in c["acciones"] if a["decision"] == "incluir"]
    assert min(inc)[1] == max(p for _, p in inc)


def test_misma_entrada_misma_decision(cliente, peticion):
    a, b = _respuesta(cliente, peticion), _respuesta(cliente, peticion)
    assert [x["decision"] for x in a["acciones"]] == [x["decision"] for x in b["acciones"]]


def test_interruptor_de_respaldo(cliente, peticion, token):
    """Con el interruptor activo responde la linea base (B1 + B5), marcada, y al apagarlo vuelve el modelo."""
    assert cliente.post("/respaldo", params={"activar": True}, headers=token).json()["respaldo"] is True
    try:
        c = _respuesta(cliente, peticion)
        assert c["modelo"]["respaldo"] is True and c["usado"].startswith("respaldo")
        assert c["n_incluidas"] == len(peticion["acciones"])         # B5: todo el universo, igual peso
        assert {a["retorno_predicho"] for a in c["acciones"]} == {c["acciones"][0]["retorno_predicho"]}
    finally:
        cliente.post("/respaldo", params={"activar": False}, headers=token)
    assert _respuesta(cliente, peticion)["usado"] == "modelo"


def test_respaldo_si_el_modelo_no_carga(cliente, peticion, monkeypatch):
    """Sin modelo cargado (p. ej. el arranque fallo), la API no cae: responde el respaldo marcado y /salud
    dice degradado."""
    from api.main import ESTADO
    monkeypatch.setattr(ESTADO, "modelo", None)
    assert cliente.get("/salud").json()["estado"] == "degradado"
    c = _respuesta(cliente, peticion)
    assert c["modelo"]["respaldo"] is True and c["usado"].startswith("respaldo")


def test_recarga_fallida_conserva_el_modelo(cliente, peticion, token, monkeypatch, tmp_path):
    """Si el alias se mueve a algo que no carga, /recargar responde 503 y se sigue sirviendo el modelo anterior."""
    monkeypatch.setenv("MODELO_URI", str(tmp_path / "no-existe"))
    assert cliente.post("/recargar", headers=token).status_code == 503
    assert _respuesta(cliente, peticion)["usado"] == "modelo"


def test_cada_prediccion_queda_registrada(cliente, peticion):
    c = _respuesta(cliente, peticion)
    lineas = [json.loads(x) for x in open(os.environ["REGISTRO_PREDICCIONES"])]
    mias = [x for x in lineas if x["id_lote"] == c["id_lote"]]
    assert len(mias) == len(peticion["acciones"])
    assert {"id_prediccion", "timestamp_utc", "entradas", "retorno_predicho", "modelo_version", "run_id",
            "latencia_ms"} <= set(mias[0])


def test_operacion_manual_en_paralelo(cliente, peticion):
    """La respuesta trae tambien la decision del competidor B7 (operacion manual), sin cambiar la del modelo:
    10 incluidas, pesos que suman 1 y ninguna sobre el tope de volatilidad."""
    c = _respuesta(cliente, peticion)
    man = [a for a in c["acciones"] if a["decision_operacion_manual"] == "incluir"]
    assert len(man) == 10 and abs(sum(a["peso_operacion_manual"] for a in man) - 1) < 1e-9
    vol = {a["accion_key"]: a["vol_63d"] for a in peticion["acciones"]}
    tope = np.quantile(list(vol.values()), 0.80)
    assert all(vol[a["accion_key"]] <= tope for a in man)
    sh = [a["sharpe_12m"] for a in c["acciones"]]
    corte = min(a["sharpe_12m"] for a in man)
    assert c["n_incluidas"] == 10 and 0 <= c["n_coinciden_operacion_manual"] <= 10
    assert sum(1 for a, v in zip(c["acciones"], sh) if v > corte and vol[a["accion_key"]] <= tope) <= 9


def test_el_orden_de_las_acciones_no_cambia_la_decision(cliente, peticion):
    """El lote es un conjunto: invertir el orden de las acciones no cambia ninguna prediccion, decision ni peso
    (dispersion_mes y el tope de volatilidad se calculan sobre todo el mes, no sobre la posicion)."""
    def por_accion(c):
        return {a["accion_key"]: (a["decision"], round(a["peso"], 12), round(a["retorno_predicho"], 12))
                for a in c["acciones"]}
    directo = por_accion(_respuesta(cliente, peticion))
    peticion["acciones"] = peticion["acciones"][::-1]
    assert por_accion(_respuesta(cliente, peticion)) == directo
