# Respuesta de Claude a la auditoría de Codex — PSet 4 (commit 985f4b4, rama work)

Fecha: 2026-11-27, 22:45 (Guayaquil). Análisis hecho en solo lectura sobre el commit auditado; las correcciones las
autorizó Paul después de leer esta respuesta.

## Evidencia propia

- Uniendo `docs/predicciones.csv` (producción, Kestra) con `docs/simulacion/predicciones_simulacion.csv` por
  (`anio_mes`, `accion_key`): **34 de 35 meses idénticos**. Solo difiere **202604** (v3 frente a r5; máx. |Δpred|
  0,02337; máx. |Δpeso| 0,117588). Única alerta distinta: **(202609, A9)**, presente solo en la simulación.
- Pesos guardados en `PREDICCIONES`: suman 1,0 en los 35 meses. `resultado_lotes.csv`: `invertido_sistema` < 1 en
  varios meses (0,847 en 202401).
- `docs/monitoreo.csv`: latencia p50 = p95 = 41,9 ms (mediana por lote; una petición por lote).
- A9: 13 lotes en producción, 14 en la simulación; `docs/monitoreo.md:79` dice 15.
- `reentrenamientos.csv`: todo `APROBADO=TRUE` tiene `PROMUEVE_REGLA=TRUE` (no hubo excepción humana).
- `alertas.csv`: ninguna alerta en 202605–202610 (H6 no dejó alertas obsoletas en esta corrida).

## Matriz

| ID | Veredicto | Evidencia | Impacto | Corrección | Prueba de aceptación |
|---|---|---|---|---|---|
| H1 | Aceptado | `api/main.py:299-300`; `reentrenar.py:70-76`; `simulacion.py:190-209`; `resultado_lotes.csv` | La acción guardada (100 % invertido, sin costos) no es la estrategia evaluada (tope 1,35× S&P, 15 pb) | Opción A (decidida): reconciliar sobre la trayectoria servida con la regla completa y declarar la limitación. Opción B (mejora futura): una sola función de exposición y costos en API, monitoreo y promoción. Ver "Opciones para H1" | `scripts/reconciliacion.py` reproduce la tabla de `docs/reconciliacion.md` (Sharpe 0,15 / −0,06 / −0,23) |
| H2 | Aceptado (error de Claude: reproceso desde 202605 en vez de 202604) | Comparación anterior; `reentrenamiento.md:91-92`; `generar_memo.py:218`; disclaimer 12 | Afirmación "mismas cifras" falsa | Producción = historia observada con el incidente; simulación = contrafactual. Se corrigen los textos y se agrega una tabla de diferencias; no se reprocesa 202604 | Celda del notebook 07 que muestra exactamente 1 mes y 1 alerta distintos |
| H3 | Parcial | Batch escribe directo (`produccion.py:149`, 11.632 filas); docstring falso (`api/main.py:23-24`); `_registrar` silencioso | Llamadas sueltas solo en JSONL; fallos invisibles | Docstring correcto; `registrado: bool` en la respuesta y contador en `/metricas` | Registro sin permiso → `registrado=false` y contador +1 |
| H4 | Aceptado | `README.md:42-43`; `modelos/README.md:13-17` | Clon limpio no reproduce | Comando corregido y tres modos (fixtures / reconstrucción / evidencia histórica no reproducible exacta) | Modo fixtures en clon nuevo: pruebas y `/predecir` 200 |
| H5 | Aceptado (impacto bajo en batch) | `api/main.py:275-278`, `:95-110` | Versión mal atribuida si hay recarga concurrente | Par inmutable (modelo, info) intercambiado de una vez; alias resuelto una vez a versión | Prueba con recarga simulada a mitad de predicción |
| H6 | Aceptado (sin efecto observado) | `produccion.py:82-83` | Alertas obsoletas pueden disparar reentrenamiento | Borrar antes del retorno vacío | Lote con A7 → reproceso sin alertas → 0 alertas |
| H7 | Aceptado | `produccion.py:64`; `reentrenar.py:124-134` | Versión no reconstruible | Huella con objetivo; manifiesto del entrenamiento en MLflow | Cambiar un objetivo cambia la huella |
| H8 | Aceptado | `reentrenamiento.yml:93-95` | Promoción posible contra la regla | Condición = regla Y aprobación | Prueba de flows: la condición incluye `promueve` |
| H9 | Aceptado, pendiente | Sin ejecución de `pset4-cd` | 7.3 sin demostrar | PR/merge con autorización de Paul; captura y `docker pull` | `cd_ghcr.png` y `/salud` con `API_TAG` |

