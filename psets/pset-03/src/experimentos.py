"""Registro de corridas en MLflow (seccion 4 de CD_PSet_3.pdf). Solo usa entrenamiento y CV, nunca hold-out.

Cada corrida registra, en el experimento "portafolio-inversiones":
- Parametros: hiperparametros del modelo, semilla (42) y la regla de negocio (topes y costo).
- Datos: tabla de origen, fecha del snapshot, fecha de corte y SHA-256 de la OBT mensual y de la diaria.
- Metricas: todas las de validar() en entrenamiento y CV (promedio y desviacion), brecha, segundos,
  IC de Spearman por mes y la metrica de negocio (Sharpe neto, drawdown, retorno, turnover, % invertido).
- Tags: fase (baseline, candidato, tuning, final), familia, modelo, commit de Git y si habia cambios sin commit.
- Artefactos: el Pipeline (mlflow.sklearn.log_model) con firma y ejemplo de entrada, el codigo de src/,
  requirements.txt, los manifiestos de los snapshots, el MAE por pliegue y las predicciones fuera de muestra.

Uso (con MLflow levantado; ver README):
    uv run --group modelos python -m src.experimentos --modelos B1_media
    uv run --group modelos python -m src.experimentos --verificar <run_id>    # recarga en sesion limpia
"""
import argparse, json, os, subprocess, sys, time
import tempfile
import warnings
# mes_calendario_obj es entero (1-12) y nunca falta: el aviso de MLflow sobre enteros con faltantes no aplica.
warnings.filterwarnings('ignore', message='Hint: Inferred schema contains integer column')
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import loguniform, randint
from sklearn.base import clone
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import cross_validate, ParameterSampler
from sklearn.metrics import mean_absolute_error
from .entorno import SEMILLA
from .pipeline import crear_pipeline, pliegues, resumir_cv, PUNTAJES, FEATURES, TARGET
from .evaluacion import ic_por_mes, resumen_ic
from .negocio import REGLA, RiesgoDiario, metrica_negocio
from .modelos.lineas_base import MediaPorAccion
from sklearn.pipeline import Pipeline

# Modelos que no usan la preparacion comun: sus columnas de X y van sin crear_pipeline().
COLUMNAS_PROPIAS = {'B3_rw_deriva': ['accion_key']}

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTO = 'portafolio-inversiones'
CONSERVAR = ['accion_key', 'anio_mes', 'vol_63d', 'ret_pct_mes_siguiente', 'rf_mes_siguiente']


def _lightgbm():
    from lightgbm import LGBMRegressor          # grupo "modelos" de pyproject.toml
    return LGBMRegressor(random_state=SEMILLA, verbose=-1)


def _xgboost():
    from xgboost import XGBRegressor            # grupo "modelos" (en macOS requiere libomp)
    return XGBRegressor(random_state=SEMILLA, n_jobs=-1)


# Modelos con su familia (tag "familia") y su nombre (tag "modelo"). Toda lista tiene >= 2 lineas base.
# Seccion 6 del PDF: candidatos con sus hiperparametros POR DEFECTO; solo se fija la semilla (y n_jobs).
# Familias del PDF: lineal regularizado (M4), bagging (M2), boosting (M3, M3b), red neuronal (M5) y
# state of the art (M8-M10, fundacionales en zero-shot: src/modelos/fundacionales.py).
CATALOGO = {
    'B1_media':         ('linea_base',   lambda: DummyRegressor()),
    'B2_rw_cero':       ('linea_base',   lambda: DummyRegressor(strategy='constant', constant=0.0)),
    'B3_rw_deriva':     ('linea_base',   lambda: MediaPorAccion()),
    'M2_random_forest': ('bagging',      lambda: RandomForestRegressor(random_state=SEMILLA, n_jobs=-1)),
    'M3_lightgbm':      ('boosting',     _lightgbm),
    'M3b_xgboost':      ('boosting',     _xgboost),
    'M4_ridge':         ('lineal',       lambda: Ridge()),
    'M5_mlp':           ('red_neuronal', lambda: MLPRegressor(random_state=SEMILLA)),
}


