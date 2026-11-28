#!/usr/bin/env bash
# Exporta las vistas del workspace.dsl con el CLI oficial de Structurizr:
#   export/*.mmd   Mermaid (texto, comparable en git)
#   export/*.puml  PlantUML (texto)
#   export/*.png   PNG en tema claro, renderizado desde el PlantUML (incluye la leyenda *-key)
# Alternativa interactiva: ver_diagramas.sh abre la UI, que exporta PNG/SVG con el tema visible.
# Requiere Docker.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p export
STRUCTURIZR_IMAGE=${STRUCTURIZR_IMAGE:-structurizr/structurizr:2026.05.22-noble}
docker run --rm -v "$PWD":/usr/local/structurizr "$STRUCTURIZR_IMAGE" validate --workspace workspace.dsl
docker run --rm -v "$PWD":/usr/local/structurizr "$STRUCTURIZR_IMAGE" export --workspace workspace.dsl --format json --output .

docker run --rm -v "$PWD":/usr/local/structurizr "$STRUCTURIZR_IMAGE" \
    export --workspace workspace.dsl --format mermaid --output export
docker run --rm -v "$PWD":/usr/local/structurizr "$STRUCTURIZR_IMAGE" \
    export --workspace workspace.dsl --format plantuml --output export

# PLANTUML_LIMIT_SIZE: sin esto PlantUML recorta los diagramas anchos a 4096 px.
docker run --rm -v "$PWD/export":/data -e PLANTUML_LIMIT_SIZE=16384 plantuml/plantuml \
    -tpng /data/*.puml

echo "Listo:"
ls export
