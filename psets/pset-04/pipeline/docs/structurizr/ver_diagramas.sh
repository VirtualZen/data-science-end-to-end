#!/usr/bin/env bash
# Abre Structurizr con el workspace.dsl de esta carpeta, en http://localhost:8080/workspace/1
# (Kestra usa :8090 y la UI de Spark :8081, así que el 8080 queda libre).
# La UI recarga al guardar el .dsl. Desde cada diagrama se exporta el PNG/SVG con su
# leyenda (casilla Download); el tema se cambia con el enlace Light/Dark del visor.
# Requiere Docker. Detener con Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")"
docker run -it --rm -p 8080:8080 -v "$PWD":/usr/local/structurizr structurizr/structurizr:2026.05.22-noble local
