"""Descarga de Yahoo Finance (biblioteca yfinance) los precios diarios del universo, con
cache, y los guarda en una base DuckDB aparte para analizarlos antes de Snowflake.

Requiere haber corrido antes:
  uv run python analisis/datos/construir_listas.py        (universo)
  uv run python analisis/datos/equivalencias_tickers.py   (simbolos viejos -> simbolo actual de Yahoo)
Debe correr en una maquina con acceso a Yahoo (tu computador o el contenedor de ingesta).

Base: analisis/datos/yahoo.duckdb
  cache_yahoo_precios    una fila por (ticker_yahoo, fecha): lo ultimo que devolvio Yahoo
  cache_yahoo_consultas  bitacora de cada consulta: rango pedido, filas, estado, version
  ticker_a_yahoo         simbolo de la composicion -> simbolo a pedir a Yahoo
  yahoo_info             bolsa y nombre segun Yahoo (solo con --info)
  yahoo_precios_diarios  vista de analisis sobre el cache

Como funciona el cache:
  - Antes de pedir un simbolo se mira que rango ya esta guardado. Solo se pide lo que
    falta al inicio y los ultimos DIAS_REVISION dias (Yahoo corrige cierres y ajustes).
  - Un simbolo que Yahoo devolvio vacio (SIN_DATOS) no se vuelve a pedir durante
    DIAS_SIN_DATOS dias: casi siempre es una accion que ya no cotiza.
  - --forzar ignora el cache y vuelve a pedir todo.

Uso, desde psets/pset-03/ (uv sync --group analisis):
  uv run python analisis/datos/traer_yahoo.py --universo nucleo    # 193 acciones con historia completa
  uv run python analisis/datos/traer_yahoo.py                      # universo completo (~800 simbolos)
  uv run python analisis/datos/traer_yahoo.py --info               # ademas, bolsa segun Yahoo (lento)
"""

import argparse
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pandas as pd

AQUI = Path(__file__).parent
INDICES = ["^GSPC", "^NYA", "^IRX"]
TAMANO_GRUPO = 50
DIAS_REVISION = 10
DIAS_SIN_DATOS = 30

CONSULTAS = {
    "todo": "select ticker from universo_comparado",
    "actual": "select ticker from universo_comparado where en_sp500_actual",
    "historico": "select ticker from universo_comparado where en_sp500_historico",
    "nucleo": "select ticker from subconjunto_nucleo",
}

ESQUEMA = """
create table if not exists cache_yahoo_precios (
    ticker_yahoo varchar, fecha date, open double, high double, low double, close double,
    adj_close double, volume double, descargado_en timestamp, lote varchar,
    primary key (ticker_yahoo, fecha));
create table if not exists cache_yahoo_consultas (
    ticker_yahoo varchar, desde date, hasta date, filas integer, estado varchar,
    detalle varchar, lote varchar, version_yfinance varchar, descargado_en timestamp);
create or replace view yahoo_precios_diarios as
    select ticker_yahoo as ticker, fecha, open, high, low, close, adj_close, volume, descargado_en
    from cache_yahoo_precios;
"""


def mapa_tickers(universo: str) -> pd.DataFrame:
    """Simbolo de la composicion -> simbolo de Yahoo, con la tabla de equivalencias."""
    with duckdb.connect(str(AQUI / "universo.duckdb"), read_only=True) as u:
        tick = u.execute(CONSULTAS[universo]).df()
        hay_eq = u.execute("select count(*) from information_schema.tables "
                           "where table_name = 'equivalencias_tickers'").fetchone()[0]
        eq = (u.execute("""select ticker_antiguo, ticker_yahoo from equivalencias_tickers
                           where ticker_antiguo is not null and estado not like 'no es cambio%'""").df()
              if hay_eq else pd.DataFrame(columns=["ticker_antiguo", "ticker_yahoo"]))
    m = tick.merge(eq, left_on="ticker", right_on="ticker_antiguo", how="left")
    m["ticker_yahoo"] = m["ticker_yahoo"].fillna(m["ticker"])
    m = m[["ticker", "ticker_yahoo"]].rename(columns={"ticker": "ticker_composicion"})
    idx = pd.DataFrame({"ticker_composicion": INDICES, "ticker_yahoo": INDICES})
    return pd.concat([m, idx]).drop_duplicates()


def rangos_pendientes(con, tickers, desde: date, hasta: date, forzar: bool):
    """Devuelve {(desde, hasta): [tickers]} con lo que falta pedir a Yahoo."""
    hoy = datetime.now(timezone.utc).replace(tzinfo=None)
    cob = con.execute("""
        select ticker_yahoo,
               min(desde) filter (where estado = 'OK') as desde_ok,
               max(hasta) filter (where estado = 'OK') as hasta_ok,
               max(descargado_en) filter (where estado = 'SIN_DATOS') as ultimo_sin_datos,
               count(*) filter (where estado = 'OK') as consultas_ok
        from cache_yahoo_consultas group by 1""").df().set_index("ticker_yahoo")
    pendientes: dict[tuple, list] = {}
    for t in tickers:
        if forzar or t not in cob.index:
            pendientes.setdefault((desde, hasta), []).append(t)
            continue
        c = cob.loc[t]
        if c["consultas_ok"] == 0:
            if pd.notna(c["ultimo_sin_datos"]) and (hoy - c["ultimo_sin_datos"]).days < DIAS_SIN_DATOS:
                continue  # ya se sabe que Yahoo no lo tiene
            pendientes.setdefault((desde, hasta), []).append(t)
            continue
        desde_ok, hasta_ok = pd.Timestamp(c["desde_ok"]).date(), pd.Timestamp(c["hasta_ok"]).date()
        if desde < desde_ok:
            pendientes.setdefault((desde, desde_ok), []).append(t)
        inicio_cola = max(desde, hasta_ok - timedelta(days=DIAS_REVISION))
        if hasta > inicio_cola:
            pendientes.setdefault((inicio_cola, hasta), []).append(t)
    return pendientes


