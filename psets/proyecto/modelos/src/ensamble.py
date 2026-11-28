"""Ensamble transversal por estadisticos de orden sobre rangos.

Cada modelo produce un puntaje por accion y mes en su propia escala (retorno esperado,
probabilidad, logit). Dentro de cada mes se convierte a rango (1 = mejor = mayor puntaje), y
para cada accion i se toman los rangos de los M modelos ordenados r_i(1) <= ... <= r_i(M):

  mediana  r_i((M+1)/2)  consenso robusto: un solo modelo no mueve la decision
  minimo   r_i(1)        cobertura: entra si algun modelo la pone arriba (mas rotacion)
  maximo   r_i(M)        filtro conservador: entra solo si todos la ponen arriba

El resultado se devuelve como puntaje = -estadistico (mayor = mejor), para que la regla de
negocio (top 10, pesos 1/vol) lo use igual que cualquier otro modelo. El rango solo usa
informacion del mismo mes (conocida al cierre), asi que no hay fuga. Que estadistico usar es un
hiperparametro: se elige en la validacion walk-forward, nunca en el hold-out.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ESTADISTICOS = ("mediana", "minimo", "maximo")


def rangos_transversales(df: pd.DataFrame, columnas: list[str], grupo: str = "anio_mes") -> pd.DataFrame:
    """Rango por mes de cada columna; 1 = mayor puntaje. Normalizado a [0, 1] (rango / n) para
    que meses con distinto numero de acciones sean comparables."""
    r = df.groupby(grupo)[columnas].rank(ascending=False, method="average")
    n = df.groupby(grupo)[columnas].transform("count")
    return r / n


def estadistico_orden(rangos: pd.DataFrame, estadistico: str = "mediana", k: int | None = None) -> pd.Series:
    """k (1..M) elige el k-esimo estadistico de orden; si no, el nombrado. Ignora modelos sin
    prediccion para esa accion (NaN)."""
    valores = np.sort(rangos.to_numpy(dtype=float), axis=1)          # NaN quedan al final
    validos = np.isfinite(valores).sum(axis=1)
    if k is not None:
        pos = np.minimum(k, validos) - 1
    elif estadistico == "mediana":
        return pd.Series(np.nanmedian(valores, axis=1), index=rangos.index)
    elif estadistico == "minimo":
        pos = np.zeros(len(valores), dtype=int)
    elif estadistico == "maximo":
        pos = validos - 1
    else:
        raise ValueError(f"estadistico debe ser uno de {ESTADISTICOS}")
    pos = np.where(validos > 0, pos, 0)
    out = valores[np.arange(len(valores)), pos]
    out[validos == 0] = np.nan
    return pd.Series(out, index=rangos.index)


class EnsambleRangos:
    """Combina las predicciones ya calculadas de varios modelos (columnas de un panel)."""

    def __init__(self, modelos: list[str], estadistico: str = "mediana"):
        if len(modelos) < 2:
            raise ValueError("El ensamble necesita al menos 2 modelos")
        self.modelos, self.estadistico = list(modelos), estadistico

    def puntaje(self, panel: pd.DataFrame) -> pd.Series:
        r = rangos_transversales(panel, self.modelos)
        return -estadistico_orden(r, self.estadistico)
