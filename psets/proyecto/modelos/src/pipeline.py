"""Preparacion de la OBT para todos los modelos del PSet 3 (seccion 3 de CD_PSet_3.pdf).

Misma forma que laboratorios/semana-09-sesion-02/plantilla-pipeline/pipeline_proyecto.py y
semana-11-sesion-02 (preparacion_taxis.py + ejercicio1_validacion.ipynb):

    from src.pipeline import preparar, dividir, pliegues, crear_pipeline, validar, FEATURES, TARGET

- preparar(obt)          filas elegibles + features derivadas (02_features)
- dividir(datos)         UNA division temporal: entrenamiento (objetivo <= 2023-12) / hold-out
- preparacion()          ColumnTransformer: numericas (mediana + escalar) y categoricas (moda + one-hot)
- crear_pipeline(modelo) Pipeline([("preparar", preparacion()), ("modelo", modelo)])
- pliegues(train)        TimeSeriesSplit sobre meses: 7 pliegues de 12 meses, gap de 1 mes
- validar(modelo, train) cross_validate con la metrica tecnica (MAE) en esos pliegues
- predecir_pliegues(...) predicciones fuera de muestra por pliegue, para IC y metrica de negocio

Catalogo de columnas de las dos OBT (pipeline/spark/jobs/construir_obt.py) y que entra como
predictor. Fuente unica: src/modelos/tabulares.py lo importa de aqui.

Para comprobar que corre de principio a fin, sin notebook:  uv run python -m src.pipeline
"""
import time

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import TimeSeriesSplit, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TARGET = 'ret_log_mes_siguiente'

# --- OBT_ACCION_MES (75 columnas): 43 del PSet 2 + 32 de F1 (PSet 3) -----------------------
OBT_MES_PSET2 = [
    'accion_key', 'ticker', 'nombre', 'bolsa', 'es_nyse', 'bolsa_desconocida', 'anio_mes', 'anio', 'mes',
    'conjunto', 'objetivo_cruza_corte', 'fecha_ultima_cotizacion', 'cotizo_al_cierre_de_mes', 'en_sp500',
    'sigue_en_sp500', 'elegible', 'precio_cierre_ajustado', 'ret_log_mes', 'ret_log_21d', 'ret_log_252d',
    'momentum_12_1', 'vol_21d', 'vol_63d', 'vol_apertura_21d', 'intradia_prom_21d', 'nocturno_prom_21d',
    'drawdown_252d', 'volumen_prom_21d', 'dolares_negociados_prom_21d', 'obs_252d', 'dias_negociados_mes',
    'dias_imputados_mes', 'hubo_tramo_excluido_mes', 'hubo_retorno_extremo_mes', 'ret_log_sp500_mes',
    'ret_log_nyse_composite_mes', 'rf_mes', 'tasa_irx_prom_mes_pct', 'ret_log_mes_siguiente',
    'exceso_ret_mes_siguiente', 'ret_log_sp500_mes_siguiente', 'ret_log_nyse_composite_mes_siguiente',
    'rf_mes_siguiente',
]
OBT_MES_F1 = [
    'ret_pct_mes', 'ret_log_mes_lag1', 'ret_pct_mes_lag1', 'ret_log_mes_lag2', 'ret_pct_mes_lag2',
    'ret_log_mes_lag3', 'ret_pct_mes_lag3', 'intradia_log_mes', 'intradia_pct_mes', 'nocturno_log_mes',
    'nocturno_pct_mes', 'intradia_pct_prom_21d', 'nocturno_pct_prom_21d', 'vol_intradia_21d',
    'rango_log_hl_mes', 'rango_pct_hl_mes', 'cambio_rango_log_hl_mes', 'cambio_rango_pct_hl_mes',
    'rango_log_hl_prom_21d', 'rango_pct_hl_prom_21d', 'rango_log_hl_prom_63d', 'rango_pct_hl_prom_63d',
    'cambio_rango_log_hl_21_63', 'cambio_rango_pct_hl_21_63', 'vol_parkinson_21d', 'vol_garman_klass_21d',
    'beta_252d', 'exceso_sp500_log_mes', 'exceso_sp500_pct_mes', 'volumen_relativo_log_21_252',
    'volumen_relativo_pct_21_252', 'ret_pct_mes_siguiente',
]
OBT_MES = OBT_MES_PSET2 + OBT_MES_F1