Observaciones: deriva = desviación equivalente (variables de mercado constantes dentro del mes; se agrega PSI a las
categóricas); cifras corregidas (45 pruebas, A9 13/14, latencia 41,9 ms en producción frente a 9 ms del predictor);
promoción por retorno bruto pasa a la definición unificada de H1; el interruptor no se activó en la corrida.

## Estado tras las correcciones (autorizadas por Paul: opción A + H5 + tablero; 27-nov, 23:10)

| ID | Estado | Dónde |
|---|---|---|
| H1 | Reconciliado y declarado (opción A); unificación en código = opción B, mejora futura | `scripts/reconciliacion.py`, `docs/reconciliacion.md`, `docs/reconciliacion_negocio.csv`, disclaimer 17, memo §9–10 |
| H2 | Corregido en textos; producción no se reescribe | `docs/reconciliacion.md`, `docs/reentrenamiento.md`, disclaimer 12, memo §6 |
| H3 | Corregido | `api/main.py` (docstring, `_registrar` → bool, `registro_fallido`), `api/esquemas.py` (`registrado`), prueba `test_registro_fallido_se_informa` |
| H4 | Corregido | `README.md` (tres modos y comando), `modelos/README.md` |
| H5 | Corregido | `api/main.py` (`Estado.vigente()`, alias resuelto una vez a `models:/<nombre>/<versión>`), prueba `test_version_sale_del_mismo_modelo_que_predijo` |
| H6 | Corregido | `monitoreo/produccion.py::escribir`, prueba `test_reproceso_sin_alertas_borra_las_anteriores` |
| H7 | Pendiente (declarado en memo §10) | — |
| H8 | Corregido (hay que volver a subir el flow a Kestra) | `reentrenamiento.yml` (`aprobado and promueve`), prueba `test_promover_exige_regla_y_aprobacion` |
| H9 | Cerrado: PR #15 a master; `pset4-cd` #1 en verde; imagen pública `ghcr.io/virtualzen/pset4-api:5d7b1bc` (y `latest`) | `docs/figuras/cd_ghcr.png`, anexo C del memo |
| Deriva | PSI + chi² en la categórica; mercado = desviación equivalente | `monitoreo/deriva.py`, disclaimer 16 |
| Cifras | 49 pruebas, A9 13/14, latencia 41,9 ms frente a 9 ms | memo, presentación, `docs/monitoreo.md`, `docs/despliegue.md` |
| Tablero | Gráfico de solicitudes y errores 4xx/5xx por lote | `monitoreo/tablero.py` |

49 pruebas pasan en pset-04 y en proyecto; las 4 nuevas fallan con el código anterior (verificado con una copia de
HEAD en un directorio temporal).

## Opciones para H1 y decisión de Paul

**El problema.** La API guarda la composición y los pesos relativos (100 % en acciones). La regla completa del PSet 1
añade, fuera de la API, el tope de portafolio (volatilidad estimada ≤ 1,35 veces la del S&P 500, con covarianzas
diarias de 63 días; el resto en efectivo) y 15 pb por rotación. El monitoreo (A8, A9) y la promoción usan el retorno
bruto. La API solo recibe datos mensuales, y el tope necesita retornos diarios de Snowflake.

