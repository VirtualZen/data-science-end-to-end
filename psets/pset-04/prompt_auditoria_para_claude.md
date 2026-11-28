# Auditoría independiente del PSet 4 y proyecto final — respuesta solicitada a Claude

Actúa como responsable técnico del proyecto y responde a esta auditoría independiente de Codex. **Primero analiza y responde; no modifiques archivos, datos, servicios ni GitHub.** Paul decidirá después qué correcciones autoriza.

Repositorio:

`/Users/paulehmig/Documents/Personal/USFQ/MaestriaDataScience/src/MSDS_6003/data-science-end-to-end-work`

Rama auditada: `work`. Commit: `985f4b40e524c0387d5be926ab181019e5936fa9`.

Los hallazgos se refieren a `psets/pset-04/` y se trasladan a sus archivos equivalentes en `psets/proyecto/`. Codex confirmó que este commit está publicado en GitHub. El único archivo sin seguimiento observado durante la auditoría fue `psets/pset-04/prompt_auditoria_codex.md`.

Este informe se guardó después de la auditoría por autorización expresa de Paul. Describe el estado auditado; no supone que archivos o servicios posteriores permanezcan iguales.

## 1. Contexto y evaluación académica

PSet 1 obtuvo 90/100 con feedback; PSet 2 y PSet 3 obtuvieron 100/100 sin observaciones. Conserva esas entregas. Los problemas heredados que afecten la operación final deben evaluarse en las copias del PSet 4, sin alterar los originales.

Valoración del auditor: buena cobertura funcional, separación de componentes, pruebas y documentación; conclusión de negocio honesta sobre la debilidad del modelo. Sin embargo, no corresponde declarar cumplimiento completo mientras no coincidan las decisiones operativas, las métricas, las evidencias y la reproducción desde cero.

Una decisión documentada en `disclaimer.txt` no queda automáticamente exenta de revisión. Distingue:

- Desviación razonable y equivalente al requisito.
- Limitación reconocida.
- Incumplimiento pendiente.
- Defecto de implementación.

## 2. Hallazgos prioritarios

**H1 — [P1] Unificar la cartera operativa y la usada para evaluar el negocio.**

Referencias:

- `api/main.py:290`, selección y ponderación.
- `monitoreo/simulacion.py:197`, cálculo de retornos.
- `monitoreo/simulacion.py:207`, cálculo del Sharpe.
- `modelos/notebooks/06_simulacion_produccion.ipynb`, celda que llama a `backtest`.
- `modelos/src/reentrenar.py:70`, retorno utilizado para promoción.

La API y las filas exportadas de `PREDICCIONES` asignan el 100 % a acciones. El tope de volatilidad del portafolio se aplica posteriormente en el backtest del notebook, pero no en la decisión persistida.

Evidencia: `docs/simulacion/resultado_lotes.csv` reduce la exposición en nueve meses. En 202602 invierte aproximadamente **64,65 %**, mientras los pesos servidos y guardados suman **100 %**.

Además, `metricas_lote` calcula retornos y Sharpe sin descontar rotación y costos; el documento define como métrica de negocio el Sharpe **neto** con 15 pb. Las alertas A8/A9 y el resultado ejecutivo no están midiendo exactamente la misma estrategia.

Explica qué cartera constituye la acción real, dónde se aplica el tope antes de actuar y cómo se reconciliarán monitoreo, promoción y evaluación. No basta con que cada cálculo sea correcto por separado.

**H2 — [P1] Reconciliar producción y simulación después del incidente v7 → v8.**

Referencias:

- `docs/predicciones.csv`.
- `docs/simulacion/predicciones_simulacion.csv`.
- `docs/reentrenamiento.md:98`.
- `docs/monitoreo.csv` y `docs/alertas.csv`.

En **202604**, las 332 acciones fueron servidas con **v3**, mientras la simulación usa **r5**, equivalente al modelo posteriormente registrado como v8. El reproceso documentado comienza en 202605.

Al unir por `anio_mes` y `accion_key`:

- Diferencia máxima de predicción: aproximadamente **0,02337**.
- Diferencia máxima de peso: aproximadamente **0,117588**.
- Retorno bruto de la cartera servida en 202604, usando los objetivos exportados: **+6,055 %**.
- Retorno bruto de la cartera simulada: **−3,372 %**.

También cambian el MAE informado en 202605 y los Sharpe posteriores. La alerta **A9 de 202609** existe en la simulación y no en producción.

Por tanto, no está respaldada la afirmación general de que ambas ejecuciones producen las mismas métricas y alertas. Determina qué evidencia representa lo ocurrido y qué evidencia representa un escenario contrafactual. No sobrescribas retrospectivamente la historia para ocultar la diferencia.

**H3 — [P1] Completar la persistencia de cada predicción y hacer visible su fallo.**

Referencias:

- `api/main.py:334–357`.
- `monitoreo/produccion.py:127`, consumidor por lotes.

