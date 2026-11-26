"""Construye las series de precios de cada accion, prueba su estacionariedad y ajusta un
ARIMA por accion y por serie, eligiendo el orden por AIC y, por separado, por BIC.

Series (todas en logaritmos, para que un cambio sea un porcentaje):
  nivel_cierre       log del cierre ajustado
  nivel_apertura     log de la apertura ajustada (open * adj_close / close)
  dif_cierre         diferencia diaria de nivel_cierre = retorno log cierre a cierre
  dif_apertura       diferencia diaria de nivel_apertura = retorno log apertura a apertura
  intradia           log(cierre / apertura) del mismo dia: ganancia o perdida dentro del dia
  nocturno           log(apertura de hoy / cierre de ayer): el salto entre sesiones
  dif_cierre_usd     diferencia simple del cierre ajustado en dolares (solo para comparar:
                     su varianza crece con el precio, por eso se prefiere el logaritmo)
dif_cierre = nocturno + intradia, asi que las dos ultimas descomponen el retorno diario.

Para cada serie: pruebas ADF (H0: raiz unitaria) y KPSS (H0: estacionaria). Si la serie
no es estacionaria se ajusta con d = 1. Se prueban p y q de 0 a 2 y se guardan todos los
candidatos con su AIC y su BIC; el mejor por cada criterio va a arima_modelos. El BIC
castiga mas los parametros: suele elegir modelos mas simples que el AIC.

Solo con datos de entrenamiento (hasta --corte). Tramos con huecos largos quedan como NaN
y el ARIMA en espacio de estados los trata como faltantes.

Lee analisis/datos/yahoo.duckdb (precios_imputados, de fechas_y_faltantes.py) y escribe:
  series_diarias         ticker, fecha y las 7 series (con la imputacion elegida)
  estacionariedad        ticker, serie, p-valor ADF, p-valor KPSS, d elegido
  arima_candidatos       todos los ordenes probados con AIC y BIC
  arima_modelos          mejor modelo por (ticker, serie, criterio = AIC o BIC)
  arima_coeficientes     coeficientes de esos modelos: valor, error estandar, z, p-valor

Uso, desde psets/pset-03/ (uv sync --group analisis):
  uv run python analisis/modelos/series_y_arima.py [--imputacion lineal|lineal_ruido|kalman] [--procesos 4]
"""

import argparse
import itertools
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

AQUI = Path(__file__).parent
MIN_OBS = 250
SERIES = ["nivel_cierre", "nivel_apertura", "dif_cierre", "dif_apertura", "intradia",
          "nocturno", "dif_cierre_usd"]


def construir_series(df: pd.DataFrame, metodo: str) -> pd.DataFrame:
    df = df.sort_values(["ticker_yahoo", "fecha"]).copy()
    c, o = np.log(df[f"adj_close_{metodo}"]), np.log(df[f"open_aj_{metodo}"])
    g = df["ticker_yahoo"]
    df["nivel_cierre"], df["nivel_apertura"] = c, o
    df["dif_cierre"] = c - c.groupby(g).shift(1)
    df["dif_apertura"] = o - o.groupby(g).shift(1)
    df["intradia"] = c - o
    df["nocturno"] = o - c.groupby(g).shift(1)
    df["dif_cierre_usd"] = df[f"adj_close_{metodo}"] - df[f"adj_close_{metodo}"].groupby(g).shift(1)
    return df[["ticker_yahoo", "fecha", "imputado", "excluir_tramo"] + SERIES]


