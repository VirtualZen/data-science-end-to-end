"""Seccion 8 de CD_PSet_3.pdf: seleccion del ganador, hold-out una sola vez y Model Registry.

- finalistas(): todos los candidatos (sin ajustar y la mejor configuracion de cada tuning) ordenados por el MAE de
  CV; el ganador y el segundo salen de ahi.
- comparar_pliegues(): diferencia de MAE pliegue a pliegue entre los dos; ¿supera la variacion entre pliegues?
- evaluar_holdout(): el UNICO uso del hold-out: metricas de regresion, IC y metrica de negocio, registrado como
  corrida con fase "final".
- registrar_en_registry(): portafolio-inversiones-modelo, alias champion y challenger.
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .evaluacion import ic_por_mes, resumen_ic
from .experimentos import EXPERIMENTO, _git, _mlflow, CONSERVAR
from .negocio import metrica_negocio, REGLA
from .pipeline import TARGET, metricas_regresion

ROOT = Path(__file__).resolve().parents[1]
NOMBRE_MODELO = f'{EXPERIMENTO}-modelo'          # <proyecto>-modelo


def finalistas() -> pd.DataFrame:
    """Candidatos de la seccion 6 y la mejor configuracion de cada tuning, ordenados por MAE de CV."""
    c = pd.read_csv(ROOT / 'docs/candidatos.csv')
    c = c[c.familia != 'linea_base'].assign(version='por defecto')
    filas = [c]
    for ruta in sorted((ROOT / 'docs').glob('tuning_M*.csv')):
        t = pd.read_csv(ruta).sort_values('mae_cv_media').head(1).assign(version='ajustado (Optuna)')
        filas.append(t)
    f = pd.concat(filas, ignore_index=True)
    cols = ['modelo', 'version', 'familia', 'mae_train_cv', 'mae_cv_media', 'mae_cv_std', 'brecha_mae', 'ic_media',
            'negocio_sharpe_neto', 'negocio_drawdown_max', 'segundos_entrenamiento', 'run_id', 'model_uri']
    f = f[[x for x in cols if x in f]].sort_values('mae_cv_media')
    # Una fila por modelo (su mejor version): champion y challenger son modelos distintos, no dos versiones del mismo.
    f = f.drop_duplicates('modelo').reset_index(drop=True)
    f['registrable'] = f.model_uri.notna() if 'model_uri' in f else False
    return f


def mae_por_pliegue(run_id: str) -> np.ndarray:
    mlflow = _mlflow()
    try:
        return np.asarray(mlflow.artifacts.load_dict(f'runs:/{run_id}/pliegues.json')['mae_cv'], dtype=float)
    except Exception:
        return np.array([])


def comparar_pliegues(run_a: str, run_b: str) -> dict:
    a, b = mae_por_pliegue(run_a), mae_por_pliegue(run_b)
    if len(a) == 0 or len(a) != len(b):
        return {'pliegues': 0}
    d = b - a                                       # > 0: el primero (a) tiene menos error
    return {'pliegues': len(d), 'diferencia_media': float(d.mean()), 'desv_diferencias': float(d.std(ddof=1)),
            'pliegues_que_gana_a': int((d > 0).sum()), 'desv_entre_pliegues_a': float(a.std(ddof=1)),
            'supera_variacion': bool(d.mean() > a.std(ddof=1)),
            't_pareado': float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))) if d.std(ddof=1) > 0 else np.nan}


def predecir_holdout(model_uri: str, holdout: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Carga el Pipeline registrado y predice el hold-out; devuelve predicciones y ms por fila."""
    import mlflow.pyfunc
    modelo = mlflow.pyfunc.load_model(model_uri)
    columnas = modelo.metadata.get_input_schema().input_names()
    t0 = time.perf_counter()
    pred = np.asarray(modelo.predict(holdout[columnas]), dtype=float)
    ms = 1000 * (time.perf_counter() - t0) / len(holdout)
    salida = holdout[[c for c in CONSERVAR if c in holdout]].assign(pred=pred, real=holdout[TARGET].values)
    return salida, ms


def evaluar_holdout(nombre, model_uri, holdout, meta, rol, riesgo=None, meta_dia=None, run_cv=None) -> dict:
    """Unico uso del hold-out para un finalista: corrida con fase "final" en MLflow."""
    mlflow = _mlflow()
    pred, ms = predecir_holdout(model_uri, holdout)
    reg = metricas_regresion(pred.real, pred.pred)
    ic = resumen_ic(ic_por_mes(pred))
    neg = metrica_negocio(pred, riesgo=riesgo)
    metricas = {**{f'{k}_holdout': v for k, v in reg.items()},
                **{f'{k}_holdout': v for k, v in ic.items() if isinstance(v, (int, float))},
                **{f'negocio_{k}_holdout': v for k, v in neg.items() if isinstance(v, (int, float)) and not isinstance(v, bool)},
                'ms_inferencia_por_fila': ms}
    metricas = {k: float(v) for k, v in metricas.items() if v is not None and np.isfinite(v)}
    commit, sucio = _git()
    with mlflow.start_run(run_name=f'final_{nombre}_{rol}') as run:
        mlflow.set_tags({'fase': 'final', 'modelo': nombre, 'rol': rol, 'git_commit': commit, 'git_dirty': str(sucio)})
        mlflow.log_params({'model_uri': model_uri, 'run_cv': run_cv or '', 'sha256': meta['sha256'],
                           'sha256_dia': (meta_dia or {}).get('sha256', ''), 'filas_holdout': len(holdout),
                           'meses_holdout': f'{holdout.anio_mes.min()}..{holdout.anio_mes.max()}',
                           **{f'regla_{k}': str(v) for k, v in REGLA.items()}})
        mlflow.log_metrics(metricas)
        with tempfile.TemporaryDirectory() as tmp:   # carpeta propia: varias corridas en paralelo
            ruta_tmp = Path(tmp) / 'holdout.csv'
            pred.to_csv(ruta_tmp, index=False)
            mlflow.log_artifact(str(ruta_tmp), artifact_path='holdout')
        return {'modelo': nombre, 'rol': rol, 'run_id': run.info.run_id, **metricas}


def registrar_en_registry(champion_uri: str, challenger_uri: str) -> dict:
    mlflow = _mlflow()
    from mlflow import MlflowClient
    cliente = MlflowClient()
    v1 = mlflow.register_model(champion_uri, NOMBRE_MODELO)
    v2 = mlflow.register_model(challenger_uri, NOMBRE_MODELO)
    cliente.set_registered_model_alias(NOMBRE_MODELO, 'champion', v1.version)
    cliente.set_registered_model_alias(NOMBRE_MODELO, 'challenger', v2.version)
    return {'nombre': NOMBRE_MODELO, 'champion': v1.version, 'challenger': v2.version}


def exportar_corridas() -> Path:
    mlflow = _mlflow()
    r = mlflow.search_runs(experiment_names=[EXPERIMENTO])
    destino = ROOT / 'docs/corridas.csv'
    r.to_csv(destino, index=False)
    return destino