El comentario de la API afirma que un flujo carga el JSONL a Snowflake. El código inspeccionado muestra que `produccion.lote` guarda las respuestas de sus propias llamadas; no se encontró un consumidor general del JSONL. Una llamada directa a `/predecir` puede quedar únicamente en el archivo local.

Además, `_registrar` captura cualquier excepción y permite devolver éxito. Codex simuló un `PermissionError`: la API devolvió **200 y 333 predicciones** sin registrar ese lote.

El PDF exige registrar cada predicción en Snowflake, directamente o mediante carga periódica. Identifica el mecanismo completo, su garantía de entrega y cómo comunica fallos. Si no existe, reconoce el pendiente.

**H4 — [P1] Completar la reproducción desde un clon limpio.**

Referencias:

- `README.md:41–46`.
- `modelos/README.md:13–17`.
- `docs/datos_p4.md`.

El README principal propone, desde la raíz del PSet:

`uv run --project modelos python -m src.datos --salida data/obt_p4.parquet`

En esa raíz no existe un módulo importable `src`; está en `modelos/src`. También debe quedar inequívoca la ubicación del archivo de salida.

El registro de MLflow se describe como una copia local con versiones y run IDs existentes, pero `modelos/mlflow/` y los snapshots están excluidos de Git. La reproducción descrita depende de estado previo que un evaluador con un clon nuevo no posee.

Presenta una secuencia completa para inicializar datos, registro y alias, distinguiendo:

- Reproducir exactamente la evidencia histórica.
- Reconstruir el sistema con datos nuevos.
- Ejecutar una demostración con fixtures.

No afirmes reproducibilidad exacta si requiere artefactos privados no suministrados.

**H5 — [P2] Vincular atómicamente modelo, versión y run ID durante la inferencia.**

Referencias:

- `api/main.py:95–110`.
- `api/main.py:275–279`.
- `api/main.py:304`.

El predictor se obtiene bajo bloqueo, pero sus metadatos se consultan después. Una recarga entre ambos pasos puede atribuir la predicción a otra versión.

Codex reprodujo un intercalado simulado: el predictor de v1 calculó la salida y la respuesta terminó etiquetada con versión `999`.

También se resuelve un alias mutable varias veces durante la carga del artefacto y sus metadatos. Propón cómo obtener una referencia inmutable y mantener unido el conjunto predictor–versión–run ID durante toda la petición.

**H6 — [P2] Corregir la sustitución de alertas cuando el resultado nuevo está vacío.**

Referencia: `monitoreo/produccion.py:80–98`.

`escribir()` retorna inmediatamente si `d.empty`, antes de ejecutar el borrado del mes. Si un lote previamente alertado se reprocesa sin alertas, las anteriores permanecen.

Codex comprobó que, con un DataFrame vacío y `borrar_mes`, ni siquiera se intenta acceder al borrado. Esto puede mantener alertas A7 obsoletas y afectar el disparador.

Describe una prueba que cubra: lote con alertas → reproceso sin alertas → ninguna alerta vigente para ese lote. Distingue tabla de estado actual e historial de eventos.

**H7 — [P2] Completar la trazabilidad del conjunto usado para reentrenar.**

Referencias:

- `monitoreo/produccion.py:64`.
- `modelos/src/reentrenar.py:124–134`.

La huella se calcula sobre claves y features de la OBT completa. Excluye el target y no representa exactamente la ventana de entrenamiento, las etiquetas ni la transformación sintética aplicada.

Codex cambió un target de **0,02 a 0,99** y obtuvo la misma huella.

`registrar_challenger` guarda esa huella y los límites temporales, pero no se observa un snapshot o manifiesto suficiente para recuperar exactamente los datos transformados que produjeron el challenger.

Explica cómo reconstruirías una versión después de que cambie la OBT. La vinculación a una tabla mutable no equivale a conservar un snapshot reproducible.

**H8 — [P2] Aclarar y controlar la relación entre regla cuantitativa y aprobación humana.**

Referencia: `pipeline/kestra/flows/reentrenamiento.yml:93–95`.

La condición que permite promover consulta solamente `aprobado`; no exige que `outputs.entrenar.vars.promueve` sea verdadero. Es posible aprobar un candidato que incumpla la regla.

Si la aprobación humana es una segunda condición necesaria, falta aplicar ambas. Si se admite una excepción humana, debe estar definida, justificada y registrada como excepción explícita. Actualmente los documentos presentan las condiciones cuantitativas como requisitos de promoción.

**H9 — [P2, pendiente de entrega] Demostrar el CD y la imagen publicada.**

Referencias:

- `.github/workflows/pset4-cd.yml` (raíz del repositorio).
- Documento técnico, anexo C.
- `plan.txt`, puntos 7.3 y 11.1.

La configuración existe, pero el anexo conserva el pendiente de la captura de GHCR. En las últimas 100 ejecuciones consultadas de GitHub Actions no apareció una ejecución de `pset4-cd`; `master` aún no contiene esta entrega.

