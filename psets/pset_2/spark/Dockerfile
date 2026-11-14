# Imagen de Spark para el maestro, el trabajador y el job de la OBT. Incluye el conector
# de Snowflake para Spark y su driver JDBC (todos los nodos los necesitan).
#   docker compose build spark-master
# Si Maven Central no tiene alguna version, cambiala con --build-arg.
ARG SPARK_IMAGE=apache/spark:3.5.3-python3
FROM ${SPARK_IMAGE}

ARG SPARK_SNOWFLAKE_VERSION=3.2.3
ARG SNOWFLAKE_JDBC_VERSION=4.0.2

ADD --chmod=644 https://repo1.maven.org/maven2/net/snowflake/spark-snowflake_2.12/${SPARK_SNOWFLAKE_VERSION}/spark-snowflake_2.12-${SPARK_SNOWFLAKE_VERSION}.jar /opt/spark/jars/
ADD --chmod=644 https://repo1.maven.org/maven2/net/snowflake/snowflake-jdbc/${SNOWFLAKE_JDBC_VERSION}/snowflake-jdbc-${SNOWFLAKE_JDBC_VERSION}.jar /opt/spark/jars/

COPY jobs/ /opt/jobs/
WORKDIR /opt/jobs