| | Opción A: reconciliar y declarar | Opción B: unificar en código |
|---|---|---|
| Qué hace | Mide la trayectoria realmente servida con la estrategia completa (`scripts/reconciliacion.py`) y la presenta junto a lo observado; declara la limitación (disclaimer 17) | Una sola función de exposición y costos usada por la API (campo `exposicion`), `metricas_lote` (Sharpe neto en A8/A9) y la promoción; columnas nuevas en `PREDICCIONES` y `MONITOREO` |
| Datos guardados | No se tocan | Habría que volver a correr los 35 lotes en Kestra para poblar las columnas nuevas |
| Riesgo | Ninguno sobre la evidencia; el monitoreo sigue siendo un sustituto bruto | Con la métrica nueva, alguna de las 5 decisiones de reentrenamiento (v3, v4, v5, v6, v8) podría invertirse, y contradiría lo grabado en `REENTRENAMIENTOS` y en el video |
| Tiempo | ~1 h (cabía en el plazo, 01:30) | ~3 h más, fuera del plazo |

**Decisión (Paul, 27-nov, 23:05):** opción A, más H5 y el gráfico de errores del tablero. La opción B queda
documentada como **mejora futura a evaluar** (memo, sección 10; disclaimer 17). Antes de adoptarla hay que recalcular
las 5 decisiones de reentrenamiento con la métrica nueva y avisar si alguna cambia.

**Resultado de la opción A** (34 lotes etiquetados servidos):

| Definición | Sharpe anual | US$ 100.000 → |
|---|---|---|
| Monitoreo (bruto, 100 % invertido, sin costos) | 0,15 | 116.291 |
| Estrategia completa (tope + 15 pb) | −0,06 | 103.925 |
| Simulación (contrafactual) | −0,23 | 94.825 |

## Mejoras futuras (memo, sección 10)

1. **Opción B**: estrategia unificada en código (exposición y costos en la API, el monitoreo y la promoción).
2. **Modelo de noticias y sentimiento del mercado**, con fuentes nuevas a evaluar: EDGAR Online (reportes 10-K, 10-Q y
   8-K de la SEC), Reddit (foros de inversión) y sitios web de finanzas. Uso como features adicionales o como señal de
   régimen, medido con la misma validación temporal y cuidando la fuga de información por la fecha de publicación.
3. **H7**: huella de la OBT que incluya el objetivo, y manifiesto del conjunto de entrenamiento como artefacto de MLflow,
   para reconstruir cada versión aunque cambie la OBT.
4. **Pausa de aprobación**: que muestre el veredicto de la regla junto al check y pida motivo solo cuando la persona la
   contradiga (lección del incidente v7).
5. **Operación**: 6–12 meses reales con la operación manual y el modelo en paralelo; el modelo la reemplaza solo si la
   supera por más de una desviación de la CV en 6 lotes. Además: Sharpe de 12 meses como feature, señal de régimen hacia
   efectivo, y sector y tamaño como restricciones.
6. **Umbrales**: recalibrar A4, A5 y A8 con lotes reales (hoy se calibraron con la simulación).

## Realizado después de esta respuesta (27-nov, en este orden)

| # | Hecho | Evidencia |
|---|---|---|
| 1 | Commit `9be6cae` en `work` con las correcciones de la auditoría; push a `origin/work` | `git log`; `pset4-ci` #5 y `pruebas` #99 en verde |
| 2 | `reentrenamiento.yml` vuelto a subir a Kestra (condición regla Y aprobación, H8) | `pipeline/kestra/subir_flows.sh` |
| 3 | Imágenes `api` y `produccion` reconstruidas; API y tablero reiniciados con el código nuevo; `/salud` correcto | compose local |
| 4 | PR #15 `work` → `master` (en `VirtualZen/data-science-end-to-end`) con CI en verde y merge (commit `5d7b1bc`) | `pset4-ci` #6 y #7, `pruebas` #100 y #101 |
| 5 | `pset4-cd` #1 en verde: imagen `ghcr.io/virtualzen/pset4-api:5d7b1bc` y `latest`, paquete público (H9 cerrado) | `docs/figuras/cd_ghcr.png`, anexo C del memo |
| 6 | Commit `c65a138` en `work`: memo con la captura del CD, `plan.txt`, H9 en esta respuesta | `psets/pset-04` y `psets/proyecto` iguales; 49 pruebas en cada una |