def candidatos():
    return {n: f() for n, (_, f) in CATALOGO.items()}


def _git():
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        sucio = bool(subprocess.check_output(['git', 'status', '--porcelain', '--', '.'], cwd=ROOT, text=True).strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        commit, sucio = os.environ.get('GIT_COMMIT', 'sin_commit_registrado'), os.environ.get('GIT_DIRTY', 'true') == 'true'
    return commit, sucio


def _tipos_confiables(pipe):
    """Tipos que skops debe aceptar al guardar y recargar el Pipeline (los genera este mismo codigo)."""
    import skops.io as sio
    return sorted(set(sio.get_untrusted_types(data=sio.dumps(pipe))) | {'numpy.dtype'})


def _mlflow():
    import mlflow
    mlflow.set_tracking_uri(os.environ.get('MLFLOW_TRACKING_URI', 'http://localhost:5001'))
    mlflow.set_experiment(os.environ.get('MLFLOW_EXPERIMENT_NAME', EXPERIMENTO))
    return mlflow


def registrar(nombre, train, meta, fase, modelo=None, riesgo=None, meta_dia=None, nested=False,
              pipe=None, columnas=None, parametros_extra=None, log_modelo=True):
    """Una corrida: CV temporal, metricas, IC, metrica de negocio, ajuste final y registro completo."""
    mlflow = _mlflow()
    from mlflow.models import infer_signature
    familia = CATALOGO[nombre][0] if nombre in CATALOGO else 'otro'
    modelo = CATALOGO[nombre][1]() if modelo is None else modelo
    columnas = columnas or COLUMNAS_PROPIAS.get(nombre, FEATURES)
    X, y = train[columnas], train[TARGET]
    cv = pliegues(train)
    if pipe is None:
        pipe = Pipeline([('modelo', clone(modelo))]) if nombre in COLUMNAS_PROPIAS else crear_pipeline(clone(modelo))
    inicio = time.perf_counter()
    with mlflow.start_run(run_name=nombre, nested=nested) as run:
        # Mismo calculo que cross_validate(scoring=PUNTAJES, return_train_score=True), pero pliegue a pliegue:
        # cada modelo se descarta al terminar su pliegue (un random forest por defecto ocupa ~1 GB).
        from .pipeline import metricas_regresion
        partes, filas_cv, filas_ent = [], [], []
        for k, (it, iv) in enumerate(cv):
            est = clone(pipe).fit(X.iloc[it], y.iloc[it])
            filas_ent.append(metricas_regresion(y.iloc[it], est.predict(X.iloc[it])))
            v = train.iloc[iv]
            p_val = est.predict(v[columnas])
            filas_cv.append(metricas_regresion(v[TARGET], p_val))
            partes.append(v[[c for c in CONSERVAR if c in v]].assign(pliegue=k, pred=p_val, real=v[TARGET].values))
            del est
        pred = pd.concat(partes, ignore_index=True)
        pipe.fit(X, y)
        segundos = time.perf_counter() - inicio
        cvd, entd = pd.DataFrame(filas_cv), pd.DataFrame(filas_ent)
        todas = {}
        for m in cvd.columns:
            todas.update({f'{m}_cv_media': cvd[m].mean(), f'{m}_cv_std': cvd[m].std(ddof=1), f'{m}_train_cv': entd[m].mean()})
        mae_pliegues = [round(float(x), 5) for x in cvd['mae']]
        ic = resumen_ic(ic_por_mes(pred))
        # Una prediccion constante no ordena acciones: la regla elegiria por el orden de las filas. Su
        # referencia de negocio es B4 (portafolios al azar), no esta corrida.
        ordena = bool(pred.groupby('anio_mes').pred.nunique().max() > 1)
        negocio = metrica_negocio(pred, riesgo=riesgo) if ordena else {}
        metricas = {**todas, 'brecha_mae': todas['mae_cv_media'] - todas['mae_train_cv'],
                    'segundos_entrenamiento': segundos, 'mae_train_final': mean_absolute_error(y, pipe.predict(X)),
                    **{k: v for k, v in ic.items() if isinstance(v, (int, float))},
                    **{f'negocio_{k}': v for k, v in negocio.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}}
        metricas = {k: float(v) for k, v in metricas.items() if v is not None and np.isfinite(v)}
        commit, sucio = _git()
        mlflow.log_params({**{k: str(v) for k, v in modelo.get_params().items()}, 'semilla': SEMILLA,
                           'tabla': meta['tabla'], 'snapshot': meta['snapshot_utc'], 'sha256': meta['sha256'],
                           'corte': meta.get('corte', '2023-12'), 'filas_entrenamiento': len(train),
                           'pliegues': f'TimeSeriesSplit({len(cv)}, test_size=12 meses, gap=1)',
                           'sha256_dia': (meta_dia or {}).get('sha256', 'sin_datos_diarios'),
                           'snapshot_dia': (meta_dia or {}).get('snapshot_utc', 'sin_datos_diarios'),
                           **{f'regla_{k}': str(v) for k, v in REGLA.items()},
                           'tope_portafolio_aplicado': str(riesgo is not None),
                           'metrica_negocio': 'calculada' if ordena else 'no_aplica_prediccion_constante',
                           **{k: str(v) for k, v in (parametros_extra or {}).items()}})
        mlflow.set_tags({'fase': fase, 'familia': familia, 'modelo': nombre, 'git_commit': commit,
                         'git_dirty': str(sucio)})
        mlflow.log_metrics(metricas)
        for fuente in sorted((ROOT / 'src').rglob('*.py')):
            mlflow.log_artifact(str(fuente), artifact_path='codigo/' + str(fuente.parent.relative_to(ROOT)))
        if (ROOT / 'requirements.txt').exists():
            mlflow.log_artifact(str(ROOT / 'requirements.txt'), artifact_path='codigo')
        mlflow.log_dict(meta, 'datos/snapshot_mes.json')
        if meta_dia:
            mlflow.log_dict(meta_dia, 'datos/snapshot_dia.json')
        mlflow.log_dict({'mae_cv': mae_pliegues}, 'pliegues.json')
        with tempfile.TemporaryDirectory() as tmp:   # carpeta propia: varias corridas en paralelo
            ruta_tmp = Path(tmp) / 'predicciones.csv'
            pred.to_csv(ruta_tmp, index=False)
            mlflow.log_artifact(str(ruta_tmp), artifact_path='predicciones_cv')
        ejemplo = X.iloc[:5]
        mlflow.log_dict({'X': ejemplo.to_dict(orient='list'), 'pred': pipe.predict(ejemplo).tolist()},
                        'verificacion/ejemplo_prediccion.json')
        uri = None
        if log_modelo:
            info = mlflow.sklearn.log_model(pipe, name='pipeline', skops_trusted_types=_tipos_confiables(pipe),
                                            signature=infer_signature(ejemplo, pipe.predict(ejemplo)), input_example=ejemplo)
            uri = info.model_uri
        return {'modelo': nombre, 'familia': familia, 'fase': fase, 'run_id': run.info.run_id,
                'model_uri': uri, 'git_dirty': sucio, **metricas}


FUNDACIONALES = {'M8_chronos': 'chronos', 'M9_timesfm': 'timesfm', 'M10_moirai': 'moirai'}


def registrar_fundacional(nombre, train, meta, riesgo=None, meta_dia=None, fase='candidato'):
    """Modelo fundacional en zero-shot (familia State of the Art del PDF): no se entrena; sus pronosticos
    (artefactos/fundacional_<m>.parquet, generados con python -m src.modelos.fundacionales) se evaluan en los
    MISMOS pliegues y con las MISMAS metricas que los tabulares. Las filas sin historia suficiente (< 64 dias)
    reciben la media del entrenamiento del pliegue (como B1) y se reporta la cobertura en validacion. Si solo se
    pronosticaron los meses de validacion (TimesFM en CPU es lento), el MAE de entrenamiento usa los meses del
    entrenamiento de cada pliegue que tienen pronostico."""
    from .pipeline import metricas_regresion
    clave = FUNDACIONALES[nombre]
    ruta = ROOT / 'artefactos' / f'fundacional_{clave}.parquet'
    info = json.loads(ruta.with_suffix('.json').read_text())
    fp = pd.read_parquet(ruta)[['accion_key', 'anio_mes', 'pred', 'ancho_10_90']]
    d = train.merge(fp, on=['accion_key', 'anio_mes'], how='left')
    cv = pliegues(d)
    cobertura = float(d.iloc[np.concatenate([iv for _, iv in cv])].pred.notna().mean())
    mlflow = _mlflow()
    with mlflow.start_run(run_name=nombre) as run:
        filas_cv, filas_ent, partes = [], [], []
        for k, (it, iv) in enumerate(cv):
            media = float(d[TARGET].iloc[it].mean())
            ent, val = d.iloc[it], d.iloc[iv]
            con = ent[ent.pred.notna()]           # si solo se pronosticaron los meses de validacion, la metrica
            if len(con):                          # de entrenamiento usa los meses del pliegue que si tienen pronostico
                filas_ent.append(metricas_regresion(con[TARGET], con.pred))
            filas_cv.append(metricas_regresion(val[TARGET], val.pred.fillna(media)))
            partes.append(val[[c for c in CONSERVAR if c in val]].assign(pliegue=k, pred=val.pred.fillna(media).values,
                                                                       real=val[TARGET].values))
        pred = pd.concat(partes, ignore_index=True)
        cvd, entd = pd.DataFrame(filas_cv), pd.DataFrame(filas_ent)
        metricas = {}
        for m in cvd.columns:
            metricas.update({f'{m}_cv_media': cvd[m].mean(), f'{m}_cv_std': cvd[m].std(ddof=1),
                             f'{m}_train_cv': entd[m].mean() if m in entd else np.nan})
        ic = resumen_ic(ic_por_mes(pred))
        negocio = metrica_negocio(pred, riesgo=riesgo)
        metricas.update({'brecha_mae': metricas['mae_cv_media'] - metricas['mae_train_cv'],
                         'segundos_entrenamiento': 0.0, 'segundos_inferencia': info.get('segundos_total', np.nan),
                         'latencia_ms_por_serie': info.get('latencia_ms_por_serie') or np.nan, 'cobertura': cobertura,
                         **{k2: v for k2, v in ic.items() if isinstance(v, (int, float))},
                         **{f'negocio_{k2}': v for k2, v in negocio.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}})
        metricas = {k2: float(v) for k2, v in metricas.items() if v is not None and np.isfinite(v)}
        commit, sucio = _git()
        mlflow.log_params({'modelo_hf': info['id'], 'contexto_dias': info['contexto'], 'horizonte_dias': info['horizonte_dias'],
                           'zero_shot': 'True', 'semilla': SEMILLA, 'tabla': meta['tabla'], 'snapshot': meta['snapshot_utc'],
                           'sha256': meta['sha256'], 'sha256_dia': (meta_dia or {}).get('sha256', 'sin_datos_diarios'),
                           'sha256_pronosticos': info['sha256'], 'filas_entrenamiento': len(train),
                           'pliegues': f'TimeSeriesSplit({len(cv)}, test_size=12 meses, gap=1)',
                           **{f'regla_{k2}': str(v) for k2, v in REGLA.items()}})
        mlflow.set_tags({'fase': fase, 'familia': 'fundacional', 'modelo': nombre, 'git_commit': commit, 'git_dirty': str(sucio)})
        mlflow.log_metrics(metricas)
        mlflow.log_artifact(str(ruta), artifact_path='pronosticos')
        mlflow.log_artifact(str(ruta.with_suffix('.json')), artifact_path='pronosticos')
        mlflow.log_artifact(str(ROOT / 'src/modelos/fundacionales.py'), artifact_path='codigo')
        mlflow.log_dict(meta, 'datos/snapshot_mes.json')
        return {'modelo': nombre, 'familia': 'fundacional', 'fase': fase, 'run_id': run.info.run_id, 'git_dirty': sucio, **metricas}


def registrar_referencia(modelo, serie, meta, fase='baseline', parametros=None, meta_dia=None):
    """Corrida de una referencia de negocio sin modelo (portafolio al azar, universo, indices):
    familia "N/A", modelo = descripcion corta; registra la metrica de negocio y la serie mensual."""
    from .negocio import resumen
    mlflow = _mlflow()
    with mlflow.start_run(run_name=modelo) as run:
        res = {**resumen(serie), 'meses': len(serie), 'invertido_prom': float(serie['invertido'].mean())}
        metricas = {f'negocio_{k}': float(v) for k, v in res.items() if v is not None and np.isfinite(v)}
        commit, sucio = _git()
        mlflow.log_params({'tabla': meta['tabla'], 'snapshot': meta['snapshot_utc'], 'sha256': meta['sha256'],
                           'sha256_dia': (meta_dia or {}).get('sha256', 'sin_datos_diarios'), 'semilla': SEMILLA,
                           'meses': f'{serie.index.min()}..{serie.index.max()}', **(parametros or {})})
        mlflow.set_tags({'fase': fase, 'familia': 'N/A', 'modelo': modelo, 'git_commit': commit, 'git_dirty': str(sucio)})
        mlflow.log_metrics(metricas)
        with tempfile.TemporaryDirectory() as tmp:   # carpeta propia: varias corridas en paralelo
            ruta_tmp = Path(tmp) / 'serie.csv'
            serie.to_csv(ruta_tmp)
            mlflow.log_artifact(str(ruta_tmp), artifact_path='serie_mensual')
        return {'modelo': modelo, 'familia': 'N/A', 'fase': fase, 'run_id': run.info.run_id, 'git_dirty': sucio, **metricas}


def verificar(run_id):
    """Recarga el Pipeline registrado (en un proceso nuevo) y compara con las predicciones guardadas."""
    mlflow = _mlflow()
    modelo = mlflow.sklearn.load_model(f'runs:/{run_id}/pipeline')
    guardado = mlflow.artifacts.load_dict(f'runs:/{run_id}/verificacion/ejemplo_prediccion.json')
    X = pd.DataFrame(guardado['X'])
    nuevo = modelo.predict(X)
    igual = bool(np.allclose(nuevo, guardado['pred'], rtol=0, atol=1e-12))
    print(json.dumps({'run_id': run_id, 'recarga_ok': igual, 'max_diferencia': float(np.max(np.abs(nuevo - guardado['pred'])))}))
    return igual


def datos_para_registro():
    from .datos import cargar
    from .pipeline import preparar, dividir
    obt, meta = cargar()
    train, _ = dividir(preparar(obt))
    riesgo = meta_dia = None
    if (ROOT / 'data/obt_dia.parquet').exists():
        dia, meta_dia = cargar(grano='dia')
        riesgo = RiesgoDiario(dia)
    return train.reset_index(drop=True), meta, riesgo, meta_dia


def avisar(estado, tarea, detalle):
    """Correo con el resultado, con el mismo notificador y credenciales (AVISO_* de pipeline/.env) que los
    avisos de Kestra. Nunca hace fallar la corrida; AVISO_EXPERIMENTOS=0 lo apaga."""
    if os.environ.get('AVISO_EXPERIMENTOS', '1') == '0':
        return False
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('notificar', ROOT / 'pipeline/scripts/notificar.py')
        notificar = importlib.util.module_from_spec(spec); spec.loader.exec_module(notificar)
        return notificar.enviar(estado, tarea, detalle)
    except Exception as e:                      # el aviso es opcional
        print(f'Aviso no enviado: {e}')
        return False


def evaluar_candidatos(train, meta, riesgo=None, meta_dia=None, nombres=None):
    nombres = list(CATALOGO) if nombres is None else nombres
    inicio, filas = time.perf_counter(), []
    try:
        for n in nombres:
            if n in FUNDACIONALES:
                filas.append(registrar_fundacional(n, train, meta, riesgo, meta_dia))
            else:
                filas.append(registrar(n, train, meta, 'baseline' if CATALOGO[n][0] == 'linea_base' else 'candidato',
                                       riesgo=riesgo, meta_dia=meta_dia))
    except Exception as e:
        avisar('Fail', 'experimentos MLflow', f'Fallo en {n} tras {len(filas)} corridas: {type(e).__name__}: {e}')
        raise
    df = pd.DataFrame(filas)
    destino = ROOT / 'docs/candidatos.csv'
    if destino.exists():                        # acumula: reemplaza solo las filas de los modelos corridos
        previo = pd.read_csv(destino)
        df = pd.concat([previo[~previo.modelo.isin(df.modelo)], df], ignore_index=True)
    df.to_csv(destino, index=False)
    cols = [c for c in ['modelo', 'familia', 'mae_cv_media', 'ic_media', 'negocio_sharpe_neto', 'run_id'] if c in df]
    uri = os.environ.get('MLFLOW_TRACKING_URI', 'http://localhost:5001')
    avisar('Success', 'experimentos MLflow',
           f"{len(filas)} corridas en {time.perf_counter() - inicio:.0f} s, experimento {EXPERIMENTO} ({uri})\n\n"
           + df[df.modelo.isin(nombres)][cols].round(4).to_string(index=False))
    return df[df.modelo.isin(nombres)].reset_index(drop=True)

def ajustar(train,meta,mejores,n_iter=30):
    import mlflow
    if len(set(mejores))!=3 or n_iter<30: raise ValueError('La guía exige 3 modelos y >=30 configuraciones cada uno')
    espacios={'M3b_xgboost':{'learning_rate':loguniform(.01,.3),'max_depth':randint(2,9),'min_child_weight':loguniform(1,500),'reg_lambda':loguniform(1e-3,100)},
              'M4_ridge':{'alpha':loguniform(1e-4,1e4)},
              'M2_random_forest':{'n_estimators':randint(100,501),'max_depth':randint(3,25),'min_samples_leaf':randint(1,200)},
              'M3_lightgbm':{'learning_rate':loguniform(.01,.3),'num_leaves':randint(8,65),'min_child_samples':randint(50,500),'reg_lambda':loguniform(1e-5,10)},
              'M5_mlp':{'alpha':loguniform(1e-6,1),'learning_rate_init':loguniform(1e-4,1e-2),'hidden_layer_sizes':[(32,),(64,),(64,32),(128,64)]}}
    mlflow=_mlflow()
    filas=[]
    for nombre in mejores:
        if nombre not in espacios: raise ValueError(f'Definir espacio de búsqueda para {nombre}')
        with mlflow.start_run(run_name='tuning_'+nombre):
            mlflow.set_tag('fase','tuning_padre')
            for cfg in ParameterSampler(espacios[nombre],n_iter=n_iter,random_state=SEMILLA):
                filas.append(registrar(nombre,train,meta,'tuning',modelo=candidatos()[nombre].set_params(**cfg),nested=True))
    df=pd.DataFrame(filas); df.to_csv(ROOT/'docs/tuning.csv',index=False)
    exp=mlflow.get_experiment_by_name(os.environ.get('MLFLOW_EXPERIMENT_NAME',EXPERIMENTO))
    mlflow.search_runs([exp.experiment_id]).to_csv(ROOT/'docs/corridas.csv',index=False)
    return df


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Registra corridas en MLflow o verifica una recarga.')
    ap.add_argument('--modelos', help='nombres de CATALOGO separados por coma (por defecto, todos)')
    ap.add_argument('--verificar', metavar='RUN_ID', help='recarga el Pipeline de esa corrida y compara')
    a = ap.parse_args()
    if a.verificar:
        sys.exit(0 if verificar(a.verificar) else 1)
    train, meta, riesgo, meta_dia = datos_para_registro()
    nombres = a.modelos.split(',') if a.modelos else None
    df = evaluar_candidatos(train, meta, riesgo, meta_dia, nombres)
    cols = ['modelo', 'familia', 'fase', 'run_id', 'mae_cv_media', 'ic_media', 'negocio_sharpe_neto', 'git_dirty']
    print(df[[c for c in cols if c in df]].to_string(index=False))
