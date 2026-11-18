#!/usr/bin/env bash
# Pruebas de la orquestacion con Kestra (plan.txt V2.4 y V2.5) y evidencia en docs/corrida/:
#   1. pruebas de la ingesta (uv), imagenes, Compose arriba y flows (incluye avisos)
#   2. V2.4a ingesta_diaria manual sin inputs (misma expresion de fecha que el trigger) -> SUCCESS
#   3. V2.5  ingesta_diaria con simular_falla=true -> 4 intentos con espera exponencial,
#            registrar_falla y aviso "Fail" -> FAILED (tarda ~15 minutos)
#   4. V2.4b si aun no son las 18:45 de Nueva York, espera la ingesta del cron de las 18:30
#            (system.from=trigger) y su resultado. Saltar con ESPERAR_CRON=0.
#   5. estados de Kestra, evidencias de Snowflake (solo SELECT), Compose abajo (sin -v)
# Llegan correos: Success de la ingesta manual (y del cron), Fail de la simulada y el resumen.
#
# Uso, desde psets/pset-03/pipeline/:   bash scripts/probar_ingesta_y_reintentos.sh
# Requiere: Docker, uv, .env y .env_encoded (bash scripts/preparar_env.sh). Sin MLflow arriba.

set -euo pipefail
cd "$(dirname "$0")/.."
PIPELINE_DIR=$(pwd)
PASO="inicio"
RESUMEN=""
paso() { PASO="$*"; printf '\n=== %s ===\n' "$*"; }
avisar() { python3 "$PIPELINE_DIR/scripts/notificar.py" "$@" || true; }
al_salir() {
    rc=$?
    if [[ $rc -ne 0 ]]; then
        avisar Fail probar_ingesta_y_reintentos "Fallo en el paso: $PASO (codigo $rc). $RESUMEN"
    fi
}
trap al_salir EXIT

while IFS= read -r linea; do export "$linea"; done < <(grep -E '^KESTRA_(USUARIO|CLAVE)=' .env)
: "${KESTRA_CLAVE:?Define KESTRA_CLAVE en .env}"
export KESTRA_USUARIO="${KESTRA_USUARIO:-admin@kestra.io}"
AUTH="${KESTRA_USUARIO}:${KESTRA_CLAVE}"
export KESTRA_API=http://localhost:8090/api/v1/main
API=$KESTRA_API
base=$(grep -E '^SNOWFLAKE_DATABASE=' .env | cut -d= -f2-)
[[ "$base" == "PORTAFOLIO_P3" ]] || { echo "pipeline/.env apunta a '$base', no a PORTAFOLIO_P3" >&2; exit 1; }
EVIDENCIA=docs/corrida/kestra_pruebas.json
INICIO_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)

estado() {  # id -> estado actual
    curl -sf --user "$AUTH" "$API/executions/$1" | python3 -c "import sys,json; print(json.load(sys.stdin)['state']['current'])"
}
esperar() {  # id -> espera a un estado terminal y lo imprime (progreso en stderr)
    local e
    while :; do
        e=$(python3 scripts/progreso_kestra.py "$API" "$AUTH" "$1")
        case "$e" in
            SUCCESS|FAILED|KILLED|WARNING|CANCELLED) echo "$e"; return 0 ;;
            *) sleep 30 ;;
        esac
    done
}
lanzar() {  # flow [campos -F] -> id
    local flow=$1; shift
    curl -sf --user "$AUTH" -X POST "$API/executions/usfq.portafolio/$flow" "$@" \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])"
}
resumen_ejecucion() {  # id prueba -> agrega un JSON por linea a /tmp con estado, intentos y etiquetas
    curl -sf --user "$AUTH" "$API/executions/$1" | python3 -c "
import sys, json
j = json.load(sys.stdin)
tareas = {t['taskId']: {'estado': t['state']['current'], 'intentos': len(t.get('attempts') or [])}
          for t in j.get('taskRunList', [])}
print(json.dumps({'prueba': '$2', 'id': j['id'], 'flow': j['flowId'], 'estado': j['state']['current'],
                  'inicio': j['state']['startDate'], 'duracion': j['state'].get('duration'),
                  'etiquetas': {l['key']: l['value'] for l in j.get('labels', [])},
                  'tareas': tareas}, ensure_ascii=False))" >> /tmp/kestra_pruebas.jsonl
}
: > /tmp/kestra_pruebas.jsonl

