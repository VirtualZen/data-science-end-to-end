# Monitoreo

Código: `monitoreo/deriva.py` (pruebas de deriva y calidad), `monitoreo/alertas.py` (plantilla y reglas),
`monitoreo/produccion.py monitorear` (lo que corre Kestra en `monitoreo.yml` después de cada lote), notebook
`modelos/notebooks/07_analisis_monitoreo.ipynb` (análisis y figuras), tablero `monitoreo/tablero.py`. Resultado por lote
en `PRODUCCION.MONITOREO` (exportado a `docs/monitoreo.csv`) y alertas en `PRODUCCION.ALERTAS` (`docs/alertas.csv`).

## Métricas por capa (PDF 6.1)

| Capa | Métrica | De dónde sale |
|---|---|---|
| Sistema | latencia p50 y p95 de `/predecir`, solicitudes, errores 4xx y 5xx | `GET /metricas?desde=…` de la API: ventana desde 30 s antes del envío del lote hasta el monitoreo |
| Sistema / datos | % de filas del lote no enviadas (nulos) o rechazadas (422) | `monitorear`: elegibles del mes frente a predicciones guardadas |
| Datos | % de nulos y % fuera del rango de entrenamiento, **por feature** (máximo y feature en `MONITOREO`; detalle en `DERIVA`) | `deriva.Referencia.evaluar` |
| Datos | categorías no vistas en entrenamiento (`mes_calendario_obj`) | idem |
| Datos | PSI por feature por acción (28) + KS; z mensual de las 6 de mercado; χ² de `hubo_retorno_extremo_mes` (lote) y de `mes_calendario_obj` (12 lotes) | idem, contra el entrenamiento 2013-2023 |
| Modelo | distribución de las predicciones (media, desviación, z frente a los meses de entrenamiento) y tasa de cada decisión (incluir / no incluir) | `metricas_lote` |
| Modelo | MAE y acierto direccional de cada lote **cuando llega su objetivo** (un lote después) | idem |
| Negocio | retorno del portafolio, de B5 y de la operación manual (B7) en el último lote etiquetado; Sharpe de 12 lotes de los tres; acciones que el modelo y la operación manual eligen en común | idem; la decisión de B7 la devuelve la API en paralelo (`decision_operacion_manual`) y queda en `PREDICCIONES` |

## Umbrales y su justificación

- **PSI** (decide la alerta): el PSI de un mes de entrenamiento contra todo el entrenamiento ya no es 0 (cada mes es una
  muestra de ~330 acciones y el mercado cambia). Para cada feature se calculó el PSI de los 132 meses de 2013-2023:
  **alerta = max(0,10; p95 histórico)**, **crítico = max(0,25; p99 histórico)**. Los pisos son los convencionales; el
  percentil evita alertar todos los meses en features que por naturaleza cambian mucho entre meses (las de rango y
  volatilidad tienen p99 de 4–6). Tabla completa en el notebook 07, sección 2.
- **KS** (respaldo): se reporta el estadístico y el p-valor (< 0,01), pero no decide: con 330 filas contra una muestra de
  5.000, casi cualquier diferencia es "significativa"; la magnitud la da el PSI.
- **z de mercado**: alerta > 2, crítico > 3 desviaciones de la historia mensual. **χ²**: alerta p < 0,01, crítico p < 0,001.
- **A4 (≥ 5 features críticas)**: con 3 se disparaba en meses normales (2024-12, 2026-04: 3 críticas); con 5, en el choque
  real de abril de 2025 (8) y en los tres lotes inducidos (5–7).
- **A7**: MAE > media de la CV + 1 desviación = 0,0641 + 0,016 = **0,0801** en **2 lotes etiquetados seguidos**. Un
  mes aislado sobre 0,080 ocurre en 8 de los 34 lotes del hold-out; dos seguidos, en episodios (fines de 2024, la
  crisis inducida, febrero-marzo de 2026).
- **A8 y A9 (Sharpe 12 lotes 0,5 bajo B5 o bajo la operación manual)**: una diferencia de medio punto de Sharpe en un año
  no se explica por un par de meses malos. A8 compara con la línea base de negocio del PSet 3 (B5, criterio R1); A9 con el
  competidor más fuerte, la operación manual (B7, criterio R6).

## Plantilla de alertas (PDF 6.3)

| Id | Métrica | Umbral | Ventana | Severidad | Quién la recibe | Acción |
|---|---|---|---|---|---|---|
| A1 | errores 5xx de la API | > 0 | desde el envío del lote | crítico | ingeniero de ML | Revisar logs; si el modelo no carga, el respaldo B1+B5 ya responde. Recargar o revertir el alias. |
| A2 | latencia p95 de `/predecir` | > 2.000 ms | desde el envío del lote | alerta | ingeniero de ML | Revisar memoria del contenedor y tamaño del lote. |
| A3 | filas no enviadas (nulos) o rechazadas (422); categorías no vistas | > 2 %; ≥ 1 | 1 lote | alerta | ingeniero de datos | Revisar ingesta y tests de dbt del mes; no reentrenar con el lote. |
| A4 | features por acción con PSI sobre su umbral crítico (KS de respaldo) | ≥ 5 | 1 lote | crítico | científico de datos | Diagnosticar captura vs. mercado; no reentrenar por esto solo. |
| A5 | features de mercado con \|z\| | > 3 (≥ 1) | 1 lote | alerta | científico de datos | Mes atípico: revisar el tope de volatilidad; informar al asesor. |
| A6 | media o dispersión de las predicciones, \|z\| | > 3 | 1 lote | alerta | científico de datos | Revisar estabilidad del top 10. |
| A7 | MAE de cada lote etiquetado | > 0,0801 | 2 lotes etiquetados seguidos | crítico | científico de datos | Disparar `reentrenamiento.yml`; promoción solo con aprobación. |
| A8 | Sharpe del portafolio − Sharpe de B5 | < −0,5 | 12 lotes etiquetados | crítico | responsable del producto | Criterio de retirada R1: interruptor de respaldo y revisión con el asesor. |
| A9 | Sharpe del portafolio − Sharpe de la operación manual (B7) | < −0,5 | 12 lotes etiquetados | crítico | responsable del producto | Criterio R6: el asesor opera con la operación manual y el modelo queda en paralelo hasta superarla. |

