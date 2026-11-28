# Reentrenamiento, promoción y reversión

Código: `modelos/src/reentrenar.py` (ventana, entrenamiento, regla de promoción, registro), `monitoreo/produccion.py`
(`reentrenar`, `decision`, `promover`, `revertir`), flow `pipeline/kestra/flows/reentrenamiento.yml`.

## Cuándo se reentrena

| Disparador | Regla | Por qué |
|---|---|---|
| Rendimiento | Alerta A7: el MAE de **2 lotes etiquetados seguidos** supera 0,0801 (media de la CV del PSet 3 + 1 desviación) | Deriva de concepto medida con etiquetas reales. Un solo mes malo no basta: en la simulación, el MAE mensual del hold-out tiene media 0,068 y desviación 0,017, y un mes aislado sobre 0,080 ocurre 1 de cada 4 meses. |
| Calendario | 12 lotes etiquetados desde el último reentrenamiento (o desde el primer lote) | Incorporar un año de datos aunque no haya alarma |
| Enfriamiento | Ninguno corre si hay menos de 3 lotes etiquetados nuevos desde el anterior | Evita reentrenar cada mes mientras dura un episodio |

**La deriva de datos sola no dispara** (A4, A5, A6): en la simulación la tasa libre de riesgo de 2024 y el choque de
volatilidad de abril de 2025 movieron las features sin subir el MAE. **Solo se usan lotes etiquetados**: el objetivo
del lote *t* existe al cierre de *t+1*; el challenger se entrena con los lotes tal como se sirvieron, unidos con su
objetivo cuando llegó.

## Cómo se reentrena

- **Ventana expansiva** desde 2013 hasta el último lote etiquetado que no se reserva para comparar. Es la que validó
  el PSet 3 (walk-forward con ventana expansiva) y conserva los regímenes de crisis (2018-Q4, 2020, 2022) que una
  ventana móvil de 3–5 años perdería. Con ~330 filas por mes, un año de lotes nuevos es ~8 % de los datos.
- **Misma preparación**: `src.pipeline` (`preparar`, `dividir`, `FEATURES`), importada, no copiada.
- **Mismos hiperparámetros del champion**: `sklearn.base.clone` del pipeline registrado (LightGBM, `random_state=42`).
  No se vuelve a buscar hiperparámetros en producción: eso es una decisión de experimentación (PSet 3), no de
  mantenimiento.
- **MLflow**: experimento `portafolio-inversiones`, tags `fase=reentrenamiento`, `motivo` (rendimiento o calendario),
  `familia`, `modelo`, `candidato=challenger`; params con la ventana, `hasta_anio_mes`, filas, `huella_datos` y
  los lotes de evaluación; métricas de la comparación. Se registra en `portafolio-inversiones-modelo` y recibe el
  alias **@challenger**.

## Regla de promoción

Champion y challenger se evalúan sobre **el lote etiquetado más reciente**, que ninguno vio al entrenar (PDF 7.2.6).
El challenger se promueve si cumple las dos condiciones:

1. **Negocio (con la variación entre pliegues):** el retorno del top 10 del challenger en ese lote supera al del
   champion por más de **una desviación estándar de la CV de esa métrica, 0,0134** (1,34 puntos de retorno mensual).
   Es la desviación, entre los 7 pliegues de la CV del PSet 3, del retorno mensual medio del top 10 que arma el champion
   (`scripts/desviacion_cv_negocio.py`; pliegues: 1,5 %, −1,1 %, 1,4 %, 0,9 %, 3,0 %, −0,4 %, 0,4 %).
2. **Técnica:** su MAE en el lote no es peor que el del champion en más de 0,1 desviaciones de la CV del MAE
   (0,1 × 0,016 = 0,0016). Un challenger que gana dinero por azar pero predice peor no pasa.

**Sensibilidad.** Un solo lote es una muestra pequeña. En la simulación, con esta regla el sistema promovió dos
challengers y terminó con Sharpe neto −0,23 (US$ 100.000 → 94.825), peor que no reentrenar nunca (0,05; 110.837).
Evaluando en los 6 últimos lotes etiquetados (`simular(..., k_evaluacion=6, enfriamiento=6)`), 0,12 (114.547). Se entrega
la regla que pide el PDF y se recomienda, con lotes reales, pasar a 6 lotes (sección 10 del documento técnico).

## Por qué el modelo no se despliega solo

Aunque la regla diga "promover", `reentrenamiento.yml` se detiene en una tarea **Pause** hasta que una persona apruebe
en la UI de Kestra (Resume con `aprobado = true/false`, `revisor` y `motivo`); sin respuesta en 7 días se cancela. Razones:

- Un lote es poco para separar habilidad de suerte: en la simulación, las dos promociones que la regla aprobó empeoraron el resultado.
- El costo de un mal cambio lo paga el cliente un mes entero; el de esperar la revisión, casi nada (hay días entre el
  cierre y la apertura).
- La persona ve lo que la regla no: si los lotes de evaluación tienen un evento extraordinario o datos sintéticos, si
  el challenger concentra el portafolio en un sector, o si el asesor tiene restricciones nuevas.

La decisión queda en `PRODUCCION.REENTRENAMIENTOS` (`aprobado`, `aprobado_por`, `motivo_decision`).

## Cómo se cambia y cómo se revierte la versión (rollback)

