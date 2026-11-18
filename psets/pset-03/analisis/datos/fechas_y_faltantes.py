"""Fechas de inicio y fin de cada accion, deteccion de valores faltantes contra el
calendario de la NYSE e imputacion de huecos cortos con tres metodos, sobre el cache de Yahoo.

Lee:     analisis/datos/yahoo.duckdb (cache de traer_yahoo.py) y analisis/datos/universo.duckdb
Escribe en analisis/datos/yahoo.duckdb (tablas nuevas):
  fechas_accion                   una fila por simbolo de Yahoo: primera y ultima fecha con
                                  precio, dias esperados segun el calendario NYSE, faltantes,
                                  hueco mas largo, fechas en el S&P 500 (fotos desde 2010) y
                                  si cubre entrenamiento y prueba
  huecos_accion                   un hueco por fila: desde, hasta, dias bursatiles faltantes
  precios_imputados               serie diaria en el calendario NYSE con el cierre ajustado y
                                  la apertura ajustada, imputados con los tres metodos
  evaluacion_imputacion           error de cada metodo al borrar valores conocidos
  evaluacion_imputacion_resumen   promedio por metodo, serie y largo del hueco

Series: cierre ajustado (adj_close) y apertura ajustada (open * adj_close / close, para que
la apertura quede en la misma escala que el cierre ajustado despues de splits y dividendos).

Deteccion: un dia falta si la NYSE abrio (pandas_market_calendars), la accion ya cotizaba
(entre su primera y su ultima fecha) y no hay cierre ajustado o apertura valida (> 0).

Imputacion, solo en huecos de hasta MAX_HUECO dias (los mas largos se excluyen):
  lineal         interpolacion lineal del log-precio (reparte el retorno del hueco en
                 partes iguales)
  lineal_ruido   la misma recta mas un puente browniano con la volatilidad diaria de la
                 accion: respeta los extremos del hueco y no aplana la volatilidad
  kalman         suavizado de Kalman de un modelo de nivel local (caminata aleatoria +
                 ruido) en espacio de estados
Los tres usan el valor posterior al hueco: sirven para limpiar el historico, no para
decidir en tiempo real.

Uso, desde psets/pset-03/ (uv sync --group analisis):
  uv run python analisis/datos/fechas_y_faltantes.py [--base RUTA] [--muestra-eval 30]
"""

import argparse
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

AQUI = Path(__file__).parent
MAX_HUECO = 5
INICIO_PRUEBA = pd.Timestamp("2024-01-01")
INICIO_ENTRENAMIENTO = pd.Timestamp("2010-01-04")
METODOS = ["lineal", "lineal_ruido", "kalman"]
SEMILLA = 7


def calendario_nyse(desde, hasta) -> pd.DatetimeIndex:
    sched = mcal.get_calendar("NYSE").schedule(start_date=desde, end_date=hasta)
    return pd.DatetimeIndex(sched.index.normalize())


def huecos(valida: pd.Series):
    """valida: booleano por dia bursatil. Devuelve [(desde, hasta, largo, pos_inicio)]."""
    faltan = ~valida.values
    res, i = [], 0
    while i < len(faltan):
        if faltan[i]:
            j = i
            while j + 1 < len(faltan) and faltan[j + 1]:
                j += 1
            res.append((valida.index[i], valida.index[j], j - i + 1, i))
            i = j + 1
        else:
            i += 1
    return res


def volatilidad_diaria(logp: pd.Series) -> float:
    r = logp.diff().dropna()
    if r.empty:
        return 0.0
    return float(1.4826 * (r - r.median()).abs().median())  # MAD: robusta a saltos


