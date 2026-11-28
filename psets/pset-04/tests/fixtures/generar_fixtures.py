"""Genera las fijas de las pruebas (tests/fixtures/), para correr en CI sin servidor de MLflow.

- modelo_champion/: copia del champion (portafolio-inversiones-modelo v1, run f7596a565f8a458492057238f245cf89)
  exportada con mlflow.sklearn.save_model desde la copia local del registro (modelos/mlflow/).
- holdout.parquet: el hold-out del PSet 3 (objetivos 2024-01 a 2026-10, snapshot c3568917) con las columnas
  de la firma y el target. El champion debe reproducir sobre el su MAE registrado (0,0673399888).
- lote_2024_01.json: una peticion valida a POST /predecir (las acciones candidatas de 2023-12, cuyo objetivo es
  2024-01), para las pruebas de contrato y comportamiento y como ejemplo del README.

Uso, desde psets/pset-04/ (una sola vez; el resultado se versiona):
    uv run --project api python tests/fixtures/generar_fixtures.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ / "modelos"))

import mlflow  # noqa: E402
import pandas as pd  # noqa: E402

from src.datos import cargar  # noqa: E402
from src.pipeline import FEATURES, FEATURES_OBT, TARGET, dividir, preparar  # noqa: E402

RUN_ID = "f7596a565f8a458492057238f245cf89"
ORIGEN = RAIZ / "modelos/mlflow/artifacts/2/models/m-98c668f764974bffa27c0c778d1eccfc/artifacts"


def main() -> None:
    destino = AQUI / "modelo_champion"
    if destino.exists():
        shutil.rmtree(destino)
    modelo = mlflow.sklearn.load_model(str(ORIGEN))
    original = mlflow.models.Model.load(str(ORIGEN))
    # pickle y no skops: es una copia propia, generada aqui desde el registro, y carga sin lista de tipos
    # confiables en CI. El registro (fuente de verdad) sigue en skops.
    mlflow.sklearn.save_model(modelo, str(destino), signature=original.signature, serialization_format="pickle",
                              metadata={"run_id_registrado": RUN_ID, "version_registrada": "1"})

    obt, meta = cargar(RAIZ / "modelos/data/obt.parquet")
    _, holdout = dividir(preparar(obt))
    holdout[["accion_key", "ticker"] + FEATURES + ["anio_mes", TARGET]].reset_index(drop=True) \
        .to_parquet(AQUI / "holdout.parquet", index=False)

    lote = obt[(obt["anio_mes"] == 202312) & obt["elegible"].astype(bool)].dropna(subset=FEATURES_OBT)
    peticion = {"anio_mes": 202312, "acciones": [
        {"accion_key": str(r["accion_key"]), "ticker": str(r["ticker"]), **{c: float(r[c]) for c in FEATURES_OBT}}
        for _, r in lote.iterrows()]}
    (AQUI / "lote_2024_01.json").write_text(json.dumps(peticion))
    print(f"modelo -> {destino.name}; holdout {len(holdout)} filas (sha {meta['sha256'][:8]}); lote {len(lote)} acciones")


if __name__ == "__main__":
    main()
