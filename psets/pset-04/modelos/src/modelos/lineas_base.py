"""Lineas base que no caben en un DummyRegressor (seccion 5 de CD_PSet_3.pdf)."""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin


class MediaPorAccion(BaseEstimator, RegressorMixin):
    """B3, random walk con deriva: predice para cada accion la media de su retorno log mensual en el
    entrenamiento del pliegue (su deriva historica). Una accion sin historia recibe la media general.
    Solo usa la columna accion_key de X; se ajusta por pliegue, asi que no ve el futuro."""

    def __init__(self, columna: str = "accion_key"):
        self.columna = columna

    def fit(self, X, y):
        clave = pd.Series(np.asarray(X[self.columna]), name="clave")
        y = pd.Series(np.asarray(y, dtype=float))
        self.media_general_ = float(y.mean())
        self.medias_ = y.groupby(clave.values).mean().to_dict()
        self.n_features_in_ = 1
        return self

    def predict(self, X):
        clave = np.asarray(X[self.columna])
        return np.array([self.medias_.get(k, self.media_general_) for k in clave], dtype=float)
