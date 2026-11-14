#!/usr/bin/env bash
# Crea o actualiza el ambiente compartido de los laboratorios (laboratorios/.venv).
# Uso: ./setup.sh
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
    echo "Falta uv. Instalalo con: brew install uv" >&2
    exit 1
fi

# Un VIRTUAL_ENV de otro proyecto hace que uv lo ignore con una advertencia.
unset VIRTUAL_ENV

uv sync --locked
echo "Ambiente listo en $(pwd)/.venv"
