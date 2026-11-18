# Imagen de Spark para el maestro, el trabajador y el job de la OBT, mas una etapa de
# pruebas. Incluye el conector de Snowflake para Spark y su driver JDBC.
#   docker compose build spark-master                          imagen pset3-spark (runtime)
#   docker compose --profile pruebas run --rm spark-pruebas    construye y corre las pruebas
# 3.1.9 es la ultima version del conector publicada para Scala 2.12 (la de Spark 3.5.x);
# las 3.2.x son solo para Scala 2.13. Si cambia, ajustala con --build-arg.
#
# Capas, de la que menos cambia a la que mas: imagen de Spark -> jars de Snowflake ->
# (pruebas: pytest) -> codigo. Editar jobs/ o tests/ solo reconstruye la ultima capa.
ARG SPARK_IMAGE=apache/spark:3.5.3-python3

# --- base: Spark + jars de Snowflake (compartida por runtime y pruebas) ----------------
FROM ${SPARK_IMAGE} AS base
ARG SPARK_SNOWFLAKE_VERSION=3.1.9
ARG SNOWFLAKE_JDBC_VERSION=3.28.0
USER root
# Cache de BuildKit para los .jar: esta capa solo se rehace si cambian las versiones o el
# script, y aun asi no vuelve a bajar de Maven lo que ya esta en el cache.
RUN --mount=type=cache,target=/var/cache/spark-jars \
    --mount=type=bind,source=descargar_jars.py,target=/tmp/descargar_jars.py \
    python3 /tmp/descargar_jars.py "${SPARK_SNOWFLAKE_VERSION}" "${SNOWFLAKE_JDBC_VERSION}"
USER spark

# --- pruebas: pytest sobre jobs/ con el PySpark y el Java de la imagen ------------------
FROM base AS pruebas
USER root
# La imagen de Spark 3.5.3 trae Python 3.8: pytest 8.3.x es la ultima serie que lo soporta.
RUN --mount=type=cache,target=/root/.cache/pip \
    python3 -m pip install pytest==8.3.5
USER spark
WORKDIR /opt/spark-pruebas
# PySpark y py4j vienen dentro de /opt/spark/python (no instalados con pip).
ENV PYTHONDONTWRITEBYTECODE=1
# Spark local: usar localhost en vez de resolver el nombre del contenedor.
ENV SPARK_LOCAL_IP=127.0.0.1 \
    SPARK_LOCAL_HOSTNAME=localhost
COPY jobs/ jobs/
COPY tests/ tests/
# Primero comprueba que pyspark y java existen: si faltaran, las pruebas se saltarian
# (skip) y el resultado pareceria verde sin haber probado nada.
CMD ["sh", "-c", "export PYTHONPATH=/opt/spark/python:$(ls /opt/spark/python/lib/py4j-*-src.zip) && python3 -c 'import pyspark, shutil, sys; assert shutil.which(\"java\"), \"falta java\"; print(\"pyspark\", pyspark.__version__, \"| python\", sys.version.split()[0])' && exec python3 -m pytest -v -rs -p no:cacheprovider tests"]

# --- runtime: la imagen que usan maestro, trabajador y spark-job (etapa por defecto) ----
FROM base AS runtime
COPY jobs/ /opt/jobs/
WORKDIR /opt/jobs
