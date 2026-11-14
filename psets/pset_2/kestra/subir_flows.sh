#!/usr/bin/env bash
# Crea o actualiza en Kestra los tres flows de kestra/flows/ (misma API que el
# script subir_a_kestra.sh de la Semana 4). Kestra debe estar corriendo.
#
# Uso, desde psets/pset_2/:   bash kestra/subir_flows.sh

set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] && set -a && source <(grep -E '^KESTRA_(USUARIO|CLAVE)=' .env) && set +a

KESTRA=${KESTRA:-http://localhost:8080/api/v1/main}
USUARIO="${KESTRA_USUARIO:-admin@kestra.io}:${KESTRA_CLAVE:-Admin1234}"

# transformar primero: los otros dos lo llaman como subflow.
for flow in kestra/flows/transformar.yml kestra/flows/ingesta_diaria.yml kestra/flows/backfill_historico.yml; do
    id=$(grep -E '^id:' "$flow" | awk '{print $2}')
    namespace=$(grep -E '^namespace:' "$flow" | awk '{print $2}')
    if curl -sf -u "$USUARIO" "$KESTRA/flows/$namespace/$id" > /dev/null; then
        curl -sf -u "$USUARIO" -X PUT -H "Content-Type: application/x-yaml" \
            --data-binary @"$flow" "$KESTRA/flows/$namespace/$id" > /dev/null
        echo "Flow $namespace.$id actualizado"
    else
        curl -sf -u "$USUARIO" -X POST -H "Content-Type: application/x-yaml" \
            --data-binary @"$flow" "$KESTRA/flows" > /dev/null
        echo "Flow $namespace.$id creado"
    fi
done