def imputar(logp: pd.Series, metodo: str, rng=None) -> pd.Series:
    """Rellena los NaN interiores de un log-precio. No toca los extremos de la serie."""
    lin = logp.interpolate(method="linear", limit_area="inside")
    if metodo == "lineal":
        return lin
    if metodo == "lineal_ruido":
        rng = rng or np.random.default_rng(SEMILLA)
        sigma = volatilidad_diaria(logp)
        out = lin.copy()
        falt = logp.isna().values & lin.notna().values
        i = 0
        while i < len(falt):
            if falt[i]:
                j = i
                while j + 1 < len(falt) and falt[j + 1]:
                    j += 1
                n = j - i + 1
                w = np.cumsum(rng.normal(0, sigma, n + 1))                  # caminata de n+1 pasos
                puente = w[:n] - (np.arange(1, n + 1) / (n + 1)) * w[n]    # vale 0 en ambos extremos
                out.iloc[i:j + 1] = lin.iloc[i:j + 1].values + puente
                i = j + 1
            else:
                i += 1
        return out
    if metodo == "kalman":
        from statsmodels.tsa.statespace.structural import UnobservedComponents
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = UnobservedComponents(logp.values, level="llevel").fit(disp=False)
        nivel = pd.Series(np.asarray(r.smoothed_state)[0], index=logp.index)
        return logp.fillna(nivel.where(lin.notna()))
    raise ValueError(metodo)


