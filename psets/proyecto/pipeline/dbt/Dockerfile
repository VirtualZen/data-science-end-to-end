# Imagen de dbt Core con el adaptador de Snowflake y el proyecto adentro.
# Kestra la corre como contenedor de tarea (pullPolicy NEVER):  docker compose build dbt
# Python 3.11 como el resto del proyecto. requirements.txt se genera desde uv.lock
# (scripts/exportar_requirements.sh, grupo dbt-imagen): dbt-core 1.12.7 fijo.
# Cache de pip en BuildKit: los reintentos de un build cortado no vuelven a descargar.
FROM python:3.11-slim
COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r /tmp/requirements.txt
WORKDIR /dbt
COPY . /dbt
ENV DBT_PROFILES_DIR=/dbt
ENTRYPOINT []
CMD ["dbt", "build", "--target", "snowflake"]
