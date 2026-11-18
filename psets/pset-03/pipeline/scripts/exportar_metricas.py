"""Exporta a docs/corrida/ las evidencias de la corrida en Snowflake: metricas de calidad,
validacion de la OBT, conteos por capa y frescura. Para el memo (seccion 3) y el README.

Uso, desde psets/pset-03/pipeline/:   python scripts/exportar_metricas.py
"""
import base64
import csv
import os
from pathlib import Path

import snowflake.connector

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "corrida"
SALIDA.mkdir(parents=True, exist_ok=True)

env = dict(os.environ)
if (RAIZ / ".env").exists():
    for linea in (RAIZ / ".env").read_text().splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            k, _, v = linea.partition("=")
            env.setdefault(k.strip(), v.strip())

con = snowflake.connector.connect(
    account=env["SNOWFLAKE_ACCOUNT"], user=env["SNOWFLAKE_USER"],
    private_key=base64.b64decode(env["SNOWFLAKE_PRIVATE_KEY"]),
    role=env.get("SNOWFLAKE_ROLE"), warehouse=env.get("SNOWFLAKE_WAREHOUSE"),
    database=env.get("SNOWFLAKE_DATABASE", "PORTAFOLIO_P3"), schema="CALIDAD",
    application="pset3_evidencias")
cur = con.cursor()

CONSULTAS = {
    "dq_metricas": "select dimension, capa, metrica, round(valor, 4) as valor, unidad, descripcion "
                   "from CALIDAD.DQ_METRICAS order by dimension, capa, metrica",
    "validacion_obt": "select * from OBT.VALIDACION_OBT order by control",
    "conteos_por_capa": """
        select 'RAW.PRECIOS_DIARIOS' t, count(*) filas from RAW.PRECIOS_DIARIOS union all
        select 'RAW.COMPOSICION_SP500', count(*) from RAW.COMPOSICION_SP500 union all
        select 'RAW.LISTADOS_BOLSA', count(*) from RAW.LISTADOS_BOLSA union all
        select 'RAW.INGESTA_LOG', count(*) from RAW.INGESTA_LOG union all
        select 'BRONZE.BRZ_PRECIOS_DIARIOS', count(*) from BRONZE.BRZ_PRECIOS_DIARIOS union all
        select 'SILVER.SLV_PRECIOS_ACCIONES', count(*) from SILVER.SLV_PRECIOS_ACCIONES union all
        select 'SILVER.SLV_MEMBRESIA_SP500', count(*) from SILVER.SLV_MEMBRESIA_SP500 union all
        select 'GOLD.DIM_ACCION', count(*) from GOLD.DIM_ACCION union all
        select 'GOLD.DIM_FECHA', count(*) from GOLD.DIM_FECHA union all
        select 'GOLD.DIM_MEMBRESIA_SP500', count(*) from GOLD.DIM_MEMBRESIA_SP500 union all
        select 'GOLD.FCT_PRECIOS_DIARIOS', count(*) from GOLD.FCT_PRECIOS_DIARIOS union all
        select 'GOLD.FCT_MERCADO_DIARIO', count(*) from GOLD.FCT_MERCADO_DIARIO union all
        select 'OBT.OBT_ACCION_MES', count(*) from OBT.OBT_ACCION_MES union all
        select 'OBT.OBT_ACCION_DIA', count(*) from OBT.OBT_ACCION_DIA
        order by 1""",
    "ingesta_resumen": """
        select estado, count(distinct ticker) tickers, sum(filas) filas
        from RAW.INGESTA_LOG group by estado order by estado""",
    "obt_resumen": """
        select conjunto, count(*) filas, sum(iff(elegible, 1, 0)) elegibles,
               count(distinct ticker) acciones, min(anio_mes) desde, max(anio_mes) hasta
        from OBT.OBT_ACCION_MES group by conjunto order by conjunto""",
    # Promesas del PSet 1 (etapa Datos): huecos por ticker y universo por fecha.
    "huecos_por_ticker": "select * from CALIDAD.DQ_HUECOS_POR_TICKER order by sin_precios, pct_huecos_miembro desc, ticker",
    "universo_por_mes": """
        select to_char(fecha, 'YYYYMM') anio_mes, count(*) dias,
               round(avg(miembros_composicion), 1) miembros_composicion,
               round(avg(miembros_con_precio), 1) miembros_con_precio,
               round(avg(miembros_nyse), 1) miembros_nyse,
               round(avg(miembros_bolsa_desconocida), 1) miembros_bolsa_desconocida,
               round(avg(pct_cobertura), 2) pct_cobertura
        from CALIDAD.DQ_UNIVERSO_POR_FECHA group by 1 order by 1""",
}

for nombre, sql in CONSULTAS.items():
    cur.execute(sql)
    cols = [c[0].lower() for c in cur.description]
    filas = cur.fetchall()
    with open(SALIDA / f"{nombre}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(filas)
    print(f"{nombre}: {len(filas)} filas -> docs/corrida/{nombre}.csv")
con.close()
