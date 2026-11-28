"""Plantilla de alertas (seccion 6.3 del PDF: metrica, umbral, ventana, severidad, quien la recibe, accion) y su
evaluacion por lote. monitoreo.yml (Kestra) escribe las que se disparan en PRODUCCION.ALERTAS y manda un correo si
hay criticas. Los umbrales de rendimiento salen de la validacion cruzada del PSet 3 (MAE 0,0641 +/- 0,016 en 7
pliegues de 12 meses); los de deriva, de la historia de entrenamiento (monitoreo/deriva.py)."""
from __future__ import annotations

import pandas as pd

MAE_CV, DE_CV = 0.0641, 0.016
UMBRAL_MAE = MAE_CV + DE_CV                      # 0,0801
LOTES_A7 = 2                                     # lotes etiquetados seguidos sobre el umbral

PLANTILLA = pd.DataFrame([
    ("A1", "sistema", "errores 5xx de la API", "> 0", "desde el envio del lote", "critico", "ingeniero de ML",
     "Revisar logs; si el modelo no carga, el respaldo B1+B5 ya responde. Recargar o revertir el alias."),
    ("A2", "sistema", "latencia p95 de /predecir", "> 2.000 ms", "desde el envio del lote", "alerta", "ingeniero de ML",
     "Revisar memoria del contenedor y tamano del lote; hay horas antes de la apertura."),
    ("A3", "datos", "filas no enviadas por nulos o rechazadas (422), o categorias no vistas", "> 2 % o >= 1",
     "1 lote", "alerta", "ingeniero de datos", "Revisar la ingesta y los tests de dbt del mes; no reentrenar con el lote."),
    ("A4", "datos", "features por accion con PSI sobre su umbral critico (KS como respaldo)", ">= 5", "1 lote",
     "critico", "cientifico de datos",
     "Diagnosticar: error de captura (comparar con la fuente) o cambio real de mercado. No reentrenar por esto solo."),
    ("A5", "datos", "features de mercado con |z| frente a la historia mensual", "> 3 (>= 1 feature)", "1 lote",
     "alerta", "cientifico de datos", "Mes atipico: revisar el tope de volatilidad; informar al asesor."),
    ("A6", "modelo", "media o dispersion de las predicciones, |z| frente a los meses de entrenamiento", "> 3",
     "1 lote", "alerta", "cientifico de datos", "Revisar que sigan 10 incluidas y la estabilidad del top 10."),
    ("A7", "modelo", "MAE de cada lote etiquetado", f"> {UMBRAL_MAE:.4f} (media CV + 1 de)",
     f"{LOTES_A7} lotes etiquetados seguidos", "critico", "cientifico de datos",
     "Deriva de concepto: dispara reentrenamiento.yml; la promocion espera aprobacion humana."),
    ("A8", "negocio", "Sharpe del portafolio menos Sharpe de B5", "< -0,5", "12 lotes etiquetados", "critico",
     "responsable del producto", "Criterio de retirada R1: interruptor de respaldo y revision con el asesor."),
    ("A9", "negocio", "Sharpe del portafolio menos Sharpe de la operacion manual (B7)", "< -0,5", "12 lotes etiquetados",
     "critico", "responsable del producto",
     "Criterio de retirada R6: el asesor opera con la operacion manual y el modelo queda en paralelo hasta superarla."),
], columns=["id", "capa", "metrica", "umbral", "ventana", "severidad", "quien_la_recibe", "accion"])


def _sobre(x) -> bool:
    return x is not None and x == x and x > UMBRAL_MAE


def evaluar(m: dict) -> list[dict]:
    """m: metricas de un lote (monitoreo.simulacion.metricas_lote). Devuelve las alertas disparadas."""
    reglas = {
        "A1": (m.get("errores_5xx") or 0) > 0,
        "A2": (m.get("latencia_p95_ms") or 0) > 2000,
        "A3": (m.get("pct_invalidas") or 0) > 2.0 or (m.get("categorias_no_vistas") or 0) >= 1,
        "A4": (m.get("n_psi_critico") or 0) >= 5,
        "A5": (m.get("n_mercado_z3") or 0) >= 1,
        "A6": max(m.get("z_pred_media") or 0, m.get("z_pred_de") or 0) > 3,
        "A7": _sobre(m.get("mae_ultimo")) and _sobre(m.get("mae_penultimo")),
        "A8": m.get("sharpe_12") is not None and m["sharpe_12"] - m["sharpe_b5_12"] < -0.5,
        "A9": m.get("sharpe_manual_12") is not None and m.get("sharpe_12") is not None
              and m["sharpe_12"] - m["sharpe_manual_12"] < -0.5,
    }
    filas = PLANTILLA.set_index("id")
    return [{"id_alerta": k, "anio_mes": m["anio_mes"], **filas.loc[k].to_dict()} for k, v in reglas.items() if v]
