#!/usr/bin/env bash
# Reconstruye la OBT de PORTAFOLIO_P3 despues de un cambio en el pipeline y deja la evidencia:
#   1. pruebas (ingesta con uv; Spark dentro de su imagen)
#   2. imagenes del pipeline (con cache) y Compose arriba
#   3. flows actualizados y flow "transformar" (dbt build + Spark) hasta que termine
#   4. evidencias en docs/corrida/ (solo SELECT en Snowflake)
#   5. Compose abajo (sin -v) y snapshot nuevo de la OBT para los notebooks de pset-03
# Avisos: al terminar envia "Success: reconstruir_obt" o "Fail: reconstruir_obt" con el paso
# que fallo (scripts/notificar.py, credenciales AVISO_* de .env). Ademas, transformar se lanza
# con la etiqueta origen=manual y el flow usfq.avisos.avisos manda su propio correo.
#
# Uso, desde psets/pset-03/pipeline/:   bash scripts/reconstruir_obt.sh
# Requiere: Docker, uv, .env y .env_encoded (bash scripts/preparar_env.sh) y ../.env de pset-03.
# No levantar a la vez que MLflow de pset-03 (OOM). No lanza la ingesta de Yahoo.

set -euo pipefail
cd "$(dirname "$0")/.."
PIPELINE_DIR=$(pwd)
PASO="inicio"
DETALLE=""
paso() { PASO="$*"; printf '\n=== %s ===\n' "$*"; }
avisar() { python3 "$PIPELINE_DIR/scripts/notificar.py" "$@" || true; }
al_salir() {
    rc=$?
    if [[ $rc -ne 0 ]]; then
        avisar Fail reconstruir_obt "Fallo en el paso: $PASO (codigo $rc). $DETALLE"
    fi
}
trap al_salir EXIT

# Solo KESTRA_USUARIO y KESTRA_CLAVE desde .env (bash 3.2 de macOS: sin "source <(...)").
while IFS= read -r linea; do export "$linea"; done < <(grep -E '^KESTRA_(USUARIO|CLAVE)=' .env)
: "${KESTRA_CLAVE:?Define KESTRA_CLAVE en .env}"
AUTH="${KESTRA_USUARIO:-admin@kestra.io}:${KESTRA_CLAVE}"
API=http://localhost:8090/api/v1/main

base=$(grep -E '^SNOWFLAKE_DATABASE=' .env | cut -d= -f2-)
[[ "$base" == "PORTAFOLIO_P3" ]] || { echo "pipeline/.env apunta a '$base', no a PORTAFOLIO_P3" >&2; exit 1; }
base3=$(grep -E '^SNOWFLAKE_DATABASE=' ../.env | cut -d= -f2- || true)
[[ "$base3" == "PORTAFOLIO_P3" ]] || { echo "pset-03/.env apunta a '$base3', no a PORTAFOLIO_P3" >&2; exit 1; }

paso "1/5 Pruebas"
uv sync --group dev -q
uv run python -m pytest -q kestra/tests
docker compose --profile pruebas run --rm --build spark-pruebas

paso "2/5 Imagenes y Compose"
docker compose --profile herramientas build
docker compose up -d
printf 'Esperando a Kestra'
until curl -sf --user "$AUTH" -o /dev/null "$API/flows/search?size=1"; do printf '.'; sleep 3; done
echo " listo"

paso "3/5 Flows y transformar"
bash kestra/subir_flows.sh
# Etiqueta origen=manual: el flow de avisos solo notifica transformar cuando se lanza a mano.
id=$(curl -sf --user "$AUTH" -X POST "$API/executions/usfq.portafolio/transformar?labels=origen:manual" \
     | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
DETALLE="transformar: $id"
echo "transformar: $id"
while :; do
    # Estado en stdout; en stderr, hora de inicio, transcurrido, tareas y fin esperado.
    estado=$(python3 scripts/progreso_kestra.py "$API" "$AUTH" "$id")
    case "$estado" in
        SUCCESS) echo "transformar $id: SUCCESS"; break ;;
        FAILED|KILLED|WARNING|CANCELLED)
            echo "transformar $id termino en $estado; logs:" >&2
            curl -sf --user "$AUTH" "$API/logs/$id?minLevel=WARN" \
              | python3 -c "import sys,json; [print(l['taskId'], l['level'], l['message'][:300]) for l in json.load(sys.stdin)]" \
              | tail -30 >&2
            exit 1 ;;
        *) sleep 20 ;;
    esac
done

paso "4/5 Evidencias (solo SELECT)"
uv run python scripts/verificar_snowflake.py
uv run python scripts/exportar_metricas.py
uv run python scripts/auditar_obt.py > /dev/null && echo "auditoria_obt.json actualizado"
echo "$id" > docs/corrida/kestra_transformar_id.txt

paso "5/5 Compose abajo y snapshot"
docker compose down
cd ..
snap=$(uv run python -m src.datos | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tabla'], d['filas'], d['sha256'])")
echo "$snap"
DETALLE="$DETALLE | snapshot: $snap"
uv run python - <<'EOF'
from src.datos import cargar
df, meta = cargar()
ult = df["anio_mes"].max()
cols = ["ret_log_sp500_mes_siguiente", "ret_log_nyse_composite_mes_siguiente", "rf_mes_siguiente"]
nulos = df.loc[df["anio_mes"] == ult, cols].isna().all().all()
print(f"H1: mercado del mes siguiente nulo en el ultimo mes cerrado ({ult}): {'OK' if nulos else 'FALLA'}")
raise SystemExit(0 if nulos else 1)
EOF
PASO="terminado"
avisar Success reconstruir_obt "$DETALLE | H1 OK"
echo "Listo. Revisa git status en pipeline/docs/corrida/."
