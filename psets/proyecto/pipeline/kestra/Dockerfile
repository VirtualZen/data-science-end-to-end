# Imagen de la tarea de ingesta. Kestra la corre como contenedor (pullPolicy NEVER),
# asi que hay que construirla antes:  docker compose build ingesta
# Python 3.11, igual que la CI del curso y el entorno local (pyproject.toml).
# requirements.txt se genera desde uv.lock (scripts/exportar_requirements.sh): versiones exactas.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
# Cache de pip en BuildKit: si el build se corta (red lenta), el siguiente intento reutiliza
# lo ya descargado. La cache vive fuera de la imagen, asi que no la agranda.
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
COPY scripts/ /app/
ENTRYPOINT []
