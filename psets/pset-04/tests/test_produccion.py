"""Lotes de produccion (monitoreo/simulacion.py), alertas, disparador y regla de promocion, con datos armados
a mano o con las cifras de la corrida en Kestra; no leen data/ ni usan Snowflake ni MLflow."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from monitoreo.alertas import evaluar
from monitoreo.simulacion import etiquetar, etiquetas, preparar_inferencia
from src.pipeline import FEATURES_OBT, TARGET


def _obt() -> pd.DataFrame:
    filas = []
    for mes in (202609, 202610):
        for i, k in enumerate(("A", "B", "C")):
            f = {c: 0.01 * (i + 1) for c in FEATURES_OBT}
            f.update({"accion_key": k, "ticker": k, "anio_mes": mes, "elegible": True,
                      TARGET: 0.02 if mes == 202609 else np.nan,
                      "ret_pct_mes_siguiente": np.nan, "rf_mes_siguiente": 0.004})
            filas.append(f)
    d = pd.DataFrame(filas)
    d.loc[(d.anio_mes == 202610) & (d.accion_key == "B"), "vol_63d"] = np.nan   # hueco en el mes en vivo
    return d


def test_el_mes_en_vivo_se_sirve_sin_objetivo():
    lote = preparar_inferencia(_obt(), 202610)
    assert len(lote) == 3 and TARGET not in lote
    assert lote["mes_calendario_obj"].eq(11).all()


def test_no_se_rellena_con_meses_posteriores():
    """El hueco de B en 2026-10 queda nulo (no se interpola): esa fila no se envia y cuenta como invalida."""
    lote = preparar_inferencia(_obt(), 202610)
    assert lote.loc[lote.accion_key == "B", "vol_63d"].isna().all()
    assert len(lote.dropna(subset=FEATURES_OBT)) == 2


def test_las_etiquetas_llegan_despues_y_solo_las_que_existen():
    obt = _obt()
    e = etiquetas(obt, deriva=())
    servido = preparar_inferencia(obt, 202610).assign(pred=0.0)
    assert etiquetar(servido, e).empty                     # el objetivo de 2026-10 aun no existe
    assert len(etiquetar(preparar_inferencia(obt, 202609).assign(pred=0.0), e)) == 3


def test_a7_pide_dos_lotes_seguidos():
    base = {"anio_mes": 202610}
    assert not any(a["id_alerta"] == "A7" for a in evaluar({**base, "mae_ultimo": 0.12, "mae_penultimo": 0.05}))
    assert any(a["id_alerta"] == "A7" for a in evaluar({**base, "mae_ultimo": 0.12, "mae_penultimo": 0.09}))


def test_la_deriva_de_datos_sola_no_dispara_reentrenamiento():
    alertas = {a["id_alerta"] for a in evaluar({"anio_mes": 202610, "n_psi_critico": 9, "n_mercado_z3": 2,
                                                "mae_ultimo": 0.05, "mae_penultimo": 0.06})}
    assert {"A4", "A5"} <= alertas and "A7" not in alertas


def test_a9_compara_contra_la_operacion_manual():
    m = {"anio_mes": 202610, "sharpe_12": 0.2, "sharpe_b5_12": 0.1, "sharpe_manual_12": 1.0}
    ids = {a["id_alerta"] for a in evaluar(m)}
    assert "A9" in ids and "A8" not in ids


# Las cinco decisiones de la corrida de produccion en Kestra (27-nov, PORTAFOLIO_P4.PRODUCCION.REENTRENAMIENTOS):
# MAE y retorno del top 10 de champion y challenger en el lote etiquetado mas reciente.
CASOS_REALES = [
    # caso,          mae_champ,  mae_chall,  ret_champ,   ret_chall,  promueve, motivo
    ("v3 (202412)", 0.10200039, 0.08659443, -0.05669296, -0.03597971, True, "cumple la regla"),
    ("v4 (202503)", 0.06817649, 0.07031634, 0.00018364, 0.01642377, False, "su MAE es peor que el del champion"),
    ("v5 (202508)", 0.11726293, 0.10647072, -0.08863979, -0.08958815, False, "no gana suficiente dinero"),
    ("v6 (202511)", 0.05117, 0.05091, 0.0377, 0.0292, False, "no gana suficiente dinero"),  # log de Kestra, redondeado
    ("v8 (202604)", 0.06620589, 0.06550803, 0.04077485, 0.07276637, True, "cumple la regla"),
]


@pytest.mark.parametrize("caso,mae_ch,mae_cl,ret_ch,ret_cl,promueve,motivo", CASOS_REALES,
                         ids=[c[0] for c in CASOS_REALES])
def test_regla_de_promocion_casos_reales(caso, mae_ch, mae_cl, ret_ch, ret_cl, promueve, motivo):
    """La regla de src/reentrenar.py (Comparacion) reproduce cada decision de la corrida en Kestra.

    Gana dinero = retorno del challenger - champion > 0,0134 (1 desviacion de la CV de la metrica de negocio);
    guarda = MAE del challenger <= MAE del champion + 0,0016. v4 gana dinero y cae por la guarda; v5 mejora
    el MAE y cae por dinero: cada mitad de la regla decide un caso. docs/reentrenamiento.md tiene la tabla."""
    from src.reentrenar import Comparacion
    c = Comparacion(lotes_evaluacion=[], mae_champion=mae_ch, mae_challenger=mae_cl, retorno_champion=ret_ch,
                    retorno_challenger=ret_cl, filas_entrenamiento=0, hasta_anio_mes=0, segundos=0.0)
    assert (c.promueve, c.motivo) == (promueve, motivo), caso


def test_enfriamiento_y_calendario_del_disparador(monkeypatch, tmp_path):
    """Una A7 dentro de los 3 lotes etiquetados siguientes a un reentrenamiento no dispara otro; al cumplirse
    el enfriamiento si (por eso v4 llego en 2025-03 con la A7 de 2024-12). Sin A7, dispara el calendario a los 12."""
    import monitoreo.produccion as prod
    monkeypatch.setattr(prod, "SALIDA_LOCAL", tmp_path)
    meses = [m for a in (2024, 2025, 2026) for m in range(a * 100 + 1, a * 100 + 13)]
    pd.DataFrame({"anio_mes_llegada": [202412]}).to_csv(tmp_path / "reentrenamientos.csv", index=False)
    pd.DataFrame({"anio_mes": [202412], "id_alerta": ["A7"]}).to_csv(tmp_path / "alertas.csv", index=False)
    assert prod.disparo(202501, meses, local=True) == (False, None)          # 2 lotes nuevos: espera
    assert prod.disparo(202502, meses, local=True) == (True, "rendimiento (A7)")
    (tmp_path / "alertas.csv").unlink()
    assert prod.disparo(202510, meses, local=True) == (False, None)
    assert prod.disparo(202511, meses, local=True) == (True, "calendario (12 lotes)")


def test_reproceso_sin_alertas_borra_las_anteriores(monkeypatch, tmp_path):
    """Auditoria H6: lote con A7 -> reproceso sin alertas -> ninguna alerta vigente para ese lote (ALERTAS es el
    estado actual por lote; el historial queda en los logs de Kestra)."""
    import monitoreo.produccion as prod
    monkeypatch.setattr(prod, "SALIDA_LOCAL", tmp_path)
    prod.escribir("ALERTAS", pd.DataFrame({"anio_mes": [202509, 202510], "id_alerta": ["A7", "A7"]}), True,
                  borrar_mes=202509)
    prod.escribir("ALERTAS", pd.DataFrame(columns=["anio_mes", "id_alerta"]), True, borrar_mes=202509)
    vigentes = prod.leer_tabla("ALERTAS", True)
    assert list(vigentes["anio_mes"]) == [202510]
