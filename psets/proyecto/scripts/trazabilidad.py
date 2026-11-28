"""Trazabilidad de una prediccion (PDF 10.6): PREDICCIONES -> version del modelo -> run_id -> snapshot de la OBT -> Gold.

Solo lee docs/predicciones.csv y docs/corridas.csv (exportados de Snowflake y de MLflow); no escribe nada.
Uso, desde psets/pset-04/ (sin id, toma la primera prediccion de cada version servida: 1, 3 y 8):
    python3 scripts/trazabilidad.py [id_prediccion ...]
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
GOLD = "FCT_PRECIOS_DIARIOS, FCT_MERCADO_DIARIO, DIM_ACCION, DIM_FECHA (pipeline/spark/jobs/construir_obt.py)"


def rastrear(p: dict, corridas: dict) -> None:
    c = corridas[p["run_id"]]
    print("1. prediccion :", p["id_prediccion"], p["anio_mes"], p["ticker"], "pred", p["retorno_predicho"], p["decision"],
          "| huella del lote", p["huella_obt"])
    print("2. modelo     : version", p["modelo_version"], "alias", p["modelo_alias"], "run_id", p["run_id"])
    print("3. corrida    :", c["tags.mlflow.runName"], "| fase", c["tags.fase"], "| motivo", c.get("tags.motivo") or "-")
    if c["params.tabla"]:
        print("4. snapshot   :", c["params.tabla"], "| snapshot", c["params.snapshot"], "| corte", c["params.corte"],
              "| filas", c["params.filas_entrenamiento"], "| sha256", c["params.sha256"][:12])
    else:
        print("4. snapshot   : PORTAFOLIO_P4.OBT.OBT_ACCION_MES | huella", c["params.huella_datos"], "| ventana",
              c["params.ventana"], "| hasta", c["params.hasta_anio_mes"], "| filas", c["params.filas"])
    print("5. Gold       :", GOLD)
    print()


def main() -> None:
    pred = list(csv.DictReader((DOCS / "predicciones.csv").open()))
    corridas = {r["run_id"]: r for r in csv.DictReader((DOCS / "corridas.csv").open())}
    ids = sys.argv[1:]
    if not ids:
        primeras: dict[str, str] = {}
        for r in pred:
            primeras.setdefault(r["modelo_version"], r["id_prediccion"])
        ids = list(primeras.values())
    por_id = {r["id_prediccion"]: r for r in pred}
    for i in ids:
        rastrear(por_id[i], corridas)


if __name__ == "__main__":
    main()
