"""Contrato de la API: 200 con entrada valida; 422 con el campo que fallo si falta un campo, si el tipo es
incorrecto, si la categoria (mes) no existe, si el valor sale del rango del contrato o si sobra un campo."""
from __future__ import annotations

import pytest


def test_salud(cliente):
    r = cliente.get("/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok" and r.json()["modelo_cargado"] is True


def test_modelo_informa_version_y_run(cliente):
    r = cliente.get("/modelo").json()
    assert r["nombre"] == "portafolio-inversiones-modelo"
    assert r["run_id"] == "f7596a565f8a458492057238f245cf89"
    assert r["version"] == "1"
    assert r["respaldo"] is False


def test_prediccion_valida(cliente, peticion):
    r = cliente.post("/predecir", json=peticion)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["usado"] == "modelo"
    assert len(cuerpo["acciones"]) == len(peticion["acciones"])
    accion = cuerpo["acciones"][0]
    assert set(accion) >= {"id_prediccion", "retorno_predicho", "decision", "peso"}
    assert accion["decision"] in {"incluir", "no incluir"}
    assert cuerpo["modelo"]["version"] == "1"


def _campos(r) -> list[str]:
    assert r.status_code == 422, r.text
    return r.json()["campos_invalidos"]


def test_falta_un_campo(cliente, peticion):
    del peticion["acciones"][0]["vol_63d"]
    assert any(c.endswith("acciones.0.vol_63d") for c in _campos(cliente.post("/predecir", json=peticion)))


def test_tipo_incorrecto(cliente, peticion):
    peticion["acciones"][0]["ret_log_mes"] = "alto"
    assert any(c.endswith("acciones.0.ret_log_mes") for c in _campos(cliente.post("/predecir", json=peticion)))


@pytest.mark.parametrize("anio_mes", [202313, 202300])
def test_categoria_desconocida_mes(cliente, peticion, anio_mes):
    peticion["anio_mes"] = anio_mes
    assert "anio_mes" in _campos(cliente.post("/predecir", json=peticion))


def test_valor_fuera_de_rango(cliente, peticion):
    peticion["acciones"][0]["vol_63d"] = -0.5           # una volatilidad no puede ser negativa
    assert any(c.endswith("acciones.0.vol_63d") for c in _campos(cliente.post("/predecir", json=peticion)))


def test_campo_extra(cliente, peticion):
    peticion["acciones"][0]["sector_inventado"] = "x"
    assert any("sector_inventado" in c for c in _campos(cliente.post("/predecir", json=peticion)))


def test_accion_repetida(cliente, peticion):
    peticion["acciones"].append(peticion["acciones"][0])
    assert cliente.post("/predecir", json=peticion).status_code == 422


def test_recargar_exige_token(cliente):
    assert cliente.post("/recargar").status_code == 401


def test_metricas_por_ventana(cliente, peticion):
    """/metricas?desde= cuenta solo lo ocurrido en la ventana: lo que usa el monitoreo de cada lote."""
    from datetime import datetime, timedelta, timezone
    desde = datetime.now(timezone.utc)
    cliente.post("/predecir", json=peticion)
    peticion["anio_mes"] = 202313
    cliente.post("/predecir", json=peticion)
    s = cliente.get("/metricas", params={"desde": desde.isoformat()}).json()["sistema"]
    assert s["solicitudes"] == 2 and s["errores_4xx"] == 1 and s["predecir_p95_ms"] is not None
    futuro = (desde + timedelta(hours=1)).isoformat()
    assert cliente.get("/metricas", params={"desde": futuro}).json()["sistema"]["solicitudes"] == 0
