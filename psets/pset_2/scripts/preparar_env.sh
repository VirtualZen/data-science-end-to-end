#!/usr/bin/env bash
# Prepara los secretos a partir de .env, sin subir nada al repositorio:
#   1. Copia el cuerpo de la llave privada (SNOWFLAKE_PRIVATE_KEY_PATH) a una sola
#      linea en SNOWFLAKE_PRIVATE_KEY dentro de .env (lo usan dbt, Spark y la ingesta).
#   2. Crea .env_encoded con cada variable SNOWFLAKE_* como SECRET_<NOMBRE> en base64,
#      que es el formato con el que Kestra (edicion abierta) lee secretos:
#      {{ secret('SNOWFLAKE_ACCOUNT') }}.
#
# Uso, desde psets/pset_2/:   bash scripts/preparar_env.sh

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "Falta .env: copia .env.example como .env y completalo." >&2
    exit 1
fi

llave=$(grep -E '^SNOWFLAKE_PRIVATE_KEY_PATH=' .env | cut -d= -f2-)
if [[ -z "$llave" || ! -f "$llave" ]]; then
    echo "No encuentro la llave privada en '$llave' (SNOWFLAKE_PRIVATE_KEY_PATH)." >&2
    exit 1
fi
cuerpo=$(grep -v -- '-----' "$llave" | tr -d '\n\r ')

tmp=$(mktemp)
grep -v -E '^SNOWFLAKE_PRIVATE_KEY=' .env > "$tmp"
echo "SNOWFLAKE_PRIVATE_KEY=$cuerpo" >> "$tmp"
mv "$tmp" .env
chmod 600 .env

: > .env_encoded
while IFS='=' read -r nombre valor; do
    [[ "$nombre" =~ ^(SNOWFLAKE_|FECHA_) ]] || continue
    [[ "$nombre" == "SNOWFLAKE_PRIVATE_KEY_PATH" ]] && continue
    echo "SECRET_${nombre}=$(printf '%s' "$valor" | base64 | tr -d '\n')" >> .env_encoded
done < <(grep -E '^[A-Z_]+=' .env)
chmod 600 .env_encoded

echo "Listo: .env actualizado y .env_encoded creado ($(wc -l < .env_encoded) secretos)."
echo "Ninguno de los dos archivos se sube a git (ver .gitignore)."