def descargar(yf, tickers, desde: date, hasta: date):
    df = yf.download(tickers, start=desde.isoformat(), end=(hasta + timedelta(days=1)).isoformat(),
                     interval="1d", auto_adjust=False, actions=False, group_by="ticker",
                     threads=True, progress=False)
    filas, log = [], []
    for t in tickers:
        try:
            sub = df[t] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            sub = pd.DataFrame()
        sub = sub.dropna(how="all")
        if sub.empty:
            log.append((t, 0, "SIN_DATOS", "Yahoo no devolvio filas"))
            continue
        sub = sub.reset_index().rename(columns=lambda c: str(c).lower().replace(" ", "_"))
        sub["ticker_yahoo"], sub["fecha"] = t, pd.to_datetime(sub["date"]).dt.date
        filas.append(sub[["ticker_yahoo", "fecha", "open", "high", "low", "close", "adj_close", "volume"]])
        log.append((t, len(sub), "OK", ""))
    return (pd.concat(filas, ignore_index=True) if filas else pd.DataFrame()), log


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--universo", choices=list(CONSULTAS), default="todo")
    p.add_argument("--desde", type=date.fromisoformat, default=date(2010, 1, 1))
    p.add_argument("--hasta", type=date.fromisoformat, default=date.today())
    p.add_argument("--forzar", action="store_true", help="ignorar el cache")
    p.add_argument("--info", action="store_true", help="consultar bolsa y nombre en Yahoo")
    p.add_argument("--base", default=str(AQUI / "yahoo.duckdb"))
    a = p.parse_args()

    import yfinance as yf

    # Verificacion de red: si ^GSPC no devuelve nada, Yahoo no es alcanzable desde esta
    # red (proxy, bloqueo). Abortar sin escribir en el cache, para no registrar SIN_DATOS
    # falsos que impedirian reintentar por DIAS_SIN_DATOS dias.
    try:
        canario = yf.download("^GSPC", period="5d", interval="1d", progress=False)
    except Exception:
        canario = None
    if canario is None or canario.dropna(how="all").empty:
        raise SystemExit("Yahoo Finance no responde desde esta red (la prueba con ^GSPC "
                         "volvio vacia). No se escribio nada en el cache. Corre este "
                         "script en una red con acceso a query1/query2.finance.yahoo.com.")

    mapa = mapa_tickers(a.universo)
    tickers = sorted(mapa["ticker_yahoo"].unique())
    lote = f"{a.universo}-{datetime.now():%Y%m%d%H%M%S}"
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)

    con = duckdb.connect(a.base)
    con.execute(ESQUEMA)
    con.register("m", mapa)
    con.execute("create or replace table ticker_a_yahoo as select * from m")
    con.unregister("m")

    pendientes = rangos_pendientes(con, tickers, a.desde, a.hasta, a.forzar)
    total = sum(len(v) for v in pendientes.values())
    print(f"{len(tickers)} simbolos en el universo; {total} pedidos pendientes (el resto sale del cache)")

    for (desde, hasta), lista in pendientes.items():
        for i in range(0, len(lista), TAMANO_GRUPO):
            grupo = lista[i:i + TAMANO_GRUPO]
            for intento in range(1, 4):
                try:
                    precios, log = descargar(yf, grupo, desde, hasta)
                    break
                except Exception as e:
                    print(f"  fallo {desde}..{hasta} grupo {i // TAMANO_GRUPO + 1} (intento {intento}): {e}")
                    time.sleep(20 * intento)
            else:
                precios, log = pd.DataFrame(), [(t, 0, "ERROR", "reintentos agotados") for t in grupo]
            if not precios.empty:
                precios["descargado_en"], precios["lote"] = ahora, lote
                con.register("p", precios)
                con.execute("insert or replace into cache_yahoo_precios select * from p")
                con.unregister("p")
            lg = pd.DataFrame(log, columns=["ticker_yahoo", "filas", "estado", "detalle"])
            lg = lg.assign(desde=desde, hasta=hasta, lote=lote, version_yfinance=yf.__version__,
                           descargado_en=ahora)
            con.register("l", lg)
            con.execute("""insert into cache_yahoo_consultas select ticker_yahoo, desde, hasta, filas,
                           estado, detalle, lote, version_yfinance, descargado_en from l""")
            con.unregister("l")
            print(f"  {desde}..{hasta}: {sum(x[2] == 'OK' for x in log)}/{len(grupo)} con datos")
            time.sleep(2)

    if a.info:
        filas = []
        for t in tickers:
            try:
                inf = yf.Ticker(t).info
                filas.append((t, inf.get("exchange"), inf.get("quoteType"), inf.get("longName"), inf.get("sector")))
            except Exception as e:
                filas.append((t, None, None, None, f"error: {e}"))
            time.sleep(0.5)
        con.execute("create or replace table yahoo_info (ticker_yahoo varchar, exchange varchar, "
                    "quote_type varchar, long_name varchar, sector varchar)")
        con.executemany("insert into yahoo_info values (?, ?, ?, ?, ?)", filas)

    print(con.execute("""select estado, count(distinct ticker_yahoo) from cache_yahoo_consultas
                         group by 1 order by 1""").fetchall())
    print("filas en cache:", con.execute("select count(*) from cache_yahoo_precios").fetchone()[0])
    con.close()


if __name__ == "__main__":
    main()
