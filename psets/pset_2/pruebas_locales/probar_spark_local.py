"""Exporta las tablas Gold de la base DuckDB de prueba a Parquet y corre el job de la OBT
en modo local. Antes: python pruebas_locales/cargar_muestra.py y dbt build --target local.

Uso, desde psets/pset_2/:   python pruebas_locales/probar_spark_local.py
"""

import subprocess
import sys
from pathlib import Path

import duckdb

AQUI = Path(__file__).parent
DATOS = AQUI / "datos" / "gold"
SALIDA = AQUI / "salida"
JOB = AQUI.parent / "spark" / "jobs" / "construir_obt.py"

DATOS.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(str(AQUI / "portafolio_local.duckdb"), read_only=True)
for t in ["fct_precios_diarios", "dim_accion", "dim_fecha", "fct_mercado_diario"]:
    con.execute(f"copy gold.{t} to '{DATOS / t}' (format parquet, per_thread_output true, overwrite true)")
con.close()

r = subprocess.run([sys.executable, str(JOB), "--modo", "local",
                    "--entrada", str(DATOS), "--salida", str(SALIDA)])
sys.exit(r.returncode)
