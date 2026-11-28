"""Seccion 7 de CD_PSet_3.pdf: ajuste de hiperparametros de los 3 mejores candidatos con Optuna.

Por que Optuna (TPE) y no RandomizedSearchCV ni busqueda exhaustiva:
  - Con 30 configuraciones por modelo y espacios de 4-8 dimensiones, una rejilla exhaustiva no cabe y el
    muestreo aleatorio desperdicia pruebas; TPE concentra las siguientes pruebas donde el MAE fue mejor.
  - Maneja escalas logaritmicas, enteros y categorias (k del filtro, rango transversal) en un solo espacio.
  - Da las graficas de historia e importancia de hiperparametros para el reporte.
Mismo esquema que los candidatos: los 7 pliegues de src/pipeline.py (TimeSeriesSplit sobre meses) y el MAE de CV
como objetivo (decision W3). Sin poda: cada configuracion se evalua completa en los 7 pliegues.

Cada configuracion es una corrida HIJA (nested) dentro de una corrida PADRE por modelo, con el mismo registro que
los candidatos (src/experimentos.registrar): parametros, datos, todas las metricas, IC, metrica de negocio y
pipeline. La corrida padre guarda la mejor configuracion, la mejora frente al modelo por defecto y si esa mejora
supera la desviacion entre pliegues (si no, el PDF dice que no es mejora).

Uso (con MLflow arriba; un modelo por terminal si se quiere en paralelo):
    uv run --group modelos python -m src.tuning --modelo M3_lightgbm --trials 30
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import pandas as pd

from .entorno import SEMILLA

# Espacios de busqueda: tasas y regularizacion en escala logaritmica (su efecto es multiplicativo); tamanos de
# hoja y de muestra minima tambien en log, porque importan los ordenes de magnitud con ~40 mil filas.
ESPACIOS = {
    "M3_lightgbm": lambda t: {
        "n_estimators": t.suggest_int("n_estimators", 50, 1000, log=True),
        "learning_rate": t.suggest_float("learning_rate", 5e-3, 0.2, log=True),
        "num_leaves": t.suggest_int("num_leaves", 4, 128, log=True),
        "min_child_samples": t.suggest_int("min_child_samples", 20, 2000, log=True),
        "subsample": t.suggest_float("subsample", 0.5, 1.0),
        "subsample_freq": 1,
        "colsample_bytree": t.suggest_float("colsample_bytree", 0.3, 1.0),
        "reg_lambda": t.suggest_float("reg_lambda", 1e-3, 100, log=True),
        "objective": t.suggest_categorical("objective", ["regression", "regression_l1", "huber"])},
    "M3b_xgboost": lambda t: {
        "n_estimators": t.suggest_int("n_estimators", 50, 1000, log=True),
        "learning_rate": t.suggest_float("learning_rate", 5e-3, 0.2, log=True),
        "max_depth": t.suggest_int("max_depth", 2, 8),
        "min_child_weight": t.suggest_float("min_child_weight", 1, 500, log=True),
        "subsample": t.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": t.suggest_float("colsample_bytree", 0.3, 1.0),
        "reg_lambda": t.suggest_float("reg_lambda", 1e-3, 100, log=True),
        "objective": t.suggest_categorical("objective", ["reg:squarederror", "reg:absoluteerror", "reg:pseudohubererror"])},
    "M2_random_forest": lambda t: {
        "n_estimators": t.suggest_int("n_estimators", 50, 400, log=True),
        "max_depth": t.suggest_int("max_depth", 3, 20),
        "min_samples_leaf": t.suggest_int("min_samples_leaf", 20, 2000, log=True),
        "max_features": t.suggest_float("max_features", 0.1, 1.0)},
    "M4_ridge": lambda t: {"alpha": t.suggest_float("alpha", 1e-3, 1e5, log=True)},
    "M5_mlp": lambda t: {
        "hidden_layer_sizes": (t.suggest_int("n1", 8, 128, log=True), t.suggest_int("n2", 4, 64, log=True)),
        "alpha": t.suggest_float("alpha", 1e-5, 10, log=True),
        "learning_rate_init": t.suggest_float("learning_rate_init", 1e-4, 1e-2, log=True),
        "early_stopping": True},
}
# Comun a todos: cuantas columnas deja el filtro SelectKBest y si se usa el rango transversal (percentil del
# mes, hallazgo 2 del EDA: el mes explica el 34,5 % de la varianza).
PREPARACION = lambda t: {"k": t.suggest_categorical("k", [10, 20, 30, "all"]),
                         "transversal": t.suggest_categorical("transversal", [True, False])}


def ajustar(nombre, train, meta, riesgo=None, meta_dia=None, n_trials=30, por_defecto=None):
    import mlflow
    import optuna
    from sklearn.base import clone
    from .experimentos import CATALOGO, _mlflow, _git, registrar, avisar
    from .modelos.tabulares import crear_pipeline
    from .pipeline import FEATURES
    if n_trials < 30:
        raise ValueError('El PDF exige al menos 30 configuraciones por modelo')
    familia, fabrica = CATALOGO[nombre]
    columnas = FEATURES + ['anio_mes']               # anio_mes solo lo usa el rango transversal
    mlflow = _mlflow()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    inicio = time.perf_counter()
    filas = []
    with mlflow.start_run(run_name=f'tuning_{nombre}') as padre:
        commit, sucio = _git()
        mlflow.set_tags({'fase': 'tuning', 'familia': familia, 'modelo': nombre, 'rol': 'padre',
                         'git_commit': commit, 'git_dirty': str(sucio)})
        mlflow.log_params({'busqueda': 'Optuna TPE', 'trials': n_trials, 'semilla': SEMILLA, 'objetivo': 'min mae_cv_media',
                           'pliegues': 'TimeSeriesSplit(7, test_size=12 meses, gap=1)', 'sha256': meta['sha256']})

        def objetivo(trial):
            params, prep = ESPACIOS[nombre](trial), PREPARACION(trial)
            modelo = clone(fabrica()).set_params(**params)
            pipe = crear_pipeline(modelo, features=FEATURES, **prep)
            r = registrar(nombre, train, meta, 'tuning', modelo=modelo, riesgo=riesgo, meta_dia=meta_dia, nested=True,
                          pipe=pipe, columnas=columnas, log_modelo=(nombre != 'M2_random_forest'),
                          parametros_extra={**{f'prep_{k}': v for k, v in prep.items()}, 'trial': trial.number,
                                            'corrida_padre': padre.info.run_id})
            filas.append({'trial': trial.number, **{f'param_{k}': v for k, v in {**params, **prep}.items()}, **r})
            trial.set_user_attr('run_id', r['run_id'])
            return r['mae_cv_media']

        estudio = optuna.create_study(study_name=nombre, direction='minimize',
                                      sampler=optuna.samplers.TPESampler(seed=SEMILLA))
        estudio.optimize(objetivo, n_trials=n_trials, gc_after_trial=True)
        df = pd.DataFrame(filas).sort_values('mae_cv_media')
        mejor = df.iloc[0]
        base = por_defecto or {}
        mejora = base.get('mae_cv_media', np.nan) - mejor.mae_cv_media
        resumen = {'mejor_mae_cv_media': mejor.mae_cv_media, 'mejor_mae_cv_std': mejor.mae_cv_std,
                   'defecto_mae_cv_media': base.get('mae_cv_media', np.nan),
                   'defecto_mae_cv_std': base.get('mae_cv_std', np.nan), 'mejora_mae': mejora,
                   'mejora_supera_desviacion': float(mejora > base.get('mae_cv_std', np.inf)),
                   'mejor_ic_media': mejor.get('ic_media', np.nan),
                   'mejor_negocio_sharpe_neto': mejor.get('negocio_sharpe_neto', np.nan),
                   'segundos_tuning': time.perf_counter() - inicio}
        mlflow.log_metrics({k: float(v) for k, v in resumen.items() if pd.notna(v)})
        mlflow.log_params({'mejor_run_id': mejor.run_id, 'mejor_trial': int(mejor.trial),
                           **{f'mejor_{k}': str(v) for k, v in estudio.best_params.items()}})
        destino = os.path.join(os.path.dirname(__file__), '..', 'docs', f'tuning_{nombre}.csv')
        df.to_csv(destino, index=False)
        mlflow.log_artifact(destino, artifact_path='tuning')
        try:
            import matplotlib
            matplotlib.use('Agg')
            from optuna.visualization import matplotlib as ov
            for nombre_fig, fig in (('historia', ov.plot_optimization_history(estudio)),
                                    ('importancia', ov.plot_param_importances(estudio))):
                ruta = os.path.join(os.path.dirname(__file__), '..', 'docs', 'figuras', f'tuning_{nombre}_{nombre_fig}.png')
                fig.figure.savefig(ruta, dpi=120, bbox_inches='tight')
                mlflow.log_artifact(ruta, artifact_path='tuning')
        except Exception as e:                    # las graficas son opcionales
            print(f'Graficas de Optuna no generadas: {e}')
    avisar('Success', f'tuning {nombre}', json.dumps({k: (round(v, 5) if isinstance(v, float) else v)
                                                       for k, v in resumen.items()}, indent=1))
    return df, resumen


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Tuning con Optuna de un candidato (seccion 7)')
    ap.add_argument('--modelo', required=True, choices=list(ESPACIOS))
    ap.add_argument('--trials', type=int, default=30)
    a = ap.parse_args()
    from .experimentos import datos_para_registro, avisar
    from pathlib import Path
    train, meta, riesgo, meta_dia = datos_para_registro()
    cand = Path(__file__).resolve().parents[1] / 'docs/candidatos.csv'
    defecto = {}
    if cand.exists():
        c = pd.read_csv(cand).set_index('modelo')
        if a.modelo in c.index:
            defecto = c.loc[a.modelo, ['mae_cv_media', 'mae_cv_std']].to_dict()
    try:
        df, res = ajustar(a.modelo, train, meta, riesgo, meta_dia, n_trials=a.trials, por_defecto=defecto)
    except Exception as e:
        avisar('Fail', f'tuning {a.modelo}', f'{type(e).__name__}: {e}')
        raise
    print(json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in res.items()}, indent=1))