# --- OBT_ACCION_DIA (33 columnas, nueva en F1): una fila por fila de GOLD.FCT_PRECIOS_DIARIOS ---
OBT_DIA = [
    'accion_key', 'ticker', 'fecha', 'anio_mes', 'conjunto', 'mes_cerrado', 'en_sp500', 'imputado',
    'despues_de_tramo_excluido', 'es_retorno_extremo',
    'precio_apertura', 'precio_maximo', 'precio_minimo', 'precio_cierre',
    'precio_apertura_ajustado', 'precio_maximo_ajustado', 'precio_minimo_ajustado', 'precio_cierre_ajustado',
    'volumen',
    'dif_cierre_ajustado', 'ret_pct_diario', 'ret_log_diario',
    'dif_apertura_ajustada', 'ret_pct_apertura', 'ret_log_apertura',
    'ret_pct_intradia', 'ret_log_intradia', 'ret_pct_nocturno', 'ret_log_nocturno',
    'rango_pct_hl', 'rango_log_hl', 'ret_log_sp500', 'rf_diaria',
]

# --- Predictores --------------------------------------------------------------------------
# PSet 2 (17): sin cambios.
BASE = ['ret_log_mes', 'ret_log_21d', 'ret_log_252d', 'momentum_12_1', 'vol_21d', 'vol_63d',
        'vol_apertura_21d', 'intradia_prom_21d', 'nocturno_prom_21d', 'drawdown_252d', 'volumen_prom_21d',
        'dolares_negociados_prom_21d', 'obs_252d', 'dias_negociados_mes', 'ret_log_sp500_mes',
        'ret_log_nyse_composite_mes', 'rf_mes']
# F1 (16): la version en logaritmo de cada variable nueva. La version en % es la misma variable
# con otra escala (prueba test_porcentaje_y_logaritmo_son_la_misma_variable): usar las dos
# duplica informacion casi colineal, asi que el % queda para EDA y la regla de negocio.
F1_LOG = ['ret_log_mes_lag1', 'ret_log_mes_lag2', 'ret_log_mes_lag3',
          'vol_intradia_21d', 'vol_parkinson_21d', 'vol_garman_klass_21d',
          'intradia_log_mes', 'nocturno_log_mes',
          'rango_log_hl_mes', 'rango_log_hl_prom_21d', 'rango_log_hl_prom_63d',
          'cambio_rango_log_hl_mes', 'cambio_rango_log_hl_21_63',
          'beta_252d', 'exceso_sp500_log_mes', 'volumen_relativo_log_21_252']
F1_PCT = ['ret_pct_mes', 'ret_pct_mes_lag1', 'ret_pct_mes_lag2', 'ret_pct_mes_lag3',
          'intradia_pct_mes', 'nocturno_pct_mes', 'intradia_pct_prom_21d', 'nocturno_pct_prom_21d',
          'rango_pct_hl_mes', 'rango_pct_hl_prom_21d', 'rango_pct_hl_prom_63d',
          'cambio_rango_pct_hl_mes', 'cambio_rango_pct_hl_21_63',
          'exceso_sp500_pct_mes', 'volumen_relativo_pct_21_252']
FEATURES_OBT = BASE + F1_LOG                         # 33 columnas tal como vienen de la OBT
# Derivadas (notebooks/02_features.ipynb), se calculan en preparar() con datos del cierre del mes t:
# - dispersion_mes: desviacion de ret_log_mes entre las acciones elegibles del mes (hallazgo 2 del EDA).
# - mes_calendario_obj: mes calendario del objetivo, 1-12 (hallazgo 2); el one-hot lo hace el Pipeline.
DERIVADAS = ['dispersion_mes', 'mes_calendario_obj']
# Iguales para todas las acciones del mes: el rango transversal no las toca.
DE_MERCADO_DERIVADAS = set(DERIVADAS)

# --- Columnas de X por tipo (como NUMERICAS / CATEGORICAS / YA_LISTAS de los laboratorios) -------
OBJETIVO = TARGET
NUMERICAS = FEATURES_OBT + ['dispersion_mes']        # 34: imputar mediana + escalar
CATEGORICAS = ['mes_calendario_obj']                 # 1: imputar moda + one-hot
CATEGORIAS = {'mes_calendario_obj': list(range(1, 13))}   # fijas: no dependen de los datos
YA_LISTAS = []
FEATURES = NUMERICAS + CATEGORICAS + YA_LISTAS        # 35 columnas de X; 45 tras el one-hot
MESES_OBJETIVO = [f'mes_calendario_obj_{m}' for m in range(2, 13)]   # nombres tras el one-hot
# Candidatas evaluadas y descartadas en 02_features por no reducir el MAE en walk-forward.
DESCARTADAS = ['vol_relativa', 'momentum_por_riesgo', 'ret_idiosincratico_mes', 'regimen_vol']
# Para modelos lineales sin regularizar: sin las 4 combinaciones lineales exactas del EDA (secc. 6b).
REDUNDANTES = ['exceso_sp500_log_mes',   # = ret_log_mes - ret_log_sp500_mes
               'nocturno_log_mes',       # = ret_log_mes - intradia_log_mes
               'nocturno_prom_21d',      # proporcional a ret_log_21d - intradia_prom_21d
               'ret_log_252d']           # = momentum_12_1 + ret_log_21d
