"""Reproduce, sin MLflow y en cualquier maquina, el MAE de CV registrado de B1, Ridge, LightGBM y el champion.
Uso: uv run --group modelos python -m src.verificar_reproducibilidad  (escribe docs/reproducibilidad.csv)"""
import json, time, ast
import numpy as np, pandas as pd
from sklearn.base import clone
from src.experimentos import CATALOGO, ROOT, datos_para_registro
from src.pipeline import FEATURES, TARGET, pliegues, crear_pipeline, metricas_regresion
from src.modelos.tabulares import crear_pipeline as crear_tab
train, meta, _, _ = datos_para_registro()
print('sha256', meta['sha256'][:12], 'filas', len(train))
cand = pd.read_csv(ROOT / 'docs/candidatos.csv').set_index('modelo')
t = pd.read_csv(ROOT / 'docs/tuning_M3_lightgbm.csv').sort_values('mae_cv_media').iloc[0]
cv = list(pliegues(train))
def mae_cv(pipe, cols):
    X, y, f = train[cols], train[TARGET], []
    for it, iv in cv:
        est = clone(pipe).fit(X.iloc[it], y.iloc[it])
        f.append(metricas_regresion(y.iloc[iv], est.predict(X.iloc[iv]))['mae'])
    return float(np.mean(f)), float(np.std(f, ddof=1))
casos = []
for n in ['B1_media', 'M4_ridge', 'M3_lightgbm']:
    casos.append((n, crear_pipeline(CATALOGO[n][1]()), FEATURES, cand.loc[n, 'mae_cv_media']))
params = {k[6:]: t[k] for k in t.index if k.startswith('param_') and k[6:] not in ('k', 'transversal') and pd.notna(t[k])}
for k in ('n_estimators', 'num_leaves', 'min_child_samples', 'subsample_freq'): params[k] = int(params[k])
m = CATALOGO['M3_lightgbm'][1]().set_params(**params)
kk = t['param_k']; kk = kk if kk == 'all' else int(kk)
casos.append(('M3_lightgbm ajustado (champion)', crear_tab(m, features=FEATURES, k=kk, transversal=bool(t['param_transversal'] in (True, 'True'))), FEATURES + ['anio_mes'], t['mae_cv_media']))
filas = []
for nombre, pipe, cols, reg in casos:
    i = time.perf_counter(); media, std = mae_cv(pipe, cols)
    filas.append({'modelo': nombre, 'mae_cv_registrado': reg, 'mae_cv_reproducido': media, 'diferencia': media - reg, 'segundos': round(time.perf_counter() - i, 1)})
    print(filas[-1], flush=True)
pd.DataFrame(filas).to_csv(ROOT / 'docs/reproducibilidad.csv', index=False)