def ajustar(args):
    ticker, serie, valores, max_p, max_q = args
    from statsmodels.stats.diagnostic import acorr_ljungbox
    from statsmodels.tsa.arima.model import ARIMA
    from statsmodels.tsa.stattools import adfuller, kpss

    y = np.asarray(valores, dtype=float)
    obs = y[np.isfinite(y)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        adf_p = float(adfuller(obs, autolag="AIC")[1])
        kpss_p = float(kpss(obs, regression="c", nlags="auto")[1])
    d = 0 if (adf_p < 0.05 and kpss_p > 0.05) else 1
    est = dict(ticker_yahoo=ticker, serie=serie, n_obs=len(obs), adf_p=adf_p, kpss_p=kpss_p,
               d_elegido=d, estacionaria=(d == 0))

    candidatos, resultados = [], {}
    for p, q in itertools.product(range(max_p + 1), range(max_q + 1)):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = ARIMA(y, order=(p, d, q), trend="c" if d == 0 else "t").fit()
            conv = bool(r.mle_retvals.get("converged", True)) if r.mle_retvals else True
            candidatos.append(dict(ticker_yahoo=ticker, serie=serie, p=p, d=d, q=q,
                                   aic=float(r.aic), bic=float(r.bic), convergio=conv))
            resultados[(p, q)] = r
        except Exception:
            continue
    modelos, coefs = [], []
    if not candidatos:
        return est, candidatos, modelos, coefs
    cand = pd.DataFrame(candidatos)
    for criterio in ("aic", "bic"):
        fila = cand.sort_values(criterio).iloc[0]
        r = resultados[(int(fila.p), int(fila.q))]
        resid = r.resid[d:][np.isfinite(r.resid[d:])]
        lb = float(acorr_ljungbox(resid, lags=[10], return_df=True)["lb_pvalue"].iloc[0])
        modelos.append(dict(ticker_yahoo=ticker, serie=serie, criterio=criterio.upper(),
                            p=int(fila.p), d=d, q=int(fila.q), aic=float(fila.aic), bic=float(fila.bic),
                            n_obs=len(obs), ljungbox_p_10=lb, residuos_ruido_blanco=lb > 0.05,
                            convergio=bool(fila.convergio),
                            sin_estructura=(fila.p == 0 and fila.q == 0)))
        for n, v, e, z, pv in zip(r.param_names, r.params, r.bse, r.tvalues, r.pvalues):
            coefs.append(dict(ticker_yahoo=ticker, serie=serie, criterio=criterio.upper(),
                              parametro=n, valor=float(v), error_std=float(e), z=float(z), p_valor=float(pv)))
    return est, candidatos, modelos, coefs


def main():
    pa = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    pa.add_argument("--base", default=str(AQUI.parent / "datos" / "yahoo.duckdb"))
    pa.add_argument("--imputacion", choices=["lineal", "lineal_ruido", "kalman"], default="lineal")
    pa.add_argument("--corte", default="2023-12-31")
    pa.add_argument("--series", nargs="*", default=SERIES)
    pa.add_argument("--max-p", type=int, default=2)
    pa.add_argument("--max-q", type=int, default=2)
    pa.add_argument("--procesos", type=int, default=4)
    pa.add_argument("--tickers", nargs="*")
    a = pa.parse_args()

    con = duckdb.connect(a.base)
    base = con.execute("select * from precios_imputados").df()
    ser = construir_series(base, a.imputacion)
    con.register("s", ser)
    con.execute("create or replace table series_diarias as select * from s")
    con.unregister("s")

    ent = ser[pd.to_datetime(ser["fecha"]) <= pd.Timestamp(a.corte)]
    if a.tickers:
        ent = ent[ent["ticker_yahoo"].isin(a.tickers)]
    trabajos = []
    for t, g in ent.groupby("ticker_yahoo"):
        for s in a.series:
            v = g[s].to_numpy(dtype=float)
            v = v[np.argmax(np.isfinite(v)):] if np.isfinite(v).any() else v
            if np.isfinite(v).sum() >= MIN_OBS:
                trabajos.append((t, s, v, a.max_p, a.max_q))
    print(f"{len(trabajos)} ajustes (accion x serie) con datos hasta {a.corte}, imputacion {a.imputacion}")

    est, cand, mods, coefs = [], [], [], []
    with ProcessPoolExecutor(max_workers=a.procesos) as ex:
        for e, c, m, k in ex.map(ajustar, trabajos, chunksize=2):
            est.append(e); cand.extend(c); mods.extend(m); coefs.extend(k)

    for nombre, d in {"estacionariedad": pd.DataFrame(est), "arima_candidatos": pd.DataFrame(cand),
                      "arima_modelos": pd.DataFrame(mods), "arima_coeficientes": pd.DataFrame(coefs)}.items():
        con.register("d", d)
        con.execute(f"create or replace table {nombre} as select * from d")
        con.unregister("d")

    print(con.execute("""select serie, round(avg(adf_p), 3) adf_p, round(avg(kpss_p), 3) kpss_p,
                                round(avg(estacionaria::int), 2) pct_estacionaria
                         from estacionariedad group by 1 order by 1""").df().to_string(index=False))
    print(con.execute("""select serie, criterio, round(avg(p), 2) p_prom, round(avg(q), 2) q_prom,
                                round(avg(sin_estructura::int), 2) pct_sin_estructura,
                                round(avg(residuos_ruido_blanco::int), 2) pct_ruido_blanco
                         from arima_modelos group by 1, 2 order by 1, 2""").df().to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
