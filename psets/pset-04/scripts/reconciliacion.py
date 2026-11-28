"""Reconciliacion de la estrategia servida con la evaluada (auditoria de Codex, H1 y H2).

Toma la trayectoria REAL de produccion (docs/predicciones.csv: lo que la API sirvio en Kestra, incluido 202604 con v3
por el incidente v7) y la mide con tres definiciones:
  - monitoreo: suma de peso x retorno simple, 100 % invertido y sin costos (lo que usan A8, A9 y MONITOREO);
  - estrategia: la regla completa del PSet 1 (src.negocio.backtest): tope de portafolio de 1,35 veces la volatilidad
    del S&P 500 con covarianzas diarias de 63 dias, efectivo a la tasa libre de riesgo y 15 pb por rotacion;
  - simulacion: la serie 'sistema' de docs/simulacion/resultado_lotes.csv (contrafactual sin el incidente).
No escribe en Snowflake ni en MLflow. Salida: docs/reconciliacion_negocio.csv y un resumen en pantalla.
Uso, desde psets/pset-04/ (necesita modelos/data/obt.parquet y obt_dia.parquet):
    uv run --project modelos python scripts/reconciliacion.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "modelos"))
from src.datos import cargar  # noqa: E402
from src.negocio import REGLA, RiesgoDiario, backtest  # noqa: E402

DOCS = RAIZ / "docs"


def sharpe(x: pd.Series, rf: pd.Series) -> float:
    e = x - rf
    return float(e.mean() / e.std(ddof=1) * np.sqrt(12))


def main() -> None:
    prod = pd.read_csv(DOCS / "predicciones.csv", low_memory=False)
    prod.columns = prod.columns.str.lower()
    prod["vol_63d"] = [json.loads(e)["vol_63d"] for e in prod["entradas"]]
    sim = pd.read_csv(DOCS / "simulacion/predicciones_simulacion.csv", low_memory=False)
    obt, _ = cargar(RAIZ / "modelos/data/obt.parquet")
    rf = obt.groupby("anio_mes")["rf_mes_siguiente"].first()
    d = prod.merge(sim[["anio_mes", "accion_key", "ret_log_mes_siguiente"]], on=["anio_mes", "accion_key"])
    d = d[d["ret_log_mes_siguiente"].notna()].copy()               # 2026-10 aun sin objetivo
    d["ret_pct_mes_siguiente"] = np.expm1(d["ret_log_mes_siguiente"])
    d["rf_mes_siguiente"] = d["anio_mes"].map(rf)

    monitoreo = d.groupby("anio_mes").apply(lambda g: float((g["peso"] * g["ret_pct_mes_siguiente"]).sum()),
                                            include_groups=False)
    dia, _ = cargar(RAIZ / "modelos/data/obt_dia.parquet", grano="dia")
    estrategia = backtest(d, "retorno_predicho", riesgo=RiesgoDiario(dia), **REGLA)
    sim_lotes = pd.read_csv(DOCS / "simulacion/resultado_lotes.csv", index_col="anio_mes")

    t = pd.DataFrame({"version_servida": d.groupby("anio_mes")["modelo_version"].first(),
                      "monitoreo_bruto_100pct": monitoreo,
                      "estrategia_neta": estrategia["neto"], "invertido": estrategia["invertido"],
                      "turnover": estrategia["turnover"], "simulacion_neta": sim_lotes["sistema"],
                      "rf": estrategia["rf"]})
    t.to_csv(DOCS / "reconciliacion_negocio.csv")
    r = {c: sharpe(t[c], t["rf"]) for c in ("monitoreo_bruto_100pct", "estrategia_neta", "simulacion_neta")}
    print(t.round(4).to_string())
    print("\nSharpe anual (", len(t), "lotes etiquetados ):", {k: round(v, 3) for k, v in r.items()})
    print("US$ 100.000 ->", {c: round(100000 * float(np.prod(1 + t[c])), 0)
                             for c in ("monitoreo_bruto_100pct", "estrategia_neta", "simulacion_neta")})
    print("meses con invertido < 1:", int((t["invertido"] < 0.999).sum()),
          "| meses con diferencia produccion-simulacion:",
          int((t["estrategia_neta"] - t["simulacion_neta"]).abs().gt(1e-9).sum()))


if __name__ == "__main__":
    main()
