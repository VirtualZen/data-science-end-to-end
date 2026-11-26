"""Construye la One Big Table (OBT) del proyecto a partir de las tablas Gold.

Grano de la OBT: una accion al cierre de un mes cerrado (accion x mes). Es la unidad de
decision del asesor: cada fin de mes elige que acciones comprar para el mes siguiente.
Cada fila trae las variables que el modelo puede usar ese dia (solo informacion pasada),
el objetivo (retorno log del mes siguiente) y los referentes de mercado.

Entradas (Gold): FCT_PRECIOS_DIARIOS, DIM_ACCION, DIM_FECHA, FCT_MERCADO_DIARIO.
Salidas (esquema OBT): OBT_ACCION_MES, OBT_ACCION_DIA (serie diaria OHLCV con sus diferencias,
para los modelos de series: ARIMA, hibridos y fundacionales) y VALIDACION_OBT.

Cada variable de precio va en logaritmo (ln, aditiva en el tiempo) y en porcentaje
(simple: exp(ln) - 1, aditiva entre acciones de un portafolio). Ver docs/series_de_tiempo.md.

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
LN2 = 0.6931471805599453
FECHA_CORTE = os.environ.get("FECHA_CORTE_ENTRENAMIENTO", "2023-12-31")
MES_CORTE = int(FECHA_CORTE[:4]) * 100 + int(FECHA_CORTE[5:7])


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
        "sfDatabase": os.environ.get("SNOWFLAKE_DATABASE", "PORTAFOLIO_P3"),
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

def condicion_elegible():
    """Accion que el asesor podia comprar al cierre del mes.

    Miembro del S&P 500 ese mes, en la NYSE o con bolsa desconocida (ya no cotiza: excluirla
    reintroduce sesgo de supervivencia), cotizo al cierre, historia y meses con negociacion
    suficientes, y volumen promedio de 21 dias positivo (H18: sin volumen el precio es un
    relleno de la fuente, p. ej. AMCR 2014-08 con precio plano y volumen 0 antes de cotizar).
    """
    return (F.col("en_sp500") & (F.col("es_nyse") | F.col("bolsa_desconocida"))
            & F.col("cotizo_al_cierre_de_mes")
            & (F.col("obs_252d") >= MIN_OBS_HISTORIA)
            & (F.col("dias_negociados_mes") >= MIN_DIAS_NEGOCIADOS_MES)
            & F.coalesce(F.col("volumen_prom_21d") > 0, F.lit(False)))


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
    # Mercado del mismo dia (muchos a uno), solo para la beta frente al S&P 500.
    diario = diario.join(mkt.select("fecha_key", "ret_log_sp500"), "fecha_key", "left")
    c.igual("join diario x fct_mercado_diario conserva filas", n_fct, diario.count())
    # Solo las columnas que usan las ventanas y el resumen del mes: el hecho diario trae 33
    # (OHLC sin ajustar, diferencias aritmeticas, etc.) y cada ventana las arrastraria todas,
    # lo que agota la memoria del ejecutor (2 GB, un nucleo). La OBT diaria se arma aparte.
    diario = diario.select(
        "accion_key", "fecha_key", "fecha", "anio", "mes", "anio_mes", "mes_cerrado",
        "es_cierre_de_mes", "conjunto", "en_sp500", "imputado", "despues_de_tramo_excluido",
        "es_retorno_extremo", "precio_cierre", "precio_cierre_ajustado", "volumen",
        "ret_log_diario", "ret_log_apertura", "ret_log_intradia", "ret_log_nocturno",
        "ret_pct_intradia", "ret_pct_nocturno", "rango_log_hl", "rango_pct_hl", "ret_log_sp500")

    # 2. Variables de ventana por accion, con informacion hasta el dia (sin mirar adelante).
    w = Window.partitionBy("accion_key").orderBy("fecha")
    w21, w63, w252 = w.rowsBetween(-20, 0), w.rowsBetween(-62, 0), w.rowsBetween(-251, 0)
    r = F.col("ret_log_diario")
    # La volatilidad se mide solo con dias observados: el forward-fill de Silver deja
    # retorno 0 en los dias imputados y la subestimaria.
    r_obs = F.when(~F.col("imputado"), r)
    obs = ~F.col("imputado")
    # OHLC del dia (solo dias observados; un dia imputado no tiene rango ni intradia propios).
    hl = F.col("rango_log_hl")                       # ln(maximo / minimo)
    co = F.when(obs, F.col("ret_log_intradia"))      # ln(cierre / apertura)
    sp_obs = F.when(r_obs.isNotNull(), F.col("ret_log_sp500"))
    diario = (diario
              .withColumn("rango_log_hl_prom_21d", F.avg(hl).over(w21))
              .withColumn("rango_pct_hl_prom_21d", F.avg("rango_pct_hl").over(w21))
              .withColumn("rango_log_hl_prom_63d", F.avg(hl).over(w63))
              .withColumn("rango_pct_hl_prom_63d", F.avg("rango_pct_hl").over(w63))
              # Volatilidad por rango (Parkinson, 1980) y por OHLC (Garman-Klass, 1980), anualizadas.
              .withColumn("vol_parkinson_21d",
                          F.sqrt(F.avg(hl * hl).over(w21) / F.lit(4 * LN2) * F.lit(252.0)))
              .withColumn("vol_garman_klass_21d",
                          F.sqrt(F.greatest(F.avg(F.lit(0.5) * hl * hl - F.lit(2 * LN2 - 1) * co * co).over(w21),
                                            F.lit(0.0)) * F.lit(252.0)))
              .withColumn("vol_intradia_21d", F.stddev(co).over(w21) * F.sqrt(F.lit(252.0)))
              .withColumn("intradia_pct_prom_21d", F.avg(F.when(obs, F.col("ret_pct_intradia"))).over(w21))
              .withColumn("nocturno_pct_prom_21d", F.avg(F.when(obs, F.col("ret_pct_nocturno"))).over(w21))
              .withColumn("beta_252d", F.covar_samp(r_obs, sp_obs).over(w252) / F.var_samp(sp_obs).over(w252))
              .withColumn("volumen_prom_252d", F.avg("volumen").over(w252)))
    diario = (diario
              .withColumn("vol_21d", F.stddev(r_obs).over(w21) * F.sqrt(F.lit(252.0)))
              .withColumn("vol_63d", F.stddev(r_obs).over(w63) * F.sqrt(F.lit(252.0)))
              .withColumn("vol_apertura_21d",
                          F.stddev(F.when(~F.col("imputado"), F.col("ret_log_apertura"))).over(w21) * F.sqrt(F.lit(252.0)))
              .withColumn("intradia_prom_21d", F.avg(F.when(~F.col("imputado"), F.col("ret_log_intradia"))).over(w21))
              .withColumn("nocturno_prom_21d", F.avg(F.when(~F.col("imputado"), F.col("ret_log_nocturno"))).over(w21))
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
        F.sum(F.col("imputado").cast("int")).alias("dias_imputados_mes"),
        F.max(F.col("despues_de_tramo_excluido").cast("int")).cast("boolean").alias("hubo_tramo_excluido_mes"),
        # Descomposicion del mes: en dias observados con retorno ret_log_diario = nocturno +
        # intradia y en los imputados el retorno es 0, asi que intradia_log_mes +
        # nocturno_log_mes = ret_log_mes. El primer dia de la serie (o tras un tramo excluido)
        # no tiene cierre anterior: no entra en ninguna de las tres sumas.
        F.sum(F.when(r_obs.isNotNull(), F.col("ret_log_intradia"))).alias("intradia_log_mes"),
        F.sum(F.when(r_obs.isNotNull(), F.col("ret_log_nocturno"))).alias("nocturno_log_mes"),
        F.avg(hl).alias("rango_log_hl_mes"),
        F.avg("rango_pct_hl").alias("rango_pct_hl_mes")))

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
                       F.when(F.col("_im_sig") == F.col("_im") + 1, F.lead("ret_log_mes").over(wa))))
    # Rezagos del retorno mensual (los "rezagos" del PSet 1) y cambio del rango frente al mes
    # anterior: solo con meses consecutivos; si hay un mes sin cotizar, quedan nulos.
    for k in (1, 2, 3):
        consecutivo = F.lag("_im", k).over(wa) == F.col("_im") - k
        obt = (obt.withColumn(f"ret_log_mes_lag{k}", F.when(consecutivo, F.lag("ret_log_mes", k).over(wa)))
                  .withColumn(f"ret_pct_mes_lag{k}", F.exp(F.col(f"ret_log_mes_lag{k}")) - 1))
    ant = F.lag("_im", 1).over(wa) == F.col("_im") - 1
    obt = (obt
           .withColumn("cambio_rango_log_hl_mes",
                       F.when(ant, F.col("rango_log_hl_mes") - F.lag("rango_log_hl_mes").over(wa)))
           .withColumn("cambio_rango_pct_hl_mes",
                       F.when(ant, F.col("rango_pct_hl_mes") / F.lag("rango_pct_hl_mes").over(wa) - 1))
           .drop("_im", "_im_sig"))

    # 6. Mercado del mes (muchos a uno por anio_mes).
    #    Los valores "del mes siguiente" solo existen si ese mes ya cerro: con el mes en curso
    #    serian un retorno parcial que cambia con cada ingesta (igual que el objetivo de la accion).
    mercado_diario = mkt.join(dim_f.select("fecha_key", "anio_mes", "mes_cerrado"), "fecha_key", "inner")
    c.igual("join fct_mercado_diario x dim_fecha conserva filas", mkt.count(), mercado_diario.count())
    mercado_mes = (mercado_diario.groupBy("anio_mes").agg(
                       F.sum("ret_log_sp500").alias("ret_log_sp500_mes"),
                       F.sum("ret_log_nyse_composite").alias("ret_log_nyse_composite_mes"),
                       F.sum("rf_diaria").alias("rf_mes"),
                       F.avg("tasa_irx_anual_pct").alias("tasa_irx_prom_mes_pct"),
                       F.min(F.col("mes_cerrado").cast("int")).cast("boolean").alias("_mes_cerrado")))
    # Una fila por mes (~200): una sola particion no cuesta nada. La particion constante
    # solo hace explicito eso y evita el WARN "No Partition Defined" de WindowExec.
    wmk = Window.partitionBy(F.lit(1)).orderBy("anio_mes")
    sig_cerrado = F.coalesce(F.lead("_mes_cerrado").over(wmk), F.lit(False))
    mercado_mes = (mercado_mes
                   .withColumn("_sig_cerrado", sig_cerrado)
                   .withColumn("ret_log_sp500_mes_siguiente",
                               F.when(F.col("_sig_cerrado"), F.lead("ret_log_sp500_mes").over(wmk)))
                   .withColumn("ret_log_nyse_composite_mes_siguiente",
                               F.when(F.col("_sig_cerrado"), F.lead("ret_log_nyse_composite_mes").over(wmk)))
                   .withColumn("rf_mes_siguiente", F.when(F.col("_sig_cerrado"), F.lead("rf_mes").over(wmk))))
    c.igual("mercado del mes siguiente solo con meses cerrados", 0,
            mercado_mes.filter(~F.col("_sig_cerrado") & (F.col("ret_log_sp500_mes_siguiente").isNotNull()
                                                          | F.col("rf_mes_siguiente").isNotNull())).count())
    mercado_mes = mercado_mes.drop("_mes_cerrado", "_sig_cerrado")
    c.llave_unica("mercado mensual", mercado_mes, ["anio_mes"])
    n_antes = obt.count()
    c.igual("OBT sin meses huerfanos de mercado", 0,
            obt.join(mercado_mes.select("anio_mes"), "anio_mes", "left_anti").count())
    obt = obt.join(mercado_mes, "anio_mes", "left")
    c.igual("join OBT x mercado mensual conserva filas", n_antes, obt.count())

    # 7. Atributos de la accion (muchos a uno por accion_key).
    acciones = dim_a.select("accion_key", "ticker", "nombre", "bolsa", "es_nyse", "sigue_en_sp500",
                            F.col("codigo_bolsa").isNull().alias("bolsa_desconocida"))
    n_antes = obt.count()
    obt = obt.join(acciones, "accion_key", "inner")
    c.igual("join OBT x dim_accion conserva filas", n_antes, obt.count())

    # 8. Variables derivadas y elegibilidad.
    #    Bolsa: el listado de bolsas es el de HOY. Una accion que ya no cotiza no tiene bolsa
    #    conocida; excluirla reintroduciria el sesgo de supervivencia, asi que es elegible y
    #    queda marcada (bolsa_desconocida) para revisarla.
    #    objetivo_cruza_corte: el ultimo mes de entrenamiento tiene como objetivo un mes de
    #    prueba; el modelo debe excluir esa fila al entrenar.
    obt = (obt
           .withColumn("momentum_12_1", F.col("ret_log_252d") - F.col("ret_log_21d"))
           .withColumn("ret_pct_mes", F.exp("ret_log_mes") - 1)
           .withColumn("intradia_pct_mes", F.exp("intradia_log_mes") - 1)
           .withColumn("nocturno_pct_mes", F.exp("nocturno_log_mes") - 1)
           .withColumn("cambio_rango_log_hl_21_63", F.log(F.col("rango_log_hl_prom_21d") / F.col("rango_log_hl_prom_63d")))
           .withColumn("cambio_rango_pct_hl_21_63", F.col("rango_pct_hl_prom_21d") / F.col("rango_pct_hl_prom_63d") - 1)
           .withColumn("exceso_sp500_log_mes", F.col("ret_log_mes") - F.col("ret_log_sp500_mes"))
           .withColumn("exceso_sp500_pct_mes", F.exp("ret_log_mes") - F.exp("ret_log_sp500_mes"))
           .withColumn("volumen_relativo_pct_21_252", F.col("volumen_prom_21d") / F.col("volumen_prom_252d") - 1)
           .withColumn("volumen_relativo_log_21_252", F.log(F.col("volumen_prom_21d") / F.col("volumen_prom_252d")))
           .withColumn("ret_pct_mes_siguiente", F.exp("ret_log_mes_siguiente") - 1)
           .withColumn("exceso_ret_mes_siguiente", F.col("ret_log_mes_siguiente") - F.col("rf_mes_siguiente"))
           .withColumn("objetivo_cruza_corte", F.col("anio_mes") == F.lit(MES_CORTE))
           .withColumn("elegible", condicion_elegible()))

    columnas = [
        "accion_key", "ticker", "nombre", "bolsa", "es_nyse", "bolsa_desconocida", "anio_mes", "anio",
        "mes", "conjunto", "objetivo_cruza_corte",
        "fecha_ultima_cotizacion", "cotizo_al_cierre_de_mes", "en_sp500", "sigue_en_sp500", "elegible",
        "precio_cierre_ajustado", "ret_log_mes", "ret_log_21d", "ret_log_252d", "momentum_12_1",
        "vol_21d", "vol_63d", "vol_apertura_21d", "intradia_prom_21d", "nocturno_prom_21d",
        "drawdown_252d", "volumen_prom_21d", "dolares_negociados_prom_21d",
        "obs_252d", "dias_negociados_mes", "dias_imputados_mes", "hubo_tramo_excluido_mes",
        "hubo_retorno_extremo_mes",
        "ret_log_sp500_mes", "ret_log_nyse_composite_mes", "rf_mes", "tasa_irx_prom_mes_pct",
        "ret_log_mes_siguiente", "exceso_ret_mes_siguiente", "ret_log_sp500_mes_siguiente",
        "ret_log_nyse_composite_mes_siguiente", "rf_mes_siguiente",
        # Variables agregadas en el PSet 3 (pset-03/docs/migracion_pipeline.md, F1).
        "ret_pct_mes", "ret_log_mes_lag1", "ret_pct_mes_lag1", "ret_log_mes_lag2", "ret_pct_mes_lag2",
        "ret_log_mes_lag3", "ret_pct_mes_lag3",
        "intradia_log_mes", "intradia_pct_mes", "nocturno_log_mes", "nocturno_pct_mes",
        "intradia_pct_prom_21d", "nocturno_pct_prom_21d", "vol_intradia_21d",
        "rango_log_hl_mes", "rango_pct_hl_mes", "cambio_rango_log_hl_mes", "cambio_rango_pct_hl_mes",
        "rango_log_hl_prom_21d", "rango_pct_hl_prom_21d", "rango_log_hl_prom_63d", "rango_pct_hl_prom_63d",
        "cambio_rango_log_hl_21_63", "cambio_rango_pct_hl_21_63",
        "vol_parkinson_21d", "vol_garman_klass_21d", "beta_252d",
        "exceso_sp500_log_mes", "exceso_sp500_pct_mes",
        "volumen_relativo_log_21_252", "volumen_relativo_pct_21_252",
        "ret_pct_mes_siguiente",
    ]
    obt = obt.select(*columnas)
    c.llave_unica("OBT (grano accion x mes)", obt, ["accion_key", "anio_mes"])
    c.igual("OBT tiene una fila por accion y mes cerrado", n_base, obt.count())
    return obt


COLUMNAS_DIA = [
    "accion_key", "ticker", "fecha", "anio_mes", "conjunto", "mes_cerrado", "en_sp500", "imputado",
    "despues_de_tramo_excluido", "es_retorno_extremo",
    "precio_apertura", "precio_maximo", "precio_minimo", "precio_cierre",
    "precio_apertura_ajustado", "precio_maximo_ajustado", "precio_minimo_ajustado", "precio_cierre_ajustado",
    "volumen",
    "dif_cierre_ajustado", "ret_pct_diario", "ret_log_diario",
    "dif_apertura_ajustada", "ret_pct_apertura", "ret_log_apertura",
    "ret_pct_intradia", "ret_log_intradia", "ret_pct_nocturno", "ret_log_nocturno",
    "rango_pct_hl", "rango_log_hl", "ret_log_sp500", "rf_diaria",
]


def construir_diaria(t: dict[str, DataFrame], c: Controles) -> DataFrame:
    """Serie diaria por accion (grano accion x dia bursatil) para los modelos de series.

    Trae todos los dias, tambien los posteriores a cada cierre de mes: el modelo debe cortar
    la serie en la fecha de origen (cierre del mes) antes de pronosticar."""
    fct, dim_a, dim_f, mkt = t["fct_precios_diarios"], t["dim_accion"], t["dim_fecha"], t["fct_mercado_diario"]
    n_fct = fct.count()
    dia = (fct.join(dim_f.select("fecha_key", "fecha", "anio_mes", "conjunto", "mes_cerrado"), "fecha_key", "inner")
              .join(dim_a.select("accion_key", "ticker"), "accion_key", "inner")
              .join(mkt.select("fecha_key", "ret_log_sp500", "rf_diaria"), "fecha_key", "left")
              .select(*COLUMNAS_DIA))
    c.igual("OBT_ACCION_DIA conserva las filas de fct_precios_diarios", n_fct, dia.count())
    c.llave_unica("OBT_ACCION_DIA (grano accion x dia)", dia, ["accion_key", "fecha"])
    return dia


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modo", choices=["snowflake", "local"], default="snowflake")
    p.add_argument("--entrada", help="carpeta con Parquet de Gold (modo local)")
    p.add_argument("--salida", help="carpeta de salida (modo local)")
    a = p.parse_args()
    if a.modo == "local" and not (a.entrada and a.salida):
        p.error("--modo local necesita --entrada y --salida")

    spark = SparkSession.builder.appName("pset3-obt-accion-mes").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    controles = Controles()
    gold = leer_gold(spark, a.modo, a.entrada)
    obt = construir(gold, controles).cache()
    dia = construir_diaria(gold, controles)

    if not controles.todos_ok():
        escribir(controles.df(spark), "VALIDACION_OBT", a.modo, a.salida)
        spark.stop()
        sys.exit("Un control fallo: no se escribe la OBT (la version anterior queda intacta).")

    escribir(obt, "OBT_ACCION_MES", a.modo, a.salida)
    escribir(dia, "OBT_ACCION_DIA", a.modo, a.salida)
    escribir(controles.df(spark), "VALIDACION_OBT", a.modo, a.salida)
    print(f"OBT_ACCION_MES escrita: {obt.count()} filas, "
          f"{obt.filter('elegible').count()} elegibles, {len(obt.columns)} columnas")
    spark.stop()


if __name__ == "__main__":
    main()
