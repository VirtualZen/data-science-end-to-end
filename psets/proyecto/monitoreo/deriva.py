"""Deriva de datos: PSI por feature (umbrales calibrados con la historia de entrenamiento), KS para las
numericas y chi-cuadrado para las categoricas; z-score para las features de mercado.

Por que tres tratamientos:
- Features por accion (28): cada lote tiene ~330 filas, una por accion. PSI con 10 cuantiles del
  entrenamiento y KS de dos muestras contra la referencia.
- Features de mercado (rf_mes, ret_log_sp500_mes, ret_log_nyse_composite_mes, dispersion_mes): valen lo
  mismo para todas las acciones del mes; su "distribucion" en un lote es un solo punto, asi que PSI y KS
  siempre saltarian. Se mide cuantas desviaciones se aleja el valor del mes de la historia mensual.
- Categoricas: mes_calendario_obj es constante en cada lote por diseno (todas las acciones predicen el
  mismo mes), asi que el chi-cuadrado se hace sobre una ventana de 12 lotes contra la frecuencia del
  entrenamiento; y hubo_retorno_extremo_mes (marca de calidad de la OBT, por accion) se prueba por lote.

Umbrales del PSI: el PSI de un mes de entrenamiento contra todo el entrenamiento ya no es 0 (cada mes es
una muestra de ~330 acciones y el mercado cambia). Para cada feature se calcula el PSI de los 132 meses de
2013-2023 y se toma: alerta = max(0,10; p95 historico) y critico = max(0,25; p99 historico). Los pisos 0,10 y
0,25 son los convencionales; el percentil evita alertar cada mes en features que por naturaleza varian mucho
entre meses (p. ej. retornos del mes) y conserva la sensibilidad en las estables.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

# dias_negociados_mes y obs_252d son conteos de dias habiles: casi iguales para todas las acciones del mes.
DE_MERCADO = ["ret_log_sp500_mes", "ret_log_nyse_composite_mes", "rf_mes", "dispersion_mes", "dias_negociados_mes",
              "obs_252d"]
CATEGORICAS_VENTANA = ["mes_calendario_obj"]
CATEGORICAS_LOTE = ["hubo_retorno_extremo_mes"]
BINS = 10
EPS = 1e-4
Z_ALERTA, Z_CRITICO = 2.0, 3.0
P_KS = 0.01


def _psi(esperado: np.ndarray, observado: np.ndarray) -> float:
    e = np.clip(esperado, EPS, None)
    o = np.clip(observado, EPS, None)
    return float(np.sum((o - e) * np.log(o / e)))


def _proporciones(x: pd.Series, cortes: np.ndarray) -> np.ndarray:
    x = x.dropna().to_numpy(dtype=float)
    if len(x) == 0:
        return np.full(len(cortes) + 1, 1.0 / (len(cortes) + 1))
    idx = np.searchsorted(cortes, x, side="right")
    return np.bincount(idx, minlength=len(cortes) + 1) / len(x)


class Referencia:
    """Lo que se guarda del entrenamiento para comparar cada lote (no se guardan los datos crudos salvo una
    muestra de 5.000 filas para el KS)."""

    def __init__(self, entrenamiento: pd.DataFrame, features: list[str], semilla: int = 42) -> None:
        self.por_accion = [f for f in features if f not in DE_MERCADO and f not in CATEGORICAS_VENTANA]
        self.cortes, self.esperado, self.muestra = {}, {}, {}
        muestra = entrenamiento.sample(min(5000, len(entrenamiento)), random_state=semilla)
        for f in self.por_accion:
            q = np.unique(np.nanquantile(entrenamiento[f].astype(float), np.linspace(0, 1, BINS + 1)[1:-1]))
            self.cortes[f] = q
            self.esperado[f] = _proporciones(entrenamiento[f], q)
            self.muestra[f] = muestra[f].dropna().to_numpy(dtype=float)
        # rango observado en entrenamiento: "fuera de rango" (seccion 6.1) es salir de [min, max]
        self.rango = {f: (float(entrenamiento[f].min()), float(entrenamiento[f].max()))
                      for f in self.por_accion + DE_MERCADO}
        self.categorias = {c: set(entrenamiento[c].dropna().unique()) for c in CATEGORICAS_VENTANA}
        mensual = entrenamiento.groupby("anio_mes")[DE_MERCADO].median()
        self.mercado = {f: (float(mensual[f].mean()), float(mensual[f].std(ddof=1))) for f in DE_MERCADO}
        self.cat_ventana = {c: entrenamiento[c].value_counts(normalize=True).sort_index()
                            for c in CATEGORICAS_VENTANA}
        self.cat_lote = {c: entrenamiento[c].astype(bool).value_counts(normalize=True)
                         for c in CATEGORICAS_LOTE if c in entrenamiento}
        self.umbrales = self._calibrar(entrenamiento)

    def _calibrar(self, entrenamiento: pd.DataFrame) -> pd.DataFrame:
        filas = []
        meses = [m for m in sorted(entrenamiento["anio_mes"].unique()) if m >= 201301]
        historico = {f: [] for f in self.por_accion}
        for _, g in entrenamiento[entrenamiento["anio_mes"].isin(meses)].groupby("anio_mes"):
            for f in self.por_accion:
                historico[f].append(_psi(self.esperado[f], _proporciones(g[f], self.cortes[f])))
        for f, v in historico.items():
            v = np.array(v)
            filas.append({"feature": f, "psi_p95_hist": float(np.quantile(v, 0.95)),
                          "psi_p99_hist": float(np.quantile(v, 0.99)),
                          "umbral_alerta": max(0.10, float(np.quantile(v, 0.95))),
                          "umbral_critico": max(0.25, float(np.quantile(v, 0.99)))})
        return pd.DataFrame(filas).set_index("feature")

    def _calidad(self, lote: pd.DataFrame, f: str) -> dict:
        x = lote[f]
        lo, hi = self.rango[f]
        fuera = ((x < lo) | (x > hi)) & x.notna()
        return {"pct_nulos": float(100 * x.isna().mean()), "pct_fuera_rango": float(100 * fuera.mean())}

    def evaluar(self, lote: pd.DataFrame, ventana: pd.DataFrame | None = None) -> pd.DataFrame:
        """Una fila por feature: % de nulos, % fuera del rango de entrenamiento, estadistico, p-valor, umbral y
        estado (ok / alerta / critico). Las categoricas traen ademas las categorias no vistas."""
        filas = []
        for f in self.por_accion:
            psi = _psi(self.esperado[f], _proporciones(lote[f], self.cortes[f]))
            x = lote[f].dropna().to_numpy(dtype=float)
            ks = stats.ks_2samp(self.muestra[f], x) if len(x) > 1 else None
            u = self.umbrales.loc[f]
            estado = "critico" if psi > u.umbral_critico else "alerta" if psi > u.umbral_alerta else "ok"
            filas.append({"feature": f, "tipo": "numerica", "prueba": "PSI+KS", "psi": psi, **self._calidad(lote, f),
                          "ks_estadistico": None if ks is None else float(ks.statistic),
                          "ks_p": None if ks is None else float(ks.pvalue),
                          "umbral_alerta": float(u.umbral_alerta), "umbral_critico": float(u.umbral_critico),
                          "estado": estado})
        for f in DE_MERCADO:
            media, de = self.mercado[f]
            z = abs(float(lote[f].median()) - media) / de if de > 0 else 0.0
            filas.append({"feature": f, "tipo": "mercado", "prueba": "z mensual", "z": z, **self._calidad(lote, f),
                          "umbral_alerta": Z_ALERTA, "umbral_critico": Z_CRITICO,
                          "estado": "critico" if z > Z_CRITICO else "alerta" if z > Z_ALERTA else "ok"})
        for c, vistas in self.categorias.items():
            no_vistas = int((~lote[c].isin(vistas) & lote[c].notna()).sum())
            filas.append({"feature": c, "tipo": "categorica", "prueba": "categorias vistas en entrenamiento",
                          "no_vistas": no_vistas, "estado": "critico" if no_vistas else "ok"})
        for c, ref in self.cat_lote.items():
            if c not in lote:
                continue
            obs = lote[c].astype(bool).value_counts().reindex(ref.index, fill_value=0)
            esperado = ref * obs.sum()
            p = float(stats.chisquare(obs, esperado).pvalue) if (esperado > 0).all() else 1.0
            # PSI decide (umbrales clasicos 0,10 / 0,25 para categorias); chi2 es el respaldo (PDF 6.2): si el PSI
            # no alerta pero chi2 da p < 0,001, el estado sube a "alerta".
            psi = _psi(ref.to_numpy(dtype=float), (obs / max(obs.sum(), 1)).to_numpy(dtype=float))
            estado = "critico" if psi > 0.25 else "alerta" if psi > 0.10 or p < 0.001 else "ok"
            filas.append({"feature": c, "tipo": "categorica", "prueba": "PSI+chi2 lote", "psi": psi, "chi2_p": p,
                          "umbral_alerta": 0.10, "umbral_critico": 0.25, "estado": estado})
        if ventana is not None and len(ventana["anio_mes"].unique()) >= 12:
            for c, ref in self.cat_ventana.items():
                meses = ventana.groupby("anio_mes")[c].first().value_counts().reindex(ref.index, fill_value=0)
                p = float(stats.chisquare(meses, ref * meses.sum()).pvalue)
                filas.append({"feature": c, "tipo": "categorica", "prueba": "chi2 ventana 12 lotes",
                              "chi2_p": p, "umbral_alerta": 0.01, "umbral_critico": 0.001,
                              "estado": "critico" if p < 0.001 else "alerta" if p < 0.01 else "ok"})
        return pd.DataFrame(filas)


class ReferenciaSalida:
    """Deriva de la salida del modelo. Las predicciones de un mes se mueven juntas (el mercado del mes las
    desplaza a todas), asi que un PSI contra todo el entrenamiento salta siempre. Se compara la media y la
    dispersion de las predicciones del lote con las de los meses de entrenamiento (z mensual)."""

    def __init__(self, pred: np.ndarray, meses: np.ndarray) -> None:
        g = pd.DataFrame({"p": pred, "m": meses}).groupby("m")["p"].agg(["mean", "std"])
        self.media = (float(g["mean"].mean()), float(g["mean"].std(ddof=1)))
        self.de = (float(g["std"].mean()), float(g["std"].std(ddof=1)))

    def z(self, pred: np.ndarray) -> tuple[float, float]:
        return (abs(float(np.mean(pred)) - self.media[0]) / self.media[1],
                abs(float(np.std(pred, ddof=1)) - self.de[0]) / self.de[1])
