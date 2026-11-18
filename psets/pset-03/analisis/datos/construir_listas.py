"""Construye y compara las listas de acciones del universo del PSet 1:
acciones del S&P 500 que cotizan en la NYSE, hoy y en el historico (desde 2010).

Fuentes (publicas, en GitHub):
  - S&P 500 actual: datasets/s-and-p-500-companies (data/constituents.csv, desde Wikipedia).
  - S&P 500 historico: chinobing/historical_sp500_constituents (fotos desde 1996, se
    actualiza sola; mismo formato que hanshof/sp500_constituents, que llega solo a
    ago-2025).
  - Bolsa actual de cada simbolo: rreichel3/US-Stock-Symbols (listas NYSE, NASDAQ y AMEX
    tomadas del screener de Nasdaq, actualizadas cada noche).

Salida:
  - analisis/datos/universo.duckdb con las tablas sp500_actual, sp500_historico,
    listados_actuales, universo_comparado y subconjunto_nucleo.
  - analisis/datos/listas/*.csv con las mismas listas, para revisarlas sin DuckDB.

Uso, desde psets/pset-03/ (uv sync --group analisis):
  uv run python analisis/datos/construir_listas.py
"""

import io
import json
import urllib.request
from pathlib import Path

import duckdb
import pandas as pd

AQUI = Path(__file__).parent
LISTAS = AQUI / "listas"
RUTA_DB = AQUI / "universo.duckdb"
INICIO = pd.Timestamp("2010-01-01")

URL_ACTUAL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
URL_HISTORICO = "https://raw.githubusercontent.com/chinobing/historical_sp500_constituents/main/sp_500_historical_components.csv"
URL_LISTADOS = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/{b}/{b}_full_tickers.json"


def bajar(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def normalizar(ticker: str) -> str:
    # Formato de Yahoo: clases con guion (BRK.B, BRK/B -> BRK-B).
    return ticker.strip().upper().replace(".", "-").replace("/", "-")


def sp500_actual() -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(bajar(URL_ACTUAL)))
    return pd.DataFrame({
        "ticker": df["Symbol"].map(normalizar), "ticker_original": df["Symbol"],
        "nombre": df["Security"], "sector": df["GICS Sector"],
        "subindustria": df["GICS Sub-Industry"], "fecha_agregada": df["Date added"],
    })


def sp500_historico() -> tuple[pd.DataFrame, pd.Timestamp]:
    df = pd.read_csv(io.BytesIO(bajar(URL_HISTORICO)))
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= INICIO]
    n_fotos, ultima = df["date"].nunique(), df["date"].max()
    largo = (df.assign(ticker=df["tickers"].str.split(","))
               .explode("ticker").assign(ticker=lambda d: d["ticker"].map(normalizar)))
    res = (largo.groupby("ticker")["date"]
           .agg(primera_foto="min", ultima_foto="max", fotos="nunique").reset_index())
    res["en_ultima_foto"] = res["ultima_foto"] == ultima
    # Miembro en todas las fotos desde 2010 = estuvo en el indice todo el periodo.
    res["siempre_miembro_desde_2010"] = res["fotos"] == n_fotos
    for c in ["primera_foto", "ultima_foto"]:
        res[c] = res[c].dt.date
    return res, ultima


def listados_actuales() -> pd.DataFrame:
    partes = []
    for bolsa, nombre_bolsa in [("nyse", "NYSE"), ("nasdaq", "Nasdaq"), ("amex", "NYSE American")]:
        d = pd.DataFrame(json.loads(bajar(URL_LISTADOS.format(b=bolsa))))
        d = d[~d["symbol"].str.contains(r"\^|\.WS|\.U$|\.R$", regex=True)]  # preferentes, warrants, unidades
        partes.append(pd.DataFrame({
            "ticker": d["symbol"].map(normalizar), "ticker_original": d["symbol"],
            "nombre_listado": d["name"].str.strip(), "bolsa": nombre_bolsa,
            "sector_listado": d["sector"], "market_cap": pd.to_numeric(d["marketCap"], errors="coerce"),
        }))
    return pd.concat(partes).drop_duplicates("ticker")


def main() -> None:
    actual = sp500_actual()
    hist, ultima_foto = sp500_historico()
    lst = listados_actuales()

    u = pd.DataFrame({"ticker": sorted(set(actual["ticker"]) | set(hist["ticker"]))})
    u = (u.merge(actual[["ticker", "nombre", "sector"]], on="ticker", how="left")
          .merge(hist, on="ticker", how="left")
          .merge(lst[["ticker", "nombre_listado", "bolsa"]], on="ticker", how="left"))
    u["en_sp500_actual"] = u["ticker"].isin(actual["ticker"])
    u["en_sp500_historico"] = u["ticker"].isin(hist["ticker"])
    u["cotiza_hoy"] = u["bolsa"].notna()
    u["es_nyse_hoy"] = u["bolsa"].eq("NYSE")
    u["siempre_miembro_desde_2010"] = u["siempre_miembro_desde_2010"].fillna(False).astype(bool)
    u["categoria"] = u.apply(lambda r:
        "actual_e_historico" if r.en_sp500_actual and r.en_sp500_historico
        else "solo_actual" if r.en_sp500_actual
        else "solo_historico_cotiza" if r.cotiza_hoy
        else "solo_historico_no_cotiza", axis=1)

    nucleo = u[u["en_sp500_actual"] & u["siempre_miembro_desde_2010"] & u["es_nyse_hoy"]].copy()

    LISTAS.mkdir(exist_ok=True)
    tablas = {"sp500_actual": actual, "sp500_historico": hist, "listados_actuales": lst,
              "universo_comparado": u, "subconjunto_nucleo": nucleo}
    RUTA_DB.unlink(missing_ok=True)
    con = duckdb.connect(str(RUTA_DB))
    for nombre, df in tablas.items():
        con.register("df", df)
        con.execute(f"create table {nombre} as select * from df")
        con.unregister("df")
        if nombre != "listados_actuales":  # el listado completo se regenera, no se guarda en CSV
            df.to_csv(LISTAS / f"{nombre}.csv", index=False)
    con.close()

    print(f"Ultima foto historica: {ultima_foto.date()}")
    print(f"S&P 500 actual: {len(actual)} | historico desde 2010: {len(hist)} | universo: {len(u)}")
    print(u.groupby(["categoria", "es_nyse_hoy"]).size().to_string())
    print(f"Subconjunto nucleo (actual, siempre miembro desde 2010, NYSE hoy): {len(nucleo)}")


if __name__ == "__main__":
    main()
