"""Candidatos tabulares (M2-M6) como Pipelines de scikit-learn sobre OBT_ACCION_MES.

Pipeline:  rango transversal (opcional) -> preparacion() de src/pipeline.py (mediana + escalar,
           moda + one-hot) -> filtro (SelectKBest) -> modelo
- Rango transversal: cada variable se convierte en su percentil dentro del mes. Solo usa
  acciones del mismo mes (conocidas al cierre): no hay fuga, y quita el nivel de mercado
  (el modelo aprende que acciones ganan a las otras, que es lo que necesita el ranking).
- Filtro: SelectKBest(f_regression o mutual_info_regression) dentro del Pipeline, para que la
  seleccion se ajuste en cada pliegue con solo los datos de entrenamiento.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.feature_selection import SelectKBest, f_regression, mutual_info_regression
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..entorno import SEMILLA

# Columnas de X: catalogo unico en src/pipeline.py (33 de la OBT + 2 derivadas).
from ..pipeline import FEATURES as FEATURES_F1, preparacion as preparacion_comun, separar  # noqa: E402
# Variables de mercado: iguales para todas las acciones del mes; el rango transversal las anula.
from ..pipeline import DE_MERCADO_DERIVADAS  # noqa: E402
DE_MERCADO = {"ret_log_sp500_mes", "ret_log_nyse_composite_mes", "rf_mes"} | DE_MERCADO_DERIVADAS


class RangoTransversal(BaseEstimator, TransformerMixin):
    """Percentil de cada variable dentro de su mes. Necesita la columna anio_mes en X."""

    def __init__(self, columnas, grupo: str = "anio_mes"):
        self.columnas, self.grupo = columnas, grupo

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        cols = [c for c in self.columnas if c not in DE_MERCADO]
        r = X.groupby(self.grupo)[cols].rank(pct=True)
        return pd.concat([r, X[[c for c in self.columnas if c in DE_MERCADO]]], axis=1)[self.columnas]

    def get_feature_names_out(self, input_features=None):
        return np.asarray(self.columnas, dtype=object)


def informacion_mutua(X, y):
    """Funcion con nombre (no lambda) para que el Pipeline se pueda guardar en MLflow."""
    return mutual_info_regression(X, y, random_state=SEMILLA)


def preparacion(features, transversal: bool = True, k: int | str = "all", filtro: str = "f_regression"):
    pasos = [("rango_transversal", RangoTransversal(features))] if transversal else []
    puntaje = f_regression if filtro == "f_regression" else informacion_mutua
    pasos += [("preparar", preparacion_comun(*separar(features))),
              ("filtro", SelectKBest(puntaje, k=k))]
    return pasos


def modelos_por_defecto() -> dict:
    """Familias del PDF con hiperparametros por defecto (fase candidato)."""
    from sklearn.dummy import DummyRegressor
    from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.neural_network import MLPRegressor
    m = {"B1_dummy_media": DummyRegressor(), "B2_rw_cero": DummyRegressor(strategy="constant", constant=0.0),
         "M4_ridge": Ridge(),
         "M2_random_forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=50, n_jobs=-1,
                                                   random_state=SEMILLA),
         "M3b_hist_gradient_boosting": HistGradientBoostingRegressor(random_state=SEMILLA),
         "M5_mlp": MLPRegressor(hidden_layer_sizes=(64, 32), early_stopping=True, random_state=SEMILLA)}
    try:
        from xgboost import XGBRegressor
        m["M3_xgboost"] = XGBRegressor(n_estimators=400, learning_rate=0.03, max_depth=4, subsample=0.8,
                                       colsample_bytree=0.8, tree_method="hist", random_state=SEMILLA, n_jobs=-1)
    except ImportError:
        pass
    try:
        from lightgbm import LGBMRegressor
        m["M3c_lightgbm"] = LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=31,
                                          min_child_samples=100, subsample=0.8, subsample_freq=1,
                                          colsample_bytree=0.8, random_state=SEMILLA, verbose=-1)
    except ImportError:
        pass
    return m


def crear_pipeline(modelo, features=FEATURES_F1, **kw) -> Pipeline:
    return Pipeline(preparacion(features, **kw) + [("modelo", modelo)])
