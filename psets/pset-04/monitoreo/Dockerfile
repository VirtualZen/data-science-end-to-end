# Imagen de las tareas de produccion que lanza Kestra (pset4-produccion): simulacion por lotes, monitoreo y
# reentrenamiento, y el tablero (Streamlit, grupo tablero de modelos/pyproject.toml). Mismo entorno que modelos/
# (requirements.txt exportado de modelos/uv.lock, con los grupos modelos y tablero) y el mismo
# src/pipeline.py, copiado. Se construye desde psets/pset-04/:
#   docker compose --env-file pipeline/.env --profile herramientas build produccion
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY modelos/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY modelos/src /app/modelos/src
COPY monitoreo /app/monitoreo
ENV PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/matplotlib GIT_PYTHON_REFRESH=quiet
ENTRYPOINT []
