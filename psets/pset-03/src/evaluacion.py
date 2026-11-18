"""Metricas estadisticas y pruebas de hipotesis sobre el panel accion x mes.

Todas las comparaciones entre modelos se hacen sobre una serie MENSUAL (promedio transversal
de la perdida, o IC del mes): las acciones de un mismo mes estan correlacionadas y no son
observaciones independientes. Con ~84 meses de validacion (2017-2023) y ~34 de hold-out, las
pruebas tienen poca potencia: un "no significativo" es el resultado esperado frente al RW.

Entrada comun: DataFrame con columnas anio_mes, real (retorno log del mes siguiente) y pred.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# ------------------------------------------------------------------ errores de pronostico
def errores(df: pd.DataFrame, pred: str = "pred", real: str = "real") -> dict:
    e = df[pred] - df[real]
    sse_rw = float((df[real] ** 2).sum())                       # random walk con retorno 0
    no_cero = df[pred] != 0
    return {
        "mae": float(e.abs().mean()),
        "rmse": float(np.sqrt((e ** 2).mean())),
        "acierto_direccional": float((np.sign(df[pred]) == np.sign(df[real]))[no_cero].mean())
        if no_cero.any() else np.nan,
        "r2_fuera_muestra_vs_rw": 1 - float((e ** 2).sum()) / sse_rw if sse_rw > 0 else np.nan,
    }


# ------------------------------------------------------------------ information coefficient
def ic_por_mes(df: pd.DataFrame, pred: str = "pred", real: str = "real", minimo: int = 20) -> pd.Series:
    """Spearman entre el ranking del mes t y el retorno de t+1, por mes. NaN si el pronostico es
    constante (p. ej. random walk con 0): ese modelo no ordena acciones y su IC no existe."""
    def ic(g):
        if len(g) < minimo or g[pred].nunique() < 2:
            return np.nan
        return stats.spearmanr(g[pred], g[real]).statistic
    return df.groupby("anio_mes")[[pred, real]].apply(ic).rename("ic")


def resumen_ic(ic: pd.Series) -> dict:
    ic = ic.dropna()
    n = len(ic)
    media, desv = float(ic.mean()), float(ic.std(ddof=1)) if n > 1 else np.nan
    return {"ic_media": media, "ic_desv": desv, "icir": media / desv if desv else np.nan,
            "ic_t": media / (desv / np.sqrt(n)) if desv else np.nan, "ic_meses": n,
            "ic_positivo_pct": float((ic > 0).mean()) if n else np.nan}


# ------------------------------------------------------------------ pruebas
def perdida_mensual(df: pd.DataFrame, pred: str, real: str = "real", tipo: str = "cuadratica") -> pd.Series:
    e = df[pred] - df[real]
    l = e ** 2 if tipo == "cuadratica" else e.abs()
    return l.groupby(df["anio_mes"]).mean()


def diebold_mariano(d_t, h: int = 1) -> tuple[float, float]:
    """d_t: diferencia de perdidas mensuales (modelo - referencia); negativo = modelo mejor.
    Correccion de Harvey-Leybourne-Newbold (1997) y t de Student con T-1 g.l. Con h = 1 (meses
    sin solapar) la varianza no lleva autocovarianzas."""
    d_t = np.asarray(d_t, dtype=float)
    d_t = d_t[np.isfinite(d_t)]
    T = len(d_t)
    if T < 6:
        return np.nan, np.nan
    var = np.var(d_t, ddof=0) / T
    if var <= 0:
        return np.nan, np.nan
    dm = d_t.mean() / np.sqrt(var)
    hln = dm * np.sqrt((T + 1 - 2 * h + h * (h - 1) / T) / T)
    return float(hln), float(2 * stats.t.sf(abs(hln), df=T - 1))


def wilcoxon_pareado(a, b) -> tuple[float, float]:
    """Rangos con signo de Wilcoxon sobre series mensuales pareadas (p. ej. IC o perdida de dos
    modelos). No supone normalidad, pero si independencia entre meses."""
    a, b = pd.Series(a), pd.Series(b)
    x = pd.concat([a, b], axis=1).dropna()
    if len(x) < 6 or (x.iloc[:, 0] == x.iloc[:, 1]).all():
        return np.nan, np.nan
    r = stats.wilcoxon(x.iloc[:, 0], x.iloc[:, 1], zero_method="wilcox")
    return float(r.statistic), float(r.pvalue)


def holm(pvalores: dict[str, float]) -> dict[str, float]:
    """p-valores ajustados por Holm-Bonferroni: se comparan muchos modelos a la vez."""
    items = sorted(((p, k) for k, p in pvalores.items() if np.isfinite(p)))
    m, ajust, previo = len(items), {}, 0.0
    for i, (p, k) in enumerate(items):
        previo = max(previo, min(1.0, (m - i) * p))
        ajust[k] = previo
    return {k: ajust.get(k, np.nan) for k in pvalores}


def comparar_contra(df: pd.DataFrame, modelos: list[str], referencia: str, real: str = "real") -> pd.DataFrame:
    """Tabla modelo vs referencia: DM sobre perdida cuadratica mensual y Wilcoxon sobre la misma
    perdida; p-valores ajustados por Holm. La referencia puede ser una columna de pronostico 0."""
    ref = perdida_mensual(df, referencia, real)
    filas = {}
    for m in modelos:
        pm = perdida_mensual(df, m, real)
        dm, p_dm = diebold_mariano((pm - ref).to_numpy())
        w, p_w = wilcoxon_pareado(pm, ref)
        filas[m] = {"dm": dm, "p_dm": p_dm, "wilcoxon": w, "p_wilcoxon": p_w}
    t = pd.DataFrame(filas).T
    t["p_dm_holm"] = pd.Series(holm(t["p_dm"].to_dict()))
    t["p_wilcoxon_holm"] = pd.Series(holm(t["p_wilcoxon"].to_dict()))
    return t
