# Patrón de despliegue: batch mensual

**Decisión: predicción por lotes (batch) una vez al mes, servida por una API que el orquestador llama con el lote
completo.** No se despliega un servicio en línea para usuarios finales.

## Por qué batch, con números

| Pregunta | Respuesta del caso | Consecuencia |
|---|---|---|
| ¿Cuándo se toma la decisión? | Al cierre de cada mes el asesor arma el portafolio del mes siguiente (regla del PSet 1: rebalanceo mensual, top 10, pesos 1/vol). | Hay **una** decisión al mes, no una por petición. |
| ¿Cuánto tiempo hay para responder? | Entre el cierre (viernes 16:00 NY) y la apertura del primer día hábil siguiente: ≥ 17 h, normalmente 65 h (fin de semana). | Un plazo de horas; el modelo predice el lote de 333 acciones en ~**9 ms** (medido en la VM); en producción, la petición completa de un lote a la API en Docker tarda **41,9 ms** (mediana de los 35 lotes; una petición por lote) y el pipeline completo (ingesta + dbt + Spark) tarda minutos. |
| ¿Cada cuánto llegan datos nuevos? | Precios diarios (ingesta_diaria 18:30 NY), pero las features son de cierre de mes: cambian **una vez al mes**. | Predecir más seguido daría la misma respuesta 20 días seguidos. |
| ¿Cuántas predicciones? | Una por acción elegible del mes: 327–337 por lote (S&P 500 ∩ NYSE), ~4.000 al año. | Volumen trivial; no justifica autoescalado ni baja latencia. |
| ¿Cuánto cuesta una predicción desactualizada? | Un mes con el portafolio equivocado: en la simulación el retorno mensual del top 10 tiene desviación de ~5 %; con US$ 100.000, un mes mal armado puede costar del orden de US$ 5.000. | Lo que importa es que el lote esté **completo y correcto** antes de la apertura, no la latencia. |

Por eso el patrón es batch: Kestra corre `produccion_lotes` al cierre de mes, lee el lote de la OBT en Snowflake,
llama a `POST /predecir` con todas las acciones a la vez (la decisión necesita el corte transversal: el top 10 y el
tope de volatilidad son relativos al mes) y guarda cada predicción en `PRODUCCION.PREDICCIONES`.

La API existe aunque el patrón sea batch porque (a) separa el modelo del orquestador: el modelo se cambia moviendo
un alias de MLflow sin tocar Kestra ni reconstruir imágenes; (b) valida el contrato de entrada (422 con el campo
que falla); y (c) permite al asesor pedir la propuesta de un mes a demanda o simular un "qué pasa si" con un lote
modificado.

## Qué se pierde con online, y qué tendría que cambiar para preferirlo

Con un servicio en línea (una petición por acción, en tiempo real) se perdería:

- **La decisión correcta**: con una sola acción la regla se reduce a cumplir el tope de volatilidad; el top 10 y el
  percentil 80 de volatilidad exigen ver todo el mes. `/predecir` acepta una acción, pero la decisión solo tiene
  sentido con el lote.
- **Reproducibilidad y trazabilidad simples**: un lote = un snapshot de la OBT (huella md5) = una versión del
  modelo. En línea habría que versionar cada consulta contra datos que cambian durante el día.
- **Costo y operación**: un servicio 24/7 con monitoreo de latencia para ~4.000 predicciones al año.

Se preferiría online si el caso de uso cambiara a:

1. **Rebalanceo intradía o por señales** (p. ej. alertas de noticias o de un salto de volatilidad que obliguen a
   reducir una posición en minutos): la decisión pasaría a ser por evento y la latencia sí importaría.
2. **Usuarios que consultan su propio portafolio** con datos que ellos ingresan (cartera actual, perfil de riesgo):
   la predicción dependería de una entrada que no existe en el lote mensual.
3. **Features diarias** (el modelo usa retornos y volatilidades de cierre de mes; con features que cambian cada día
   la predicción también lo haría).

Ninguno está en el alcance del PSet 1 (ejecución automática fuera de alcance; rebalanceo mensual).
