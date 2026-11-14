#!/usr/bin/env bash
# Corre los scripts de los laboratorios con el ambiente compartido.
#
#   ./run.sh                 corre todos los ejercicios (pasos locales)
#   ./run.sh 03-01 05-01     corre solo las sesiones indicadas (semana-sesion)
#   ./run.sh --docker        ademas construye las imagenes Docker de la semana 03
#
# Los scripts escriben sus salidas en sus carpetas (datos/*.csv, *.duckdb).
# ingesta_inestable.py e ingesta_clima.py fallan al azar a proposito; eso no detiene el resto.
set -uo pipefail

RAIZ="$(cd "$(dirname "$0")" && pwd)"
cd "$RAIZ"
unset VIRTUAL_ENV

DOCKER=0
SESIONES=()
for arg in "$@"; do
    if [ "$arg" = "--docker" ]; then DOCKER=1; else SESIONES+=("$arg"); fi
done

[ -x .venv/bin/python ] || { echo "Falta el ambiente. Corre primero ./setup.sh" >&2; exit 1; }

seleccionada() {
    [ ${#SESIONES[@]} -eq 0 ] && return 0
    for s in "${SESIONES[@]}"; do [ "$s" = "$1" ] && return 0; done
    return 1
}

FALLOS=0
py() {  # py <carpeta> <script> [args...]
    local dir=$1; shift
    echo; echo "=== $dir: $*"
    (cd "$RAIZ/$dir" && uv run --project "$RAIZ" "$@") || { echo "(termino con error)"; FALLOS=$((FALLOS + 1)); }
}

if seleccionada 03-01; then
    py semana-03-sesion-01/starter/ejercicio1 procesar.py
    py semana-03-sesion-01/starter/ejercicio2 contar_filas.py
    py semana-03-sesion-01/starter/ejercicio2 resumir_clientes.py
    echo; echo "=== semana-03-sesion-01/starter/ejercicio2: comprobar.sh"
    (cd semana-03-sesion-01/starter/ejercicio2 && bash comprobar.sh)
fi
if seleccionada 04-01; then
    py semana-04-sesion-01/starter/ejercicio1 ingesta_inestable.py
    py semana-04-sesion-01/starter/ejercicio2 ingesta_clima.py 2024-01-01
fi
if seleccionada 04-02; then
    py semana-04-sesion-02/starter ejercicio1_diagnostico.py
    py semana-04-sesion-02/starter ejercicio2_pedidos.py
fi
if seleccionada 05-01; then
    py semana-05-sesion-01/starter ejercicio1_warehouse.py
    py semana-05-sesion-01/starter ejercicio2_ventas.py
fi

if [ "$DOCKER" -eq 1 ]; then
    if seleccionada 03-01; then
        echo; echo "=== docker: semana-03-sesion-01/ejercicio1"
        docker build -q -t procesar semana-03-sesion-01/starter/ejercicio1 \
            && docker run --rm -v "$RAIZ/semana-03-sesion-01/starter/ejercicio1/datos:/app/datos" procesar \
            || FALLOS=$((FALLOS + 1))
    fi
    if seleccionada 03-02; then
        echo; echo "=== docker: semana-03-sesion-02 (solo build; la ingesta necesita Postgres)"
        docker build -q -t ingesta semana-03-sesion-02/starter || FALLOS=$((FALLOS + 1))
    fi
fi

echo; echo "Terminado. Scripts con error: $FALLOS"
[ "$FALLOS" -eq 0 ]
