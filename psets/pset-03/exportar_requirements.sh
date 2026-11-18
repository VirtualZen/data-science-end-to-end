#!/usr/bin/env bash
# Regenera requirements.txt del PSet 3 desde uv.lock (no se edita a mano).
#
# Uso, desde psets/pset-03:
#   uv lock                          # solo si cambiaste pyproject.toml
#   bash exportar_requirements.sh
#
# requirements.txt lo usan Dockerfile.runner y src/experimentos.py (se registra en MLflow).
set -euo pipefail
cd "$(dirname "$0")"

uv export --frozen --format requirements-txt --no-hashes --no-emit-project \
    --no-dev --group modelos --output-file requirements.txt > /dev/null

echo "OK: requirements.txt regenerado desde uv.lock"
