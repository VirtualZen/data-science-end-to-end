"""Graficas de diagnostico para el memo y la notebook de entrega.

  t-SNE 2D        del espacio de variables que deja el Pipeline (despues del filtro), coloreado
                  por regimen de mercado o por direccion del retorno siguiente. Solo describe:
                  t-SNE no conserva distancias globales y no se usa para predecir.
  Optuna          historia de optimizacion, importancia de hiperparametros y coordenadas
                  paralelas (optuna.visualization.matplotlib).
  Aprendizaje     (a) por tamano de entrenamiento: ventana walk-forward expansiva con 2, 4, 6...
                  anios, metrica en entrenamiento y validacion; (b) por epoca en las redes
                  (historia de redes.entrenar).
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .entorno import SEMILLA


def regimen_mercado(panel: pd.DataFrame) -> pd.Series:
    """Alcista / bajista segun el retorno del S&P 500 de los ultimos 12 meses (dato del cierre)."""
    m = panel.groupby("anio_mes")["ret_log_sp500_mes"].first().sort_index()
    r12 = m.rolling(12, min_periods=6).sum()
    etiqueta = np.where(r12 >= 0, "alcista", "bajista")
    return panel["anio_mes"].map(pd.Series(etiqueta, index=m.index))


def tsne_2d(pipeline_ajustado, X: pd.DataFrame, color: pd.Series, muestra: int = 5000, ax=None):
    from sklearn.manifold import TSNE
    idx = X.sample(min(muestra, len(X)), random_state=SEMILLA).index
    Z = pipeline_ajustado[:-1].transform(X.loc[idx])            # todo menos el modelo final
    emb = TSNE(n_components=2, perplexity=30, init="pca", random_state=SEMILLA).fit_transform(Z)
    ax = ax or plt.subplots(figsize=(6, 5))[1]
    for valor in pd.unique(color.loc[idx]):
        sel = (color.loc[idx] == valor).to_numpy()
        ax.scatter(emb[sel, 0], emb[sel, 1], s=4, alpha=0.5, label=str(valor))
    ax.set(title="t-SNE 2D de las variables seleccionadas", xticks=[], yticks=[])
    ax.legend(markerscale=3)
    return ax


def graficas_optuna(estudio, carpeta=None):
    from optuna.visualization import matplotlib as ov
    figs = {"historia": ov.plot_optimization_history(estudio).figure,
            "importancia": ov.plot_param_importances(estudio).figure,
            "coordenadas": ov.plot_parallel_coordinate(estudio).figure}
    if carpeta:
        for k, f in figs.items():
            f.savefig(f"{carpeta}/optuna_{estudio.study_name}_{k}.png", dpi=150, bbox_inches="tight")
    return figs


def curva_aprendizaje(filas: list[dict], metrica: str = "mae", ax=None):
    """filas: [{'anios_entrenamiento', 'entrenamiento', 'validacion'}] o historia por epoca."""
    d = pd.DataFrame(filas)
    x = "anios_entrenamiento" if "anios_entrenamiento" in d else "epoca"
    ax = ax or plt.subplots(figsize=(6, 4))[1]
    ax.plot(d[x], d["entrenamiento"], marker="o", label="entrenamiento")
    ax.plot(d[x], d["validacion"], marker="o", label="validacion")
    ax.set(xlabel=x.replace("_", " "), ylabel=metrica, title="Curva de aprendizaje")
    ax.legend()
    return ax
