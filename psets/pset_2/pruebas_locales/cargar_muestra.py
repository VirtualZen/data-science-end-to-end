"""Carga una muestra pequena en DuckDB con las mismas tablas RAW que usa Snowflake, para
probar dbt (target local) y el job de Spark (--modo local) sin cuenta de Snowflake.

NO son los datos del proyecto y no sirven para el memo. Solo verifican que el codigo
corre y que los tests detectan lo que deben. Lo que se carga:
  - Composicion historica del S&P 500 completa (la misma fuente real del pipeline).
  - Precios diarios reales de ORCL, UBER y VST (acciones de la NYSE que estan en el
    S&P 500) de un espejo publico de Yahoo en GitHub (yennanliu/finance_data), que no
    trae cierre ajustado: aqui ADJ_CLOSE = CLOSE.
  - Como esta muestra no tiene ^GSPC ni ^NYA, se usan VTI y QQQ como SUSTITUTOS de esos
    indices solo para tener calendario y retornos de mercado. No hay ^IRX: la prueba
    corre con exigir_tasa_libre_riesgo = false.
  - Las mismas fechas recientes se cargan dos veces (como hace la ventana de revision
    del flow diario) para probar que Bronze elimina duplicados.

Uso, desde psets/pset_2/:   python pruebas_locales/cargar_muestra.py
"""

import io
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd

AQUI = Path(__file__).parent
RUTA_DB = AQUI / "portafolio_local.duckdb"
ESPEJO = "https://raw.githubusercontent.com/yennanliu/finance_data/main/data/prices/{}.csv"
COMPOSICION = ("https://raw.githubusercontent.com/hanshof/sp500_constituents/main/"
               "sp_500_historical_components.csv")
ACCIONES = {"orcl": "ORCL", "uber": "UBER", "vst": "VST"}
SUSTITUTOS = {"vti": "^GSPC", "qqq": "^NYA"}


def leer(url: str) -> pd.DataFrame:
    with urllib.request.urlopen(url, timeout=60) as r:
        return pd.read_csv(io.BytesIO(r.read()))


def precios(archivo: str, ticker: str, fuente: str) -> pd.DataFrame:
    df = leer(ESPEJO.format(archivo))
    return pd.DataFrame({
        "TICKER": ticker, "FECHA": pd.to_datetime(df["date"]).dt.date,
        "OPEN": df["open"], "HIGH": df["high"], "LOW": df["low"], "CLOSE": df["close"],
        "ADJ_CLOSE": df["close"], "VOLUME": df["volume"].astype(float), "FUENTE": fuente,
    })


def main() -> None:
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    partes = [precios(a, t, "prueba_local: espejo yennanliu/finance_data") for a, t in ACCIONES.items()]
    partes += [precios(a, t, f"prueba_local: {a.upper()} como sustituto de {t}") for a, t in SUSTITUTOS.items()]
    p = pd.concat(partes, ignore_index=True)
    p["LOTE_ID"], p["INGESTA_TS"] = "historico-prueba", t0

    # Segunda carga de los ultimos 30 dias (ventana de revision): mismas claves, otra hora.
    corte = p["FECHA"].max() - timedelta(days=30)
    rep = p[p["FECHA"] >= corte].copy()
    rep["LOTE_ID"], rep["INGESTA_TS"] = "diario-prueba", t0 + timedelta(days=1)
    p = pd.concat([p, rep], ignore_index=True)

    comp = leer(COMPOSICION).rename(columns={"date": "FECHA", "tickers": "TICKERS"})
    comp["FECHA"] = pd.to_datetime(comp["FECHA"]).dt.date
    comp["FUENTE"], comp["LOTE_ID"], comp["INGESTA_TS"] = COMPOSICION, "historico-prueba", t0

    # Bolsa de las tres acciones de la muestra (las tres cotizan en la NYSE).
    lst = pd.DataFrame({
        "SIMBOLO": ["ORCL", "UBER", "VST"],
        "NOMBRE": ["Oracle Corporation", "Uber Technologies, Inc.", "Vistra Corp."],
        "CODIGO_BOLSA": ["N", "N", "N"], "ES_ETF": "N", "ES_PRUEBA": "N",
        "ARCHIVO": "otherlisted.txt", "FUENTE": "prueba_local", "LOTE_ID": "historico-prueba",
        "INGESTA_TS": t0,
    })

    RUTA_DB.unlink(missing_ok=True)
    con = duckdb.connect(str(RUTA_DB))
    con.execute("create schema raw")
    for nombre, df in {"precios_diarios": p, "composicion_sp500": comp, "listados_bolsa": lst}.items():
        con.register("df", df)
        con.execute(f"create table raw.{nombre} as select * from df")
        con.unregister("df")
    con.execute("""create table raw.ingesta_log (LOTE_ID varchar, TICKER varchar, FECHA_DESDE date,
                   FECHA_HASTA date, FILAS integer, ESTADO varchar, DETALLE varchar, INGESTA_TS timestamp)""")
    for t in ["precios_diarios", "composicion_sp500", "listados_bolsa"]:
        print(t, con.execute(f"select count(*) from raw.{t}").fetchone()[0], "filas")
    con.close()
    print("Muestra cargada en", RUTA_DB)


if __name__ == "__main__":
    main()
