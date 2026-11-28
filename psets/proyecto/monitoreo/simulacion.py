"""Simulacion de produccion por lotes mensuales posteriores al corte del entrenamiento (PSet 4, seccion 5).

Cada lote es un cierre de mes desde 2023-12 (el primero cuyo objetivo, 2024-01, cae despues del corte) hasta el
ultimo mes cerrado de la OBT (2026-10): 35 lotes. Los 34 primeros tienen etiqueta; el de 2026-10 es el mes "en
vivo": se predice, pero su objetivo (noviembre de 2026) aun no existe.

Preparacion de inferencia (preparar_inferencia): las filas elegibles del mes tal como estan en la OBT, con las
derivadas de src.pipeline.derivar. A diferencia de preparar/dividir (entrenamiento), NO exige el objetivo ni
interpola huecos con meses posteriores: al servir solo se conoce el pasado. Una fila con alguna feature nula no se
envia a la API y se cuenta como invalida (alerta A3).

Horizonte: la etiqueta del lote t (retorno de t+1) solo se conoce al llegar el lote t+1. Al llegar el lote t:
  1. se etiqueta el lote t-1 (union de lo servido con el objetivo de la OBT) y se mide su desempeno;
  2. si la regla se dispara (rendimiento A7 o calendario de 12 lotes, con enfriamiento), se entrena un challenger
     con src.reentrenar y se aplica la regla de promocion; la promocion pasa por aprobar() (en Kestra, Pause);
  3. el champion predice el lote t y se arma la decision (top 10, 1/vol, tope de volatilidad);
  4. se mide la deriva del lote t y se evaluan las alertas.

Deriva inducida (docs/simulacion.md): en los lotes LOTES_DERIVA (2025-05 a 2025-07) todas las volatilidades x2, el
retorno del mes de cada accion y del mercado -10 % log y el OBJETIVO tambien -10 % log, como marzo de 2020. Solo en
la simulacion: las filas quedan con sintetico=True y nada se escribe en la OBT.
"""
from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np
import pandas as pd

from src.negocio import REGLA, pesos_mes
from src.operacion_manual import seleccion_mes
from src.pipeline import EXCLUIDAS, FEATURES_OBT, NUMERICAS, TARGET, derivar, dividir, preparar
from src.reentrenar import COLUMNAS, K_EVALUACION, entrenar_y_comparar

from .alertas import evaluar
from .deriva import Referencia, ReferenciaSalida

LOTES_DERIVA = (202505, 202506, 202507)
FACTOR_VOL = 2.0
CHOQUE_RET = -0.10
VOLATILIDADES = ["vol_21d", "vol_63d", "vol_apertura_21d", "vol_intradia_21d", "vol_parkinson_21d",
                 "vol_garman_klass_21d", "rango_log_hl_mes", "rango_log_hl_prom_21d", "rango_log_hl_prom_63d"]
RETORNOS_MES = ["ret_log_mes", "ret_log_21d", "intradia_log_mes", "ret_log_sp500_mes",
                "ret_log_nyse_composite_mes"]
PRIMER_LOTE = 202312
CALENDARIO = 12                      # lotes etiquetados entre reentrenamientos por calendario
ENFRIAMIENTO = 3                     # lotes etiquetados nuevos antes de volver a reentrenar
ETIQUETAS = ["accion_key", "anio_mes", TARGET, "ret_pct_mes_siguiente", "rf_mes_siguiente"]


def preparar_inferencia(obt: pd.DataFrame, mes: int) -> pd.DataFrame:
    """Filas elegibles del cierre de mes, listas para la API. No usa el objetivo ni meses posteriores."""
    d = obt[(obt["anio_mes"] == mes) & obt["elegible"].fillna(False).astype(bool)].copy()
    if "ticker" in d:
        d = d[~d["ticker"].astype(str).str.upper().isin(EXCLUIDAS)]
    for c in FEATURES_OBT:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = derivar(d)
    d[NUMERICAS] = d[NUMERICAS].replace([np.inf, -np.inf], np.nan).astype(float)
    d["sintetico"] = False
    return d.drop(columns=[c for c in ETIQUETAS[2:] if c in d]).reset_index(drop=True)


def inducir_deriva(lote: pd.DataFrame) -> pd.DataFrame:
    d = lote.copy()
    d[VOLATILIDADES] = d[VOLATILIDADES] * FACTOR_VOL
    d[RETORNOS_MES] = d[RETORNOS_MES] + CHOQUE_RET
    d["sintetico"] = True
    return derivar(d)                                          # recalcula dispersion_mes


def lote_del_mes(obt: pd.DataFrame, mes: int, deriva: tuple = LOTES_DERIVA) -> pd.DataFrame:
    lote = preparar_inferencia(obt, mes)
    return inducir_deriva(lote) if mes in deriva else lote


