"""Metrica de negocio del PSet 1: portafolio mensual de 10 acciones ponderadas por 1/vol, en US$.

Regla (decidida por Paul el 18-nov), cada cierre de mes t:
1. Candidatas: acciones elegibles con prediccion; se excluye el 20 % mas volatil del mes
   (vol_63d por encima del percentil 80 del mes: tope relativo por accion).
2. Se eligen las n = 10 con mayor prediccion; ponderacion w_i = (1/vol_i) / sum(1/vol_j).
3. Tope de portafolio: la volatilidad estimada del portafolio (covarianza de los ultimos 63 dias
   habiles de OBT_ACCION_DIA, anualizada con raiz de 252) no puede superar 1,35 veces la del
   S&P 500 en los mismos 63 dias. Si la supera, se invierte solo la fraccion k = tope / vol_port en
   acciones y el resto queda en efectivo, que gana la tasa libre de riesgo. Solo compras, sin
   apalancamiento.
4. Costo: 15 pb (0,15 %) por cada US$ comprado o vendido: costo = turnover * costo_bps / 1e4,
   turnover = suma |w_nuevo - w_derivado| de las acciones, con w_derivado la ponderacion del mes
   anterior despues de moverse con los precios.

Se mide en retornos SIMPLES (ret_pct_mes_siguiente), que son los que se suman entre acciones.
"Ponderacion" (peso) es la fraccion del capital en cada accion, no una moneda: todo esta en US$.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def pesos_mes(g: pd.DataFrame, puntaje: str, vol: str = "vol_63d", n: int = 10,
              tope_vol: float | None = None, tope_percentil: float | None = None,
              ponderacion: str = "inv_vol") -> pd.Series:
    """Ponderaciones de las n acciones con mayor puntaje del mes, tras los topes por accion:
    1/vol (regla del PSet 1) o iguales (portafolio del universo, B5)."""
    c = g[g[puntaje].notna() & (g[vol] > 0)]
    if tope_percentil is not None and len(c):
        c = c[c[vol] <= g.loc[g[vol] > 0, vol].quantile(tope_percentil)]   # percentil del mes, todo el universo
    if tope_vol is not None:
        c = c[c[vol] <= tope_vol]
    c = c.nlargest(n, puntaje)
    if c.empty:
        return pd.Series(dtype=float)
    w = 1.0 / c[vol] if ponderacion == "inv_vol" else pd.Series(1.0, index=c.index)
    return (w / w.sum()).set_axis(c["accion_key"])


class RiesgoDiario:
    """Covarianzas de 63 dias habiles hasta el cierre de cada mes, desde OBT_ACCION_DIA."""
    def __init__(self, dia: pd.DataFrame, ventana: int = 63):
        d = dia[["fecha", "accion_key", "ret_log_diario"]].dropna()
        self.r = d.pivot_table(index="fecha", columns="accion_key", values="ret_log_diario").sort_index()
        sp = dia[["fecha", "ret_log_sp500"]].dropna().drop_duplicates("fecha").set_index("fecha")["ret_log_sp500"]
        self.sp = sp.sort_index()
        self.fechas = pd.to_datetime(self.r.index)
        self.ventana = ventana

    def _hasta(self, anio_mes: int):
        fin = pd.Period(str(int(anio_mes)), freq="M").end_time
        return self.fechas <= fin

    def vol_portafolio(self, anio_mes: int, w: pd.Series) -> float:
        m = self._hasta(anio_mes)
        bloque = self.r.loc[m, self.r.columns.intersection(w.index)].iloc[-self.ventana:]
        bloque = bloque.loc[:, bloque.notna().sum() >= self.ventana // 2]
        ww = w.reindex(bloque.columns).fillna(0.0)
        cov = bloque.cov(min_periods=self.ventana // 2).fillna(0.0).values
        return float(np.sqrt(max(ww.values @ cov @ ww.values, 0.0) * 252))

    def vol_sp500(self, anio_mes: int) -> float:
        fin = pd.Period(str(int(anio_mes)), freq="M").end_time
        s = self.sp[pd.to_datetime(self.sp.index) <= fin].iloc[-self.ventana:]
        return float(s.std(ddof=1) * np.sqrt(252))


def backtest(df: pd.DataFrame, puntaje: str, n: int = 10, vol: str = "vol_63d",
             tope_vol: float | None = None, tope_percentil: float | None = None,
             factor_tope_portafolio: float | None = None, riesgo: RiesgoDiario | None = None,
             costo_bps: float = 15.0, retorno: str = "ret_pct_mes_siguiente",
             rf: str = "rf_mes_siguiente", ponderacion: str = "inv_vol") -> pd.DataFrame:
    """Serie mensual: retorno bruto, turnover, costo, retorno neto, tasa libre de riesgo, fraccion
    invertida en acciones y volatilidades estimadas (si hay datos diarios para el tope de portafolio)."""
    if retorno not in df:                                   # snapshot anterior a F1
        df = df.assign(ret_pct_mes_siguiente=np.expm1(df["ret_log_mes_siguiente"]))
    filas, previos = [], pd.Series(dtype=float)
    for mes, g in df.sort_values("anio_mes").groupby("anio_mes"):
        w = pesos_mes(g, puntaje, vol, n, tope_vol, tope_percentil, ponderacion)
        tasa = float(g[rf].iloc[0]) if rf in g and g[rf].notna().any() else 0.0
        vol_port = vol_sp = np.nan
        invertido = 1.0
        if factor_tope_portafolio is not None and riesgo is not None and len(w):
            vol_port, vol_sp = riesgo.vol_portafolio(mes, w), riesgo.vol_sp500(mes)
            tope = factor_tope_portafolio * vol_sp
            if np.isfinite(vol_port) and np.isfinite(tope) and vol_port > tope > 0:
                invertido = tope / vol_port
                w = w * invertido                           # el resto (1 - invertido) queda en efectivo
        r = g.set_index("accion_key")[retorno].reindex(w.index).fillna(0.0)   # sin cotizacion: 0
        bruto = float((w * r).sum() + (1 - w.sum()) * tasa)
        todos = w.index.union(previos.index)
        turnover = float((w.reindex(todos, fill_value=0) - previos.reindex(todos, fill_value=0)).abs().sum())
        neto = bruto - turnover * costo_bps / 1e4
        filas.append({"anio_mes": mes, "bruto": bruto, "turnover": turnover, "neto": neto, "rf": tasa,
                      "n_acciones": len(w), "invertido": float(w.sum()), "vol_portafolio": vol_port,
                      "vol_sp500": vol_sp})
        valor = w * (1 + r)
        total = valor.sum() + (1 - w.sum()) * (1 + tasa)
        previos = valor / total if total > 0 else valor
    return pd.DataFrame(filas).set_index("anio_mes")


def sharpe_anual(serie: pd.DataFrame, col: str = "neto") -> float:
    exceso = serie[col] - serie["rf"]
    return float(exceso.mean() / exceso.std(ddof=1) * np.sqrt(12)) if exceso.std(ddof=1) > 0 else np.nan


def drawdown_maximo(serie: pd.DataFrame, col: str = "neto") -> float:
    riqueza = (1 + serie[col]).cumprod()
    return float((riqueza / riqueza.cummax() - 1).min())


def resumen(serie: pd.DataFrame) -> dict:
    return {"sharpe_neto": sharpe_anual(serie, "neto"), "sharpe_bruto": sharpe_anual(serie, "bruto"),
            "drawdown_max": drawdown_maximo(serie), "turnover_prom": float(serie["turnover"].mean()),
            "retorno_anual_neto": float((1 + serie["neto"]).prod() ** (12 / len(serie)) - 1)}


# Regla del PSet 1 con las decisiones de Paul del 18-nov.
REGLA = {"n": 10, "vol": "vol_63d", "tope_percentil": 0.80, "tope_vol": None,
         "factor_tope_portafolio": 1.35, "costo_bps": 15.0}


def metrica_negocio(pred: pd.DataFrame, puntaje: str = "pred", riesgo: RiesgoDiario | None = None,
                    **regla) -> dict:
    """Metrica de negocio sobre predicciones fuera de muestra (src.pipeline.predecir_pliegues):
    Sharpe anual neto de costos del portafolio top 10 con pesos 1/vol, y drawdown maximo, que mide el
    error mas costoso del proyecto (una caida que el cliente no tolera y lo lleva a vender en panico)."""
    serie = backtest(pred, puntaje, riesgo=riesgo, **{**REGLA, **regla})
    return {**resumen(serie), "meses": len(serie), "invertido_prom": float(serie["invertido"].mean()),
            "tope_portafolio_aplicado": riesgo is not None}


def portafolios_aleatorios(df: pd.DataFrame, sorteos: int = 200, semilla: int = 42, **kw) -> pd.DataFrame:
    """B4: distribucion del Sharpe de portafolios de n acciones elegidas al azar cada mes."""
    rng = np.random.default_rng(semilla)
    out = []
    for s in range(sorteos):
        d = df.assign(_azar=rng.random(len(df)))
        out.append({"sorteo": s, **resumen(backtest(d, "_azar", **kw))})
    return pd.DataFrame(out)


# ---------------------------------------------------------------- referencias de negocio (seccion 5)
def portafolio_universo(df: pd.DataFrame, costo_bps: float = REGLA["costo_bps"]) -> pd.DataFrame:
    """B5: todas las acciones elegibles del mes (S&P 500 que cotizan en NYSE) con igual ponderacion,
    rebalanceo mensual y el mismo costo. Es el "indice" de nuestro universo, sin elegir acciones."""
    return backtest(df.assign(_todas=1.0), "_todas", n=10**6, costo_bps=costo_bps, ponderacion="igual")


def serie_indice(df: pd.DataFrame, columna_log: str, rf: str = "rf_mes_siguiente") -> pd.DataFrame:
    """B6: comprar y mantener un indice (^GSPC o ^NYA). Son indices de PRECIO: no incluyen dividendos,
    a diferencia de los retornos ajustados de las acciones, asi que subestiman al indice ~1,5-2 % al anio."""
    m = df.groupby("anio_mes").agg(log=(columna_log, "first"), rf=(rf, "first")).sort_index()
    bruto = np.expm1(m["log"])
    return pd.DataFrame({"bruto": bruto, "turnover": 0.0, "neto": bruto, "rf": m["rf"].fillna(0.0),
                         "n_acciones": np.nan, "invertido": 1.0}, index=m.index)