paso "1/5 Pruebas, imagenes y Kestra"
uv sync --group dev -q
uv run python -m pytest -q kestra/tests
docker compose --profile herramientas build
docker compose up -d
printf 'Esperando a Kestra'
until curl -sf --user "$AUTH" -o /dev/null "$API/flows/search?size=1"; do printf '.'; sleep 3; done
echo " listo"
bash kestra/subir_flows.sh

paso "2/5 V2.4a ingesta_diaria manual"
id_manual=$(lanzar ingesta_diaria)
RESUMEN="manual: $id_manual"
echo "ingesta_diaria manual: $id_manual"
e=$(esperar "$id_manual"); echo; echo "ingesta_diaria $id_manual: $e"
resumen_ejecucion "$id_manual" "V2.4a ingesta manual"
[[ "$e" == "SUCCESS" ]] || exit 1

paso "3/5 V2.5 falla simulada con reintentos"
id_falla=$(lanzar ingesta_diaria -F simular_falla=true)
RESUMEN="$RESUMEN | falla simulada: $id_falla"
echo "ingesta_diaria con simular_falla: $id_falla (unos 15 minutos)"
e=$(esperar "$id_falla"); echo; echo "ingesta_diaria $id_falla: $e"
resumen_ejecucion "$id_falla" "V2.5 falla simulada"
intentos=$(tail -1 /tmp/kestra_pruebas.jsonl | python3 -c "import sys,json; print(json.load(sys.stdin)['tareas'].get('extraer_cargar_raw',{}).get('intentos',0))")
echo "intentos de extraer_cargar_raw: $intentos"
[[ "$e" == "FAILED" && "$intentos" -ge 2 ]] || { echo "Se esperaba FAILED con reintentos" >&2; exit 1; }

paso "4/5 V2.4b ingesta lanzada por el cron (18:30 NY)"
hora_ny=$(TZ=America/New_York date +%H%M)
if [[ "${ESPERAR_CRON:-1}" == "1" && "$hora_ny" -lt 1845 ]]; then
    echo "Hora en Nueva York: $hora_ny. Esperando la ejecucion del trigger cierre_nyse..."
    id_cron=""
    while [[ -z "$id_cron" ]]; do
        id_cron=$(curl -sf --user "$AUTH" "$API/executions/search?namespace=usfq.portafolio&flowId=ingesta_diaria&size=10&sort=state.startDate:desc" \
            | python3 -c "
import sys, json
for e in json.load(sys.stdin)['results']:
    etiquetas = {l['key']: l['value'] for l in e.get('labels', [])}
    if etiquetas.get('system.from') == 'trigger' and e['state']['startDate'] >= '$INICIO_UTC':
        print(e['id']); break")
        [[ -n "$id_cron" ]] || sleep 60
    done
    RESUMEN="$RESUMEN | cron: $id_cron"
    echo "ingesta del cron: $id_cron"
    e=$(esperar "$id_cron"); echo; echo "ingesta_diaria $id_cron (cron): $e"
    resumen_ejecucion "$id_cron" "V2.4b ingesta del cron"
else
    echo "Se omite (hora NY $hora_ny o ESPERAR_CRON=0)."
fi

paso "5/5 Evidencias y Compose abajo"
python3 -c "import json; print(json.dumps([json.loads(l) for l in open('/tmp/kestra_pruebas.jsonl')], indent=2, ensure_ascii=False))" > "$EVIDENCIA"
echo "$EVIDENCIA:"; cat "$EVIDENCIA"
uv run python scripts/verificar_kestra.py estado > /dev/null && echo "docs/corrida/kestra_estados.json actualizado"
uv run python scripts/verificar_snowflake.py
uv run python scripts/exportar_metricas.py
docker compose down
PASO="terminado"
avisar Success probar_ingesta_y_reintentos "$RESUMEN | intentos en la falla simulada: $intentos"
echo "Listo."
