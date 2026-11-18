#!/usr/bin/env bash
# Regenera los requirements.txt del PSet 2 desde uv.lock (no se editan a mano).
#
# Uso, desde psets/pset-03/pipeline/:
#   uv lock                               # solo si cambiaste pyproject.toml
#   bash scripts/exportar_requirements.sh
#
# Produce:
#   requirements.txt          entorno local (pipeline + pruebas locales con Spark + memo)
#   kestra/requirements.txt   solo la imagen pset3-ingesta (grupo "ingesta")
#   dbt/requirements.txt      solo la imagen pset3-dbt (grupo "dbt-imagen")
# Ambos con versiones exactas (==) tomadas del mismo uv.lock.
set -euo pipefail
cd "$(dirname "$0")/.."

uv export --frozen --format requirements-txt --no-hashes --no-emit-project \
    --no-dev --group pruebas-locales --output-file requirements.txt > /dev/null
uv export --frozen --format requirements-txt --no-hashes --no-emit-project \
    --only-group ingesta --output-file kestra/requirements.txt > /dev/null
uv export --frozen --format requirements-txt --no-hashes --no-emit-project \
    --only-group dbt-imagen --output-file dbt/requirements.txt > /dev/null

echo "OK: requirements.txt, kestra/requirements.txt y dbt/requirements.txt regenerados desde uv.lock"
