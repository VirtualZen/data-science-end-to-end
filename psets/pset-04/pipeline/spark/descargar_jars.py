"""Descarga a /opt/spark/jars el conector de Snowflake para Spark y su driver JDBC.

Lo usa spark/Dockerfile durante el build (no se copia a la imagen):
  python3 /tmp/descargar_jars.py <version_conector> <version_jdbc>
Los .jar se guardan en un cache de BuildKit (/var/cache/spark-jars): si el build se repite
o se corta, no se vuelven a bajar de Maven.
"""
from __future__ import annotations   # la imagen de Spark trae Python 3.8

import shutil
import sys
import urllib.request
from pathlib import Path

MAVEN = "https://repo1.maven.org/maven2/net/snowflake"
CACHE = Path("/var/cache/spark-jars")
DESTINO = Path("/opt/spark/jars")


def urls(conector: str, jdbc: str) -> list[str]:
    return [
        f"{MAVEN}/spark-snowflake_2.12/{conector}/spark-snowflake_2.12-{conector}.jar",
        f"{MAVEN}/snowflake-jdbc/{jdbc}/snowflake-jdbc-{jdbc}.jar",
    ]


def main(conector: str, jdbc: str) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    for url in urls(conector, jdbc):
        jar = CACHE / url.rsplit("/", 1)[1]
        if jar.exists() and jar.stat().st_size > 0:
            print(f"cache: {jar.name}")
        else:
            parcial = jar.with_suffix(".parcial")   # un corte no deja un .jar incompleto
            urllib.request.urlretrieve(url, parcial)
            parcial.rename(jar)
            print(f"descargado: {jar.name} ({jar.stat().st_size} bytes)")
        copia = DESTINO / jar.name
        shutil.copyfile(jar, copia)
        copia.chmod(0o644)


if __name__ == "__main__":
    main(*sys.argv[1:3])
