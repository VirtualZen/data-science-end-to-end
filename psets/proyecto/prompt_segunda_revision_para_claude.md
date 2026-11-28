# Segunda revisión de Codex: respuesta solicitada a Claude

Actúa como auditor técnico y académico. Contrasta esta revisión con los archivos actuales; no aceptes sus conclusiones sin verificar. Responde en español con evidencia y un prompt de respuesta listo para devolver a Codex.

## Alcance y autorización

Repositorio: VirtualZen/data-science-end-to-end, clon data-science-end-to-end-work, rama work. Referencia local auditada: 89cef4a. El tag pset-04 apunta a b926fc9, merge del PR 16; distinguir ambas referencias y comprobar el estado actual antes de concluir.

Esta solicitud autoriza análisis y una respuesta en el chat, no cambios de código, documentos, datos, servicios ni GitHub. No ejecutes scripts que escriban salidas. No hagas commits, push, merges, cambios de alias ni ejecuciones de Snowflake/Kestra. Propón cambios concretos para una autorización posterior. Conserva los comentarios existentes: cuando una corrección sea autorizada y verificada, solo cambia TODO por DONE, sin borrar el comentario.

Lee AGENTS.md, ESTANDARES_CODIGO.md, CLAUDE.md, psets/pset-04/CD-PSet-4.pdf y los laboratorios pertinentes. El PDF prevalece para requisitos académicos. PSet 1 recibió 90/100 y tiene feedback; PSet 2 y 3 recibieron 100/100 y no deben alterarse.

## Evidencia de partida

- psets/pset-04/respuesta_auditoria_para_codex.md y prompt_auditoria_para_claude.md.
- API, monitoreo, modelos/src, tests y pipeline/kestra/flows: 61 archivos versionados comparados coinciden entre pset-04 y proyecto. No interpretar esto como comparación de todos los archivos.
- CI del tag: https://github.com/VirtualZen/data-science-end-to-end/actions/runs/46109227934 (success).
- CD de b926fc9: https://github.com/VirtualZen/data-science-end-to-end/actions/runs/46108996944 (success).
- CI/CD verde demuestra el alcance de sus jobs, no un despliegue integral de los servicios.
- Codex no volvió a ejecutar pytest ni el sistema integrado en la segunda pasada; revisó código, resultados existentes y cálculos en memoria.

## Hallazgos que debes responder

### H1. Regla de negocio: mitigación documental, no unificación operativa

La API produce selección y pesos; el monitoreo utiliza retornos brutos. El backtest aplica el tope de riesgo, efectivo y costos. La opción A aceptada por Paul preserva esa arquitectura y reconcilia después. No la presentes como implementación de una única regla en producción.

PDF: sección 2 exige devolver la acción del PSet 1; secciones 6.1 y 9 exigen métrica de negocio; sección 10.5 exige coherencia de decisiones. Explica qué parte de la acción completa realiza la API y qué parte queda al asesor o al análisis posterior. No atribuyas al PDF una obligación de ejecutar órdenes bursátiles: no la exige.

### H2. Reconciliación: explicar julio de 2025

Al recalcular desde docs/reconciliacion_negocio.csv, los 34 meses etiquetados dan:

| Serie | Sharpe anual | Capital final desde USD 100.000 |
|---|---:|---:|
| monitoreo_bruto_100pct | 0,152899 | 116.290,98 |
| estrategia_neta | -0,056140 | 103.925,24 |
| simulacion_neta | -0,229081 | 94.824,97 |

Hay dos meses con diferencia neta mayor que 1e-9:

- 202507: estrategia -0,091640 frente a simulación -0,089834; turnover reconstruido 2,0.
- 202604: estrategia 0,057822 frente a simulación -0,036722; turnover reconstruido 1,818528.

La explicación de abril no explica julio. Verifica selección, pesos, cartera anterior, universo, retornos, costos y estado del backtest. Identifica la causa con archivo/línea y cálculo reproducible sin escribir archivos. No supongas que es redondeo o turnover sin demostrarlo. La igualdad de predicciones/pesos en 34/35 lotes no implica igualdad de retornos netos.

scripts/reconciliacion.py recalcula pesos mediante backtest a partir de scores: comprueba que replica las decisiones persistidas antes del escalado de riesgo y que trata correctamente fallback, empates y etiquetas ausentes. Distingue cálculo a partir del CSV de reconstrucción independiente desde los datos fuente. PDF: secciones 9, 10.5, 10.7 y documento técnico, apartado 9.

### H3. Persistencia: fallo visible no equivale a persistencia garantizada

registrado=false y registro_fallido corrigen el silencio ante errores locales. El flujo oficial persiste sus respuestas; las llamadas independientes no se cargan automáticamente en Snowflake.

PDF sección 1 permite batch; sección 2 permite explícitamente registro directo o carga periódica con Kestra. No exijas escritura síncrona como requisito del profesor. Demuestra el alcance del flujo oficial y explica qué pasa con una llamada válida fuera de él, un fallo de carga y un reintento. Distingue registrado en JSONL de confirmado en Snowflake. Propón el mínimo mecanismo de recuperación o delimitación del servicio, sin implementarlo.

### H4. Reproducibilidad y H7. Trazabilidad

El README distingue pruebas, reconstrucción con datos nuevos e historia. Eso es una mejora documental, pero no entrega por sí solo acceso a los snapshots históricos. La huella de leer_obt incluye claves y FEATURES_OBT y excluye el target.

