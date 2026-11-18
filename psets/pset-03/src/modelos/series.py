"""M1 y entradas de M6/M7: ARIMA-GARCH por accion, estimado sin mirar el futuro.

Serie: ret_log_diario de OBT_ACCION_DIA (dias observados). ARIMA(p, 0, q) con constante sobre
el retorno logaritmico es ARIMA(p, 1, q) con deriva sobre ln P (docs/series_de_tiempo.md).
Sobre los residuos, GARCH(1, 1) con media cero (paquete arch, en escala x100 por estabilidad).

Esquema sin fuga (mas estricto que estimar una vez por ventana de entrenamiento):
  - Para los origenes (cierres de mes) del anio Y, el orden (p, q) por AIC y todos los
    parametros (phi, theta, omega, alpha, beta) se estiman con datos hasta el 31-dic de Y-1.
  - En cada origen t se filtra con esos parametros FIJOS y los retornos hasta t: varianza
    condicional, residuos estandarizados y pronostico de los 21 dias siguientes.
Asi una fila de entrenamiento y una de validacion se construyen igual (las dos fuera de
muestra) y la tabla sirve para todas las ventanas walk-forward: no depende del pliegue.
"""
from __future__ import annotations

import warnings
from itertools import product

import numpy as np
import pandas as pd

ORDENES = tuple(product(range(3), range(3)))     # p, q en 0..2 (9 modelos)
MIN_OBS = 500                                   # ~2 anios de retornos para estimar
ESCALA = 100.0


def _ajustar_arima(r: np.ndarray, ordenes, criterio: str):
    from statsmodels.tsa.arima.model import ARIMA
    mejor = None
    for p, q in ordenes:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = ARIMA(r, order=(p, 0, q), trend="c").fit()
        except Exception:
            continue
        valor = res.aic if criterio == "aic" else res.bic
        if np.isfinite(valor) and (mejor is None or valor < mejor[0]):
            mejor = (valor, p, q, res)
    return mejor


def _ajustar_garch(resid: np.ndarray):
    from arch import arch_model
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return arch_model(resid * ESCALA, mean="Zero", vol="GARCH", p=1, q=1).fit(disp="off")


class ArimaGarchAccion:
    """Una accion, un anio de parametros. ajustar() con datos hasta Y-1; en_origen() en cada t de Y."""

    def __init__(self, ordenes=ORDENES, criterio: str = "aic"):
        self.ordenes, self.criterio = ordenes, criterio

    def ajustar(self, r: np.ndarray) -> "ArimaGarchAccion":
        r = r[np.isfinite(r)]
        if len(r) < MIN_OBS:
            raise ValueError(f"Serie corta ({len(r)} < {MIN_OBS})")
        mejor = _ajustar_arima(r, self.ordenes, self.criterio)
        if mejor is None:
            raise ValueError("Ningun ARIMA convergio")
        _, self.p, self.q, self.arima = mejor
        self.garch = _ajustar_garch(np.asarray(self.arima.resid))
        return self

    def coeficientes(self) -> dict:
        prm = dict(zip(self.arima.model.param_names, self.arima.params))
        g = self.garch.params
        out = {"arima_p": self.p, "arima_q": self.q, "arima_const": prm.get("const", 0.0),
               "garch_omega": g["omega"] / ESCALA ** 2, "garch_alpha": g["alpha[1]"], "garch_beta": g["beta[1]"]}
        for i in (1, 2):
            out[f"arima_phi{i}"] = prm.get(f"ar.L{i}", 0.0)
            out[f"arima_theta{i}"] = prm.get(f"ma.L{i}", 0.0)
        return out

    def en_origen(self, r_hasta_t: np.ndarray, h: int = 21) -> dict:
        """Filtra con parametros fijos y datos hasta el origen; pronostica h dias."""
        from arch import arch_model
        r = r_hasta_t[np.isfinite(r_hasta_t)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = self.arima.apply(r, refit=False)
            fijo = arch_model(np.asarray(res.resid) * ESCALA, mean="Zero", vol="GARCH", p=1, q=1) \
                .fix(self.garch.params)
            var = fijo.forecast(horizon=h, reindex=False).variance.to_numpy()[-1] / ESCALA ** 2
        z = np.asarray(fijo.std_resid)
        return {"arima_pronostico_mes": float(np.sum(res.forecast(h))),
                "garch_var_condicional": float(fijo.conditional_volatility[-1] ** 2 / ESCALA ** 2),
                "garch_var_pronostico_mes": float(var.sum()),
                "resid_std_ultimo": float(z[-1]),
                "resid_std_prom_21d": float(np.nanmean(z[-21:])),
                "resid_std_abs_prom_21d": float(np.nanmean(np.abs(z[-21:])))}


def caracteristicas_accion(dia: pd.DataFrame, origenes: pd.DataFrame, anios, **kw) -> list[dict]:
    """dia: una accion (fecha, ret_log_diario, imputado). origenes: anio_mes y fecha_origen
    (ultima cotizacion del mes). Devuelve una fila por origen con coeficientes y estados."""
    dia = dia.sort_values("fecha")
    fechas = dia["fecha"].to_numpy()
    r = dia["ret_log_diario"].where(~dia["imputado"].astype(bool)).to_numpy(dtype=float)
    filas = []
    for anio in anios:
        corte = np.datetime64(f"{anio - 1}-12-31")
        sub = origenes[origenes["anio_mes"] // 100 == anio]
        if sub.empty:
            continue
        try:
            m = ArimaGarchAccion(**kw).ajustar(r[fechas <= corte])
        except ValueError:
            continue
        coef = m.coeficientes()
        for o in sub.itertuples():
            hasta = r[fechas <= np.datetime64(o.fecha_origen)]
            try:
                filas.append({"anio_mes": o.anio_mes, **coef, **m.en_origen(hasta)})
            except Exception:
                continue
    return filas


def caracteristicas_panel(diaria: pd.DataFrame, panel: pd.DataFrame, anios=range(2011, 2027),
                          n_jobs: int = -1, **kw) -> pd.DataFrame:
    """Tabla accion x mes con las variables de ARIMA-GARCH para M1, M6 y M7.
    diaria: OBT_ACCION_DIA; panel: OBT_ACCION_MES (accion_key, anio_mes, fecha_ultima_cotizacion)."""
    from joblib import Parallel, delayed
    org = panel[["accion_key", "anio_mes", "fecha_ultima_cotizacion"]].rename(
        columns={"fecha_ultima_cotizacion": "fecha_origen"})
    grupos = [(k, g, org[org.accion_key == k]) for k, g in diaria.groupby("accion_key")]

    def una(k, g, o):
        return [{"accion_key": k, **f} for f in caracteristicas_accion(g, o, anios, **kw)]
    res = Parallel(n_jobs=n_jobs)(delayed(una)(k, g, o) for k, g, o in grupos)
    return pd.DataFrame([f for lista in res for f in lista])