Las críticas mandan un correo (`monitoreo.yml`, tarea `correo`, con la cuenta de `AVISO_CORREO`); todas quedan en el log
de Kestra y en `ALERTAS`.

## Tabla de diagnóstico (PDF 6.2)

| Entradas | Desempeño | Diagnóstico | Acción en el proyecto |
|---|---|---|---|
| Cambian | Se mantiene | Deriva de datos sin impacto | A4/A5 de aviso; diagnosticar captura vs. mercado; **no** se reentrena. Casos: tasa ~5 % en 2024; aranceles en abril de 2025. |
| Cambian | Cae | Deriva de datos con impacto | A4 + A7: reentrenar con los lotes etiquetados; si el challenger no gana, criterio de retirada (A8 → respaldo). Caso: la crisis inducida. |
| Estables | Cae | Deriva conceptual | A7 sin A4: reentrenar. Casos: fines de 2024, febrero-marzo de 2026. |

## Diagnóstico de los lotes con alertas (simulación, 35 lotes)

| Lotes | Alertas | Diagnóstico | Acción |
|---|---|---|---|
| 2024-04, 05, 07, 08 | A5 | `rf_mes` con z > 3: la tasa libre de riesgo (~5,3 % anual) está lejos de 2013-2023 (media 0,9 %). Deriva real de una variable de mercado; el MAE no cambia. | Ninguna sobre el modelo; se informa. |
| 2024-12 | A7 | MAE de 2024-10 y 2024-11: 0,097 y 0,102 (meses de retornos extremos). Deriva de concepto real. | Ya corrió el reentrenamiento por calendario al llegar 2024-12 (r1, promovido); la A7 queda pendiente y dispara al llegar 2025-03 (r2, rechazado). |
| 2025-04 | A4 | 8 features de volatilidad y volumen con PSI crítico: el choque de abril de 2025 (aranceles). Deriva de datos sin deriva de concepto (MAE 0,055). | No se reentrena por deriva de datos. |
| 2025-05 a 07 | A4, A8 (+A7 en 07) | **Deriva inducida**: datos y concepto cambian a la vez. | Reentrenamiento al llegar 2025-08 (r3, rechazado); criterio de retirada R1. |
| 2025-08 a 10 y 2025-12 | A8 (+A7 en 2025-08) | Arrastre de la crisis: el Sharpe de 12 lotes sigue 0,5–0,8 bajo B5. | Respaldo mientras dura; revisión humana. |
| 2026-03 | A7 | MAE de 2026-02 y 2026-03: 0,089 y 0,111 (caída real del mercado en febrero). | Reentrenamiento al llegar 2026-04 (r5, promovido). |

Tabla por lote completa: `docs/diagnostico_lotes.csv`. Figuras: `docs/figuras/{psi_por_lote, mae_por_lote,
sharpe_12_lotes}.png`.

**A9** se enciende en 14 lotes en la simulación y en 13 en producción (la diferencia es 2026-09, `docs/reconciliacion.md`): desde 2024-12, cuando hay 12 lotes de historia, hasta
2025-12, y otra vez en 2026-09. El modelo y la operación manual casi no eligen las mismas acciones (0 a 2 de 10 por lote).
No es una falsa alarma: es la evidencia de que la regla simple le gana al modelo (`docs/simulacion/competidores.csv`).

## Falsas alarmas y ajuste de umbrales

El PDF pide que los lotes sin alterar no disparen la alerta. En los 32 lotes reales:

- **A4 en 2025-04** (1 lote): no es error de datos sino un choque real (aranceles), sin impacto en el MAE. Subir el umbral a
  9 features la silenciaría, pero también la detección del lote inducido 2025-06 (5). Se deja en 5, como alerta de
  diagnóstico que no reentrena.
- **A5 en 2024** (4 lotes): es falsa alarma para el modelo: el entrenamiento casi no tuvo tasas altas. Ajuste propuesto: medir
  el z contra los últimos 36 meses, no contra todo el entrenamiento, o dejar A5 como informativa sin correo.
- **A7 en lotes reales** (2024-12, 2026-03): meses con caídas reales; es deriva conceptual transitoria, no falsa. El
  enfriamiento de 3 lotes evita reentrenar cada mes.
- **A8 después de la crisis** (2025-08 a 10 y 2025-12): la ventana de 12 lotes todavía incluye los meses inducidos; es efecto de la
  ventana. Ajuste: excluir los lotes marcados `sintetico` del cálculo, o ventana de 6 lotes para la retirada.

## Tablero

`monitoreo/tablero.py` (Streamlit), servicio `tablero` del `docker-compose.yml` (http://localhost:8501). Lee
`PRODUCCION.MONITOREO`, `ALERTAS` y `REENTRENAMIENTOS` (o, con `--csv`, los CSV de `docs/`) y muestra lote por lote las
alertas, el MAE con su umbral, el Sharpe frente a B5, las features con PSI crítico y la latencia, con los
reentrenamientos marcados (líneas: verde promovido, gris rechazado) y los lotes inducidos sombreados.