PDF sección 10.3 y Repositorio: reproducción desde cero. Sección 10.6: cadena predicción → versión → run_id → snapshot de entrenamiento → Gold. El PDF no prescribe MD5/SHA ni manifiestos: son mecanismos propuestos para demostrar esa cadena, no requisitos textuales.

Comprueba especialmente las versiones reentrenadas: qué snapshot concreto se recupera, si contiene objetivo, corte temporal, filas y preparación. Una huella del lote de inferencia no prueba el snapshot de entrenamiento. Propón manifiesto y huella completa o una alternativa equivalente. Separa reconstruir el pipeline con nuevos datos de reproducir exactamente las cifras históricas.

### H5, H6, H8 y H9

- H5: corrección presente: snapshot de modelo/metadatos y resolución única del alias. Revisar prueba de concurrencia y alcance real; un fallo del test antiguo por ausencia de vigente no demuestra por sí solo la carrera original.
- H6: corrección presente: borrar alertas del mes aun cuando el nuevo resultado esté vacío. Revisar ruta local y Snowflake; conservar meses ajenos.
- H8: condición humana AND regla cuantitativa presente. PDF 4 y 7.2. Una prueba de substrings en YAML no sustituye demostrar los cuatro casos booleanos y el alias final. Señalar qué evidencia integrada existe y cuál falta.
- H9: construcción/publicación verificadas. PDF 7.3: main se implementa como master, la rama principal existente; nombres pset4-ci.yml/pset4-cd.yml y ubicación raíz tienen justificación técnica. Verificar filtros: CI solo corre para rutas seleccionadas; CD no se dispara por cambios exclusivamente en psets/proyecto. No afirmar literalmente cada push/merge sin esa salvedad.

## Matriz de cumplimiento del PDF que debes completar

Para cada fila: requisito y sección, evidencia exacta, estado (demostrado/parcial/desviación justificada/no verificado), justificación y pendiente mínimo. No inventes porcentajes ni nota final.

1. Patrón batch y contrapropuesta online: latencia, frecuencia, volumen y costo de desactualización (1).
2. API, alias, Docker, Pydantic, acción y persistencia (2); mantener H1/H3 visibles.
3. Contrato, métrica fija, dos comportamientos y fallback; CI con imagen (3). No confundir número de pruebas con cobertura.
4. Regla de promoción con negocio y variabilidad, rollback y trazabilidad de versión (4).
5. Al menos ocho lotes, horizonte y deriva inducida documentada (5). Hay 35 lotes y 34 etiquetados en las evidencias; comprobarlos.
6. Sistema/modelo/datos, PSI y pruebas estadísticas, alertas y tablero (6). disclaimer.txt punto 16 reconoce desviación: variables de mercado con z-score y calendario con categoría vista. Puede ser razonable por el grano mensual, pero no equivale literalmente a PSI por feature; no declarar cumplimiento total sin salvedad. Una solicitud por lote produce p50=p95: explicitar su escaso alcance estadístico.
7. Entrenar solo con objetivos maduros, misma preparación/hiperparámetros, evaluación no vista, pausa y decisión; CD y ciclo con deriva (7).
8. Subgrupos, costo de errores, al menos tres criterios de retirada, interruptor demostrado y supervisión (8). El PDF exige escribir criterios e implementar/demostrar interruptor; no exige automatizar todos los criterios. No convertir la ausencia de automatización en incumplimiento literal. Aclarar si los resultados son de una política con retirada ejecutada o sin ella.
9. Resultado por lote contra baseline y no actuar, reentrenamientos marcados, respuesta honesta al valor generado (9). Conservar H2 y distinguir bruto/neto y real/simulado.
10. Proyecto unificado, compose, README, cambios de PSet1, decisiones y cadena de datos (10). Psets 2/3 no tienen feedback pendiente. proyecto/ frente a proyecto_final/ y organización anidada son desviaciones documentadas, no cumplimiento literal ni aceptación del docente demostrada. Workflows deben vivir en .github/workflows de la raíz para que GitHub los detecte.
11. Memo <=12 páginas sin anexos, presentación 10–12 láminas, video <=7 minutos con todos los pasos y enlace en memo (11 y entregables). La revisión previa encontró 7 páginas de cuerpo y 11 láminas: confirmar en versión actual. No inferir duración ni contenido del video de su enlace o guion; no se ha visto en esta auditoría.
12. CSV de predicciones, monitoreo, alertas, todas las corridas y reentrenamientos; notebooks con salida y anexos (Repositorio). Salidas guardadas sin error no prueban Restart + Run All reciente.

## Formato de tu respuesta a Codex

1. Estado del repo y alcance realmente leído/ejecutado; distinguir local y remoto.
2. Aceptación o refutación motivada de H1–H9 y de la diferencia de julio.
3. Matriz completa de requisitos del PDF, con rutas y líneas o páginas.
4. Propuestas mínimas priorizadas, separando defectos, cumplimiento literal, desviaciones justificadas y mejoras opcionales.
5. Evidencia faltante que impide cerrar cada punto; no usar DONE, CI verde o documentación como prueba única.
6. Al final, un bloque titulado «Prompt de respuesta para Codex» con conclusiones verificables, cifras, referencias y preguntas específicas. No declares cambios que no realizaste ni ejecuciones que no observaste.

No crees ni modifiques archivos al responder este prompt salvo autorización posterior de Paul.
