# Imagen de la API (PSet 4). Se construye desde psets/pset-04/ (necesita modelos/src):
#   docker build -f api/Dockerfile -t pset4-api .
# El modelo NO va en la imagen: se carga al arrancar desde el Model Registry
# (MODELO_URI, por defecto models:/portafolio-inversiones-modelo@champion, con MLFLOW_TRACKING_URI).
# Cambiar de version = mover el alias y llamar a POST /recargar; no se reconstruye la imagen.
FROM python:3.11-slim

# lightgbm necesita la biblioteca de OpenMP en tiempo de ejecucion
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt

# Las mismas funciones del modelado (src.pipeline.derivar, src.negocio.pesos_mes), importadas.
COPY modelos/src /app/src
COPY api/__init__.py api/main.py api/esquemas.py api/contrato.json /app/api/

ENV PYTHONUNBUFFERED=1 \
    MLFLOW_DISABLE_AGENT_HINT=1 \
    REGISTRO_PREDICCIONES=/app/registros/predicciones.jsonl
RUN useradd --create-home --uid 1000 api && mkdir -p /app/registros && chown api /app/registros
USER api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD curl -sf http://localhost:8000/salud || exit 1
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