FEATURES_LINEALES = [c for c in FEATURES if c not in REDUNDANTES]

# Nunca predictores: el futuro (objetivo y mercado del mes siguiente) y atributos de hoy que
# no se conocian en el mes (sigue_en_sp500, bolsa actual, ultima cotizacion).
FUGA = ['ret_log_mes_siguiente', 'ret_pct_mes_siguiente', 'exceso_ret_mes_siguiente',
        'ret_log_sp500_mes_siguiente', 'ret_log_nyse_composite_mes_siguiente', 'rf_mes_siguiente',
        'sigue_en_sp500', 'bolsa', 'es_nyse', 'bolsa_desconocida', 'fecha_ultima_cotizacion']


# Acciones fuera del analisis (H19): la semilla equivalencias_tickers une BMS (Bemis) con AMCR (Amcor) como
# si fuera un cambio de simbolo, pero fue una adquisicion. AMCR 2012-2014 queda en el S&P 500 con barras de
# solo cierre (rango maximo-minimo 0, volumen casi nulo) y deja predictores 0/0. Se quitan las dos.
EXCLUIDAS = ('BMS', 'AMCR')


def faltan_columnas(df, esperadas=OBT_MES):
    return [c for c in esperadas if c not in df.columns]


def preparar(df):
    falta = faltan_columnas(df, FEATURES_OBT + [TARGET, 'elegible', 'anio_mes', 'accion_key'])
    if falta:
        raise KeyError(f'El snapshot no tiene {len(falta)} columnas de F1 ({falta[:3]}...): '
                       'regenerarlo con "uv run python -m src.datos" tras reconstruir la OBT.')
    d = df.copy().sort_values(['anio_mes', 'accion_key']).reset_index(drop=True)
    num = [c for c in FEATURES_OBT + F1_PCT + [TARGET, 'ret_pct_mes_siguiente'] if c in d]
    for c in num:
        d[c] = pd.to_numeric(d[c], errors='coerce')
    d = d[d.elegible.fillna(False).astype(bool)].copy()
    if 'ticker' in d:
        d = d[~d.ticker.astype(str).str.upper().isin(EXCLUIDAS)]
    d = derivar(d)
    d[NUMERICAS] = d[NUMERICAS].replace([np.inf, -np.inf], np.nan).astype(float)
    # El objetivo se filtra despues de derivar: dispersion_mes usa todas las elegibles del mes, tambien las
    # que dejan de cotizar en t+1 (al cierre de t no se sabe cuales tendran objetivo).
    d = d[d[TARGET].notna()].copy()
    return d.reset_index(drop=True)


def derivar(d):
    """Features derivadas. Solo usan el mes t: el corte transversal del mismo mes y el calendario."""
    d = d.copy()
    d['mes_objetivo'] = pd.PeriodIndex(d.anio_mes.astype(int).astype(str), freq='M') + 1
    d['dispersion_mes'] = d.groupby('anio_mes').ret_log_mes.transform('std')
    d['mes_calendario_obj'] = d.mes_objetivo.dt.month.astype(int)
    return d


def interpolar_huecos(d, columnas=NUMERICAS):
    """Interpola linealmente, por accion y en orden de mes, solo los huecos intermedios (con un valor
    observado antes y otro despues). Los nulos al inicio o al final de la historia quedan nulos y los
    imputa la mediana del Pipeline, ajustada en cada pliegue. Se aplica a cada lado del corte por separado
    (ver dividir), asi que un hueco del entrenamiento nunca se rellena con un mes del hold-out."""
    columnas = [c for c in columnas if c in d]
    if not columnas or 'accion_key' not in d or 'anio_mes' not in d or not d[columnas].isna().any().any():
        return d
    d = d.sort_values(['accion_key', 'anio_mes'])
    d[columnas] = d.groupby('accion_key', sort=False)[columnas].transform(
        lambda s: s.interpolate(method='linear', limit_area='inside'))
    return d.sort_values(['anio_mes', 'accion_key'])


