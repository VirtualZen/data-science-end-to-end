"""Prueba funcional aislada, no selección final ni consumo del hold-out."""
import json,os,time,platform
from importlib.metadata import version as package_version
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from .datos import exportar,cargar,RAIZ
from .pipeline import preparar,dividir,FEATURES,TARGET
from .experimentos import registrar

def main():
    uri=os.environ.get('MLFLOW_TRACKING_URI','http://localhost:5001')
    for intento in range(30):
        try:
            r=requests.get(uri+'/health',timeout=5)
            if r.ok:break
        except requests.RequestException:pass
        time.sleep(2)
    else:raise RuntimeError('MLflow no respondió al healthcheck')
    meta=exportar();obt,_=cargar();train,holdout=dividir(preparar(obt))
    print('Snapshot Snowflake:',meta['filas'],'filas; entrenamiento:',len(train),'hold-out reservado:',len(holdout))
    import nbformat
    from nbclient import NotebookClient
    for name in ['01_eda.ipynb','02_features.ipynb']:
        p=RAIZ/'notebooks'/name;n=nbformat.read(p,4)
        NotebookClient(n,timeout=180,resources={'metadata':{'path':str(RAIZ/'notebooks')}}).execute()
        nbformat.write(n,p);print(name,'OK')
    filas=[]
    for nombre in ['B1_media','B2_rw_cero','M4_ridge']:     # >= 2 lineas base
        filas.append(registrar(nombre,train,meta,'verificacion_entorno'))
    import mlflow
    from mlflow import MlflowClient
    client=MlflowClient()
    run_id=filas[-1]['run_id']
    # Registro separado: no asigna champion/challenger ni decide un modelo final.
    model_name='portafolio-verificacion-modelo'
    version=mlflow.register_model(filas[-1]['model_uri'],model_name)
    client.set_registered_model_alias(model_name,'verificacion',version.version)
    modelo=mlflow.pyfunc.load_model(f'models:/{model_name}@verificacion')
    pred=modelo.predict(train[FEATURES])
    from sklearn.metrics import mean_absolute_error
    reproduced=float(mean_absolute_error(train[TARGET],pred))
    assert np.isclose(reproduced,filas[-1]['mae_train_final'],rtol=1e-12,atol=1e-12)
    exp=mlflow.get_experiment_by_name(os.environ.get('MLFLOW_EXPERIMENT_NAME','portafolio-inversiones'))
    out=RAIZ/'docs/verificacion';out.mkdir(exist_ok=True)
    pd.DataFrame(filas).to_csv(out/'resultados.csv',index=False)
    mlflow.search_runs([exp.experiment_id]).to_csv(out/'corridas.csv',index=False)
    result={'python':platform.python_version(),'versiones':{p:package_version(p) for p in ['mlflow','scikit-learn','pandas','numpy','pyarrow']},'estado':'OK','tipo':'verificacion_funcional_no_seleccion_final','snapshot':meta,'train_filas':len(train),'holdout_filas_reservadas':len(holdout),'holdout_evaluado':False,'modelo_prueba':model_name,'alias':'verificacion','version':version.version,'run_id':run_id,'mae_train_reproducido':reproduced,'runs_esta_verificacion':[r['run_id'] for r in filas]}
    (out/'resultado.json').write_text(json.dumps(result,indent=2)); print(json.dumps({k:v for k,v in result.items() if k!='snapshot'},indent=2))
if __name__=='__main__':main()
