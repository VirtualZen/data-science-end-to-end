# Ética, criterios de retirada y supervisión humana

## 1. Desempeño por subgrupo

El universo no trae sector (la fuente de listados no lo publica), así que los subgrupos son los que deciden a quién se
le asigna capital: **tamaño** (quintil de dólares negociados del mes) y **volatilidad** (quintil de `vol_63d`). 31 lotes
reales etiquetados de la simulación (sin los 3 sintéticos), `docs/simulacion/subgrupos.csv`:

| Subgrupo | MAE | Acierto direccional | Tasa de "incluir" | Retorno medio de las incluidas |
|---|---|---|---|---|
| Tamaño Q1 (pequeñas) | 0,0686 | 44,5 % | 2,6 % | **−3,4 %** |
| Tamaño Q2–Q4 | 0,068–0,070 | 44,7–46,6 % | 2,8–3,2 % | 1,1–2,4 % |
| Tamaño Q5 (grandes) | 0,0692 | 47,1 % | 3,4 % | 3,8 % |
| Volatilidad Q1 (baja) | 0,0537 | 42,1 % | 3,2 % | 1,6 % |
| Volatilidad Q4 | 0,0746 | 47,0 % | 7,0 % | 1,2 % |
| Volatilidad Q5 (alta) | 0,0912 | 47,8 % | 0 % (tope) | — |

**¿Es aceptable la diferencia?** El error es parejo por tamaño (0,068–0,070), pero las pocas acciones **pequeñas** que el
modelo elige rinden −3,4 % al mes en promedio frente a +1,1 a 3,8 % del resto. Para el negocio no es aceptable sin control:
es el subgrupo que más le cuesta al cliente, y por eso tiene su propio criterio de retirada (R3). Para las personas
afectadas —el inversionista, que asume la pérdida— la diferencia es material: con US$ 10.000 por posición, −3,4 % son
~US$ 340 por acción pequeña incluida y por mes. Las empresas no resultan "afectadas" en un sentido ético: el modelo no
les niega un servicio. El MAE crece con la volatilidad (más ruido) y el quintil más volátil nunca entra por el tope del PSet
1, una exclusión deliberada que protege al cliente.

## 2. Costo de cada tipo de error y quién lo asume (US$ 100.000, 10 posiciones)

| Error | Qué es | Frecuencia por lote | Costo por lote (mediana / máximo) | Quién lo asume |
|---|---|---|---|---|
| Sobreestimación (falso positivo) | Se incluye una acción que el mes siguiente cae | 4,2 de 10 | US$ 1.638 / US$ 10.167 de pérdida real | **El inversionista** (su capital); el **asesor**, en confianza y en riesgo de que el cliente se vaya |
| Subestimación (falso negativo) | Una del top 10 real del mes queda fuera | 9,6 de 10 | US$ 17.846 / US$ 44.892 de ganancia no obtenida frente a lo incluido | **El inversionista** como costo de oportunidad, sin pérdida de capital; la **casa de valores** si el cliente compara con el índice |

La sobreestimación es el error **más caro para el cliente**: es dinero que pierde. La subestimación es casi inevitable
(acertar los 10 mejores de 330 es predecir extremos). Por eso la regla prioriza controlar el riesgo (pesos 1/vol, tope de
volatilidad, tope de portafolio de 1,35 × S&P 500) y no maximizar aciertos.

## 3. Criterios de retirada

| Id | Métrica | Umbral | Respuesta |
|---|---|---|---|
| **R1** | Sharpe de los últimos 12 lotes del portafolio menos el de B5 (alerta A8) | < −0,5 durante 3 lotes seguidos | Activar el **interruptor de respaldo** (B5: universo con igual peso, que no depende del modelo) y revisar con el asesor. Se vuelve al modelo cuando la diferencia sea > −0,5 por 3 lotes. |
| **R2** | Drawdown del portafolio desde su máximo | < −25 % (el cliente del PSet 1 tolera −20 %) | Pasar a efectivo la fracción que exceda el tope de volatilidad y avisar al cliente; revisión humana antes de rearmar. |
| **R3** | Retorno medio de las acciones pequeñas (Q1 de tamaño) incluidas, 12 lotes | < −2 % | Excluir Q1 de tamaño de las candidatas hasta reentrenar y revisar. |
| **R4** | Disponibilidad: errores 5xx o el modelo no carga (A1) | cualquier lote | La API ya responde con el respaldo marcado (`respaldo: true`); recargar o revertir el alias (`docs/reentrenamiento.md`). |
| **R5** | Dos reentrenamientos seguidos rechazados con A7 activa | 2 | Retirar el modelo: volver a experimentación (PSet 3) con features nuevas; mientras, respaldo. |
| **R6** | Sharpe de 12 lotes del modelo menos el de la operación manual (alerta A9) | < −0,5 durante 3 lotes | El asesor opera con la operación manual (la API ya devuelve su decisión en paralelo); el modelo sigue en sombra hasta superarla en 6 lotes. |