def etiquetas(obt: pd.DataFrame, deriva: tuple = LOTES_DERIVA) -> pd.DataFrame:
    """Objetivo de cada accion y mes (lo que llega un mes despues), con el choque de los lotes sinteticos."""
    e = obt[ETIQUETAS].copy()
    e[TARGET] = pd.to_numeric(e[TARGET], errors="coerce")
    e = e[e[TARGET].notna()]
    m = e["anio_mes"].isin(deriva)
    e.loc[m, TARGET] = e.loc[m, TARGET] + CHOQUE_RET
    e["ret_pct_mes_siguiente"] = np.expm1(e[TARGET])
    return e


def etiquetar(servido: pd.DataFrame, e: pd.DataFrame) -> pd.DataFrame:
    """Une lo servido con su objetivo; las acciones sin objetivo (dejaron de cotizar) quedan fuera del MAE."""
    return servido.merge(e, on=["accion_key", "anio_mes"], how="inner")


def meses_produccion(obt: pd.DataFrame) -> list[int]:
    return [int(m) for m in sorted(obt.loc[obt["anio_mes"] >= PRIMER_LOTE, "anio_mes"].unique())]


def decidir(lote: pd.DataFrame, pred: np.ndarray) -> pd.DataFrame:
    lote = lote.assign(pred=pred)
    w = pesos_mes(lote, "pred", vol=REGLA["vol"], n=REGLA["n"], tope_percentil=REGLA["tope_percentil"])
    lote["peso"] = lote["accion_key"].map(w).fillna(0.0)
    lote["decision"] = np.where(lote["peso"] > 0, "incluir", "no incluir")
    # competidor B7 (operacion manual), en paralelo: lo mismo que devuelve la API
    lote["peso_manual"] = lote["accion_key"].map(seleccion_mes(lote)).fillna(0.0)
    lote["decision_manual"] = np.where(lote["peso_manual"] > 0, "incluir", "no incluir")
    return lote


def simular(champion, obt: pd.DataFrame, deriva: tuple = LOTES_DERIVA, aprobar: Callable | None = None,
            version_inicial: str = "1", k_evaluacion: int = K_EVALUACION, enfriamiento: int = ENFRIAMIENTO) -> dict:
    """k_evaluacion y enfriamiento permiten el analisis de sensibilidad de la regla (notebook 06)."""
    aprobar = aprobar or (lambda comp: comp.promueve)
    entrenamiento, _ = dividir(preparar(obt))
    e = etiquetas(obt, deriva)
    ref = Referencia(entrenamiento, [c for c in COLUMNAS if c != "anio_mes"])
    salida = ReferenciaSalida(champion.predict(entrenamiento[COLUMNAS]), entrenamiento["anio_mes"].to_numpy())
    etiquetados = entrenamiento.copy()
    version, n_version = version_inicial, 0
    desde_entreno, enfriar, pendiente_a7 = 0, 0, False
    servidos, monitoreo, alertas, reentrenos = [], [], [], []
    for mes in meses_produccion(obt):
        completo = lote_del_mes(obt, mes, deriva)
        lote = completo.dropna(subset=FEATURES_OBT)
        # 1. etiqueta del lote anterior
        if servidos:
            previo = etiquetar(servidos[-1].drop(columns=["pred", "peso", "decision", "modelo_version", "peso_manual",
                                                          "decision_manual"]), e)
            etiquetados = pd.concat([etiquetados, previo], ignore_index=True)
            desde_entreno += 1
            enfriar = max(0, enfriar - 1)
        # 2. reentrenamiento
        por_calendario = desde_entreno >= CALENDARIO
        if (pendiente_a7 or por_calendario) and enfriar == 0:
            motivo = "rendimiento (A7)" if pendiente_a7 else "calendario (12 lotes)"
            challenger, comp = entrenar_y_comparar(champion, etiquetados, k_evaluacion)
            aprobado = bool(aprobar(comp))
            n_version += 1
            reentrenos.append({"anio_mes_llegada": int(mes), "disparador": motivo, "version_champion": version,
                               "version_challenger": f"r{n_version}", "aprobado": aprobado, **comp.como_dict()})
            if aprobado:
                champion, version = challenger, f"r{n_version}"
                salida = ReferenciaSalida(champion.predict(entrenamiento[COLUMNAS]), entrenamiento["anio_mes"].to_numpy())
            desde_entreno, enfriar, pendiente_a7 = 0, enfriamiento, False
        # 3. prediccion y decision
        inicio = time.perf_counter()
        pred = champion.predict(lote[COLUMNAS])
        latencia = (time.perf_counter() - inicio) * 1000
        lote = decidir(lote, pred).assign(modelo_version=version)
        servidos.append(lote)
        # 4. monitoreo del lote t (datos y salida) y del rendimiento hasta t-1
        hist = etiquetar(pd.concat(servidos[:-1], ignore_index=True), e) if len(servidos) > 1 else None
        sistema = {"latencia_p50_ms": latencia, "latencia_p95_ms": latencia, "solicitudes": 1, "errores_4xx": 0,
                   "errores_5xx": 0, "pct_invalidas": 100 * (len(completo) - len(lote)) / max(len(completo), 1)}
        m = metricas_lote(ref, salida, completo, lote, hist, pd.concat(servidos[-12:]), sistema)
        monitoreo.append({**m, "modelo_version": version})
        disparadas = evaluar(m)
        alertas += [{**a, "modelo_version": version} for a in disparadas]
        pendiente_a7 = pendiente_a7 or any(a["id_alerta"] == "A7" for a in disparadas)
    pred = pd.concat(servidos, ignore_index=True)
    return {"predicciones": pred.merge(e, on=["accion_key", "anio_mes"], how="left"),
            "monitoreo": pd.DataFrame(monitoreo), "alertas": pd.DataFrame(alertas),
            "reentrenamientos": pd.DataFrame(reentrenos)}


