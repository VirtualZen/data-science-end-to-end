"""Tabla de equivalencias de tickers: simbolo antiguo -> simbolo actual, con fecha del cambio.

Por que importa: la composicion historica usa el simbolo que tenia cada empresa en cada
fecha (FB en 2020), pero Yahoo guarda toda la historia bajo el simbolo ACTUAL (META) y el
simbolo viejo ya no existe o pertenece hoy a otra empresa. Sin esta tabla, una empresa
que cambio de simbolo parece salir del indice y otra parece entrar, y sus precios
anteriores al cambio no se encuentran.

Metodo (sobre la composicion historica de chinobing/historical_sp500_constituents):
  1. Para cada miembro actual del S&P 500 se compara su "Date added" (Wikipedia, via
     datasets/s-and-p-500-companies) con la primera foto en que aparece su simbolo. Si el
     simbolo aparece mas de 45 dias despues de que la empresa entro al indice, la empresa
     ya estaba con otro simbolo: es un cambio.
  2. El simbolo antiguo es el que sale del indice el mismo dia en que entra el nuevo.
     Si salen varios, se descartan los que hoy siguen cotizando con ese mismo simbolo
     (una empresa renombrada deja de cotizar con el simbolo viejo). Si queda uno, es el
     antiguo; si quedan cero o varios, el caso queda para revisar.
  3. Se cruzan con cambios confirmados en fuentes publicas (VERIFICADOS, con su URL).

Limitaciones: la fuente a veces reescribe la historia con el simbolo actual (por ejemplo
MDLZ aparece desde 2007 aunque hasta 2012 era KFT); en esos casos no hay cambio visible y
no hace falta equivalencia para bajar de Yahoo. Tampoco se detectan cambios de empresas
que ya no estan en el indice.

Salida: tabla equivalencias_tickers en analisis/datos/universo.duckdb y
        analisis/datos/listas/equivalencias_tickers.csv

Uso, desde psets/pset-03/ (uv sync --group analisis):
  uv run python analisis/datos/equivalencias_tickers.py
"""

import io
import json
import urllib.request
from pathlib import Path

import duckdb
import pandas as pd

AQUI = Path(__file__).parent
URL_HIST = ("https://raw.githubusercontent.com/chinobing/historical_sp500_constituents/main/"
            "sp_500_historical_components.csv")
URL_ACTUAL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
URL_LISTADOS = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/{b}/{b}_full_tickers.json"
MARGEN_DIAS = 45
DESDE = pd.Timestamp("2010-01-01")   # alcance del proyecto

# Cambios confirmados en fuentes publicas: (antiguo, nuevo, fecha oficial, fuente).
VERIFICADOS = [
    ("BK", "BNY", "2026-05-21", "https://stockanalysis.com/actions/changes/"),
    ("MMC", "MRSH", "2026-01-14", "https://stockanalysis.com/actions/changes/"),
    ("FI", "FISV", "2025-11-11", "https://stockanalysis.com/actions/changes/"),
    ("SATS", "ECHO", "2026-06-24", "https://stockanalysis.com/actions/changes/"),
    ("FBHS", "FBIN", "2022-12-15", "https://stockanalysis.com/actions/changes/2022/"),
    ("RE", "EG", "2023-07-10", "https://tickericons.com/changes"),
    ("FB", "META", None, "https://wrds-www.wharton.upenn.edu/classroom/sp500-introduction/over-time/"),
    ("KFT", "MDLZ", "2012-10-02", "https://tickericons.com/changes"),
    ("WSH", "WLTW", "2016-01-05", "https://tickericons.com/changes"),
    ("DOW", "DWDP", "2017-09-01", "https://tickericons.com/changes"),
    ("DWDP", "DD", "2019-06-03", "https://tickericons.com/changes"),
    ("BMS", "AMCR", "2019-06-11", "https://tickericons.com/changes"),
    ("WR", "EVRG", "2018-06-05", "https://tickericons.com/changes"),
]

# Correcciones a la deteccion automatica, sin fuente citada todavia: quedan con estado
# "manual: verificar". (nuevo -> antiguo correcto, nota)
MANUALES = {
    "LIN": ("PX", "Fusion de Praxair (PX) con Linde AG; la regla tomo CA, que salio el mismo dia por otra razon"),
    "HWM": ("ARNC", "Arconic (ARNC) se separo y la parte que quedo se renombro Howmet; RTN salio por la fusion con UTX"),
    "TFC": ("BBT", "BB&T (BBT) absorbio a SunTrust (STI) y se renombro Truist"),
    "BKR": ("BHGE", "Baker Hughes, a GE company (BHGE) se renombro Baker Hughes"),
    "COR": ("ABC", "AmerisourceBergen (ABC) se renombro Cencora"),
    "CPAY": ("FLT", "FleetCor (FLT) se renombro Corpay"),
    "VMRK": ("EQR", "Equity Residential (EQR) compro AvalonBay (AVB) y se renombro Vivmark (ver tickericons)"),
    "SKYD": ("PSKY", "Paramount Skydance (PSKY) cambio a SKYD"),
}

