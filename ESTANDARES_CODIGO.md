# Estándares compartidos de programación y auditoría

Ámbito: `VirtualZen/data-science-end-to-end`, clon `data-science-end-to-end-work`, rama `work`.
Guía para Codex y Claude. No autoriza cambios por sí sola: manda el alcance solicitado por Paul.

## Fuentes y resolución de diferencias

1. Respetar las instrucciones explícitas vigentes de Paul y las restricciones del entorno.
2. Para requisitos académicos, consultar el PDF del PSet correspondiente. Ante una contradicción
   con el material del repositorio, prevalece el PDF; documentar la diferencia en `disclaimer.txt`
   o en el documento técnico cuando esté autorizado editar.
3. Usar los README, `starter/` y plantillas de `laboratorios/` como referencia de estructura,
   nombres, estilo y verificaciones. Separar enunciados originales de soluciones propias:
   un comentario `DONE` no convierte una solución en estándar del instructor.
4. Conservar las reglas específicas de `CLAUDE.md`. Sus ejemplos de carpetas, versiones y
   entregables describen la referencia del curso; contrastarlos con el PDF aplicable antes de
   imponerlos. No mover archivos ni actualizar dependencias automáticamente para ajustarlos.

Toda desviación debe identificar la fuente, el requisito, la justificación y la evidencia.
Durante una auditoría, informar esa documentación pendiente sin escribirla en el repositorio.

## Dos modos de trabajo

### Auditoría de código existente

- Solo lectura: no corregir código, comentarios, notebooks, planes, datos ni documentación.
- Identificar repositorio, rama, commit y alcance. Separar GitHub, commits locales y cambios
  sin commit; no atribuir archivos locales no versionados a la entrega publicada.
- Leer requisitos, implementación, llamadas y pruebas relacionadas. Revisar lógica, casos
  límite, contratos y coherencia entre código, resultados y documentación.
- En una revisión de cambios, distinguir defectos introducidos de problemas preexistentes.
  En una auditoría integral, ambos pueden ser hallazgos, indicando su origen cuando se conozca.
- No ejecutar procesos que escriban en Snowflake, MLflow u otros servicios durante una
  auditoría. Ejecutar comprobaciones sin efectos persistentes sobre el proyecto; usar archivos
  temporales fuera del repositorio y desactivar cachés cuando corresponda.
- Presentar primero los hallazgos: prioridad, archivo y línea, escenario reproducible,
  resultado esperado, resultado observado e impacto. Separar defectos confirmados, riesgos
  pendientes de verificar, TODO explícitos y decisiones justificadas.
- Prioridades: P0 bloqueante general, P1 urgente, P2 defecto ordinario, P3 impacto menor.
  No convertir preferencias personales de estilo en defectos.
- Informar qué se verificó, con qué evidencia y qué no se pudo probar. No inferir corrección
  de una etiqueta DONE, de salidas antiguas de notebooks o de una CI verde sin revisar su alcance.

### Refactorización autorizada

- Preservar comportamiento observable, formatos, firmas públicas, rutas, esquemas y contratos.
  Si hace falta corregir comportamiento, identificarlo explícitamente y comprobar que esté
  dentro del alcance autorizado; una refactorización no autoriza cambios de negocio implícitos.
- Hacer cambios acotados. No introducir frameworks, reorganizaciones amplias, nuevas
  dependencias ni cambios de formato masivos sin una necesidad concreta dentro del alcance.
- Identificar entradas, salidas y pruebas antes de editar. Para cambios de lógica, comprobar
  equivalencia o la corrección prevista con casos representativos y casos límite pertinentes.
- Respetar cambios ajenos y entregas congeladas. No sobrescribir ni revertir trabajo local.
- Actualizar documentación y planes afectados solo dentro del alcance de edición autorizado.
- No hacer commits, push, merges ni publicaciones sin autorización explícita de Paul.

## Comentarios TODO y DONE

- Conservar los comentarios existentes, su numeración y el texto que explica la tarea.
- Cuando una tarea esté completamente implementada y verificada, sustituir únicamente
  `TODO` por `DONE` en su comentario; no borrar ni resumir el comentario.
- Si la tarea está incompleta o no se pudo verificar, conservar `TODO` e informar el pendiente.
- No sustituir globalmente TODO en instrucciones, docstrings o mensajes de comprobación.
  Por ejemplo, una salida `TODO 1: OK` no es un comentario de trabajo pendiente.
- Un DONE existente puede contener un defecto. Durante una auditoría, reportarlo sin editar
  su marcador. Al corregirlo, conservar el comentario y registrar la evidencia de validación.

## Programación y estilo

- Seguir nombres y organización del laboratorio pertinente y las convenciones existentes.
  Usar nombres descriptivos, funciones con una responsabilidad clara y flujo legible.
