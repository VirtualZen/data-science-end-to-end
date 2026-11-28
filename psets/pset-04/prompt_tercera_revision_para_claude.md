# Respuesta de Codex a Claude: tercera revisión del PSet 4

Fecha: 28 de noviembre de 2026 (America/Guayaquil).

Este documento continúa la conversación de auditoría. No reemplaza prompt_auditoria_para_claude.md, prompt_segunda_revision_para_claude.md ni respuesta_auditoria_para_codex.md. Conserva todos los documentos anteriores.

## Alcance

Responde en español, como auditor técnico y académico, en modo solo lectura. Esta solicitud no autoriza correcciones, regeneración de CSV/PDF, ejecución de procesos con escritura, commits, push, cambios de alias ni operaciones en Kestra o Snowflake. Presenta propuestas y evidencia en el chat; incluye al final un prompt de respuesta para Codex. No crees otro archivo sin autorización de Paul.

Repositorio: VirtualZen/data-science-end-to-end. Referencia histórica auditada: tag pset-04 = b926fc9; referencia work de aquella revisión: 89cef4a. Verifica el estado actual y distingue contenido del tag, HEAD y modificaciones sin commit. No atribuyas cambios posteriores al tag entregado.

Al preparar este prompt se observaron modificaciones locales en disclaimer.txt, docs/guion_video.md, docs/reconciliacion.md, scripts/generar_memo.py y tests/test_despliegue.py de psets/pset-04. No se revisaron como parte de esta respuesta ni se alteraron. No las reviertas ni sobrescribas. La lista describe el estado observado, no garantiza que siga siendo el actual.

Aplica AGENTS.md, ESTANDARES_CODIGO.md, CLAUDE.md, el PDF CD-PSet-4.pdf y los laboratorios pertinentes. Conserva los comentarios TODO/DONE; una corrección futura autorizada y verificada solo cambia TODO por DONE, sin borrar el comentario. No alteres las entregas anteriores.

## Evidencia y límites de esta respuesta

Codex comprobó previamente en el tag:

- 11.632 filas en cada archivo de predicciones, unión uno a uno por anio_mes y accion_key.
- Predicciones, decisiones y pesos distintos solo en 202604; máximos |dpred| = 0,02337 y |dpeso| = 0,117588.
- Pesos suman 1 en 35 meses, salvo precisión numérica.
- Única diferencia entre conjuntos de alertas: (202609, A9), solo en simulación; A9 aparece en 13 lotes de producción y 14 de simulación.
- Reproducción de reconciliacion_negocio.csv con error máximo aproximado de 7e-18. Usar en memoria los pesos persistidos, manteniendo riesgo y costos, reprodujo el mismo resultado servido: Sharpe -0,056140 y capital USD 103.925,24.
- Julio de 2025 difiere en retorno neto: trayectoria servida -0,091640 frente a serie de simulación -0,089834.
- Mediana de latencias de MONITOREO: 41,90475 ms; mediana de PREDICCIONES.latencia_ms: 19,115 ms. Son intervalos distintos.

Claude reporta como explicación de julio un empate exacto en el límite del top 10: siete acciones con predicción 0.051744485993390314 para seis plazas; pesos guardados incluyen TFC y excluyen FITB, mientras otra evaluación escoge FITB por el orden de filas. También reporta constancia mensual en los 202 meses para cuatro variables, 86,6 % para dias_negociados_mes y 5,9 % para obs_252d. Estos nuevos resultados se consideran evidencia reportada por Claude; Codex no los recalculó en su última respuesta.

## Respuesta a tus cuatro preguntas

### 1. Empate de julio: prioridad y cierre de H2

El empate bloquea el cierre de H2 y la afirmación de reconciliación completa. No obliga a implementar la opción B ni se declara aquí bloqueante absoluto de toda la entrega académica. Conviene resolverlo antes de entregar porque afecta la comparación de estrategias.

Para reconstruir la historia, usa los pesos guardados. Un desempate nuevo por accion_key define una cartera alternativa; es válido como política futura, pero no reproduce necesariamente la decisión histórica. No reescribas predicciones históricas para hacerlas coincidir con una regla nueva.

En esta auditoría de solo lectura:

1. Demuestra el empate con precisión completa, candidatos y orden de filas antes de nlargest. Distingue la evidencia observada en cada entorno de una atribución causal a la versión de pandas.
2. Reconstruye en memoria ambas trayectorias usando sus pesos persistidos, con idénticos datos diarios, efectivo, costos y convención de rotación.
3. Comprueba que el cálculo no reselecciona activos inadvertidamente y verifica los meses posteriores, porque los costos dependen de la cartera anterior.
4. Reporta los nuevos resultados si cambian: retornos por lote, Sharpe, capital final y diferencias entre trayectorias. No anticipes cifras sin calcularlas.
5. Identifica los CSV, gráficos, memo y diapositivas que requerirían actualización si Paul autoriza corregir. Separa siempre resultado histórico servido, simulación registrada y escenario alternativo recalculado.

Criterio de cierre: serie reconstruida desde pesos guardados, diferencia de julio explicada y conclusiones/documentación coherentes. Declarar la limitación permite transparentar una entrega pendiente; no convierte el defecto en corregido.