def metricas_lote(ref: Referencia, salida: ReferenciaSalida, completo: pd.DataFrame, lote: pd.DataFrame,
                  hist: pd.DataFrame | None, ventana: pd.DataFrame | None, sistema: dict) -> dict:
    """Metricas de un lote. completo: todas las filas elegibles del mes (para nulos); lote: las enviadas, con
    pred, peso y decision; hist: lotes anteriores ya etiquetados; sistema: metricas de la API en la ventana del
    lote (o las medidas en memoria en la simulacion)."""
    d = ref.evaluar(completo, ventana)
    num = d[d["tipo"] == "numerica"]
    feats = d[d["tipo"].isin(["numerica", "mercado"])]
    m = {"anio_mes": int(lote["anio_mes"].iloc[0]), "n_acciones": int(len(completo)), "n_enviadas": int(len(lote)),
         "sintetico": bool(lote["sintetico"].any()), **sistema,
         "pct_nulos_max": float(feats["pct_nulos"].max()), "feature_nulos_max": str(feats.loc[feats["pct_nulos"].idxmax(), "feature"]),
         "pct_fuera_rango_max": float(feats["pct_fuera_rango"].max()),
         "feature_fuera_rango_max": str(feats.loc[feats["pct_fuera_rango"].idxmax(), "feature"]),
         "n_features_fuera_rango": int((feats["pct_fuera_rango"] > 5).sum()),
         "categorias_no_vistas": int(d.loc[d["tipo"] == "categorica", "no_vistas"].fillna(0).sum()),
         "n_psi_alerta": int((num["estado"] == "alerta").sum()), "n_psi_critico": int((num["estado"] == "critico").sum()),
         "psi_max": float(num["psi"].max()), "feature_psi_max": str(num.loc[num["psi"].idxmax(), "feature"]),
         "n_ks_p001": int((num["ks_p"] < 0.01).sum()),
         "n_mercado_z3": int(((d["tipo"] == "mercado") & (d["estado"] == "critico")).sum()),
         "pred_media": float(lote["pred"].mean()), "pred_de": float(lote["pred"].std()),
         "z_pred_media": salida.z(lote["pred"].to_numpy())[0], "z_pred_de": salida.z(lote["pred"].to_numpy())[1],
         "n_incluidas": int((lote["peso"] > 0).sum()), "tasa_incluir": float((lote["peso"] > 0).mean()),
         "mae_ultimo": None, "mae_penultimo": None, "direccional_ultimo": None, "retorno_ultimo": None,
         "retorno_b5_ultimo": None, "retorno_manual_ultimo": None, "sharpe_12": None, "sharpe_b5_12": None,
         "sharpe_manual_12": None,
         "coinciden_manual": int(((lote["peso"] > 0) & (lote["peso_manual"] > 0)).sum()) if "peso_manual" in lote else None}
    if hist is not None and len(hist):
        por_mes = []
        for mes, g in hist.groupby("anio_mes"):
            r = g.set_index("accion_key")["ret_pct_mes_siguiente"]
            por_mes.append({"mes": mes, "mae": float(np.mean(np.abs(g[TARGET] - g["pred"]))),
                            "dir": float(np.mean(np.sign(g[TARGET]) == np.sign(g["pred"]))),
                            "ret": float((g.set_index("accion_key")["peso"] * r).sum()),
                            "b5": float(r.mean()), "rf": float(g["rf_mes_siguiente"].iloc[0]),
                            "manual": float((g.set_index("accion_key")["peso_manual"] * r).sum())
                            if "peso_manual" in g else np.nan})
        p = pd.DataFrame(por_mes)
        m.update({"mae_ultimo": p["mae"].iloc[-1], "mae_penultimo": p["mae"].iloc[-2] if len(p) >= 2 else None,
                  "direccional_ultimo": p["dir"].iloc[-1], "retorno_ultimo": p["ret"].iloc[-1],
                  "retorno_b5_ultimo": p["b5"].iloc[-1], "retorno_manual_ultimo": p["manual"].iloc[-1]})
        if len(p) >= 12:
            u = p.tail(12)
            sh = lambda x: float((x - u["rf"]).mean() / (x - u["rf"]).std(ddof=1) * np.sqrt(12))
            m.update({"sharpe_12": sh(u["ret"]), "sharpe_b5_12": sh(u["b5"]),
                      "sharpe_manual_12": sh(u["manual"]) if u["manual"].notna().all() else None})
    return m