En la simulación **R1 se habría activado** en 2025-07 (A8 en 2025-05, 06 y 07) y **R3** también se cumple (−3,4 % en las pequeñas incluidas). **R5** se cumple al llegar 2025-11: los challengers de 2025-03, 2025-08 y 2025-11 se rechazaron seguidos con A7 activa. Es la señal más seria de la simulación: el modelo no se recupera reentrenando. **R6** se cumple desde 2025-02 (A9 en 2024-12, 2025-01 y 2025-02).

## 4. Interruptor de respaldo

Dos formas, ambas probadas en `tests/test_comportamiento.py`:

- **Variable de entorno** `USAR_RESPALDO=true` en `pipeline/.env` y `docker compose up -d api`: arranca sirviendo la
  línea base.
- **Endpoint protegido** sin reiniciar: `curl -X POST -H "X-Token: $API_TOKEN" "localhost:8000/respaldo?activar=true"`
  (y `activar=false` para volver). Sin el token responde 401.

Con el respaldo activo, `/predecir` responde B1 (media del entrenamiento) como retorno y B5 como decisión (todo el
universo con igual peso), con `respaldo: true` y `usado: "respaldo: ..."` en cada respuesta y en `PREDICCIONES`.
`/salud` y `/modelo` lo muestran.

## 5. Supervisión humana

| Momento | Quién | Qué revisa | Dónde queda |
|---|---|---|---|
| Cada lote mensual, antes de enviar la propuesta | Asesor | Las 10 acciones, sus pesos y las alertas del lote (correo si hay críticas) | `PREDICCIONES`, `ALERTAS` |
| Cada reentrenamiento | Científico de datos | Comparación champion/challenger en MLflow y lotes de evaluación; aprueba o rechaza en la pausa de Kestra | `REENTRENAMIENTOS.aprobado_por` |
| Alerta A8 / criterios R1–R3 | Responsable del producto con el asesor | Si activar el respaldo y cómo informar al cliente | `ALERTAS`, bitácora del interruptor en los logs de la API |
| Trimestral | Equipo | Subgrupos (sección 1), costo de errores y si los umbrales siguen siendo razonables | notebook 07 |

El sistema **no ejecuta órdenes**: propone el portafolio; el asesor y el cliente deciden (fuera de alcance desde el
PSet 1).

**Revisión del juicio humano del PSet 1 (decisión de Paul, 27-nov).** El juicio se **mantiene**: el cliente aprueba
siempre cada propuesta, aunque el modelo siga en servicio. Se amplía en tres puntos por lo que mostró la operación:

1. **Dos propuestas por mes.** El asesor presenta al cliente la propuesta del modelo **y** la de la operación manual
   (B7, que se agregó como challenger adicional y la API calcula en paralelo: `decision_operacion_manual`,
   `peso_operacion_manual`, `n_coinciden_operacion_manual`). El cliente ve en qué coinciden y en qué difieren y elige.
   Motivo: en la simulación la operación manual le ganó al modelo (Sharpe 0,35 frente a 0,05 con el champion fijo) y
   A9 estuvo activa desde 2025-02.
2. **Revisión mensual de mantener o retirar el servicio.** Cada mes, con el monitoreo del lote, el responsable del
   producto y el asesor deciden si el modelo sigue en servicio, pasa al respaldo o se retira. Pesan sobre todo las
   alertas alrededor del reentrenamiento: A7 repetidas, challengers rechazados seguidos (R5) y A8/A9 activas. Muchas
   alertas en el reentrenamiento sin un challenger que gane indican que reentrenar no corrige el problema.
3. **Aprobación del cambio de modelo.** Un científico de datos aprueba o rechaza cada challenger en la pausa de Kestra.
   El incidente v7 → v8 (`docs/reentrenamiento.md`) mostró que esa pausa debe mostrar el veredicto de la regla junto al
   check y pedir motivo solo cuando la decisión humana la contradice.
