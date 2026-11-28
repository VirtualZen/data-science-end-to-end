"""Calcula DE_CV_NEGOCIO (src/reentrenar.py): desviacion estandar, entre los 7 pliegues de la validacion cruzada
del PSet 3, del retorno mensual medio del top 10 que arma el champion (mismos pliegues, misma regla de pesos).
Es la "variacion entre pliegues" de la metrica de negocio que usa la regla de promocion (PDF, seccion 4).

Uso, desde psets/pset-04/ (snapshot del PSet 3 y copia del champion de tests/fixtures):
    uv run --project api python scripts/desviacion_cv_negocio.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ), str(RAIZ / "modelos")]

import mlflow  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.base import clone  # noqa: E402

from src.datos import cargar  # noqa: E402
from src.pipeline import TARGET, dividir, pliegues, preparar  # noqa: E402
from src.reentrenar import COLUMNAS, retorno_top10  # noqa: E402


def main() -> None:
    champion = mlflow.sklearn.load_model(str(RAIZ / "tests/fixtures/modelo_champion"))
    obt, meta = cargar(RAIZ / "modelos/data/obt.parquet")
    entrenamiento, _ = dividir(preparar(obt))
    filas = []
    for k, (it, iv) in enumerate(pliegues(entrenamiento)):
        modelo = clone(champion).fit(entrenamiento[COLUMNAS].iloc[it], entrenamiento[TARGET].iloc[it])
        v = entrenamiento.iloc[iv]
        r = [retorno_top10(g, modelo.predict(g[COLUMNAS])) for _, g in v.groupby("anio_mes")]
        filas.append({"pliegue": k, "retorno_mensual_medio": np.mean(r), "meses": len(r)})
    d = pd.DataFrame(filas)
    print(d.round(4).to_string(index=False))
    print(f"snapshot {meta['sha256'][:8]}; DE_CV_NEGOCIO = {d['retorno_mensual_medio'].std(ddof=1):.4f}")


if __name__ == "__main__":
    main()
