"""Competidor "operacion manual" (modelos/src/operacion_manual.py), con datos armados a mano."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.operacion_manual import portafolio, seleccion_mes, sharpe_12m


def _mes(anio_mes: int, n: int = 20, semilla: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    return pd.DataFrame({"accion_key": [f"A{i:02d}" for i in range(n)], "anio_mes": anio_mes,
                         "ret_log_252d": np.linspace(-0.2, 0.4, n), "vol_63d": rng.uniform(0.15, 0.35, n),
                         "rf_mes": 0.003, "ret_pct_mes_siguiente": 0.01, "rf_mes_siguiente": 0.003})


def test_sharpe_12m():
    d = pd.DataFrame({"ret_log_252d": [0.30, 0.30, 0.1], "rf_mes": [0.0025, 0.0025, 0.0], "vol_63d": [0.2, 0.0, np.nan]})
    s = sharpe_12m(d)
    assert np.isclose(s[0], (0.30 - 0.03) / 0.2) and s[1:].isna().all()


def test_elige_diez_por_sharpe_bajo_el_tope():
    g = _mes(202401)
    w = seleccion_mes(g)
    assert len(w) == 10 and np.isclose(w.sum(), 1)
    tope = g["vol_63d"].quantile(0.80)
    elegibles = g[g["vol_63d"] <= tope].assign(s=sharpe_12m(g)).nlargest(10, "s")
    assert set(w.index) == set(elegibles["accion_key"])
    assert (g.set_index("accion_key").loc[w.index, "vol_63d"] <= tope).all()


def test_una_accion_muy_volatil_no_entra_aunque_tenga_el_mejor_sharpe():
    g = _mes(202401)
    g.loc[0, ["ret_log_252d", "vol_63d"]] = [5.0, 2.0]          # Sharpe 2,5 pero volatilidad fuera del tope
    assert "A00" not in seleccion_mes(g).index


def test_compra_y_vende_solo_la_diferencia():
    """Si el top 10 no cambia de un mes a otro, la rotacion es solo el ajuste de pesos por precios (pequena);
    si el orden se invierte, se vende la mayor parte y se compra la nueva seleccion (rotacion mayor que 1)."""
    a, b = _mes(202401), _mes(202402)
    igual = portafolio(pd.concat([a, b]))
    b2 = b.assign(ret_log_252d=b["ret_log_252d"].values[::-1])    # el orden de Sharpe se invierte
    distinto = portafolio(pd.concat([a, b2]))
    assert igual.loc[202402, "turnover"] < 0.05 and distinto.loc[202402, "turnover"] > 1.0
    assert distinto.loc[202402, "neto"] < igual.loc[202402, "neto"]          # el costo de 15 pb por US$