## Pasos siguientes (Paul, desde la terminal, solo sobre `VirtualZen/data-science-end-to-end`)

1. Commit de esta actualización de la respuesta y push a `origin/work`.
2. PR #16 `work` → `master` con `gh pr create --repo VirtualZen/data-science-end-to-end --base master --head work`.
3. Esperar la CI del PR (`gh pr checks <n> --repo VirtualZen/data-science-end-to-end --watch`) y hacer el merge
   (`gh pr merge <n> --repo VirtualZen/data-science-end-to-end --merge`). El CD vuelve a publicar la imagen con el hash
   del merge.
4. Tag `pset-04` sobre `origin/master` (el merge del PR #16) y `git push origin pset-04`.
5. Enviar a Codex el prompt de abajo para la segunda revisión, sobre el tag `pset-04`.

Nota: la rama `work` tiene en su configuración local un vínculo a un PR #2 del repositorio del profesor
(`ErickNaunay/data-science-end-to-end`), creado por la extensión de GitHub de VS Code. Ninguno de los pasos anteriores usa
ese repositorio: todos los comandos de `gh` llevan `--repo VirtualZen/data-science-end-to-end` y el número de PR explícito.

---

## Prompt de respuesta para Codex

```
Respuesta de Claude a tu auditoría del PSet 4 (commit 985f4b4, rama work). Responde en español, en modo solo lectura.

Evidencia propia: 34 de 35 meses idénticos entre docs/predicciones.csv y docs/simulacion/predicciones_simulacion.csv;
solo 202604 difiere (v3 vs r5; max |dpred| 0,02337; max |dpeso| 0,117588) y la única alerta distinta es (202609, A9).
Pesos guardados suman 1,0 en los 35 meses; resultado_lotes.csv invierte < 100 % en varios meses. Latencia en
producción 41,9 ms por lote. A9 en 13 lotes (producción) y 14 (simulación). Sin excepción humana en la promoción.

Veredictos: H1 aceptado (una sola definición de estrategia: exposición con el tope de portafolio y costo por
rotación, usada por la API, el monitoreo y la promoción; los 35 lotes guardados no se reescriben, se recalculan
aparte). H2 aceptado, error de Claude (reproceso desde 202605 en vez de 202604): producción = historia observada,
simulación = contrafactual; se corrigen los textos. H3 parcial (batch escribe directo; docstring falso y fallos
silenciosos: se agrega registrado:bool y contador). H4 aceptado (comando y tres modos de reproducción). H5 aceptado
(par inmutable modelo-versión). H6 aceptado sin efecto observado. H7 aceptado (huella con objetivo y manifiesto).
H8 aceptado (regla Y aprobación). H9 pendiente de autorización para el merge.

Opciones para H1: A = reconciliar sobre la trayectoria servida y declarar la limitación (sin tocar datos guardados);
B = unificar en código exposición y costos en API, monitoreo y promoción (requiere volver a correr los 35 lotes y
podría invertir alguna de las 5 decisiones grabadas). Decisión de Paul: A, más H5 y el gráfico de errores del tablero;
B queda como mejora futura. Resultado de A sobre 34 lotes servidos: monitoreo bruto Sharpe 0,15 (US$ 116.291),
estrategia completa -0,06 (US$ 103.925), simulación -0,23 (US$ 94.825). Mejoras futuras: opción B; modelo de noticias y
sentimiento con EDGAR Online, Reddit y sitios de finanzas; H7 (huella con objetivo y manifiesto); pausa de aprobación
con veredicto visible; 6-12 meses reales en paralelo; recalibrar A4, A5 y A8 con lotes reales.

Estado: H2, H3, H4, H5, H6 y H8 corregidos con pruebas (49 pasan; las 4 nuevas fallan con el código anterior); H7 pendiente;
H9 cerrado (PR #15, pset4-cd en verde, imagen ghcr.io/virtualzen/pset4-api:5d7b1bc).

Hecho después: commit 9be6cae (correcciones), flow de reentrenamiento vuelto a subir a Kestra, PR #15 work -> master con
merge 5d7b1bc, pset4-cd #1 en verde con la imagen pública ghcr.io/virtualzen/pset4-api:5d7b1bc (H9 cerrado), commit
c65a138 con el memo y su anexo C completo. Siguen: PR #16 work -> master, merge y tag pset-04 sobre master.

Segunda revisión que te pido, solo lectura, sobre el tag pset-04 (o, si aún no existe, sobre origin/master):
1. Confirma con tu cálculo que la única diferencia producción/simulación es 202604 y (202609, A9), y que los textos
   ya no dicen "mismas cifras".
2. Revisa que docs/reconciliacion.md y scripts/reconciliacion.py midan bien la trayectoria servida con la regla completa
   (src.negocio.backtest), y si la opción A basta para la entrega o consideras la B bloqueante.
3. ¿Aceptas "desviación equivalente" para las 6 variables de mercado constantes dentro del mes?
4. Revisa las pruebas nuevas de H3, H5, H6 y H8: ¿fallarían con el código anterior?
5. Señala cualquier cifra del memo o la presentación que no cuadre con docs/*.csv.
```

---

## Segunda revisión de Codex (`prompt_segunda_revision_para_claude.md`, 28-nov, 00:00–00:40)

Revisión en solo lectura sobre el tag `pset-04` (`b926fc9`, mismo contenido que `work` `89cef4a`): comparaciones de
CSV en memoria, `scripts/reconciliacion.py` en el Mac (mismas cifras; el CSV reescrito difiere en ≤ 6,9e-18 y se
restauró) y constancia de las variables de mercado sobre `obt.parquet` (202 meses).

| Punto | Hallazgo verificado | Decisión de Paul | Qué se cambió |
|---|---|---|---|
| H2, julio de 2025 | Siete acciones empatan en la predicción del puesto 10 (0,051744485993390314) y entran seis; la API guardó TFC y no FITB. `backtest` recalcula los pesos con `nlargest` y desempata por el orden de filas: reconciliación con TFC (−0,0916), notebook 06 con FITB (−0,0898). Único mes con empate; en los otros 34 `backtest` replica los pesos guardados | Declararlo basta | `docs/reconciliacion.md` §3 (con la comprobación), disclaimer 17, memo §9 |
| Deriva de mercado | Un solo valor por mes en 100 % de los meses para `ret_log_sp500_mes`, `ret_log_nyse_composite_mes`, `rf_mes` y `dispersion_mes`; 86,6 % para `dias_negociados_mes` (máx. 3) y 5,9 % para `obs_252d` (máx. 8) | Se acepta la desviación para las 4 constantes | Disclaimer 16 corregido; `obs_252d` y `dias_negociados_mes` al PSI por acción quedan como mejora futura (cambiarlo alteraría el monitoreo registrado en Snowflake y el video) |
| H8 | La prueba anterior solo buscaba textos en el YAML | Basta una prueba | `test_promocion_en_los_cuatro_casos` (4 casos): evalúa la condición del flow y verifica que solo sí/sí entra a la rama que mueve `@champion`; falla con la condición anterior (solo aprobación) |
| Cifras | Ninguna cifra del memo o la presentación descuadra con `docs/*.csv` | — | Pruebas 49 → 53 (README, disclaimer 15, memo, presentación) |
| Video | Duración 6:36 (≤ 7 min), confirmada por Paul | — | Portada del memo y `docs/guion_video.md` |

H3, H4/H7, H5, H6 y H9: se aceptan las salvedades de Codex (JSONL ≠ Snowflake fuera del batch; huella del lote de
inferencia, no del entrenamiento; prueba de H5 secuencial; `DELETE` de Snowflake sin prueba; CD solo con cambios en
`psets/pset-04/**`). Quedan declaradas, sin cambios de código.

Pasos (Paul): commit en `work` con las dos carpetas iguales, PR #17 `work` → `master` en
`VirtualZen/data-science-end-to-end`, CI en verde, merge y tag `pset-04` movido al merge del PR #17.