No confundas configuración implementada con publicación verificada. Solicita autorización independiente antes de integrar o publicar, y especifica la evidencia que cerraría el requisito: ejecución, commit, imagen y prueba de consumo.

## 3. Observaciones académicas y documentales adicionales

- **Deriva:** `monitoreo/deriva.py:112–137` sustituye PSI/KS por z mensual en seis variables y usa chi-cuadrado sin PSI en categóricas. La motivación estadística está explicada, pero el PDF pide PSI por feature. Evalúa explícitamente esta diferencia y su equivalencia; no la presentes como cumplimiento literal.
- **Cifras desactualizadas:** memo y presentación dicen **33 pruebas**, mientras se ejecutaron **45** por carpeta. La documentación afirma **15 lotes con A9**, pero el CSV de producción contiene **13**.
- **Latencia:** el memo cita 9 ms y p95 de 12 ms. Los exportados de producción presentan una mediana de los p50 por lote de aproximadamente **41,90 ms**. Aclara medición, entorno y alcance; no mezcles tiempo del predictor con latencia de la petición.
- **Rechazo por versión del entorno:** omitir pruebas con las dependencias del curso es una excepción documentada y existe una CI específica que sí las ejecuta. No lo clasifiques automáticamente como defecto, pero tampoco uses el verde de `pruebas.yml` como evidencia de validación del proyecto.
- **Promoción por retorno:** se compara retorno bruto del top 10 con variación de esa métrica, mientras el objetivo global es Sharpe neto. Justifica esa métrica sustituta y sus limitaciones.
- **Comunicación ejecutiva:** distingue claramente políticas de retirada propuestas, intervenciones realmente ejecutadas y resultados sin esas intervenciones. Un interruptor disponible no demuestra que haya protegido la cartera durante la simulación.

## 4. Cumplimiento provisional

| Sección del PDF | Evaluación |
|---|---|
| 1. Patrón de despliegue | Cumple en diseño y justificación |
| 2. Servicio | Parcial: API funcional; problemas de persistencia, trazabilidad y decisión de riesgo |
| 3. Pruebas y CI | Cobertura sustancial; faltan regresiones para los casos anteriores |
| 4. Versionado y rollback | Evidencia existente; falta garantizar identidad consistente durante recargas |
| 5. Simulación | 35 lotes y deriva documentada; pendiente reconciliar ejecución y simulación |
| 6. Monitoreo | Implementado; métricas de negocio y alertas requieren coherencia |
| 7. Reentrenamiento y CD | Ciclo documentado; controles de promoción y evidencia de CD pendientes |
| 8. Ética y retirada | Criterios e interruptor presentes; aclarar aplicación efectiva |
| 9. Resultado de negocio | Parcial: cifras calculadas, pero no todas corresponden a la trayectoria servida |
| 10. Integración y reproducción | Copias coherentes; arranque limpio y snapshots incompletamente resueltos |
| 11. Comunicación | Formato y enlace presentes; cifras y afirmaciones pendientes de reconciliación |

## 5. Evidencia verificada por Codex

- GitHub `work` coincide con el commit auditado.
- PSet 2 y PSet 3 no presentan diferencias respecto de sus tags.
- Los archivos compartidos de PSet 4 y `proyecto` coinciden, aplicando las exclusiones declaradas.
- **45 pruebas aprobadas en cada carpeta**, usando el entorno existente y sin caché de pytest.
- CI específica publicada en verde para el commit auditado.
- CSV: **11.632 predicciones, 35 filas de monitoreo, 32 alertas, 149 corridas y 6 registros de reentrenamiento**.
- Los diez notebooks inspeccionados tienen sus celdas de código ejecutadas y sin errores guardados.
- Documento técnico: **7 páginas de cuerpo**, seguido de anexos; presentación: **11 diapositivas**.
- El documento final incluye un enlace al video.

No se volvió a ejecutar la infraestructura, no se escribió en Snowflake/MLflow/Kestra y no se verificó el contenido audiovisual ni una imagen remota de GHCR. Los defectos reproducidos con dobles de prueba no se presentan como incidentes observados en el servicio real.

## 6. Respuesta que debes generar para Paul y Codex

Responde con una matriz:

`ID | aceptado/refutado/parcial | evidencia archivo:línea | impacto | corrección propuesta | prueba de aceptación`

Para refutar, aporta evidencia concreta y reproducible. No basta citar el disclaimer o que las 45 pruebas pasan.

Después:

1. Prioriza qué impide cerrar la entrega y qué es una mejora posterior.
2. Indica qué documentos, métricas o artefactos habría que regenerar si se autoriza corregir.
3. Identifica qué acciones requieren acceso a servicios o autorización para publicar.
4. Conserva PSet 1–3 y los comentarios; `TODO` solo pasa a `DONE` al implementar y verificar.
5. **Termina con un bloque titulado “Prompt de respuesta para Codex”**, listo para copiar, con tus conclusiones, evidencia y solicitudes concretas de segunda revisión.

**No implementes las correcciones todavía. Esta solicitud es de análisis y respuesta.**
