# Imagen de dbt Core con el adaptador de Snowflake y el proyecto adentro.
# Kestra la corre como contenedor de tarea (pullPolicy NEVER):  docker compose build dbt
FROM python:3.12-slim
RUN pip install --no-cache-dir "dbt-core>=1.10,<2" "dbt-snowflake>=1.10,<2"
WORKDIR /dbt
COPY . /dbt
ENV DBT_PROFILES_DIR=/dbt
ENTRYPOINT []
CMD ["dbt", "build", "--target", "snowflake"]