El servicio sirve siempre `models:/portafolio-inversiones-modelo@champion`. La imagen no contiene el modelo.

```bash
# promover la version N (deja la anterior en @anterior) y recargar la API
docker compose --env-file pipeline/.env --profile herramientas run --rm produccion \
  python -m monitoreo.produccion --api http://api:8000 promover --version N
# revertir: @champion vuelve a @anterior (o a --version M)
docker compose --env-file pipeline/.env --profile herramientas run --rm produccion \
  python -m monitoreo.produccion --api http://api:8000 revertir
curl -s localhost:8000/modelo
```

`/modelo` muestra la versión, el alias y el run_id que se sirven después de cada cambio. Alternativa manual: mover
el alias en la UI de MLflow (Models → portafolio-inversiones-modelo → Aliases) y llamar
`curl -X POST -H "X-Token: $API_TOKEN" localhost:8000/recargar`.

## Resultado en la simulación (35 lotes)

| Llegada | Disparador | Champion → challenger | Entrena hasta / evalúa en | MAE champ. / chall. | Retorno top 10 champ. / chall. | Regla | Decisión |
|---|---|---|---|---|---|---|---|
| 2024-12 | calendario | v1 → r1 | 2024-10 / 2024-11 | 0,1020 / 0,0866 | −5,7 % / −3,6 % | promover | aprobado |
| 2025-03 | A7 | r1 → r2 | 2025-01 / 2025-02 | 0,0682 / 0,0703 | 0,0 % / 1,6 % | MAE peor | rechazado |
| 2025-08 | A7 (crisis) | r1 → r3 | 2025-06 / 2025-07 | 0,1173 / 0,1065 | −8,9 % / −9,0 % | no gana dinero | rechazado |
| 2025-11 | A7 | r1 → r4 | 2025-09 / 2025-10 | 0,0512 / 0,0509 | 3,8 % / 2,9 % | no gana dinero | rechazado |
| 2026-04 | A7 | r1 → r5 | 2026-02 / 2026-03 | 0,0662 / 0,0655 | 4,1 % / 7,3 % | promover | aprobado |

**Corrida en Kestra + Snowflake (27-nov).** Las cinco decisiones de la tabla se repitieron en `produccion_lotes`, con
las mismas cifras (`PORTAFOLIO_P4.PRODUCCION.REENTRENAMIENTOS`, `docs/reentrenamientos.csv`). En el registro de MLflow, r1 a
r5 son las versiones 3, 4, 5, 6 y **8** (v1 y v2 son las del PSet 3). La prueba
`tests/test_produccion.py::test_regla_de_promocion_casos_reales` recorre las cinco filas con las cifras de Snowflake y
verifica que la regla dé la misma decisión y el mismo motivo. Así, cada mitad de la regla tiene un caso real que la
justifica: r2 gana dinero y cae por la guarda de MAE, y r3 mejora el MAE y cae por dinero.

**Incidente v7 → v8 (error humano corregido).** En la pausa de la llegada 2026-04, el revisor envió el formulario sin
marcar `aprobado`, y en `motivo` quedó el texto de la regla. El flujo hizo lo que le pedía la respuesta: registró
"rechazado" y dejó a v3 como champion. La v7 quedó rechazada aunque la regla decía promover. Como la decisión humana no
coincidía con su motivo, se corrigió así:
(1) se detuvo `produccion_lotes`;
(2) se volvió a ejecutar `reentrenamiento` desde Kestra (Replay). El nuevo entrenamiento, con semilla 42 y los mismos
datos, registró la **v8**, con MAE 0,06551 y retorno 7,28 %, idénticos a los de v7, y el revisor la aprobó;
(3) se volvieron a correr los lotes 2026-05 a 2026-10, que se habían servido con v3, para que quedaran servidos con v8.
Las escrituras por lote son idempotentes, así que no hubo filas duplicadas.
`REENTRENAMIENTOS` conserva las dos filas de 2026-04 (v7 rechazada y v8 aprobada) como traza de auditoría; no se borró
ninguna. Lección para la operación: la pausa debería mostrar el veredicto de la regla junto al check y pedir el motivo
solo cuando la decisión humana la contradice (sección 10 del documento técnico).

**Ciclo completo sobre la deriva inducida** (alerta → reentrenamiento → challenger → comparación → decisión). Los lotes
2025-05 a 07 disparan A4 (datos) y A8 (negocio) desde el primer lote. Al medir 2025-06 (MAE 0,129) con 2025-05 también
sobre el umbral (0,093), el monitoreo de 2025-07 dispara **A7**; al llegar 2025-08 `reentrenamiento.yml` entrena el
challenger r3 con los lotes hasta 2025-06 (ya incluye dos meses de crisis), lo registra como @challenger y lo compara con el
champion en 2025-07: mejora el MAE (0,1065 frente a 0,1173) pero su top 10 rinde lo mismo (−9,0 % frente a −8,9 %), lejos
del margen de 1,34 puntos. La regla dice no promover y el revisor lo rechaza con ese motivo; @champion queda intacto.
Lección: **reentrenar no protege de una caída que afecta a todas las acciones por igual**, porque el modelo ordena acciones
dentro del mes; lo que protege es el criterio de retirada R1 (A8 → interruptor de respaldo, `docs/criterio_retirada.md`).
