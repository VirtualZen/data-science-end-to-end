"""Competidor "operacion manual": la regla que un asesor puede aplicar sin modelo, en una hoja de calculo.

Cada cierre de mes t:
1. Universo usable: las acciones elegibles del mes (S&P 500 historico que cotiza en NYSE, con historia suficiente:
   la misma elegibilidad de la OBT).
2. Puntaje: el Sharpe de los ultimos 12 meses de cada accion, con datos que existen al cierre de t:
       sharpe_12m = (ret_log_252d - 12 * rf_mes) / vol_63d
   ret_log_252d es el retorno log de 252 dias habiles (12 meses), 12 * rf_mes la tasa libre de riesgo del mismo
   anio (aproximada con la del mes) y vol_63d la volatilidad anualizada de 63 dias, la misma de la regla de riesgo.
   La OBT no trae una volatilidad de 252 dias; con vol_63d el puntaje castiga el riesgo reciente.
3. Volatilidad aprobada: la misma del PSet 1, para comparar solo la seleccion: se descarta el 20 % mas volatil del
   mes (vol_63d sobre el percentil 80) y la volatilidad del portafolio no puede pasar de 1,35 veces la del S&P 500
   (el exceso queda en efectivo).
4. Se eligen las 10 de mayor puntaje, con pesos 1/vol_63d, y se compra o vende la diferencia con el portafolio del mes
   anterior, con 15 pb por US$ negociado (src.negocio.backtest).

Es la linea base B7 del proyecto (competidor de negocio, junto a B4, B5 y B6): no pronostica retornos, ordena
acciones, asi que se mide con la metrica de negocio y no con el MAE.

Uso:
    from src.operacion_manual import portafolio
    serie = portafolio(df_mes, riesgo=RiesgoDiario(dia))      # serie mensual: bruto, turnover, neto, rf...
Registrar la corrida de linea base en MLflow (MLFLOW_TRACKING_URI del entorno; snapshot del PSet 3):
    uv run python -m src.operacion_manual --registrar
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .negocio import REGLA, RiesgoDiario, backtest, pesos_mes

NOMBRE = "operación manual"
ID = "B7_operacion_manual"
PUNTAJE = "sharpe_12m"
COLUMNAS = ["ret_log_252d", "rf_mes", "vol_63d"]


def sharpe_12m(d: pd.DataFrame) -> pd.Series:
    """Sharpe de 12 meses de cada accion al cierre del mes. NaN si falta un dato o la volatilidad no es positiva."""
    vol = d["vol_63d"].where(d["vol_63d"] > 0)
    return ((d["ret_log_252d"] - 12 * d["rf_mes"].fillna(0.0)) / vol).replace([np.inf, -np.inf], np.nan)


def puntuar(d: pd.DataFrame) -> pd.DataFrame:
    return d.assign(**{PUNTAJE: sharpe_12m(d)})


def seleccion_mes(g: pd.DataFrame, regla: dict | None = None) -> pd.Series:
    """Pesos del mes (accion_key -> peso) antes del tope de portafolio: lo que el asesor compraria."""
    r = {**REGLA, **(regla or {})}
    return pesos_mes(puntuar(g), PUNTAJE, vol=r["vol"], n=r["n"], tope_vol=r["tope_vol"],
                     tope_percentil=r["tope_percentil"])


def portafolio(df: pd.DataFrame, riesgo: RiesgoDiario | None = None, **regla) -> pd.DataFrame:
    """Serie mensual del competidor con la misma regla de riesgo y costos que el modelo (src.negocio.REGLA)."""
    return backtest(puntuar(df), PUNTAJE, riesgo=riesgo, **{**REGLA, **regla})


def evaluar(obt: pd.DataFrame, riesgo: RiesgoDiario | None = None) -> dict:
    """Metrica de negocio en los meses de validacion de la CV del PSet 3 (7 pliegues, 2017-2023) y en el hold-out
    (objetivos 2024-01 a 2026-10). La regla no aprende nada: los pliegues solo fijan los meses que se miden."""
    from .negocio import resumen
    from .pipeline import dividir, pliegues, preparar
    entrenamiento, holdout = dividir(preparar(obt))
    meses_cv = np.concatenate([iv for _, iv in pliegues(entrenamiento)])
    cv = resumen(portafolio(entrenamiento.iloc[meses_cv], riesgo=riesgo))
    ho = resumen(portafolio(holdout, riesgo=riesgo))
    return {**{f"negocio_{k}": v for k, v in cv.items()}, **{f"negocio_{k}_holdout": v for k, v in ho.items()}}


def registrar(obt: pd.DataFrame, meta: dict, riesgo: RiesgoDiario | None = None) -> str:
    """Corrida de linea base en el experimento del proyecto, como B1-B5 en el PSet 3. Devuelve el run_id."""
    import os
    import mlflow
    from .experimentos import EXPERIMENTO
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001"))
    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", EXPERIMENTO))
    metricas = evaluar(obt, riesgo)
    with mlflow.start_run(run_name=ID) as run:
        mlflow.set_tags({"fase": "linea_base", "familia": "regla_negocio", "modelo": ID,
                         "descripcion": "10 acciones de mejor Sharpe de 12 meses bajo la volatilidad aprobada"})
        mlflow.log_params({"puntaje": "(ret_log_252d - 12*rf_mes)/vol_63d", **{f"regla_{k}": v for k, v in REGLA.items()},
                           "tabla": meta.get("tabla"), "huella_datos": meta["sha256"][:12], "filas": meta.get("filas"),
                           "tope_portafolio_con_datos_diarios": riesgo is not None})
        mlflow.log_metrics({k: float(v) for k, v in metricas.items() if v == v})
    print(f"{ID}: run {run.info.run_id}; Sharpe CV {metricas['negocio_sharpe_neto']:.3f}, "
          f"hold-out {metricas['negocio_sharpe_neto_holdout']:.3f}")
    return run.info.run_id


if __name__ == "__main__":
    import argparse
    from .datos import cargar
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--registrar", action="store_true", help="registra la corrida de linea base en MLflow")
    args = a.parse_args()
    obt, meta = cargar()
    dia, _ = cargar(grano="dia")
    riesgo = RiesgoDiario(dia)
    if args.registrar:
        registrar(obt, meta, riesgo)
    else:
        print(NOMBRE, evaluar(obt, riesgo))
