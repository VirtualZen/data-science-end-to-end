"""Construye la One Big Table (OBT) del proyecto a partir de las tablas Gold.

Grano de la OBT: una accion al cierre de un mes cerrado (accion x mes). Es la unidad de
decision del asesor: cada fin de mes elige que acciones comprar para el mes siguiente.
Cada fila trae las variables que el modelo puede usar ese dia (solo informacion pasada),
el objetivo (retorno log del mes siguiente) y los referentes de mercado.

Entradas (Gold): FCT_PRECIOS_DIARIOS, DIM_ACCION, DIM_FECHA, FCT_MERCADO_DIARIO.
Salidas (esquema OBT): OBT_ACCION_MES y VALIDACION_OBT (resultado de cada control).

Uso:
  spark-submit construir_obt.py --modo snowflake
      Lee Gold y escribe en OBT de Snowflake (credenciales en variables SNOWFLAKE_*).
  spark-submit construir_obt.py --modo local --entrada DIR --salida DIR
      Lee y escribe Parquet (solo para probar el codigo, ver pruebas_locales/).

Si un control falla (filas duplicadas o perdidas en un join), el job termina con error
antes de escribir y la OBT anterior queda intacta.
"""

from __future__ import annotations

import argparse
import os
import sys

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

FUENTE_SNOWFLAKE = "net.snowflake.spark.snowflake"
TABLAS_GOLD = ["FCT_PRECIOS_DIARIOS", "DIM_ACCION", "DIM_FECHA", "FCT_MERCADO_DIARIO"]
MIN_OBS_HISTORIA = 200        # dias con retorno en los ultimos 252 para ser elegible
MIN_DIAS_NEGOCIADOS_MES = 15


# ---------------------------------------------------------------------------
# Lectura y escritura
# ---------------------------------------------------------------------------

def opciones_snowflake(esquema: str) -> dict:
    llave = os.environ.get("SNOWFLAKE_PRIVATE_KEY", "").strip()
    if not llave:
        sys.exit("Falta SNOWFLAKE_PRIVATE_KEY (corre scripts/preparar_env.sh).")
    return {
        "sfURL": f"{os.environ['SNOWFLAKE_ACCOUNT']}.snowflakecomputing.com",
        "sfUser": os.environ["SNOWFLAKE_USER"],
        "pem_private_key": llave,
        "sfRole": os.environ.get("SNOWFLAKE_ROLE", "PSET2_ROL"),
        "sfWarehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "PSET2_WH"),
        "sfDatabase": os.environ.get("SNOWFLAKE_DATABASE", "PORTAFOLIO"),
        "sfSchema": esquema,
    }


def minusculas(df: DataFrame) -> DataFrame:
    return df.toDF(*[c.lower() for c in df.columns])


def leer_gold(spark: SparkSession, modo: str, entrada: str | None) -> dict[str, DataFrame]:
    tablas = {}
    for t in TABLAS_GOLD:
        if modo == "snowflake":
            df = (spark.read.format(FUENTE_SNOWFLAKE).options(**opciones_snowflake("GOLD"))
                  .option("dbtable", t).load())
        else:
            df = spark.read.parquet(os.path.join(entrada, t.lower()))
        tablas[t.lower()] = minusculas(df)
    return tablas


def escribir(df: DataFrame, tabla: str, modo: str, salida: str | None) -> None:
    if modo == "snowflake":
        (df.toDF(*[c.upper() for c in df.columns]).write.format(FUENTE_SNOWFLAKE)
         .options(**opciones_snowflake("OBT")).option("dbtable", tabla).mode("overwrite").save())
    else:
        df.write.mode("overwrite").parquet(os.path.join(salida, tabla.lower()))


# ---------------------------------------------------------------------------
# Controles de los joins
# ---------------------------------------------------------------------------

class Controles:
    def __init__(self) -> None:
        self.filas: list[tuple[str, int, int, bool]] = []

    def igual(self, nombre: str, esperado: int, obtenido: int) -> None:
        ok = esperado == obtenido
        self.filas.append((nombre, esperado, obtenido, ok))
        print(f"[{'OK' if ok else 'FALLA'}] {nombre}: esperado={esperado} obtenido={obtenido}")

    def llave_unica(self, nombre: str, df: DataFrame, columnas: list[str]) -> None:
        total = df.count()
        distintos = df.select(*columnas).distinct().count()
        self.igual(f"{nombre}: filas = combinaciones distintas de {columnas}", total, distintos)

    def df(self, spark: SparkSession) -> DataFrame:
        return spark.createDataFrame(self.filas, "control string, esperado long, obtenido long, ok boolean") \
                    .withColumn("ejecutado_en", F.current_timestamp())

    def todos_ok(self) -> bool:
        return all(ok for *_, ok in self.filas)