# Cambios de empresas que ya no estan en el indice (la regla 1 no los ve): en la
# composicion el simbolo viejo sale y el nuevo entra en fotos consecutivas. Manual: verificar.
FUERA_DEL_INDICE = [
    ("SYMC", "NLOK", "Symantec vendio su negocio de empresas y se renombro NortonLifeLock"),
    ("CTL", "LUMN", "CenturyLink se renombro Lumen Technologies"),
    ("COG", "CTRA", "Cabot Oil & Gas se fusiono con Cimarex y se renombro Coterra"),
    ("VIAC", "PARA", "ViacomCBS se renombro Paramount Global"),
    ("CDAY", "DAY", "Ceridian se renombro Dayforce"),
    ("PARA", "PSKY", "Paramount Global se fusiono con Skydance (Paramount Skydance)"),
]

# Simbolos que la regla marca pero no son cambios: la fuente no los tiene en fotos
# anteriores aunque ya eran miembros (huecos de la fuente, se reportan en CALIDAD).
NO_SON_CAMBIO = ["CEG", "DOW", "FOX", "FOXA", "IR"]


def bajar(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def norm(t):
    return t.strip().upper().replace(".", "-").replace("/", "-")


def main():
    h = pd.read_csv(io.BytesIO(bajar(URL_HIST)))
    h["date"] = pd.to_datetime(h["date"])
    h["set"] = h["tickers"].str.split(",").apply(lambda l: {norm(x) for x in l if x.strip()})
    fechas, sets = list(h["date"]), list(h["set"])

    primera, ultima = {}, {}
    for d, s in zip(fechas, sets):
        for t in s:
            primera.setdefault(t, d)
            ultima[t] = d
    entran = {fechas[i]: sets[i] - sets[i - 1] for i in range(1, len(sets))}
    salen = {fechas[i]: sets[i - 1] - sets[i] for i in range(1, len(sets))}

    listados = set()
    for b in ["nyse", "nasdaq", "amex"]:
        listados |= {norm(x["symbol"]) for x in json.loads(bajar(URL_LISTADOS.format(b=b)))}

    act = pd.read_csv(io.BytesIO(bajar(URL_ACTUAL)))
    act["ticker"] = act["Symbol"].map(norm)
    act["agregada"] = pd.to_datetime(act["Date added"], errors="coerce")

    filas = []
    for _, r in act.iterrows():
        f = primera.get(r.ticker)
        if f is None or pd.isna(r.agregada) or f == fechas[0] or f < DESDE:
            continue
        if f <= r.agregada + pd.Timedelta(days=MARGEN_DIAS):
            continue
        salieron = sorted(salen.get(f, set()))
        candidatos = [t for t in salieron if t not in listados]
        if len(candidatos) == 1:
            antiguo, estado = candidatos[0], "detectado"
        elif not salieron:
            antiguo, estado = None, "revisar: no sale ningun simbolo ese dia (hueco en la fuente)"
        else:
            antiguo, estado = None, f"revisar: candidatos {', '.join(salieron)}"
        filas.append(dict(ticker_antiguo=antiguo, ticker_nuevo=r.ticker, empresa=r.Security,
                          fecha_cambio_composicion=f.date(), fecha_cambio_oficial=None,
                          fecha_ingreso_indice=r.agregada.date(), metodo="fecha de ingreso vs primera foto",
                          estado=estado, fuente="composicion historica"))

    df = pd.DataFrame(filas)
    for nuevo, (antiguo, nota) in MANUALES.items():
        m = df["ticker_nuevo"].eq(nuevo)
        df.loc[m, ["ticker_antiguo", "estado", "metodo"]] = [antiguo, "manual: verificar", nota]
    for antiguo, nuevo, nota in FUERA_DEL_INDICE:
        df.loc[len(df)] = dict(
            ticker_antiguo=antiguo, ticker_nuevo=nuevo, empresa=None,
            fecha_cambio_composicion=primera[nuevo].date(), fecha_cambio_oficial=None,
            fecha_ingreso_indice=None, metodo=nota, estado="manual: verificar",
            fuente="composicion historica")
    m = df["ticker_nuevo"].isin(NO_SON_CAMBIO)
    df.loc[m, "estado"] = "no es cambio: hueco de la fuente (ya era miembro con el mismo simbolo)"
    df.loc[m, "ticker_antiguo"] = None
    for antiguo, nuevo, fecha, url in VERIFICADOS:
        m = df["ticker_nuevo"].eq(nuevo) & (df["ticker_antiguo"].eq(antiguo) | df["ticker_antiguo"].isna())
        if m.any():
            df.loc[m, ["ticker_antiguo", "fecha_cambio_oficial", "estado", "fuente"]] = \
                [antiguo, fecha, "verificado", url]
        else:
            f_nuevo = primera.get(nuevo)
            visible = antiguo in ultima and f_nuevo is not None and f_nuevo > primera[antiguo]
            df.loc[len(df)] = dict(
                ticker_antiguo=antiguo, ticker_nuevo=nuevo, empresa=None,
                fecha_cambio_composicion=f_nuevo.date() if visible else None,
                fecha_cambio_oficial=fecha, fecha_ingreso_indice=None,
                metodo="fuente publica",
                estado="verificado" + ("" if visible else " (la composicion ya usa el simbolo nuevo en toda la historia)"),
                fuente=url)

    # Cadenas: si el simbolo nuevo de un cambio vuelve a cambiar DESPUES, el simbolo de
    # Yahoo es el ultimo. Se respeta la fecha: DOW (Dow Chemical, hasta 2017) -> DWDP -> DD,
    # pero el DOW actual (Dow Inc., desde 2019) es otra empresa y se queda como DOW.
    df["_fecha"] = pd.to_datetime(df["fecha_cambio_oficial"].fillna(df["fecha_cambio_composicion"]))
    def final(t, desde):
        for _ in range(10):
            sig = df[df["ticker_antiguo"].eq(t) & (df["_fecha"] > desde)].sort_values("_fecha")
            if sig.empty:
                return t
            t, desde = sig.iloc[0]["ticker_nuevo"], sig.iloc[0]["_fecha"]
        return t
    df["ticker_yahoo"] = [final(n, f) if pd.notna(f) else n for n, f in zip(df["ticker_nuevo"], df["_fecha"])]
    df = df.drop(columns="_fecha")
    df["ultima_foto_antiguo"] = df["ticker_antiguo"].map(lambda t: ultima[t].date() if t in ultima else None)
    df["antiguo_cotiza_hoy_con_ese_simbolo"] = df["ticker_antiguo"].map(lambda t: t in listados if t else None)
    df = df.sort_values(["fecha_cambio_composicion", "ticker_nuevo"], na_position="first").reset_index(drop=True)

    cols = ["ticker_antiguo", "ticker_nuevo", "ticker_yahoo", "empresa", "fecha_cambio_oficial",
            "fecha_cambio_composicion", "ultima_foto_antiguo", "fecha_ingreso_indice",
            "antiguo_cotiza_hoy_con_ese_simbolo", "metodo", "estado", "fuente"]
    df = df[cols]
    (AQUI / "listas").mkdir(exist_ok=True)
    df.to_csv(AQUI / "listas" / "equivalencias_tickers.csv", index=False)

    # Copia para el pipeline: seed de dbt y archivo que usa la ingesta de Kestra. Solo los
    # cambios reales; valido_hasta = primera foto de la composicion con el simbolo nuevo
    # (antes de esa fecha el simbolo antiguo corresponde al actual de Yahoo). Si la
    # composicion no muestra el cambio, se usa la fecha oficial.
    semilla = df[df["ticker_antiguo"].notna() & ~df["estado"].str.startswith("no es cambio")].copy()
    semilla["valido_hasta"] = pd.to_datetime(
        semilla["fecha_cambio_composicion"].fillna(semilla["fecha_cambio_oficial"])).dt.date
    semilla["estado"] = semilla["estado"].str.split(" ").str[0].str.rstrip(":")
    semilla = semilla[["ticker_antiguo", "ticker_yahoo", "valido_hasta", "estado"]]
    # La semilla la consume el pipeline copiado en psets/pset-03/pipeline/ (pset-02 ya se
    # entrego y no se modifica).
    raiz = AQUI.parent.parent / "pipeline"
    for destino in [raiz / "dbt" / "seeds" / "equivalencias_tickers.csv",
                    raiz / "kestra" / "scripts" / "equivalencias_tickers.csv"]:
        destino.parent.mkdir(parents=True, exist_ok=True)
        semilla.to_csv(destino, index=False)
    con = duckdb.connect(str(AQUI / "universo.duckdb"))
    con.register("df", df)
    con.execute("create or replace table equivalencias_tickers as select * from df")
    con.close()
    print(df.drop(columns=["fuente", "metodo", "empresa"]).to_string())
    print(df["estado"].str.split(":").str[0].value_counts().to_string())


if __name__ == "__main__":
    main()
