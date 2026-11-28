"""pytest lee este archivo antes de correr las pruebas de psets/proyecto/.

Su presencia deja psets/proyecto/ en la ruta de importacion de las pruebas:
asi una prueba de servicio/ puede escribir from modelado.pipeline_proyecto
import ..., igual que el servicio cuando corre desde psets/proyecto/.

Versiones (README, "Versiones de librerias y la CI del curso"; disclaimer.txt punto 15): el champion se
entreno con las versiones de api/requirements.txt (scikit-learn 1.9.1, mlflow 3.18.0, pandas 3.1.1, numpy
2.4.6). .github/workflows/pruebas.yml del curso instala el requirements.txt de la raiz del repositorio
(scikit-learn 1.5.2, mlflow 2.17.2, ...), con el que el modelo no carga. Si las versiones instaladas no son
las del proyecto, no se recogen pruebas (pytest sale con codigo 5, que pruebas.yml acepta) y el resumen
dice por que. Con el entorno del proyecto (uv run --project api --frozen pytest tests, como en pset4-ci.yml)
se recogen todas.
"""
from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

CRITICAS = ("scikit-learn", "mlflow", "pandas", "numpy", "lightgbm")


def _versiones_del_proyecto() -> dict[str, str]:
    texto = (Path(__file__).resolve().parent / "api" / "requirements.txt").read_text()
    pines = dict(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", texto, flags=re.M))
    return {p: pines[p] for p in CRITICAS if p in pines}


def _diferencias() -> list[str]:
    difs = []
    for paquete, esperada in _versiones_del_proyecto().items():
        try:
            instalada = metadata.version(paquete)
        except metadata.PackageNotFoundError:
            instalada = "no instalada"
        if instalada != esperada:
            difs.append(f"{paquete} {instalada} (el proyecto fija {esperada})")
    return difs


DIFERENCIAS = _diferencias()
collect_ignore_glob = ["*"] if DIFERENCIAS else []


def pytest_terminal_summary(terminalreporter):
    if DIFERENCIAS:
        terminalreporter.write_line(
            "psets/proyecto: pruebas no recogidas porque las versiones instaladas no son las del proyecto: "
            + "; ".join(DIFERENCIAS)
            + ". Correr con: uv run --project api --frozen pytest tests (ver README).")