# ---------------------------------------------------------------------------
# Construccion
# ---------------------------------------------------------------------------

def construir(t: dict[str, DataFrame], c: Controles) -> DataFrame:
    fct, dim_a, dim_f, mkt = t["fct_precios_diarios"], t["dim_accion"], t["dim_fecha"], t["fct_mercado_diario"]

    # Las dimensiones deben tener una fila por llave, si no los joins duplican filas.
    c.llave_unica("dim_accion", dim_a, ["accion_key"])
    c.llave_unica("dim_fecha", dim_f, ["fecha_key"])
    c.llave_unica("fct_mercado_diario", mkt, ["fecha_key"])
    c.llave_unica("fct_precios_diarios", fct, ["accion_key", "fecha_key"])

    # 1. Hecho diario + calendario (muchos a uno): no debe cambiar el numero de filas.
    n_fct = fct.count()
    fechas = dim_f.select("fecha_key", "fecha", "anio", "mes", "anio_mes", "mes_cerrado",
                          "es_cierre_de_mes", "conjunto")
    diario = fct.join(fechas, "fecha_key", "inner")
    c.igual("join fct_precios_diarios x dim_fecha conserva filas", n_fct, diario.count())

    # 2. Variables de ventana por accion, con informacion hasta el dia (sin mirar adelante).
    w = Window.partitionBy("accion_key").orderBy("fecha")
    w21, w63, w252 = w.rowsBetween(-20, 0), w.rowsBetween(-62, 0), w.rowsBetween(-251, 0)
    r = F.col("ret_log_diario")
    diario = (diario
              .withColumn("vol_21d", F.stddev(r).over(w21) * F.sqrt(F.lit(252.0)))
              .withColumn("vol_63d", F.stddev(r).over(w63) * F.sqrt(F.lit(252.0)))
              .withColumn("ret_log_21d", F.sum(r).over(w21))
              .withColumn("ret_log_252d", F.sum(r).over(w252))
              .withColumn("obs_252d", F.count(r).over(w252))
              .withColumn("drawdown_252d",
                          F.col("precio_cierre_ajustado") / F.max("precio_cierre_ajustado").over(w252) - 1)
              .withColumn("volumen_prom_21d", F.avg("volumen").over(w21))
              .withColumn("dolares_negociados_prom_21d",
                          F.avg(F.col("volumen") * F.col("precio_cierre")).over(w21)))

    # 3. Resumen del mes por accion.
    mes_accion = (diario.groupBy("accion_key", "anio_mes").agg(
        F.sum(r).alias("ret_log_mes"),
        F.count("*").alias("dias_negociados_mes"),
        F.max(F.col("es_retorno_extremo").cast("int")).cast("boolean").alias("hubo_retorno_extremo_mes"),
        F.sum(F.col("hay_hueco_previo").cast("int")).alias("huecos_en_mes")))

    # 4. Una fila por accion y mes cerrado: el ultimo dia que la accion cotizo en el mes.
    wm = Window.partitionBy("accion_key", "anio_mes").orderBy(F.col("fecha").desc())
    cierre = (diario.filter("mes_cerrado")
              .withColumn("_n", F.row_number().over(wm)).filter("_n = 1").drop("_n")
              .withColumnRenamed("es_cierre_de_mes", "cotizo_al_cierre_de_mes")
              .withColumnRenamed("fecha", "fecha_ultima_cotizacion"))
    n_base = cierre.count()

    obt = cierre.join(mes_accion, ["accion_key", "anio_mes"], "inner")
    c.igual("join cierre x resumen del mes (uno a uno) conserva filas", n_base, obt.count())

    # 5. Objetivo: retorno log del mes siguiente (~21 dias habiles, igual al rebalanceo).
    #    Solo si el mes siguiente es el consecutivo; si la accion no cotizo, queda nulo.
    indice_mes = (F.floor(F.col("anio_mes") / 100) * 12 + F.col("anio_mes") % 100).cast("int")
    wa = Window.partitionBy("accion_key").orderBy("anio_mes")
    obt = (obt.withColumn("_im", indice_mes)
           .withColumn("_im_sig", F.lead("_im").over(wa))
           .withColumn("ret_log_mes_siguiente",
                       F.when(F.col("_im_sig") == F.col("_im") + 1, F.lead("ret_log_mes").over(wa)))
           .drop("_im", "_im_sig"))

    # 6. Mercado del mes (muchos a uno por anio_mes).
    mercado_mes = (mkt.join(dim_f.select("fecha_key", "anio_mes"), "fecha_key", "inner")
                   .groupBy("anio_mes").agg(
                       F.sum("ret_log_sp500").alias("ret_log_sp500_mes"),
                       F.sum("ret_log_nyse_composite").alias("ret_log_nyse_composite_mes"),
                       F.sum("rf_diaria").alias("rf_mes"),
                       F.avg("tasa_irx_anual_pct").alias("tasa_irx_prom_mes_pct")))
    wmk = Window.orderBy("anio_mes")
    mercado_mes = (mercado_mes
                   .withColumn("ret_log_sp500_mes_siguiente", F.lead("ret_log_sp500_mes").over(wmk))
                   .withColumn("ret_log_nyse_composite_mes_siguiente", F.lead("ret_log_nyse_composite_mes").over(wmk))
                   .withColumn("rf_mes_siguiente", F.lead("rf_mes").over(wmk)))
    c.llave_unica("mercado mensual", mercado_mes, ["anio_mes"])
    n_antes = obt.count()
    obt = obt.join(mercado_mes, "anio_mes", "left")
    c.igual("join OBT x mercado mensual conserva filas", n_antes, obt.count())

    # 7. Atributos de la accion (muchos a uno por accion_key).
    acciones = dim_a.select("accion_key", "ticker", "nombre", "bolsa", "es_nyse", "sigue_en_sp500")
    n_antes = obt.count()
    obt = obt.join(acciones, "accion_key", "inner")
    c.igual("join OBT x dim_accion conserva filas", n_antes, obt.count())

    # 8. Variables derivadas y elegibilidad.
    obt = (obt
           .withColumn("momentum_12_1", F.col("ret_log_252d") - F.col("ret_log_21d"))
           .withColumn("exceso_ret_mes_siguiente", F.col("ret_log_mes_siguiente") - F.col("rf_mes_siguiente"))
           .withColumn("elegible",
                       F.col("en_sp500") & F.col("es_nyse") & F.col("cotizo_al_cierre_de_mes")
                       & (F.col("obs_252d") >= MIN_OBS_HISTORIA)
                       & (F.col("dias_negociados_mes") >= MIN_DIAS_NEGOCIADOS_MES)))

    columnas = [
        "accion_key", "ticker", "nombre", "bolsa", "es_nyse", "anio_mes", "anio", "mes", "conjunto",
        "fecha_ultima_cotizacion", "cotizo_al_cierre_de_mes", "en_sp500", "sigue_en_sp500", "elegible",
        "precio_cierre_ajustado", "ret_log_mes", "ret_log_21d", "ret_log_252d", "momentum_12_1",
        "vol_21d", "vol_63d", "drawdown_252d", "volumen_prom_21d", "dolares_negociados_prom_21d",
        "obs_252d", "dias_negociados_mes", "huecos_en_mes", "hubo_retorno_extremo_mes",
        "ret_log_sp500_mes", "ret_log_nyse_composite_mes", "rf_mes", "tasa_irx_prom_mes_pct",
        "ret_log_mes_siguiente", "exceso_ret_mes_siguiente", "ret_log_sp500_mes_siguiente",
        "ret_log_nyse_composite_mes_siguiente", "rf_mes_siguiente",
    ]
    obt = obt.select(*columnas)
    c.llave_unica("OBT (grano accion x mes)", obt, ["accion_key", "anio_mes"])
    c.igual("OBT tiene una fila por accion y mes cerrado", n_base, obt.count())
    return obt


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modo", choices=["snowflake", "local"], default="snowflake")
    p.add_argument("--entrada", help="carpeta con Parquet de Gold (modo local)")
    p.add_argument("--salida", help="carpeta de salida (modo local)")
    a = p.parse_args()
    if a.modo == "local" and not (a.entrada and a.salida):
        p.error("--modo local necesita --entrada y --salida")

    spark = SparkSession.builder.appName("pset2-obt-accion-mes").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    controles = Controles()
    obt = construir(leer_gold(spark, a.modo, a.entrada), controles).cache()

    if not controles.todos_ok():
        escribir(controles.df(spark), "VALIDACION_OBT", a.modo, a.salida)
        spark.stop()
        sys.exit("Un control fallo: no se escribe la OBT (la version anterior queda intacta).")

    escribir(obt, "OBT_ACCION_MES", a.modo, a.salida)
    escribir(controles.df(spark), "VALIDACION_OBT", a.modo, a.salida)
    print(f"OBT_ACCION_MES escrita: {obt.count()} filas, "
          f"{obt.filter('elegible').count()} elegibles, {len(obt.columns)} columnas")
    spark.stop()


if __name__ == "__main__":
    main()
