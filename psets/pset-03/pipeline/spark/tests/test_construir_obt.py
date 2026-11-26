"""Pruebas de construir_obt.py con datos armados a mano (no leen data/ ni Snowflake).

Verifican que la OBT sale con el grano accion x mes cerrado, que el objetivo es el retorno
del mes siguiente y que los controles detectan joins que duplican o pierden filas.

Uso, desde psets/pset-03/pipeline/ (requiere Java 17 y el grupo opcional de pyspark):
  uv sync --group dev --group pruebas-locales
  uv run python -m pytest -q spark/tests
Sin pyspark o sin Java las pruebas se saltan (skip), no fallan.
O dentro de la imagen de Spark, sin Java ni pyspark en el host (falla si faltan, no salta):
  docker compose --profile pruebas run --rm --build spark-pruebas
"""
from __future__ import annotations

import datetime as dt
import math
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("pyspark")
if shutil.which("java") is None:
    pytest.skip("Spark necesita Java en el PATH", allow_module_level=True)

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jobs"))
import construir_obt as obt_mod  # noqa: E402

# Dos sesiones por mes; enero de 2024 queda abierto (mes_cerrado = False).
# El corte por defecto es 2023-12-31: noviembre y diciembre son entrenamiento.
SESIONES = [
    (dt.date(2023, 11, 29), True, False), (dt.date(2023, 11, 30), True, True),
    (dt.date(2023, 12, 28), True, False), (dt.date(2023, 12, 29), True, True),
    (dt.date(2024, 1, 2), False, False), (dt.date(2024, 1, 3), False, False),
]
RET = {1: 0.01, 2: -0.02}   # retorno log diario constante por accion
HL = 0.02                    # ln(maximo / minimo) constante en los dias observados
INTRADIA = {1: 0.004, 2: -0.006}


@pytest.fixture(scope="module")
def spark():
    s = (SparkSession.builder.master("local[1]").appName("test-obt")
         .config("spark.sql.shuffle.partitions", "1").config("spark.ui.enabled", "false")
         .getOrCreate())
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()


