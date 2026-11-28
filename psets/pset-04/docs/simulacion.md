# Simulación de producción por lotes

**Lotes.** Los cierres de mes posteriores al corte del entrenamiento se pasan por el sistema como **35 lotes
mensuales**, en orden: 2023-12 a 2026-09 (34 lotes, el hold-out del PSet 3, con objetivo) y 2026-10, el mes "en vivo",
cuyo objetivo (noviembre de 2026) aún no existe: se predice y se monitorea, pero nunca se etiqueta. Cada lote es el corte
transversal de un cierre de mes: 327–340 acciones elegibles (S&P 500 ∩ NYSE) leídas de
`PORTAFOLIO_P4.OBT.OBT_ACCION_MES`.

**Preparación de inferencia.** `monitoreo.simulacion.preparar_inferencia` toma las filas elegibles del mes tal como
están en la OBT y calcula las dos derivadas con `src.pipeline.derivar`. A diferencia de `preparar`/`dividir`
(entrenamiento), no exige el objetivo ni interpola huecos con meses posteriores: al servir solo se conoce el pasado.
Una fila con alguna feature nula no se envía y cuenta como inválida (A3). Las etiquetas se unen después
(`etiquetar`), cuando llegan.

**Dos formas de correrla, mismo código.**

| | Kestra (producción) | Notebook 06 (análisis) |
|---|---|---|
| Entrada | Snowflake, `produccion_lotes.yml` | `modelos/data/obt_p4.parquet` |
| Predicción | `POST /predecir` de la API (contenedor) | El mismo modelo en memoria |
| Reentrenamiento | `reentrenamiento.yml`, registro en MLflow, `Pause` con aprobación humana | `src.reentrenar`, aprobación simulada = regla |
| Salida | `PRODUCCION.{PREDICCIONES, MONITOREO, ALERTAS, REENTRENAMIENTOS}` → `docs/*.csv` | `docs/simulacion/*.csv` |

Se verificó que dan lo mismo: los 35 lotes por la API (con una copia del registro) producen los mismos
reentrenamientos, decisiones y alertas que la simulación en memoria.

**Horizonte.** La etiqueta del lote *t* es el retorno del mes *t+1*: se conoce al llegar el lote *t+1*. El MAE, el
acierto direccional y el retorno del portafolio se calculan siempre con un lote de retraso, y el reentrenamiento
solo usa lotes etiquetados (`monitoreo/simulacion.py`, paso 1; `monitoreo/produccion.py`, `reentrenar`).

## Deriva inducida

Los lotes **2025-05, 2025-06 y 2025-07** se reemplazan por un escenario sintético de crisis inspirado en marzo de
2020 (`monitoreo.simulacion.inducir_deriva`):

| Qué cambia | Cuánto | Por qué |
|---|---|---|
| 9 features de volatilidad y rango (vol_21d, vol_63d, Parkinson, Garman-Klass, rangos) | × 2 | En marzo de 2020 la volatilidad del S&P 500 se multiplicó por más de 3; ×2 es un choque grave pero dentro del contrato de la API (no lo rechaza la validación). |
| Retornos del mes de cada acción y del mercado | −10 % log | Un mes de caída generalizada. |
| **Objetivo** (retorno del mes siguiente) | −10 % log | La caída continúa: hay deriva de concepto, no solo de datos. |

Las filas quedan con `sintetico = True` en `PREDICCIONES` y en `MONITOREO`; nada se escribe en la OBT.

Primero se probó deriva solo en las features (volatilidades ×2 y ×3 sin tocar el objetivo): el MAE del lote 2025-07
pasó de 0,0481 a 0,0495 y 0,0508. La deriva de datos sola casi no mueve el MAE porque el error está dominado por el
ruido del retorno; por eso el escenario también desplaza el objetivo.

## Qué detectó el sistema en los lotes con deriva

| Lote | Datos (A4: ≥ 5 features con PSI crítico) | Concepto (A7: MAE > 0,0801 en 2 lotes seguidos) | Negocio (A8: Sharpe 12 lotes < B5 − 0,5) |
|---|---|---|---|
| 2025-05 | 7 features críticas | se mide el lote 2025-04: 0,055 | sí (−0,47 frente a 0,30) |
| 2025-06 | 5 | se mide 2025-05 (primero inducido): 0,093 | sí |
| 2025-07 | 6 | se mide 2025-06: 0,129; con 2025-05 sobre el umbral, **A7** | sí |

El MAE de cada lote se conoce un lote después. La A7 del monitoreo de 2025-07 dispara el reentrenamiento al llegar
**2025-08**: el challenger se entrena con los lotes etiquetados hasta 2025-06 y se compara con el champion en 2025-07,
el último lote etiquetado, que ninguno vio. El ciclo completo está en `docs/reentrenamiento.md`.
