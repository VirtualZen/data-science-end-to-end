"""Extrae los datos del proyecto y los carga, sin transformar, en el esquema RAW de Snowflake.

Fuentes (todas publicas, sin credenciales):
  - Precios diarios OHLCV y cierre ajustado de Yahoo Finance (biblioteca yfinance) para
    las acciones que alguna vez estuvieron en el S&P 500 y para ^GSPC, ^NYA e ^IRX.
  - Composicion historica del S&P 500 (repositorio chinobing/historical_sp500_constituents,
    actualizado a diario; hanshof/sp500_constituents, del mismo formato, llega solo a
    ago-2025).
  - Bolsa de cada simbolo (repositorio rreichel3/US-Stock-Symbols: listas NYSE, NASDAQ y
    AMEX que publica Nasdaq, actualizadas cada noche), para saber que acciones cotizan
    en la NYSE.
  - equivalencias_tickers.csv (junto a este script, lo genera
    analisis/equivalencias_tickers.py): la composicion usa el simbolo que tenia cada
    empresa en cada fecha (FB en 2020) y Yahoo guarda toda la historia bajo el simbolo
    actual (META). A Yahoo se le pide siempre el simbolo actual.

Modos:
  diario     python extraer_cargar.py diario --fecha 2026-11-13
             Trae una ventana de DIAS_REVISION dias habiles hacia atras (Yahoo corrige
             cierres y ajustes despues del dia), para las acciones de la ultima foto de
             la composicion. Los lunes recarga tambien composicion y listados.
             Primera carga sin intervencion: si RAW.PRECIOS_DIARIOS esta vacia, hace el
             historico completo (ANIO_INICIO hasta la fecha, un anio por vez, igual que el
             flow backfill_historico) en lugar de la ventana diaria.
  historico  python extraer_cargar.py historico --desde 2010-01-01 --hasta 2010-12-31
             Backfill: todas las acciones que estuvieron en el indice en ese rango.

Raw es append-only: cada corrida agrega filas con LOTE_ID e INGESTA_TS. Si una fecha
se carga dos veces, Bronze conserva la carga mas reciente.

Sesion en curso: si el script corre con la bolsa abierta (antes de CIERRE_NY en Nueva
York), Yahoo devuelve para hoy el precio del momento, no el cierre. Esa fila no se guarda;
la trae la siguiente corrida (la programada es a las 18:30 de Nueva York).

Credenciales: variables de entorno SNOWFLAKE_* (ver .env.example). En Kestra llegan
desde secretos; nunca se escriben en el codigo ni en el repositorio.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import os
import sys
import time
import uuid
from datetime import date, datetime, time as hora, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests

URL_COMPOSICION = (
    "https://raw.githubusercontent.com/chinobing/historical_sp500_constituents/main/"
    "sp_500_historical_components.csv"
)
URL_LISTADOS = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/{b}/{b}_full_tickers.json"
BOLSAS = {"nyse": "N", "nasdaq": "Q", "amex": "A"}   # mismos codigos que Nasdaq Trader
RUTA_EQUIVALENCIAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "equivalencias_tickers.csv")
INDICES = ["^GSPC", "^NYA", "^IRX"]
DIAS_REVISION = 7
TAMANO_LOTE = 100
INTENTOS_POR_LOTE = 3
MAX_PROPORCION_LOTES_FALLIDOS = 0.10
ANIO_INICIO = 2010         # mismo inicio que el flow backfill_historico y la var fecha_inicio de dbt
ZONA_NY = ZoneInfo("America/New_York")
CIERRE_NY = hora(16, 30)   # cierre de la NYSE (16:00) + margen para que Yahoo publique el cierre

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingesta")


# ---------------------------------------------------------------------------
# Snowflake
# ---------------------------------------------------------------------------

def conectar():
    import snowflake.connector

    cuerpo = os.environ.get("SNOWFLAKE_PRIVATE_KEY", "").strip()
    if not cuerpo:
        ruta = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH", "")
        if not ruta or not os.path.exists(ruta):
            sys.exit("Falta SNOWFLAKE_PRIVATE_KEY o SNOWFLAKE_PRIVATE_KEY_PATH.")
        with open(ruta) as f:
            cuerpo = "".join(l.strip() for l in f if "-----" not in l)
    llave_der = base64.b64decode(cuerpo)

    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=llave_der,
        role=os.environ.get("SNOWFLAKE_ROLE"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "PORTAFOLIO_P3"),
        schema="RAW",
        application="pset3_ingesta",
    )


def cargar(conn, df: pd.DataFrame, tabla: str) -> int:
    from snowflake.connector.pandas_tools import write_pandas

    if df.empty:
        return 0
    ok, _, filas, _ = write_pandas(
        conn, df, tabla, schema="RAW", quote_identifiers=False,
        auto_create_table=False, use_logical_type=True,
    )
    if not ok:
        raise RuntimeError(f"write_pandas fallo en RAW.{tabla}")
    log.info("RAW.%s: %s filas agregadas", tabla, filas)
    return filas


# ---------------------------------------------------------------------------
# Extraccion
# ---------------------------------------------------------------------------

def descargar_texto(url: str) -> str:
    for intento in range(1, INTENTOS_POR_LOTE + 1):
        try:
            r = requests.get(url, timeout=60, headers={"User-Agent": "pset3-usfq/1.0"})
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            log.warning("Fallo %s (intento %s): %s", url, intento, e)
            time.sleep(5 * intento)
    raise RuntimeError(f"No se pudo descargar {url}")


def extraer_composicion() -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(descargar_texto(URL_COMPOSICION)), dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    df = df.rename(columns={"DATE": "FECHA"})
    df["FECHA"] = pd.to_datetime(df["FECHA"]).dt.date
    return df[["FECHA", "TICKERS"]]


def extraer_listados() -> pd.DataFrame:
    partes = []
    for b, codigo in BOLSAS.items():
        datos = json.loads(descargar_texto(URL_LISTADOS.format(b=b)))
        df = pd.DataFrame(datos)
        partes.append(pd.DataFrame({
            "SIMBOLO": df["symbol"], "NOMBRE": df["name"].str.strip(), "CODIGO_BOLSA": codigo,
            "ES_ETF": None, "ES_PRUEBA": None, "ARCHIVO": f"{b}_full_tickers.json"}))
    return pd.concat(partes, ignore_index=True)


def normalizar(ticker: str) -> str:
    # La fuente mezcla BRK.B, BRK-B y BRK/B; Yahoo usa el guion.
    return ticker.strip().upper().replace(".", "-").replace("/", "-")


def leer_equivalencias() -> pd.DataFrame:
    if not os.path.exists(RUTA_EQUIVALENCIAS):
        log.warning("No hay %s: se piden los simbolos tal como vienen", RUTA_EQUIVALENCIAS)
        return pd.DataFrame(columns=["ticker_antiguo", "ticker_yahoo", "valido_hasta"])
    eq = pd.read_csv(RUTA_EQUIVALENCIAS, dtype=str)
    eq["valido_hasta"] = pd.to_datetime(eq["valido_hasta"]).dt.date
    return eq


def a_simbolo_yahoo(ticker: str, fecha: date, eq: pd.DataFrame) -> str:
    """Simbolo actual de Yahoo para el simbolo que tenia la empresa en esa fecha."""
    t = normalizar(ticker)
    m = eq[(eq["ticker_antiguo"] == t) & (eq["valido_hasta"] > fecha)]
    return m["ticker_yahoo"].iloc[0] if not m.empty else t


def universo(composicion: pd.DataFrame, desde: date, hasta: date, modo: str) -> list[str]:
    comp = composicion.sort_values("FECHA")
    if modo == "diario":
        fotos = comp.tail(1)
    else:
        # La foto vigente al inicio del rango y todas las que caen dentro de el.
        previas = comp[comp["FECHA"] <= desde].tail(1)
        fotos = pd.concat([previas, comp[(comp["FECHA"] > desde) & (comp["FECHA"] <= hasta)]])
    eq = leer_equivalencias()
    tickers = {a_simbolo_yahoo(t, f, eq) for f, lista in zip(fotos["FECHA"], fotos["TICKERS"])
               for t in lista.split(",") if t.strip()}
    return sorted(tickers) + INDICES


def ultima_sesion_cerrada(ahora_utc: datetime) -> date:
    """Ultima fecha cuyo cierre ya existe: hoy si en Nueva York ya paso CIERRE_NY, si no ayer.

    No revisa feriados: un dia sin sesion simplemente no trae filas de Yahoo.
    """
    if ahora_utc.tzinfo is None:
        ahora_utc = ahora_utc.replace(tzinfo=timezone.utc)
    ny = ahora_utc.astimezone(ZONA_NY)
    return ny.date() if ny.time() >= CIERRE_NY else ny.date() - timedelta(days=1)


def quitar_sesion_en_curso(precios: pd.DataFrame, ahora_utc: datetime) -> tuple[pd.DataFrame, int]:
    """Quita las filas posteriores a la ultima sesion cerrada (precio intradia, no cierre)."""
    if precios.empty:
        return precios, 0
    tope = ultima_sesion_cerrada(ahora_utc)
    abiertas = precios["FECHA"] > tope
    return precios[~abiertas].reset_index(drop=True), int(abiertas.sum())


def descargar_precios(tickers: list[str], desde: date, hasta: date):
    import yfinance as yf

    # yfinance trata 'end' como exclusivo.
    df = yf.download(
        tickers, start=desde.isoformat(), end=(hasta + timedelta(days=1)).isoformat(),
        interval="1d", auto_adjust=False, actions=False, group_by="ticker",
        threads=True, progress=False,
    )
    filas, bitacora = [], []
    for t in tickers:
        try:
            sub = df[t] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            sub = pd.DataFrame()
        sub = sub.dropna(how="all")
        if sub.empty:
            bitacora.append((t, 0, "SIN_DATOS", "Yahoo no devolvio filas"))
            continue
        sub = sub.reset_index().rename(columns={
            "Date": "FECHA", "Open": "OPEN", "High": "HIGH", "Low": "LOW",
            "Close": "CLOSE", "Adj Close": "ADJ_CLOSE", "Volume": "VOLUME"})
        sub["TICKER"] = t
        filas.append(sub[["TICKER", "FECHA", "OPEN", "HIGH", "LOW", "CLOSE", "ADJ_CLOSE", "VOLUME"]])
        bitacora.append((t, len(sub), "OK", ""))
    precios = pd.concat(filas, ignore_index=True) if filas else pd.DataFrame()
    if not precios.empty:
        precios["FECHA"] = pd.to_datetime(precios["FECHA"]).dt.date
    return precios, bitacora


# ---------------------------------------------------------------------------
# Corrida
# ---------------------------------------------------------------------------

def correr(modo: str, desde: date, hasta: date, incluir_referencias: bool) -> None:
    lote = f"{modo}-{hasta.isoformat()}-{uuid.uuid4().hex[:8]}"
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    sello = {"LOTE_ID": lote, "INGESTA_TS": ahora}
    log.info("Lote %s: %s a %s", lote, desde, hasta)

    composicion = extraer_composicion()
    conn = conectar()
    try:
        if incluir_referencias:
            cargar(conn, composicion.assign(FUENTE=URL_COMPOSICION, **sello), "COMPOSICION_SP500")
            cargar(conn, extraer_listados().assign(FUENTE="github.com/rreichel3/US-Stock-Symbols", **sello),
                   "LISTADOS_BOLSA")

        tickers = universo(composicion, desde, hasta, modo)
        log.info("%s simbolos a descargar", len(tickers))
        lotes = [tickers[i:i + TAMANO_LOTE] for i in range(0, len(tickers), TAMANO_LOTE)]
        fallidos = 0
        for n, grupo in enumerate(lotes, 1):
            for intento in range(1, INTENTOS_POR_LOTE + 1):
                try:
                    precios, bitacora = descargar_precios(grupo, desde, hasta)
                    break
                except Exception as e:  # red, limite de Yahoo, respuesta malformada
                    log.warning("Grupo %s/%s fallo (intento %s): %s", n, len(lotes), intento, e)
                    time.sleep(30 * intento)
            else:
                fallidos += 1
                precios = pd.DataFrame()
                bitacora = [(t, 0, "ERROR", "fallaron los reintentos del grupo") for t in grupo]

            precios, en_curso = quitar_sesion_en_curso(precios, datetime.now(timezone.utc))
            if en_curso:
                log.info("Grupo %s/%s: %s filas de la sesion en curso no se guardan (sin cierre)",
                         n, len(lotes), en_curso)
            cargar(conn, precios.assign(FUENTE="yahoo_finance/yfinance", **sello), "PRECIOS_DIARIOS")
            cargar(conn, pd.DataFrame(
                [dict(LOTE_ID=lote, TICKER=t, FECHA_DESDE=desde, FECHA_HASTA=hasta, FILAS=f,
                      ESTADO=e, DETALLE=d, INGESTA_TS=ahora) for t, f, e, d in bitacora]),
                "INGESTA_LOG")
            time.sleep(2)  # no saturar a Yahoo

        if lotes and fallidos / len(lotes) > MAX_PROPORCION_LOTES_FALLIDOS:
            # Falla la tarea para que Kestra la reintente; lo ya cargado no se duplica
            # en Bronze porque alli se conserva solo la carga mas reciente.
            sys.exit(f"{fallidos} de {len(lotes)} grupos fallaron: se aborta el lote {lote}")
        log.info("Lote %s terminado (%s grupos fallidos de %s)", lote, fallidos, len(lotes))
    finally:
        conn.close()


def tramos_historico(hasta: date, anio_inicio: int = ANIO_INICIO) -> list[tuple[date, date]]:
    """Un tramo por anio desde anio_inicio hasta la fecha 'hasta' (el ultimo anio, recortado)."""
    return [(date(a, 1, 1), min(date(a, 12, 31), hasta)) for a in range(anio_inicio, hasta.year + 1)]


def raw_precios_vacia() -> bool:
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("select 1 from PRECIOS_DIARIOS limit 1")
        return cur.fetchone() is None
    finally:
        conn.close()


def correr_diario(hasta: date, incluir_referencias: bool) -> None:
    if raw_precios_vacia():
        tramos = tramos_historico(hasta)
        log.info("RAW.PRECIOS_DIARIOS vacia: primera carga historica en %s tramos (%s a %s)",
                 len(tramos), tramos[0][0], hasta)
        for desde, hasta_tramo in tramos:
            correr("historico", desde, hasta_tramo, incluir_referencias=True)
        return
    desde = hasta - timedelta(days=DIAS_REVISION + 4)  # ~7 dias habiles
    refs = incluir_referencias or hasta.isoweekday() == 1
    correr("diario", desde, hasta, refs)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="modo", required=True)
    d = sub.add_parser("diario")
    d.add_argument("--fecha", type=date.fromisoformat, default=date.today())
    d.add_argument("--incluir-referencias", action="store_true")
    h = sub.add_parser("historico")
    h.add_argument("--desde", type=date.fromisoformat, required=True)
    h.add_argument("--hasta", type=date.fromisoformat, required=True)
    a = p.parse_args()

    if a.modo == "diario":
        correr_diario(a.fecha, a.incluir_referencias)
    else:
        if a.desde > a.hasta:
            sys.exit("--desde debe ser anterior a --hasta")
        correr("historico", a.desde, a.hasta, incluir_referencias=True)


if __name__ == "__main__":
    main()