def tablas(spark, dim_accion_extra=(), fct_extra=(), quitar_mercado_mes=None, ret_futuro=None):
    fechas = [(int(f.strftime("%Y%m%d")), f, f.year, f.month, f.year * 100 + f.month, cerrado, cierre,
               "entrenamiento" if f <= dt.date(2023, 12, 31) else "prueba")
              for f, cerrado, cierre in SESIONES]
    dim_f = spark.createDataFrame(fechas, "fecha_key int, fecha date, anio int, mes int, anio_mes int, "
                                          "mes_cerrado boolean, es_cierre_de_mes boolean, conjunto string")
    # ret_futuro: retorno distinto para las sesiones posteriores a esa fecha (prueba de no fuga).
    def ret(a, f):
        return ret_futuro[1] if ret_futuro and f > ret_futuro[0] else RET[a]
    # Retorno diario = nocturno + intradia, como en Silver.
    fct_filas = [(a, fk, ret(a, f), False, 0.0, INTRADIA[a], ret(a, f) - INTRADIA[a], 100.0, 1000.0, 100.0,
                  False, False, True)
                 for a in RET for fk, f, *_ in fechas]
    fct = spark.createDataFrame(fct_filas + list(fct_extra),
                                "accion_key int, fecha_key int, ret_log_diario double, imputado boolean, "
                                "ret_log_apertura double, ret_log_intradia double, ret_log_nocturno double, "
                                "precio_cierre_ajustado double, volumen double, precio_cierre double, "
                                "es_retorno_extremo boolean, despues_de_tramo_excluido boolean, en_sp500 boolean")
    fct = completar_ohlc(fct)
    acciones = [(1, "AAA", "Acme", "NYSE", True, True, "N"), (2, "BBB", "Beta", "NYSE", True, False, "N")]
    dim_a = spark.createDataFrame(acciones + list(dim_accion_extra),
                                  "accion_key int, ticker string, nombre string, bolsa string, es_nyse boolean, "
                                  "sigue_en_sp500 boolean, codigo_bolsa string")
    mercado = [(fk, 0.001, 0.001, 0.0001, 5.0) for fk, *_ in fechas
               if quitar_mercado_mes is None or fk // 100 != quitar_mercado_mes]
    mkt = spark.createDataFrame(mercado, "fecha_key int, ret_log_sp500 double, ret_log_nyse_composite double, "
                                         "rf_diaria double, tasa_irx_anual_pct double")
    return {"fct_precios_diarios": fct, "dim_accion": dim_a, "dim_fecha": dim_f, "fct_mercado_diario": mkt}


def completar_ohlc(fct):
    """Agrega las columnas OHLC y de diferencias que Gold trae desde Silver."""
    obs = ~F.col("imputado")
    return (fct
            .withColumn("rango_log_hl", F.when(obs, F.lit(HL)))
            .withColumn("rango_pct_hl", F.exp("rango_log_hl") - 1)
            .withColumn("ret_pct_diario", F.exp("ret_log_diario") - 1)
            .withColumn("ret_pct_apertura", F.exp("ret_log_apertura") - 1)
            .withColumn("ret_pct_intradia", F.exp("ret_log_intradia") - 1)
            .withColumn("ret_pct_nocturno", F.exp("ret_log_nocturno") - 1)
            .withColumn("dif_cierre_ajustado", F.col("precio_cierre_ajustado") * (1 - F.exp(-F.col("ret_log_diario"))))
            .withColumn("dif_apertura_ajustada", F.lit(0.0))
            .withColumn("precio_apertura", F.col("precio_cierre") * F.exp(-F.col("ret_log_intradia")))
            .withColumn("precio_apertura_ajustado", F.col("precio_apertura"))
            .withColumn("precio_minimo", F.col("precio_apertura") * 0.99)
            .withColumn("precio_maximo", F.col("precio_minimo") * F.exp(F.lit(HL)))
            .withColumn("precio_minimo_ajustado", F.col("precio_minimo"))
            .withColumn("precio_maximo_ajustado", F.col("precio_maximo")))


def construir(spark, **kw):
    c = obt_mod.Controles()
    return obt_mod.construir(tablas(spark, **kw), c), c


def fallidos(c):
    return [nombre for nombre, _, _, ok in c.filas if not ok]


def test_datos_validos_pasan_todos_los_controles(spark):
    obt, c = construir(spark)
    assert c.todos_ok(), fallidos(c)
    assert len(c.filas) == 15
    # 2 acciones x 2 meses cerrados; enero (abierto) no entra.
    assert obt.count() == 4
    assert obt.select("accion_key", "anio_mes").distinct().count() == 4
    assert len(obt.columns) == 75


def test_objetivo_es_el_retorno_del_mes_siguiente(spark):
    obt, _ = construir(spark)
    filas = {(r.accion_key, r.anio_mes): r for r in obt.collect()}
    nov, dic = filas[(1, 202311)], filas[(1, 202312)]
    assert nov.ret_log_mes == pytest.approx(2 * RET[1])
    assert nov.ret_log_mes_siguiente == pytest.approx(dic.ret_log_mes)
    # El mes siguiente a diciembre (enero) no esta cerrado: sin objetivo.
    assert dic.ret_log_mes_siguiente is None


def test_mercado_del_mes_siguiente_solo_con_meses_cerrados(spark):
    obt, _ = construir(spark)
    filas = {(r.accion_key, r.anio_mes): r for r in obt.collect()}
    nov, dic = filas[(1, 202311)], filas[(1, 202312)]
    # Noviembre: el mes siguiente (diciembre) esta cerrado.
    assert nov.ret_log_sp500_mes_siguiente == pytest.approx(dic.ret_log_sp500_mes)
    assert nov.rf_mes_siguiente == pytest.approx(dic.rf_mes)
    # Diciembre: enero esta abierto, asi que el mercado del mes siguiente queda nulo
    # (antes salia el retorno parcial de enero).
    assert dic.ret_log_sp500_mes_siguiente is None
    assert dic.ret_log_nyse_composite_mes_siguiente is None
    assert dic.rf_mes_siguiente is None
    assert dic.exceso_ret_mes_siguiente is None


def test_variables_de_noviembre_no_usan_datos_posteriores(spark):
    # Sin fuga: si cambian los retornos posteriores al cierre de noviembre, las variables de
    # la fila de noviembre no cambian; solo su objetivo (el mes siguiente).
    columnas_futuras = {"ret_log_mes_siguiente", "exceso_ret_mes_siguiente", "ret_log_sp500_mes_siguiente",
                        "ret_log_nyse_composite_mes_siguiente", "rf_mes_siguiente", "ret_pct_mes_siguiente"}
    base, _ = construir(spark)
    otro, c = construir(spark, ret_futuro=(dt.date(2023, 11, 30), 0.25))
    assert c.todos_ok(), fallidos(c)
    b = {r.accion_key: r.asDict() for r in base.collect() if r.anio_mes == 202311}
    o = {r.accion_key: r.asDict() for r in otro.collect() if r.anio_mes == 202311}
    for accion in b:
        for col, valor in b[accion].items():
            if col in columnas_futuras:
                continue
            assert o[accion][col] == pytest.approx(valor) if isinstance(valor, float) else o[accion][col] == valor, col
        assert o[accion]["ret_log_mes_siguiente"] != pytest.approx(b[accion]["ret_log_mes_siguiente"])


def test_corte_marca_entrenamiento_y_mes_que_cruza(spark):
    obt, _ = construir(spark)
    filas = {(r.accion_key, r.anio_mes): r for r in obt.collect()}
    assert {r.conjunto for r in filas.values()} == {"entrenamiento"}
    assert filas[(1, 202312)].objetivo_cruza_corte is True
    assert filas[(1, 202311)].objetivo_cruza_corte is False


def test_dimension_accion_duplicada_falla(spark):
    _, c = construir(spark, dim_accion_extra=[(1, "AAA", "Acme bis", "NYSE", True, True, "N")])
    assert not c.todos_ok()
    assert any(n.startswith("dim_accion") for n in fallidos(c))
    assert "join OBT x dim_accion conserva filas" in fallidos(c)


def test_hecho_diario_duplicado_falla(spark):
    duplicado = (1, 20231129, RET[1], False, 0.0, RET[1], 0.0, 100.0, 1000.0, 100.0, False, False, True)
    _, c = construir(spark, fct_extra=[duplicado])
    assert any(n.startswith("fct_precios_diarios") for n in fallidos(c))


def test_mes_sin_mercado_falla(spark):
    _, c = construir(spark, quitar_mercado_mes=202312)
    assert "OBT sin meses huerfanos de mercado" in fallidos(c)


def test_porcentaje_y_logaritmo_son_la_misma_variable(spark):
    obt, _ = construir(spark)
    for r in obt.collect():
        for log, pct in [("ret_log_mes", "ret_pct_mes"), ("intradia_log_mes", "intradia_pct_mes"),
                         ("nocturno_log_mes", "nocturno_pct_mes"), ("ret_log_mes_siguiente", "ret_pct_mes_siguiente")]:
            if r[log] is not None:
                assert r[pct] == pytest.approx(math.exp(r[log]) - 1), pct


def test_mes_se_descompone_en_intradia_y_nocturno(spark):
    obt, _ = construir(spark)
    for r in obt.collect():
        assert r.intradia_log_mes + r.nocturno_log_mes == pytest.approx(r.ret_log_mes)
        assert r.intradia_log_mes == pytest.approx(2 * INTRADIA[r.accion_key])


def test_rezagos_solo_con_meses_consecutivos(spark):
    obt, _ = construir(spark)
    filas = {(r.accion_key, r.anio_mes): r for r in obt.collect()}
    nov, dic = filas[(1, 202311)], filas[(1, 202312)]
    assert nov.ret_log_mes_lag1 is None and nov.cambio_rango_log_hl_mes is None
    assert dic.ret_log_mes_lag1 == pytest.approx(nov.ret_log_mes)
    assert dic.ret_pct_mes_lag1 == pytest.approx(math.exp(nov.ret_log_mes) - 1)
    assert dic.ret_log_mes_lag2 is None
    assert dic.cambio_rango_log_hl_mes == pytest.approx(0.0)


def test_volatilidad_por_rango_y_exceso_sobre_mercado(spark):
    obt, _ = construir(spark)
    r = {(x.accion_key, x.anio_mes): x for x in obt.collect()}[(1, 202312)]
    assert r.rango_log_hl_mes == pytest.approx(HL)
    assert r.rango_pct_hl_mes == pytest.approx(math.exp(HL) - 1)
    assert r.vol_parkinson_21d == pytest.approx(math.sqrt(HL ** 2 / (4 * math.log(2)) * 252))
    gk = 0.5 * HL ** 2 - (2 * math.log(2) - 1) * INTRADIA[1] ** 2
    assert r.vol_garman_klass_21d == pytest.approx(math.sqrt(gk * 252))
    assert r.exceso_sp500_log_mes == pytest.approx(r.ret_log_mes - r.ret_log_sp500_mes)
    assert r.volumen_relativo_log_21_252 == pytest.approx(0.0)
    assert r.cambio_rango_log_hl_21_63 == pytest.approx(0.0)


def test_obt_diaria_conserva_filas_y_trae_ohlcv(spark):
    t = tablas(spark)
    c = obt_mod.Controles()
    dia = obt_mod.construir_diaria(t, c)
    assert c.todos_ok(), fallidos(c)
    assert len(c.filas) == 2
    assert dia.count() == t["fct_precios_diarios"].count()
    assert dia.columns == obt_mod.COLUMNAS_DIA
    for col in ["fecha", "precio_apertura", "precio_maximo", "precio_minimo", "precio_cierre",
                "precio_cierre_ajustado", "volumen", "dif_cierre_ajustado", "ret_pct_diario",
                "ret_log_diario", "ret_pct_intradia", "rango_pct_hl", "rango_log_hl"]:
        assert col in dia.columns


def test_elegible_exige_volumen_positivo(spark):
    """H18: una accion sin volumen en 21 dias (precio de relleno) no es elegible."""
    base = dict(en_sp500=True, es_nyse=True, bolsa_desconocida=False, cotizo_al_cierre_de_mes=True,
                obs_252d=252, dias_negociados_mes=21)
    filas = [dict(base, caso="con volumen", volumen_prom_21d=1000.0),
             dict(base, caso="volumen cero", volumen_prom_21d=0.0),
             dict(base, caso="volumen nulo", volumen_prom_21d=None),
             dict(base, caso="historia corta", volumen_prom_21d=1000.0, obs_252d=100)]
    df = spark.createDataFrame(filas, "en_sp500 boolean, es_nyse boolean, bolsa_desconocida boolean, "
                                      "cotizo_al_cierre_de_mes boolean, obs_252d int, dias_negociados_mes int, "
                                      "caso string, volumen_prom_21d double")
    r = {x.caso: x.elegible for x in df.withColumn("elegible", obt_mod.condicion_elegible()).collect()}
    assert r == {"con volumen": True, "volumen cero": False, "volumen nulo": False, "historia corta": False}
