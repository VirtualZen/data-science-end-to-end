"""Pruebas del diseno experimental (validacion, metricas, ensamble, negocio, tabulares, series).
Datos sinteticos: no leen Snowflake ni data/."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import ensamble, evaluacion, negocio, validacion  # noqa: E402


def panel(meses=pd.period_range("2011-01", "2024-06", freq="M"), n=30, semilla=0):
    rng = np.random.default_rng(semilla)
    filas = []
    for m in meses:
        for a in range(n):
            filas.append({"accion_key": a, "anio_mes": int(m.strftime("%Y%m")),
                          "real": rng.normal(0, 0.08), "vol_63d": rng.uniform(0.1, 0.6),
                          "rf_mes_siguiente": 0.003})
    d = pd.DataFrame(filas)
    d["ret_log_mes_siguiente"] = d["real"]
    return d


# ---------------------------------------------------------------- validacion
def test_walk_forward_sin_fuga_y_sin_holdout():
    d = panel()
    vs = validacion.ventanas_walk_forward()
    assert [v.nombre for v in vs] == [f"wf_{a}" for a in range(2017, 2024)]
    for v in vs:
        it, iv = validacion.indices(d, v)
        mo = validacion.mes_objetivo(d)
        assert mo[it].max() == v.inicio_validacion - 2          # embargo de 1 mes
        assert mo[iv].max() <= pd.Period("2023-12", freq="M")
        assert mo[iv].min() == v.inicio_validacion


def test_fuga_se_detecta():
    d = panel()
    mo = validacion.mes_objetivo(d)
    it = np.flatnonzero(mo <= pd.Period("2019-01", freq="M"))
    iv = np.flatnonzero(mo == pd.Period("2019-01", freq="M"))
    with pytest.raises(AssertionError):
        validacion.verificar_sin_fuga(d, it, iv)


def test_ventana_fija():
    v = validacion.ventanas_walk_forward(anios_validacion=[2020], ventana_meses=36)[0]
    assert (v.fin_entrenamiento - v.inicio_entrenamiento).n == 35


# ---------------------------------------------------------------- evaluacion
def test_ic_de_random_walk_no_existe_y_de_oraculo_es_uno():
    d = panel()
    d["rw"], d["oraculo"] = 0.0, d["real"]
    assert evaluacion.ic_por_mes(d, "rw").isna().all()
    assert evaluacion.ic_por_mes(d, "oraculo").dropna().eq(1.0).all()


def test_diebold_mariano_y_wilcoxon_detectan_un_modelo_mejor():
    d = panel()
    rng = np.random.default_rng(1)
    d["bueno"] = 0.6 * d["real"] + rng.normal(0, 0.02, len(d))
    d["rw"] = 0.0
    t = evaluacion.comparar_contra(d, ["bueno"], "rw")
    assert t.loc["bueno", "dm"] < 0 and t.loc["bueno", "p_dm"] < 0.01
    assert t.loc["bueno", "p_wilcoxon"] < 0.01


def test_holm_es_monotono():
    p = evaluacion.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert p["a"] == pytest.approx(0.03) and p["c"] == pytest.approx(0.06) and p["b"] == pytest.approx(0.06)


# ---------------------------------------------------------------- ensamble
def test_estadisticos_de_orden():
    d = pd.DataFrame({"anio_mes": 1, "accion_key": [0, 1, 2],
                      "m1": [3.0, 2.0, 1.0], "m2": [1.0, 3.0, 2.0], "m3": [3.0, 1.0, 2.0]})
    r = ensamble.rangos_transversales(d, ["m1", "m2", "m3"]) * 3     # rangos 1..3
    assert list(ensamble.estadistico_orden(r, "minimo")) == [1, 1, 2]
    assert list(ensamble.estadistico_orden(r, "maximo")) == [3, 3, 3]
    assert list(ensamble.estadistico_orden(r, "mediana")) == [1, 2, 2]
    s = ensamble.EnsambleRangos(["m1", "m2", "m3"], "mediana").puntaje(d)
    assert s.idxmax() == 0                                            # la mejor por consenso


def test_ensamble_ignora_modelo_sin_prediccion():
    d = pd.DataFrame({"anio_mes": 1, "accion_key": [0, 1], "m1": [1.0, 2.0], "m2": [np.nan, np.nan]})
    r = ensamble.rangos_transversales(d, ["m1", "m2"])
    assert ensamble.estadistico_orden(r, "maximo").notna().all()


# ---------------------------------------------------------------- negocio
def test_backtest_pesos_turnover_y_costos():
    d = panel(meses=pd.period_range("2024-01", "2024-03", freq="M"))
    d["puntaje"] = d["accion_key"]                       # siempre las mismas 10
    s = negocio.backtest(d, "puntaje", costo_bps=10)
    assert (s["n_acciones"] == 10).all()
    assert s["turnover"].iloc[0] == pytest.approx(1.0)  # compra inicial
    assert (s["bruto"] - s["neto"]).iloc[0] == pytest.approx(1e-3)
    assert negocio.drawdown_maximo(s) <= 0
    w = negocio.pesos_mes(d[d.anio_mes == 202401], "puntaje")
    assert w.sum() == pytest.approx(1.0)


def test_tope_de_volatilidad():
    d = panel(meses=pd.period_range("2024-01", "2024-01", freq="M"))
    d["puntaje"] = d["accion_key"]
    w = negocio.pesos_mes(d, "puntaje", tope_vol=0.3)
    assert (d.set_index("accion_key").loc[w.index, "vol_63d"] <= 0.3).all()


# ---------------------------------------------------------------- tabulares
def test_rango_transversal_solo_usa_el_mismo_mes():
    from src.modelos.tabulares import RangoTransversal
    X = pd.DataFrame({"anio_mes": [1, 1, 2, 2], "a": [1.0, 2.0, 100.0, 50.0], "rf_mes": [0.1, 0.1, 0.2, 0.2]})
    r = RangoTransversal(["a", "rf_mes"]).fit_transform(X)
    assert list(r["a"]) == [0.5, 1.0, 1.0, 0.5]
    assert list(r["rf_mes"]) == [0.1, 0.1, 0.2, 0.2]       # variable de mercado sin rango
    X2 = X.copy(); X2.loc[X2.anio_mes == 2, "a"] = [-5.0, 9.0]
    assert list(RangoTransversal(["a"]).fit_transform(X2)["a"][:2]) == [0.5, 1.0]


def test_pipeline_con_filtro_entrena_y_predice():
    from sklearn.linear_model import Ridge
    from src.modelos.tabulares import crear_pipeline
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(200, 5)), columns=list("abcde"))
    X["anio_mes"] = np.repeat(np.arange(20), 10)
    y = X["a"] * 0.5 + rng.normal(0, 0.1, 200)
    p = crear_pipeline(Ridge(), features=list("abcde"), k=2, filtro="informacion_mutua").fit(X, y)
    assert p.named_steps["filtro"].get_support().sum() == 2
    assert len(p.predict(X)) == 200


# ---------------------------------------------------------------- series (ARIMA-GARCH)
def test_arima_garch_sin_fuga():
    pytest.importorskip("arch")
    from src.modelos.series import caracteristicas_accion
    rng = np.random.default_rng(1)
    n = 900
    r = 0.0003 + rng.standard_normal(n) * 0.01
    dia = pd.DataFrame({"fecha": pd.bdate_range("2015-01-01", periods=n), "ret_log_diario": r, "imputado": False})
    org = pd.DataFrame({"anio_mes": [201801], "fecha_origen": [pd.Timestamp("2018-01-31")]})
    a = caracteristicas_accion(dia, org, [2018], ordenes=((0, 0), (1, 0)))
    dia.loc[dia.fecha > "2018-01-31", "ret_log_diario"] = 0.2
    b = caracteristicas_accion(dia, org, [2018], ordenes=((0, 0), (1, 0)))
    assert a and a == b


def test_tope_relativo_excluye_el_20_por_ciento_mas_volatil():
    g = pd.DataFrame({"accion_key": list("ABCDEFGHIJ"), "puntaje": range(10, 0, -1),
                      "vol_63d": [0.9, 0.8, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.15, 0.25]})
    w = negocio.pesos_mes(g, "puntaje", n=10, tope_percentil=0.80)
    assert "A" not in w.index and "B" not in w.index and len(w) == 8
    assert abs(w.sum() - 1) < 1e-12


def test_tope_de_portafolio_deja_efectivo_cuando_se_pasa():
    rng = np.random.default_rng(0)
    fechas = pd.bdate_range("2024-01-01", "2024-03-29")
    filas = []
    for f in fechas:
        sp = rng.normal(0, 0.005)
        for k, s in (("A", 0.03), ("B", 0.03)):
            filas.append({"fecha": f, "accion_key": k, "ret_log_diario": rng.normal(0, s), "ret_log_sp500": sp})
    riesgo = negocio.RiesgoDiario(pd.DataFrame(filas))
    d = pd.DataFrame({"anio_mes": [202403] * 2, "accion_key": ["A", "B"], "p": [2, 1], "vol_63d": [0.45, 0.45],
                      "ret_pct_mes_siguiente": [0.10, 0.10], "rf_mes_siguiente": [0.004] * 2})
    s = negocio.backtest(d, "p", n=2, factor_tope_portafolio=1.35, riesgo=riesgo, costo_bps=15)
    fila = s.iloc[0]
    assert fila.vol_portafolio > 1.35 * fila.vol_sp500
    k = 1.35 * fila.vol_sp500 / fila.vol_portafolio
    assert abs(fila.invertido - k) < 1e-9
    assert abs(fila.bruto - (k * 0.10 + (1 - k) * 0.004)) < 1e-12
    assert abs(fila.neto - (fila.bruto - k * 15 / 1e4)) < 1e-12        # solo se paga por lo invertido


def test_universo_igual_ponderacion_e_indice():
    d = pd.DataFrame({"anio_mes": [202401] * 4, "accion_key": list("ABCD"), "vol_63d": [0.1, 0.2, 0.3, 0.4],
                      "ret_pct_mes_siguiente": [0.04, 0.0, -0.04, 0.08], "rf_mes_siguiente": [0.0] * 4,
                      "ret_log_sp500_mes_siguiente": [np.log(1.02)] * 4})
    u = negocio.portafolio_universo(d, costo_bps=15)
    assert abs(u.bruto.iloc[0] - 0.02) < 1e-12 and u.n_acciones.iloc[0] == 4
    i = negocio.serie_indice(d, "ret_log_sp500_mes_siguiente")
    assert abs(i.neto.iloc[0] - 0.02) < 1e-12 and i.turnover.iloc[0] == 0


def test_b3_media_por_accion_sin_futuro():
    from src.modelos.lineas_base import MediaPorAccion
    X = pd.DataFrame({"accion_key": [1, 1, 2, 2]})
    m = MediaPorAccion().fit(X, [0.02, 0.04, -0.01, 0.01])
    p = m.predict(pd.DataFrame({"accion_key": [1, 2, 3]}))
    assert np.allclose(p, [0.03, 0.0, 0.015])                  # la 3 no tiene historia: media general
