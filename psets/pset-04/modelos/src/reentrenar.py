"""Reentrenamiento del modelo (PSet 4, seccion 7). Lo usan la simulacion (monitoreo/simulacion.py) y el flow
de Kestra reentrenamiento.yml.

Decisiones:
- Ventana: expansiva desde el inicio del historico (2013) hasta el ultimo lote etiquetado que no se usa para
  comparar. El PSet 3 entreno asi (validacion walk-forward con ventana expansiva) y la ventana larga conserva
  los regimenes de crisis (2018-Q4, 2020, 2022) que una ventana movil de 3-5 anios perderia; con ~330 filas por
  mes, un anio de lotes nuevos es ~8 % de los datos, de modo que el reentrenamiento corrige deriva gradual, no saltos.
- Misma preparacion: src.pipeline.preparar/dividir/interpolar_huecos y FEATURES, importadas; mismos
  hiperparametros del champion: sklearn.base.clone del pipeline registrado (LightGBM, semilla 42).
- Solo lotes etiquetados: el objetivo del lote t (retorno de t+1) existe al cierre de t+1. Los k lotes mas
  recientes se reservan para comparar champion y challenger, que no los ven al entrenar.
- Comparacion (PDF 7.2.6): champion y challenger sobre el lote etiquetado mas reciente, que ninguno vio al
  entrenar (k = 1).
- Regla de promocion (PDF seccion 4: metrica de negocio y variacion entre pliegues):
    1. negocio: el retorno del top 10 del challenger en ese lote debe superar al del champion por mas de una
       desviacion estandar de la CV de esa misma metrica: DE_CV_NEGOCIO = 0,0134, la desviacion, entre los 7
       pliegues del PSet 3, del retorno mensual medio del top 10 del champion (scripts/desviacion_cv_negocio.py);
    2. tecnica: su MAE en el lote no puede ser peor que el del champion en mas de 0,1 desviaciones de la CV del
       MAE (0,1 x 0,016 = 0,0016): un challenger que gana dinero por azar pero predice peor no pasa.
  Si no se cumplen las dos, queda el champion. Aun cumpliendolas, la promocion espera aprobacion humana.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import clone

from .negocio import REGLA, pesos_mes
from .experimentos import _tipos_confiables
from .pipeline import FEATURES, TARGET

COLUMNAS = FEATURES + ["anio_mes"]
K_EVALUACION = 1
DE_CV_NEGOCIO = 0.0134
MARGEN_RETORNO = DE_CV_NEGOCIO
DE_CV = 0.016
MARGEN_MAE = 0.1 * DE_CV


@dataclass
class Comparacion:
    lotes_evaluacion: list
    mae_champion: float
    mae_challenger: float
    retorno_champion: float
    retorno_challenger: float
    filas_entrenamiento: int
    hasta_anio_mes: int
    segundos: float
    promueve: bool = field(init=False)
    motivo: str = field(init=False)

    def __post_init__(self):
        gana_dinero = self.retorno_challenger - self.retorno_champion > MARGEN_RETORNO
        no_peor = self.mae_challenger <= self.mae_champion + MARGEN_MAE
        self.promueve = bool(gana_dinero and no_peor)
        self.motivo = ("cumple la regla" if self.promueve else
                       "no gana suficiente dinero" if not gana_dinero else "su MAE es peor que el del champion")

    def como_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("lotes_evaluacion", "hasta_anio_mes", "filas_entrenamiento",
                                              "mae_champion", "mae_challenger", "retorno_champion",
                                              "retorno_challenger", "promueve", "segundos")} | {"motivo_regla": self.motivo}


def retorno_top10(lote: pd.DataFrame, pred: np.ndarray) -> float:
    """Retorno simple del mes siguiente del top 10 con pesos 1/vol y tope de volatilidad por accion (sin
    el tope de portafolio, que pide datos diarios): lo que se compara entre modelos."""
    g = lote.assign(_p=pred)
    w = pesos_mes(g, "_p", vol=REGLA["vol"], n=REGLA["n"], tope_percentil=REGLA["tope_percentil"])
    r = g.set_index("accion_key")["ret_pct_mes_siguiente"].reindex(w.index).fillna(0.0)
    return float((w * r).sum())


def ventana(etiquetados: pd.DataFrame, k: int = K_EVALUACION) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """Entrenamiento (todo menos los k lotes etiquetados mas recientes) y evaluacion (esos k)."""
    meses = sorted(etiquetados["anio_mes"].unique())
    evaluacion = meses[-k:]
    return (etiquetados[~etiquetados["anio_mes"].isin(evaluacion)],
            etiquetados[etiquetados["anio_mes"].isin(evaluacion)], evaluacion)


def entrenar_y_comparar(champion, etiquetados: pd.DataFrame, k: int = K_EVALUACION):
    """Entrena el challenger (clon del champion) y lo compara con el champion en los k ultimos lotes."""
    inicio = time.perf_counter()
    entrenamiento, evaluacion, lotes = ventana(etiquetados, k)
    challenger = clone(champion).fit(entrenamiento[COLUMNAS], entrenamiento[TARGET])
    maes, rets = {}, {}
    for nombre, m in (("champion", champion), ("challenger", challenger)):
        p = m.predict(evaluacion[COLUMNAS])
        maes[nombre] = float(np.mean(np.abs(evaluacion[TARGET] - p)))
        acumulado = 1.0
        for mes in lotes:
            lote = evaluacion[evaluacion["anio_mes"] == mes]
            acumulado *= 1 + retorno_top10(lote, m.predict(lote[COLUMNAS]))
        rets[nombre] = acumulado - 1
    comp = Comparacion(lotes_evaluacion=[int(x) for x in lotes], mae_champion=maes["champion"],
                       mae_challenger=maes["challenger"], retorno_champion=rets["champion"],
                       retorno_challenger=rets["challenger"], filas_entrenamiento=len(entrenamiento),
                       hasta_anio_mes=int(entrenamiento["anio_mes"].max()),
                       segundos=time.perf_counter() - inicio)
    return challenger, comp


def registrar_challenger(challenger, comp: Comparacion, motivo: str, huella_datos: str, ejemplo: pd.DataFrame,
                         nombre: str = "portafolio-inversiones-modelo") -> str:
    """Corrida de MLflow con tag fase=reentrenamiento y motivo; registra la version y le pone @challenger.
    Devuelve la version. MLFLOW_TRACKING_URI viene del entorno."""
    import mlflow
    from mlflow.models import infer_signature
    from mlflow.tracking import MlflowClient

    mlflow.set_experiment("portafolio-inversiones")
    with mlflow.start_run(run_name=f"reentrenamiento-{comp.hasta_anio_mes}") as run:
        mlflow.set_tags({"fase": "reentrenamiento", "motivo": motivo, "familia": "ensamble",
                         "modelo": "lightgbm", "candidato": "challenger"})
        params = {f"modelo__{k}": v for k, v in challenger.steps[-1][1].get_params().items()
                  if k in ("n_estimators", "learning_rate", "num_leaves", "min_child_samples", "reg_lambda",
                           "colsample_bytree", "subsample", "random_state")}
        mlflow.log_params({**params, "ventana": "expansiva", "hasta_anio_mes": comp.hasta_anio_mes,
                           "filas": comp.filas_entrenamiento, "huella_datos": huella_datos,
                           "lotes_evaluacion": ",".join(map(str, comp.lotes_evaluacion))})
        mlflow.log_metrics({"mae_eval_challenger": comp.mae_challenger, "mae_eval_champion": comp.mae_champion,
                            "retorno_eval_challenger": comp.retorno_challenger,
                            "retorno_eval_champion": comp.retorno_champion,
                            "promueve_regla": float(comp.promueve), "segundos": comp.segundos})
        ejemplo = ejemplo[COLUMNAS].head(5)              # firma con los mismos tipos que la del champion
        info = mlflow.sklearn.log_model(challenger, name="pipeline",
                                        skops_trusted_types=_tipos_confiables(challenger),
                                        signature=infer_signature(ejemplo, challenger.predict(ejemplo)))
        mv = mlflow.register_model(info.model_uri, nombre, tags={"motivo": motivo})
    MlflowClient().set_registered_model_alias(nombre, "challenger", mv.version)
    return str(mv.version)


def promover(version: str, nombre: str = "portafolio-inversiones-modelo") -> dict:
    """Mueve @champion a la version aprobada y deja la anterior en @anterior (para revertir con un paso)."""
    from mlflow.tracking import MlflowClient
    c = MlflowClient()
    previa = c.get_model_version_by_alias(nombre, "champion").version
    c.set_registered_model_alias(nombre, "anterior", previa)
    c.set_registered_model_alias(nombre, "champion", version)
    return {"champion": version, "anterior": previa}