def evaluar(series: dict, muestra: int) -> pd.DataFrame:
    """Borra al azar 10 huecos de 1, 3 y 5 dias en series completas y mide el error de
    cada metodo y cuanto cambia la volatilidad de los retornos alrededor de los huecos."""
    rng = np.random.default_rng(SEMILLA)
    filas = []
    for t in list(series)[:muestra]:
        for nombre_serie, s in series[t].items():
            s = np.log(s.dropna())
            if len(s) < 300:
                continue
            for largo in (1, 3, 5):
                idx = []
                for _ in range(10):
                    k = int(rng.integers(50, len(s) - 50))
                    idx.extend(range(k, k + largo))
                enmasc = s.copy()
                enmasc.iloc[idx] = np.nan
                vent = sorted({x + d for x in idx for d in (0, 1) if 0 < x + d < len(s)})
                vol_real = s.diff().iloc[vent].std()
                for metodo in METODOS:
                    try:
                        imp = imputar(enmasc, metodo, np.random.default_rng(SEMILLA))
                    except Exception:
                        continue
                    err = (imp.iloc[idx] - s.iloc[idx]).dropna()
                    vol_imp = imp.diff().iloc[vent].std()
                    filas.append((t, nombre_serie, largo, metodo, len(err),
                                  float(np.sqrt((err ** 2).mean())), float(err.abs().mean()),
                                  float(vol_imp / vol_real) if vol_real else np.nan))
    return pd.DataFrame(filas, columns=["ticker", "serie", "largo_hueco", "metodo", "n",
                                        "rmse_log_precio", "mae_log_precio", "ratio_volatilidad"])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default=str(AQUI / "yahoo.duckdb"))
    p.add_argument("--universo", default=str(AQUI / "universo.duckdb"))
    p.add_argument("--muestra-eval", type=int, default=30, help="acciones para evaluar imputacion")
    a = p.parse_args()

    con = duckdb.connect(a.base)
    precios = con.execute("""select ticker_yahoo, fecha, open, close, adj_close
                             from cache_yahoo_precios where ticker_yahoo not like '^%'
                             order by 1, 2""").df()
    if precios.empty:
        raise SystemExit("El cache esta vacio: corre primero analisis/datos/traer_yahoo.py")
    precios["fecha"] = pd.to_datetime(precios["fecha"])
    precios["open_aj"] = precios["open"] * precios["adj_close"] / precios["close"]

    with duckdb.connect(a.universo, read_only=True) as u:
        hist = u.execute("select ticker, primera_foto, ultima_foto, en_ultima_foto from sp500_historico").df()
    try:
        mapa = con.execute("select ticker_composicion, ticker_yahoo from ticker_a_yahoo").df()
    except duckdb.Error:
        mapa = pd.DataFrame({"ticker_composicion": hist["ticker"], "ticker_yahoo": hist["ticker"]})
    sp = (hist.merge(mapa, left_on="ticker", right_on="ticker_composicion")
              .groupby("ticker_yahoo").agg(tickers_composicion=("ticker", lambda x: ",".join(sorted(set(x)))),
                                           primera_fecha_sp500=("primera_foto", "min"),
                                           ultima_fecha_sp500=("ultima_foto", "max"),
                                           sigue_en_sp500=("en_ultima_foto", "max")))

    cal = calendario_nyse(precios["fecha"].min(), precios["fecha"].max())
    ultimo_dia = cal.max()
    filas, filas_h, imputados, completas = [], [], [], {}
    for t, g in precios.groupby("ticker_yahoo"):
        g = g.drop_duplicates("fecha").set_index("fecha")
        ini, fin = g.index.min(), g.index.max()
        dias = cal[(cal >= ini) & (cal <= fin)]
        s = g.reindex(dias)
        valida = (s["adj_close"] > 0) & (s["open_aj"] > 0)
        hs = huecos(valida)
        filas.append(dict(
            ticker_yahoo=t, primera_fecha_precio=ini.date(), ultima_fecha_precio=fin.date(),
            dias_con_precio=int(valida.sum()), dias_bursatiles_esperados=len(dias),
            dias_faltantes=int((~valida).sum()), pct_faltantes=100.0 * (~valida).mean(),
            n_huecos=len(hs), hueco_max_dias=max([h[2] for h in hs], default=0),
            huecos_largos=sum(h[2] > MAX_HUECO for h in hs),
            filas_fuera_de_calendario=int((~g.index.isin(cal)).sum()),
            sigue_cotizando=bool(fin >= ultimo_dia - pd.Timedelta(days=7)),
            cubre_entrenamiento=bool(ini <= INICIO_ENTRENAMIENTO),
            cubre_prueba=bool(fin >= INICIO_PRUEBA)))
        largos = np.zeros(len(dias), dtype=bool)
        for d, h, n, i0 in hs:
            filas_h.append((t, d.date(), h.date(), n, n <= MAX_HUECO))
            if n > MAX_HUECO:
                largos[i0:i0 + n] = True

        salida = pd.DataFrame({"ticker_yahoo": t, "fecha": dias.date,
                               "imputado": (~valida).values & ~largos, "excluir_tramo": largos})
        for col in ["adj_close", "open_aj"]:
            logp = np.log(s[col].where(valida))
            salida[f"{col}_original"] = s[col].where(valida).values
            for m in METODOS:
                imp = imputar(logp, m, np.random.default_rng(SEMILLA)) if hs else logp
                v = np.exp(imp.values)
                v[largos] = np.nan
                salida[f"{col}_{m}"] = v
        imputados.append(salida)
        if not hs:
            completas[t] = {"adj_close": s["adj_close"], "open_aj": s["open_aj"]}

    fechas = pd.DataFrame(filas).merge(sp, left_on="ticker_yahoo", right_index=True, how="left")
    hue = pd.DataFrame(filas_h, columns=["ticker_yahoo", "desde", "hasta", "dias_bursatiles", "se_imputa"])
    imp = pd.concat(imputados, ignore_index=True)
    ev = evaluar(completas, a.muestra_eval)
    resumen = (ev.groupby(["serie", "largo_hueco", "metodo"])[["rmse_log_precio", "mae_log_precio", "ratio_volatilidad"]]
                 .mean().reset_index() if not ev.empty else ev)

    for nombre, df in {"fechas_accion": fechas, "huecos_accion": hue, "precios_imputados": imp,
                       "evaluacion_imputacion": ev, "evaluacion_imputacion_resumen": resumen}.items():
        con.register("df", df)
        con.execute(f"create or replace table {nombre} as select * from df")
        con.unregister("df")
    con.close()

    print(f"{len(fechas)} acciones | faltantes: {fechas['dias_faltantes'].sum()} dias "
          f"({fechas['dias_faltantes'].sum() / fechas['dias_bursatiles_esperados'].sum():.4%}) | "
          f"huecos: {len(hue)} ({(hue['dias_bursatiles'] > MAX_HUECO).sum()} largos)")
    if not resumen.empty:
        print(resumen.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