def dividir(d, corte='2023-12'):
    limite = pd.Period(corte, freq='M')
    # Objetivos que terminan antes de 2024: diciembre 2023 no entra al entrenamiento.
    # El corte se hace antes de interpolar: cada lado solo usa sus propios meses.
    return (interpolar_huecos(d[d.mes_objetivo <= limite].copy()),
            interpolar_huecos(d[d.mes_objetivo > limite].copy()))


def mes_objetivo(d):
    if 'mes_objetivo' in d:
        return pd.PeriodIndex(d['mes_objetivo'], freq='M')
    return pd.PeriodIndex(d['anio_mes'].astype(int).astype(str), freq='M') + 1


def pliegues(d, n_splits=7, meses_validacion=12, gap=1):
    """Validacion cruzada temporal: TimeSeriesSplit sobre los MESES (no sobre las filas).

    Cada pliegue valida 12 meses de objetivo completos y entrena con todos los meses anteriores
    (ventana expansiva); gap=1 deja un mes fuera entre los dos, porque el objetivo del ultimo mes
    de entrenamiento se conoce un mes despues. Con el entrenamiento hasta 2023-12 son los anios
    2017-2023. Todas las acciones de un mes caen en el mismo lado: el choque comun del mes
    (34,5 % de la varianza, EDA) no se reparte entre entrenamiento y validacion.
    Devuelve una lista de (indices_entrenamiento, indices_validacion), como cv= de cross_validate."""
    mo = mes_objetivo(d)
    meses = np.sort(mo.unique())
    salida = []
    for tr, va in TimeSeriesSplit(n_splits=n_splits, test_size=meses_validacion, gap=gap).split(meses):
        it, iv = np.flatnonzero(mo.isin(meses[tr])), np.flatnonzero(mo.isin(meses[va]))
        assert mo[it].max() + gap < mo[iv].min(), 'pliegue con fuga temporal'
        salida.append((it, iv))
    return salida


def preparacion(numericas=NUMERICAS, categoricas=CATEGORICAS, ya_listas=YA_LISTAS):
    """ColumnTransformer de los laboratorios. Se ajusta solo con lo que reciba en fit (el pliegue de
    entrenamiento): medianas, medias y desviaciones nunca ven la validacion ni el hold-out.
    El one-hot usa categorias fijas (1-12) con enero de referencia; una categoria desconocida es un
    error, no una fila de ceros que pasaria por enero."""
    pasos = [('numericas', Pipeline([('imputar', SimpleImputer(strategy='median', keep_empty_features=True)),
                                     ('escalar', StandardScaler())]), list(numericas))]
    if categoricas:
        pasos.append(('categoricas', Pipeline([
            ('imputar', SimpleImputer(strategy='most_frequent')),
            ('codificar', OneHotEncoder(categories=[CATEGORIAS[c] for c in categoricas], drop='first',
                                        handle_unknown='error', sparse_output=False))]), list(categoricas)))
    if ya_listas:
        pasos.append(('ya_listas', 'passthrough', list(ya_listas)))
    return ColumnTransformer(pasos, remainder='drop', verbose_feature_names_out=False)


def separar(columnas):
    """Reparte una lista de columnas de X entre numericas, categoricas y ya listas."""
    columnas = list(columnas)
    cat = [c for c in columnas if c in CATEGORICAS]
    listas = [c for c in columnas if c in YA_LISTAS]
    return [c for c in columnas if c not in cat and c not in listas], cat, listas


def crear_pipeline(modelo, features=FEATURES):
    return Pipeline([('preparar', preparacion(*separar(features))), ('modelo', modelo)])


# --- Metricas (docs/diseno_experimental.md, decision W3) --------------------------------------
# La tecnica para decidir es el MAE (la misma para todos los modelos). Las demas se calculan y se
# registran siempre, pero no deciden nada: sirven para comparar con otros trabajos y para el reporte.
# No se usa MAPE: el objetivo es un retorno que vale ~0 muchas veces y el error porcentual explota.
METRICA_TECNICA = 'mae'


def acierto_direccional(y, pred):
    """Fraccion de filas donde el signo predicho coincide con el real (sin las predicciones = 0)."""
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    m = pred != 0
    return float((np.sign(pred[m]) == np.sign(y[m])).mean()) if m.any() else np.nan


def r2_vs_rw(y, pred):
    """R2 fuera de muestra contra el random walk de retorno 0: 1 - SSE / sum(y^2). > 0 = mejor que RW."""
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    return float(1 - ((y - pred) ** 2).sum() / (y ** 2).sum())


