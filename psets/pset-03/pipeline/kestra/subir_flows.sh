#!/usr/bin/env bash
# Crea o actualiza en Kestra los cuatro flows de kestra/flows/ (misma API que el
# script subir_a_kestra.sh de la Semana 4). Kestra debe estar corriendo.
#
# Uso, desde psets/pset-03/pipeline/:   bash kestra/subir_flows.sh

set -euo pipefail
cd "$(dirname "$0")/.."
# Carga solo KESTRA_USUARIO y KESTRA_CLAVE desde .env. Sin "source <(...)": el bash 3.2
# de macOS no lee bien la sustitucion de procesos con source.
if [[ -f .env ]]; then
    while IFS= read -r linea; do export "$linea"; done < <(grep -E '^KESTRA_(USUARIO|CLAVE)=' .env)
fi

KESTRA=${KESTRA:-http://localhost:8090/api/v1/main}
USUARIO="${KESTRA_USUARIO:-admin@kestra.io}:${KESTRA_CLAVE:?Define KESTRA_CLAVE en .env}"

# Envia un flow y, si Kestra lo rechaza, muestra su mensaje en vez de salir en silencio.
enviar() {  # metodo url archivo
    respuesta=$(curl -s -u "$USUARIO" -X "$1" -H "Content-Type: application/x-yaml" \
        --data-binary @"$3" -w '\n%{http_code}' "$2")
    codigo=${respuesta##*$'\n'}
    if [[ "$codigo" != 2* ]]; then
        echo "Kestra rechazo $3 (HTTP $codigo): ${respuesta%$'\n'*}" >&2
        exit 1
    fi
}

# transformar primero: los otros dos lo llaman como subflow. avisos al final.
for flow in kestra/flows/transformar.yml kestra/flows/ingesta_diaria.yml \
            kestra/flows/backfill_historico.yml kestra/flows/avisos.yml; do
    id=$(grep -E '^id:' "$flow" | awk '{print $2}')
    namespace=$(grep -E '^namespace:' "$flow" | awk '{print $2}')
    if curl -sf -u "$USUARIO" "$KESTRA/flows/$namespace/$id" > /dev/null; then
        enviar PUT "$KESTRA/flows/$namespace/$id" "$flow"
        echo "Flow $namespace.$id actualizado"
    else
        enviar POST "$KESTRA/flows" "$flow"
        echo "Flow $namespace.$id creado"
    fi
done