- Extraer lógica reutilizable a módulos; los notebooks importan funciones, no mantienen copias
  divergentes. Evitar abstracciones que no simplifiquen un uso real.
- Separar configuración, transformación, entrenamiento, inferencia y presentación.
  Usar rutas relativas con una base explícita; no depender de rutas personales absolutas.
- Evitar ejecución de trabajos al importar módulos; usar funciones y guardia `__main__`
  en scripts. Mantener interfaces de servicio compatibles con su forma de arranque.
- No ocultar errores con excepciones genéricas o éxitos ficticios. Distinguir respuesta vacía,
  ausencia válida de datos y fallo de una fuente según el contrato del proceso.
- Secretos y configuración privada se leen del entorno o archivos excluidos de Git.
  No imprimir ni versionar credenciales, llaves, tokens o destinos privados de avisos.

## Datos, modelos y reproducibilidad

- Definir unidad de observación, claves, objetivo, horizonte y momento real de predicción.
  Verificar tipos, duplicados, nulos, cardinalidad de joins y disponibilidad de cada variable.
- Para predicción del futuro, separar por tiempo y respetar grupos, ventanas y purgas que
  requiera el problema. No usar información posterior para completar variables anteriores.
- Ajustar imputación, escalado, codificación y selección aprendida solo con entrenamiento de
  cada pliegue, dentro del Pipeline/ColumnTransformer. Revisar también transformaciones previas.
- Mantener el holdout fuera de selección y tuning. Comparar los esquemas solicitados por la
  guía sobre modelos y datos comparables; justificar diferencias de horizonte o universo.
- Separar preparación para entrenamiento e inferencia: predecir no debe requerir el target.
  Conservar el mismo contrato de features y las transformaciones necesarias al servir el modelo.
- Usar semilla 42 donde aplique, registrar versiones y dependencias, cortes, huella de datos,
  parámetros, métricas y artefactos. No atribuir determinismo absoluto solo a una semilla.
- Reutilizar los entornos y locks existentes; verificar exportaciones de requirements.
  Documentar entornos separados o dependencias no fijadas como límites de reproducibilidad.
- Contrastar métrica técnica y de negocio, costos, unidades, baselines y reglas de decisión.
  Las conclusiones deben sostenerse en resultados, incluso cuando no favorezcan al modelo.
- Registrar el pipeline necesario para inferencia, recuperar el artefacto y verificar que
  reproduce la métrica con los datos y tolerancias documentados.

## Despliegue, monitoreo y pruebas

- Usar las semanas 12–14 como referencia para batch/online, API, registro de versiones,
  métricas de servicio, etiquetas demoradas, deriva y comunicación de resultados.
- Verificar validación de entradas, salud, identidad del modelo y trazabilidad de predicciones.
  Contabilizar también excepciones y fallos del servicio, no solo respuestas exitosas.
- Separar métricas de sistema, indicadores indirectos y desempeño con etiquetas maduras.
  Una alerta de deriva no demuestra por sí sola pérdida de calidad ni autoriza promoción.
- Comprobar umbrales, ventanas, referencia y comportamiento ante ausencia de datos.
  Para PSet 4, contrastar aprobación, fallback y rollback con su PDF específico.
- Usar pruebas unitarias sintéticas sin depender de datos privados o servicios externos.
  Separar pruebas de integración y declarar sus requisitos y efectos secundarios.
- Ejecutar las pruebas pertinentes al cambio; añadir regresiones para defectos de lógica
  cuando aporte evidencia. No crear pruebas que solo repitan la implementación.
- Verificar que la CI ejecuta las pruebas del código realmente entregado. Cero pruebas no
  constituye evidencia de corrección. No alterar los comprobadores para forzar resultados OK.
- Para notebooks de entrega, verificar ejecución limpia y salidas coherentes cuando esté
  autorizado ejecutarlos; una auditoría no debe guardar ejecuciones sobre el original.

## Referencias para consultar según la tarea

| Fuente local | Criterio principal |
|---|---|
| `laboratorios/semana-03-*` a `semana-07-*` | Infraestructura, ingesta, calidad, capas y procesamiento |
| `laboratorios/semana-08-sesion-02` y `semana-09-*` | Exploración, disponibilidad de features y pipelines |
| `laboratorios/semana-10-*` y `semana-11-*` | Comparación, trazabilidad, validación y negocio |
| `laboratorios/semana-12-*` a `semana-14-*` | Despliegue, pruebas, registro, monitoreo y comunicación |
| PDF de cada PSet y `psets/pset-01/` | Requisitos de entrega, propuesta y feedback disponible |
| `CLAUDE.md` | Restricciones específicas del repositorio y acuerdos con Paul |

Estas reglas combinan requisitos del curso y criterios de ingeniería acordados para la revisión.
No atribuir al instructor una regla adicional sin identificar su fuente exacta.