from sklearn.metrics import make_scorer  # noqa: E402
PUNTAJES = {'mae': 'neg_mean_absolute_error',            # tecnica (decide)
            'rmse': 'neg_root_mean_squared_error',
            'mse': 'neg_mean_squared_error',
            'medae': 'neg_median_absolute_error',        # mediana del error absoluto
            'max_error': 'neg_max_error',                # peor error absoluto del pliegue
            'r2': 'r2',                                  # contra la media del pliegue de validacion
            'varianza_explicada': 'explained_variance',
            'r2_vs_rw': make_scorer(r2_vs_rw),           # contra predecir retorno 0
            'acierto_direccional': make_scorer(acierto_direccional)}
ERRORES = ('mae', 'rmse', 'mse', 'medae', 'max_error')   # scikit-learn los devuelve con signo negativo


def metricas_regresion(y, pred):
    """Las mismas metricas de PUNTAJES para un vector de predicciones (p. ej. el hold-out)."""
    from sklearn import metrics as m
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    return {'mae': m.mean_absolute_error(y, pred), 'rmse': m.root_mean_squared_error(y, pred),
            'mse': m.mean_squared_error(y, pred), 'medae': m.median_absolute_error(y, pred),
            'max_error': m.max_error(y, pred), 'r2': m.r2_score(y, pred),
            'varianza_explicada': m.explained_variance_score(y, pred), 'r2_vs_rw': r2_vs_rw(y, pred),
            'acierto_direccional': acierto_direccional(y, pred)}


def resumir_cv(r):
    """De la salida de cross_validate a {metrica}_cv_media, _cv_std y _train_cv (errores en positivo)."""
    salida = {}
    for nombre in PUNTAJES:
        signo = -1.0 if nombre in ERRORES else 1.0
        cv, ent = signo * r[f'test_{nombre}'], signo * r.get(f'train_{nombre}', np.full_like(r[f'test_{nombre}'], np.nan))
        salida.update({f'{nombre}_cv_media': float(np.nanmean(cv)), f'{nombre}_cv_std': float(np.nanstd(cv, ddof=1)),
                       f'{nombre}_train_cv': float(np.nanmean(ent))})
    salida['mae_pliegues'] = [round(float(x), 5) for x in -r['test_mae']]
    return salida


def validar(modelo, d, features=FEATURES, cv=None):
    """Como evaluar() del laboratorio 11-2: cross_validate del Pipeline completo en los pliegues
    temporales. Devuelve todas las metricas de PUNTAJES (promedio y desviacion en validacion, y
    promedio en entrenamiento); el MAE es la que decide."""
    cv = pliegues(d) if cv is None else cv
    inicio = time.perf_counter()
    r = cross_validate(crear_pipeline(clone(modelo), features), d[features], d[TARGET], cv=cv,
                       scoring=PUNTAJES, return_train_score=True, error_score='raise')
    return {**resumir_cv(r), 'segundos': time.perf_counter() - inicio}


def predecir_pliegues(modelo, d, features=FEATURES, cv=None,
                      conservar=('accion_key', 'anio_mes', 'vol_63d', 'ret_pct_mes_siguiente', 'rf_mes_siguiente')):
    """Predicciones fuera de muestra de cada pliegue (para IC por mes y metrica de negocio)."""
    cv = pliegues(d) if cv is None else cv
    partes = []
    for k, (it, iv) in enumerate(cv):
        p = crear_pipeline(clone(modelo), features).fit(d[features].iloc[it], d[TARGET].iloc[it])
        v = d.iloc[iv]
        partes.append(v[[c for c in conservar if c in v]].assign(
            pliegue=k, mes_objetivo=mes_objetivo(v), pred=p.predict(v[features]), real=v[TARGET].values))
    return pd.concat(partes, ignore_index=True)


if __name__ == '__main__':
    from sklearn.dummy import DummyRegressor
    from .datos import cargar
    obt, meta = cargar()
    train, holdout = dividir(preparar(obt))
    print('Entrenamiento:', train.shape, 'hold-out:', holdout.shape)
    p = crear_pipeline(DummyRegressor()).fit(train[FEATURES], train[TARGET])
    print(len(p.named_steps['preparar'].get_feature_names_out()), 'columnas tras preparar')
    for k, (it, iv) in enumerate(pliegues(train)):
        print(k, mes_objetivo(train)[it].max(), '->', mes_objetivo(train)[iv].min(), mes_objetivo(train)[iv].max())