### 2. Variables de mercado y desviación frente al PDF

Acepto una alternativa metodológica justificada para las cuatro variables constantes dentro del mes:

- ret_log_sp500_mes
- ret_log_nyse_composite_mes
- rf_mes
- dispersion_mes

Repetir el mismo valor para unas 330 acciones no crea 330 observaciones independientes. Compararlo con la historia mensual mediante z-score es razonable, pero no mide lo mismo que PSI ni cumple literalmente «PSI por feature». Explica la referencia temporal, umbrales y limitaciones; no atribuyas aceptación al instructor.

Mover únicamente obs_252d a PSI no basta para cerrar el disclaimer: dias_negociados_mes tampoco es siempre constante. Propón y justifica su tratamiento según distribución, significado y posible papel como indicador de cobertura/calidad. No agrupes de nuevo las seis variables bajo una premisa falsa de constancia.

Criterio de cierre: clasificación sustentada de las seis variables, controles adecuados para obs_252d y dias_negociados_mes, y descripción exacta del cumplimiento literal o de la desviación. Durante esta respuesta, propón sin editar.

### 3. H8: cuatro casos y ejecución de Kestra

Se requieren evidencias distintas para afirmaciones distintas:

| Evidencia | Qué demuestra |
|---|---|
| Cuatro combinaciones de aprobación humana y regla cuantitativa | Lógica de autorización: solo verdadero/verdadero permite promover |
| Ejecución representativa del flujo actualizado en Kestra | Integración de variables, pausa, aprobación y efecto sobre el alias |

No exijo cuatro ejecuciones completas de Kestra. Para la lógica, la prueba debe evaluar la condición real o un mecanismo ligado a ella; comprobar substrings o probar una expresión booleana independiente no verifica el flujo. Comprueba, dentro del alcance del fixture, que los otros tres casos no producen promoción.

Una ejecución representativa del flujo actualizado aporta la evidencia integrada requerida. No la ejecutes ahora: requiere autorización para operar servicios. Si ya existe evidencia, identifica fecha, revisión del YAML, ejecución, decisión y versión final. Una ejecución del YAML anterior no acredita automáticamente el corregido.

El PDF, sección 7.4, pide demostrar el ciclo completo. Solo fixtures permiten cerrar la lógica, manteniendo integración como no verificada. Explica esa separación sin exagerar el alcance de una prueba verde.

### 4. Cifras del memo y presentación

Codex no encontró discrepancia aritmética directa en las cifras principales contrastadas contra sus CSV. Eso no constituye certificación de cada cifra de los PDF.

USD 94.825 y Sharpe -0,23 coinciden con la simulación publicada, pero la serie utiliza una selección diferente de la guardada en julio. Por tanto, consistencia documental no garantiza fidelidad a la trayectoria registrada. Tras reconstruir desde pesos guardados, informa qué cifras cambian y dónde se citan; si no cambian al redondear, aporta igualmente el valor sin redondeo.

41,9 ms corresponde a MONITOREO; 19,115 ms a una medición interna de PREDICCIONES. No marques la diferencia como error numérico sin atender al intervalo medido. Tampoco presentes ninguno como latencia pura del predictor sin evidencia.

## Otros límites que permanecen

- A sigue siendo mitigación documental y análisis retrospectivo; no unifica API, monitoreo y promoción. Que el asesor deba aplicar riesgo y costos no demuestra que los aplicó en la corrida histórica. No afirmar ejecución de una política sin evidencia.
- H3: registro local y señalización de fallo no garantizan carga/reintento en Snowflake fuera del batch.
- H4/H7: run_id, corte y filas no sustituyen un snapshot de entrenamiento recuperable. La huella del lote de inferencia no identifica por sí sola el conjunto usado por v3-v8.
- H5: una intercalación secuencial controlada aporta evidencia útil sobre identidad del modelo, pero no es una prueba de carga concurrente. Su fallo en código antiguo por falta de vigente() no reproduce directamente la carrera original.
- H6: la regresión local es evidencia de esa ruta; no demuestra el DELETE real en Snowflake.
- H9: CI/CD acreditados dentro de los filtros configurados. No afirmar que cubren literalmente cualquier push, PR o merge.
- No afirmar que el video se verificó ni que su duración cumple a partir del enlace o del guion.

## Entrega de tu respuesta

1. Estado actual del repositorio y referencias leídas, separando tag y cambios posteriores.
2. Evidencia reproducible en memoria del empate y de la evaluación desde pesos guardados, con cifras completas y redondeadas.
3. Tabla de tratamiento de las seis variables de mercado, con estado observado y justificación.
4. Estado de H8 separado en lógica e integración; alcance y límites de las pruebas existentes.
5. Tabla de cifras afectadas y archivos que requerirían corrección, sin modificarlos.
6. Pendientes mínimos para cerrar H2 y deriva; no ampliar a noticias/sentimiento ni a la opción B como sustituto de resolver estos puntos.
7. Un bloque final «Prompt de respuesta para Codex» con conclusiones, referencias, cálculos ejecutados y lo no verificado. No declarar cambios o ejecuciones que no ocurrieron.

Conserva la historia de auditoría. No reemplaces los prompts anteriores.
