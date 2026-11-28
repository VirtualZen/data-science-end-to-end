"""Fijas comunes. Las pruebas no usan servidor de MLflow ni Snowflake ni leen modelos/data/: cargan la copia
del champion de tests/fixtures/modelo_champion (MODELO_URI) y los lotes de tests/fixtures/."""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import pytest

FIJAS = Path(__file__).resolve().parent / "fixtures"
RAIZ = FIJAS.parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(1, str(RAIZ / "modelos"))     # src.pipeline y src.negocio, igual que la API

os.environ["MODELO_URI"] = str(FIJAS / "modelo_champion")
os.environ.setdefault("API_TOKEN", "token-de-prueba")
os.environ.pop("USAR_RESPALDO", None)


@pytest.fixture(scope="session")
def lote() -> dict:
    """Peticion valida: las 333 acciones elegibles de 2023-12 (objetivo 2024-01)."""
    return json.loads((FIJAS / "lote_2024_01.json").read_text())


@pytest.fixture
def peticion(lote) -> dict:
    return copy.deepcopy(lote)


@pytest.fixture(scope="session")
def cliente(tmp_path_factory):
    os.environ["REGISTRO_PREDICCIONES"] = str(tmp_path_factory.mktemp("registros") / "predicciones.jsonl")
    from fastapi.testclient import TestClient

    from api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def token() -> dict:
    return {"X-Token": os.environ["API_TOKEN"]}
