"""Rutas relativas, dispositivo y modo de ejecucion (Mac M4, Colab o contenedor).

Nada usa rutas absolutas: todo cuelga de RAIZ (la carpeta psets/pset-03 del repo clonado) o de
PSET3_DATOS si se define (p. ej. una carpeta de Google Drive montada en Colab).

Fases (docs/diseno_experimental.md):
  pesada   corre una vez en la Mac (o en Colab con GPU): ARIMA-GARCH por accion, fundacionales,
           redes; guarda artefactos/*.parquet y artefactos/*.pt con su sha256.
  entrega  el notebook de Colab carga los artefactos, evalua, compara y grafica en < 1 h.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
DATOS = Path(os.environ.get("PSET3_DATOS", RAIZ / "data"))
ARTEFACTOS = Path(os.environ.get("PSET3_ARTEFACTOS", RAIZ / "artefactos"))
SEMILLA = 42   # semilla unica del proyecto (decision de Paul, 18-nov)


def en_colab() -> bool:
    return "COLAB_RELEASE_TAG" in os.environ or "COLAB_GPU" in os.environ


def dispositivo() -> str:
    """cuda (Colab T4) > mps (Apple M4) > cpu. Sin torch instalado devuelve cpu."""
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def fijar_semillas(semilla: int = SEMILLA) -> None:
    random.seed(semilla)
    np.random.seed(semilla)
    try:
        import torch
        torch.manual_seed(semilla)
    except ImportError:
        pass


def nucleos() -> int:
    """Procesos para joblib: todos menos uno (en Colab, 2 vCPU -> 2)."""
    n = os.cpu_count() or 1
    return n if n <= 2 else n - 1


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def guardar_artefacto(df, nombre: str, meta: dict | None = None) -> Path:
    """Guarda un parquet en artefactos/ con un .json al lado (sha256, filas, metadatos)."""
    ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    ruta = ARTEFACTOS / f"{nombre}.parquet"
    df.to_parquet(ruta, index=False)
    (ARTEFACTOS / f"{nombre}.json").write_text(json.dumps(
        {"archivo": ruta.name, "sha256": sha256(ruta), "filas": len(df), **(meta or {})}, indent=2, default=str))
    return ruta


def cargar_artefacto(nombre: str):
    import pandas as pd
    ruta = ARTEFACTOS / f"{nombre}.parquet"
    meta = json.loads((ARTEFACTOS / f"{nombre}.json").read_text())
    if sha256(ruta) != meta["sha256"]:
        raise ValueError(f"{ruta.name} no coincide con su sha256 registrado")
    return pd.read_parquet(ruta), meta
