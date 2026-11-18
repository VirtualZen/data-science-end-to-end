# Calidad y limpieza por tabla y columna — PSet 2

Diagnóstico ejecutado: 2026-11-17T18:33:43.313314+00:00. Base: `PORTAFOLIO_P3`. 22 tablas y 236 columnas. Las consultas exactas e identificadores Snowflake están en [consultas.sql](consultas.sql) y [consultas.json](consultas.json).

## Alcance y denominadores

El diagnóstico principal consulta las cuatro tablas **RAW, antes de la limpieza dbt**. No utiliza los valores corregidos de Silver/Gold como sustitutos de la calidad de entrada. RAW ya contiene extracción y tipado de ingesta; no permite medir filas que el proveedor nunca devolvió ni errores descartados antes de llegar a Snowflake. El script no limpia ni escribe en Snowflake.

Los perfiles Bronze/Silver/Gold/OBT son una revisión **posterior**, presentada por separado. El calendario NYSE es una referencia para detectar sesiones ausentes. Para retornos y huecos se usa una selección diagnóstica de la última fila RAW por símbolo-fecha, sin persistirla; evita tratar reingestas como días sucesivos.

Faltantes = (nulos + cadenas vacías/solo espacios) / filas de la tabla. Inválidos y contradicciones se calculan sobre las mismas filas; los nulos se cuentan aparte. Cada problema temporal tiene su propio denominador explícito. No se suman porcentajes de reglas que pueden solaparse. `No evaluado` no significa 0% ni que el dato sea correcto. Timestamps INGESTA_TS se comparan en UTC.

La precisión se evalúa con coherencia OHLC, saltos de retorno e IQR; **no se ha contrastado exactitud de precios con una fuente oficial independiente**. Una anomalía estadística no equivale a un valor inválido.

## Hallazgos y decisiones principales

| Problema | Evidencia | Acción | Justificación |
| --- | --- | --- | --- |
| ES_ETF no disponible | 123267/123267 nulos (100%) | Mantener NULL en Bronze; corregido y ejecutado con dbt. | El JSON no aporta el indicador; desconocido no es false. |
| ES_PRUEBA no disponible | 123267/123267 nulos (100%) | Mantener NULL en Bronze; corregido y ejecutado con dbt. | El JSON no aporta el indicador; desconocido no es false. |
| OPEN: invalidos | 1/1856299 (0.000054%) | Silver descarta OHLC inválido; marca cierre fuera de rango/volumen cero. No imputar volumen. | OHLC válido es necesario para log-precios; cierre fuera del rango puede requerir revisión del proveedor. Volumen cero puede ser legítimo en índices/tasa. |
| CLOSE: inconsistentes | 2/1856299 (0.000108%) | Silver descarta OHLC inválido; marca cierre fuera de rango/volumen cero. No imputar volumen. | OHLC válido es necesario para log-precios; cierre fuera del rango puede requerir revisión del proveedor. Volumen cero puede ser legítimo en índices/tasa. |
| VOLUME: anomalos | 5185/1856299 (0.279319%) | Silver descarta OHLC inválido; marca cierre fuera de rango/volumen cero. No imputar volumen. | OHLC válido es necesario para log-precios; cierre fuera del rango puede requerir revisión del proveedor. Volumen cero puede ser legítimo en índices/tasa. |
| Espacios en símbolos | 34/123267 (0.027582%) | TRIM/UPPER y normalización de separadores en dbt. | Evitar pérdidas de joins por formato. |
| Reingestas de precios | 11132/1856299 filas redundantes (0.599688%) | Conservar RAW; Bronze elige última ingesta/lote. | Append-only preserva auditoría; duplicado crudo no significa hecho duplicado. |
| Claves precio con revisiones de cierre ajustado | 601/1845167 (0.032572%) | Conservar carga reciente en Bronze; conservar RAW. | Puede ser revisión retrospectiva de Yahoo; no confundir reingesta idéntica con conflicto. |
| Revisiones de cierre ajustado mayores a 0.01% relativo | 601/1845160 (0.032572%) | Conservar versión reciente y RAW para auditoría. | Descarta diferencias menores a 0.01%; no prueba error, puede reflejar ajustes retrospectivos. |
| Saltos absolutos log-precio >0.40 en RAW último por clave | 63/1831825 (0.003439%) | Marcar y revisar; no winsorizar ni borrar automáticamente. | Proxy de plausibilidad; incluye saltos entre observaciones separadas por huecos, no solo retornos diarios. |
| Retornos fuera de 1.5 IQR por acción (mínimo 20 retornos) | 91058/1831825 (4.97089%) | Señal diagnóstica; conservar y revisar, no recortar automáticamente. | IQR por acción evita mezclar escalas de precios; colas financieras reales pueden ser atípicas. Incluye saltos sobre huecos. |
| Retornos con z-score robusto (MAD) mayor a 3.5 por acción, sesiones consecutivas (mínimo 20 retornos) | 44140/1831813 (2.409635%) | Marcar y cotejar con eventos reales (ver outliers_mad_por_fecha.csv); no recortar automáticamente. | Criterio del PSet 1. MAD es robusto a las colas; muchos casos el mismo día indican un evento de mercado, no un error de datos. |
| Sesiones sin fila durante la vida observada de cada acción | 11331/1843765 (0.614558%) | Silver construye grilla; forward-fill hasta cinco sesiones internas; excluye huecos mayores. | No supone precios antes de primera o después de última cotización; no cubre acciones sin ningún precio. |
| Precios de acciones fuera del calendario NYSE | 0/1832434 (0%) | Excluir al unir con calendario en Silver. | Fin de semana/feriado no constituye una sesión faltante. |
| Fotos de composición con menos de 495 símbolos | 920/2349 (39.165602%) | No inventar constituyentes; documentar cobertura. | Umbral diagnóstico: 500 empresas no significa siempre 500 símbolos. |
| Símbolos del listado con múltiples bolsas en última carga | 0/7251 (0%) | Bronze conserva una fila por símbolo con prioridad de archivo. | La prioridad es técnica, no verificación de la bolsa correcta; revisar si hay conflictos. |
| Símbolos sin precios devueltos en bitácora | 1142/10081 (11.328241%) | Conservar SIN_DATOS y medir cobertura; no imputar toda una historia. | Denominador solicitudes registradas, no empresas únicas. |
| Errores agotados en bitácora | 0/10081 (0%) | Retry en Kestra y revisión del lote. | Una corrida exitosa puede tolerar hasta 10% de grupos fallidos; ver porcentaje real. |

Las diferencias de cierre ajustado se midieron tanto por igualdad exacta como con tolerancia relativa de 0,01%. No se deben presentar diferencias pequeñas como revisiones económicas confirmadas. Los saltos RAW incluyen intervalos sobre huecos; no son directamente comparables con los retornos diarios extremos de Silver.

El porcentaje de fotos incompletas de RAW usa longitud de la lista original. La métrica de CALIDAD sobre Bronze cuenta símbolos normalizados y deduplicados: por eso puede diferir. La ausencia de sesiones dentro de la vida observada tampoco equivale a días sin precio durante membresía: los universos y denominadores son distintos.

## Perfil de entrada por columna

Porcentajes sobre todas las filas de cada tabla RAW. Las reglas exactas y conteos se conservan en [perfil_columnas.csv](perfil_columnas.csv). El cero en precios observados no descarta sesiones ausentes ni empresas sin cobertura.

### RAW.COMPOSICION_SP500

| Columna | Faltantes % | Inválidos % | Inconsistentes % | Anómalos % |
| --- | --- | --- | --- | --- |
| FECHA | 0 | 0 | No evaluado | No evaluado |
| TICKERS | 0 | No evaluado | 0 | No evaluado |
| FUENTE | 0 | No evaluado | 0 | No evaluado |
| LOTE_ID | 0 | No evaluado | 0 | No evaluado |
| INGESTA_TS | 0 | 0 | No evaluado | No evaluado |

### RAW.INGESTA_LOG

| Columna | Faltantes % | Inválidos % | Inconsistentes % | Anómalos % |
| --- | --- | --- | --- | --- |
| LOTE_ID | 0 | No evaluado | 0 | No evaluado |
| TICKER | 0 | No evaluado | 0 | No evaluado |
| FECHA_DESDE | 0 | No evaluado | No evaluado | No evaluado |
| FECHA_HASTA | 0 | No evaluado | 0 | No evaluado |
| FILAS | 0 | 0 | No evaluado | No evaluado |
| ESTADO | 0 | 0 | 0 | No evaluado |
| DETALLE | 88.671759 | No evaluado | 0 | No evaluado |
| INGESTA_TS | 0 | 0 | No evaluado | No evaluado |

### RAW.LISTADOS_BOLSA

| Columna | Faltantes % | Inválidos % | Inconsistentes % | Anómalos % |
| --- | --- | --- | --- | --- |
| SIMBOLO | 0 | No evaluado | 0.027582 | No evaluado |
| NOMBRE | 0 | No evaluado | 0 | No evaluado |
| CODIGO_BOLSA | 0 | 0 | 0 | No evaluado |
| ES_ETF | 100 | 0 | 0 | No evaluado |
| ES_PRUEBA | 100 | 0 | 0 | No evaluado |
| ARCHIVO | 0 | No evaluado | 0 | No evaluado |
| FUENTE | 0 | No evaluado | 0 | No evaluado |
| LOTE_ID | 0 | No evaluado | 0 | No evaluado |
| INGESTA_TS | 0 | 0 | No evaluado | No evaluado |

### RAW.PRECIOS_DIARIOS

| Columna | Faltantes % | Inválidos % | Inconsistentes % | Anómalos % |
| --- | --- | --- | --- | --- |
| TICKER | 0 | No evaluado | 0 | No evaluado |
| FECHA | 0 | 0 | No evaluado | No evaluado |
| OPEN | 0 | 0.000054 | 0.001778 | No evaluado |
| HIGH | 0 | 0 | 0 | No evaluado |
| LOW | 0 | 0 | 0 | No evaluado |
| CLOSE | 0 | 0 | 0.000108 | No evaluado |
| ADJ_CLOSE | 0 | 0 | No evaluado | No evaluado |
| VOLUME | 0 | 0 | 0 | 0.279319 |
| FUENTE | 0 | No evaluado | 0 | No evaluado |
| LOTE_ID | 0 | No evaluado | 0 | No evaluado |
| INGESTA_TS | 0 | 0 | No evaluado | No evaluado |

`DETALLE` vacío con estado OK es esperado, no pérdida del precio. `ES_ETF`/`ES_PRUEBA` nulos son ausencia estructural del proveedor. Los tipos ya son los declarados en Snowflake: no se puede estimar aquí una tasa de fallo de parseo anterior a RAW.

Los perfiles temporales por año y segmento (acción/índice/tasa) están en [perfil_raw_por_anio.csv](perfil_raw_por_anio.csv); permiten separar volumen cero en referentes del volumen de acciones. Los precios no se mezclan entre símbolos para evaluar IQR: se calculan retornos por acción, con al menos 20 retornos.

## Políticas de limpieza por columna RAW

Estas reglas se aplican en dbt para staging/Bronze y su continuación Silver. El diagnóstico Python solo mide. La política se repite explícitamente por columna para que ningún campo quede sin decisión.

### RAW.COMPOSICION_SP500

| Columna | Acción implementada | Justificación / límite | Código |
| --- | --- | --- | --- |
| FECHA | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| TICKERS | No imputar identificadores. dbt normaliza, explota listas y aplica equivalencias temporales; elimina claves nulas según cada modelo y deduplica. Conserva símbolo original cuando corresponde. | Una identidad inventada produce joins falsos; equivalencias parciales no garantizan identidad permanente. | dbt/models/bronze/ |
| FUENTE | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| LOTE_ID | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| INGESTA_TS | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |

### RAW.INGESTA_LOG

| Columna | Acción implementada | Justificación / límite | Código |
| --- | --- | --- | --- |
| LOTE_ID | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| TICKER | No imputar identificadores. dbt normaliza, explota listas y aplica equivalencias temporales; elimina claves nulas según cada modelo y deduplica. Conserva símbolo original cuando corresponde. | Una identidad inventada produce joins falsos; equivalencias parciales no garantizan identidad permanente. | dbt/models/bronze/ |
| FECHA_DESDE | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| FECHA_HASTA | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| FILAS | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| ESTADO | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| DETALLE | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| INGESTA_TS | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |

### RAW.LISTADOS_BOLSA

| Columna | Acción implementada | Justificación / límite | Código |
| --- | --- | --- | --- |
| SIMBOLO | No imputar identificadores. dbt normaliza, explota listas y aplica equivalencias temporales; elimina claves nulas según cada modelo y deduplica. Conserva símbolo original cuando corresponde. | Una identidad inventada produce joins falsos; equivalencias parciales no garantizan identidad permanente. | dbt/models/bronze/ |
| NOMBRE | No inferir bolsa histórica. Mantener nombre/código desconocidos; Gold etiqueta bolsa desconocida y es_nyse=false; OBT marca bolsa_desconocida. | Listado actual: ausencia no implica que nunca cotizó en NYSE; no completar con una moda. | dbt/models/silver/slv_acciones.sql; dbt/models/gold/dim_accion.sql |
| CODIGO_BOLSA | No inferir bolsa histórica. Mantener nombre/código desconocidos; Gold etiqueta bolsa desconocida y es_nyse=false; OBT marca bolsa_desconocida. | Listado actual: ausencia no implica que nunca cotizó en NYSE; no completar con una moda. | dbt/models/silver/slv_acciones.sql; dbt/models/gold/dim_accion.sql |
| ES_ETF | No disponible en el JSON: RAW nulo; Bronze conserva NULL y solo convierte Y/N conocidos. | No es evidencia de que no sea ETF/prueba; no usar para certificar tipo. Silver admite desconocidos y solo excluye prueba conocida. | dbt/models/bronze/brz_listados_bolsa.sql |
| ES_PRUEBA | No disponible en el JSON: RAW nulo; Bronze conserva NULL y solo convierte Y/N conocidos. | No es evidencia de que no sea ETF/prueba; no usar para certificar tipo. Silver admite desconocidos y solo excluye prueba conocida. | dbt/models/bronze/brz_listados_bolsa.sql |
| ARCHIVO | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| FUENTE | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| LOTE_ID | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| INGESTA_TS | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |

### RAW.PRECIOS_DIARIOS

| Columna | Acción implementada | Justificación / límite | Código |
| --- | --- | --- | --- |
| TICKER | No imputar identificadores. dbt normaliza, explota listas y aplica equivalencias temporales; elimina claves nulas según cada modelo y deduplica. Conserva símbolo original cuando corresponde. | Una identidad inventada produce joins falsos; equivalencias parciales no garantizan identidad permanente. | dbt/models/bronze/ |
| FECHA | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| OPEN | Bronze tipa/deduplica. Silver excluye observaciones de acciones con OHLC nulo/no positivo o high<low; rellena hacia adelante (forward-fill) solo log-cierre y log-apertura ajustados en huecos internos de hasta 5 sesiones. OHLC originales no se imputan. ^IRX se trata como tasa, no como precio. | No inventar extremos OHLC. Forward-fill marcado, como fija el PSet 1: el valor imputado no usa precios futuros (el largo del hueco sí mira el siguiente día observado para decidir imputar o excluir). Huecos largos se excluyen y retorno posterior queda nulo. | dbt/models/bronze/brz_precios_diarios.sql; dbt/models/silver/slv_precios_acciones.sql |
| HIGH | Bronze tipa/deduplica. Silver excluye observaciones de acciones con OHLC nulo/no positivo o high<low; rellena hacia adelante (forward-fill) solo log-cierre y log-apertura ajustados en huecos internos de hasta 5 sesiones. OHLC originales no se imputan. ^IRX se trata como tasa, no como precio. | No inventar extremos OHLC. Forward-fill marcado, como fija el PSet 1: el valor imputado no usa precios futuros (el largo del hueco sí mira el siguiente día observado para decidir imputar o excluir). Huecos largos se excluyen y retorno posterior queda nulo. | dbt/models/bronze/brz_precios_diarios.sql; dbt/models/silver/slv_precios_acciones.sql |
| LOW | Bronze tipa/deduplica. Silver excluye observaciones de acciones con OHLC nulo/no positivo o high<low; rellena hacia adelante (forward-fill) solo log-cierre y log-apertura ajustados en huecos internos de hasta 5 sesiones. OHLC originales no se imputan. ^IRX se trata como tasa, no como precio. | No inventar extremos OHLC. Forward-fill marcado, como fija el PSet 1: el valor imputado no usa precios futuros (el largo del hueco sí mira el siguiente día observado para decidir imputar o excluir). Huecos largos se excluyen y retorno posterior queda nulo. | dbt/models/bronze/brz_precios_diarios.sql; dbt/models/silver/slv_precios_acciones.sql |
| CLOSE | Bronze tipa/deduplica. Silver excluye observaciones de acciones con OHLC nulo/no positivo o high<low; rellena hacia adelante (forward-fill) solo log-cierre y log-apertura ajustados en huecos internos de hasta 5 sesiones. OHLC originales no se imputan. ^IRX se trata como tasa, no como precio. | No inventar extremos OHLC. Forward-fill marcado, como fija el PSet 1: el valor imputado no usa precios futuros (el largo del hueco sí mira el siguiente día observado para decidir imputar o excluir). Huecos largos se excluyen y retorno posterior queda nulo. | dbt/models/bronze/brz_precios_diarios.sql; dbt/models/silver/slv_precios_acciones.sql |
| ADJ_CLOSE | Bronze tipa/deduplica. Silver excluye observaciones de acciones con OHLC nulo/no positivo o high<low; rellena hacia adelante (forward-fill) solo log-cierre y log-apertura ajustados en huecos internos de hasta 5 sesiones. OHLC originales no se imputan. ^IRX se trata como tasa, no como precio. | No inventar extremos OHLC. Forward-fill marcado, como fija el PSet 1: el valor imputado no usa precios futuros (el largo del hueco sí mira el siguiente día observado para decidir imputar o excluir). Huecos largos se excluyen y retorno posterior queda nulo. | dbt/models/bronze/brz_precios_diarios.sql; dbt/models/silver/slv_precios_acciones.sql |
| VOLUME | No imputar ni interpolar volumen; cero se marca en Silver. Negativos se diagnostican; no hay filtro explícito actual. Promedios Spark ignoran nulos. | Cero y desconocido no equivalen; imputar distorsiona liquidez. Si aparecen negativos, corregir en dbt antes de usar. | dbt/models/silver/slv_precios_acciones.sql; spark/jobs/construir_obt.py |
| FUENTE | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| LOTE_ID | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |
| INGESTA_TS | No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK. | No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios. | kestra/scripts/extraer_cargar.py; dbt/models/bronze/ |

## Staging en dbt y tratamientos posteriores

- `brz_precios_diarios.sql`: tipos, identidad, nombres normalizados, descarte de claves nulas y última versión por símbolo-fecha. No calcula medias globales ni reemplaza precios.
- `brz_composicion_sp500.sql`: última carga, explosión de TICKERS, normalización y equivalencias temporales, con conservación del símbolo original y deduplicación.
- `brz_listados_bolsa.sql`: última carga, normalización, exclusión de instrumentos fuera del alcance, deduplicación y conversión Y/N; los flags desconocidos permanecen NULL. Se corrigió la imputación implícita anterior a false.
- Silver: grilla NYSE, exclusión de observaciones inválidas de acciones, forward-fill de log-cierre/log-apertura ajustados para huecos internos de hasta cinco sesiones; no se imputan máximos, mínimos, OHLC original ni volumen. Los huecos mayores se excluyen y no se calcula un retorno que los atraviese.
- Mercado Silver: ^IRX se rellena hacia adelante con el último valor; las series ^GSPC/^NYA no se interpolan. ^IRX es una tasa: no aplicar indiscriminadamente la regla precio > 0.
- Membresía Silver: une huecos de hasta siete días naturales; requiere revisión externa porque es una hipótesis de omisión, no identidad histórica certificada.
- Gold/OBT: derivan claves, medidas, ventanas y flags; no sustituyen el saneamiento de staging. Los objetivos futuros no se imputan. La imputación estadística de features para modelos queda en PSet 3, dentro de entrenamiento.

El forward-fill no usa precios posteriores (criterio del PSet 1); solo el largo del hueco, que decide imputar o excluir, mira el siguiente día observado. Antes (hasta el 15-nov-2026) se interpolaba linealmente con el vecino posterior; el snapshot registraba 0% de días imputados, así que el cambio no altera las cifras. Los outliers se diagnostican con z-score robusto (MAD > 3,5) y 1,5 IQR por acción; outliers_mad_top.csv y outliers_mad_por_fecha.csv permiten cotejarlos con eventos reales.

## Fuentes adicionales y repositorios

| Fuente | Uso real | Repositorio / archivo | Límite |
| --- | --- | --- | --- |
| Yahoo Finance / yfinance | OHLCV ajustado y no ajustado, ^GSPC, ^NYA, ^IRX | https://github.com/ranaroussi/yfinance | API no oficial; ajustes retrospectivos y cobertura incompleta |
| Composición histórica S&P 500 | Miembros por foto; permite incluir empresas que salieron | https://github.com/chinobing/historical_sp500_constituents — sp_500_historical_components.csv | Fotos incompletas y fuentes cambiantes; no acredita historia oficial |
| Listados actuales de bolsa | Símbolo y nombre; código N/Q/A asignado por carpeta de origen | https://github.com/rreichel3/US-Stock-Symbols — nyse/nyse_full_tickers.json, nasdaq/nasdaq_full_tickers.json, amex/amex_full_tickers.json | No aporta bolsa histórica ni indicadores ETF/prueba en el extractor usado |
| Calendario NYSE | Sesiones y medias jornadas; denominador de huecos | https://github.com/rsheftel/pandas_market_calendars — scripts/generar_calendario_nyse.py → dbt/seeds/calendario_nyse.csv | Referencia de calendario, no proveedor de precios |
| Equivalencias de ticker | Cambio de símbolo con fecha de validez y estado | dbt/seeds/equivalencias_tickers.csv; copia en kestra/scripts/ | Referencia local, no repositorio externo independiente ni validación universal; estados verificado/detectado/manual |

## Inventario: datos de origen y columnas del proceso

Inventario completo: [inventario_columnas.csv](inventario_columnas.csv). `origen` identifica campos externos; `creada_ingesta` metadatos/bitácora o indicadores ausentes del JSON; `origen_transformado` y `heredada_o_normalizada` conservan información previa; `creada_dbt`/`creada_spark` identifican derivados; `referencia_seed` son datos auxiliares. La clasificación es funcional, no un linaje SQL automático exhaustivo de cada expresión.

| Tabla | Filas | Columnas | Clave | Redundantes % |
| --- | --- | --- | --- | --- |
| BRONZE.BRZ_COMPOSICION_SP500 | 1869975 | 7 | FECHA_FOTO,TICKER | 0 |
| BRONZE.BRZ_LISTADOS_BOLSA | 6828 | 10 | TICKER | 0 |
| BRONZE.BRZ_PRECIOS_DIARIOS | 1845167 | 11 | TICKER,FECHA | 0 |
| BRONZE.CALENDARIO_NYSE | 7041 | 2 | FECHA | 0 |
| BRONZE.EQUIVALENCIAS_TICKERS | 38 | 4 | TICKER_ANTIGUO,VALIDO_HASTA | 0 |
| CALIDAD.DQ_METRICAS | 22 | 7 | METRICA | 0 |
| GOLD.DIM_ACCION | 1130 | 15 | ACCION_KEY | 0 |
| GOLD.DIM_FECHA | 4245 | 13 | FECHA_KEY | 0 |
| GOLD.DIM_MEMBRESIA_SP500 | 1179 | 6 | PERIODO_KEY | 0 |
| GOLD.FCT_MERCADO_DIARIO | 4245 | 8 | FECHA_KEY | 0 |
| GOLD.FCT_PRECIOS_DIARIOS | 1832433 | 21 | ACCION_KEY,FECHA_KEY | 0 |
| OBT.OBT_ACCION_MES | 87178 | 43 | ACCION_KEY,ANIO_MES | 0 |
| OBT.VALIDACION_OBT | 13 | 5 | CONTROL | 0 |
| RAW.COMPOSICION_SP500 | 67082 | 5 | LOTE_ID,FECHA | 0.456158 |
| RAW.INGESTA_LOG | 10081 | 8 | LOTE_ID,TICKER | 0 |
| RAW.LISTADOS_BOLSA | 123267 | 9 | LOTE_ID,SIMBOLO,CODIGO_BOLSA | 0 |
| RAW.PRECIOS_DIARIOS | 1856299 | 11 | TICKER,FECHA | 0.599688 |
| SILVER.SLV_ACCIONES | 1130 | 13 | TICKER | 0 |
| SILVER.SLV_CALENDARIO_NYSE | 4245 | 3 | FECHA | 0 |
| SILVER.SLV_MEMBRESIA_SP500 | 1179 | 6 | PERIODO_KEY | 0 |
| SILVER.SLV_MERCADO_DIARIO | 4245 | 8 | FECHA | 0 |
| SILVER.SLV_PRECIOS_ACCIONES | 1832433 | 21 | TICKER,FECHA | 0 |

### BRONZE.BRZ_COMPOSICION_SP500

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| FECHA_FOTO | DATE | origen_transformado | 0 |
| TICKER | TEXT | heredada_o_normalizada | 0 |
| TICKER_COMPOSICION | TEXT | origen_transformado | 0 |
| TICKER_ORIGINAL | TEXT | origen_transformado | 0 |
| SIMBOLO_TRADUCIDO | BOOLEAN | creada_dbt | 0 |
| LOTE_ID | TEXT | heredada_o_normalizada | 0 |
| INGESTA_TS | TIMESTAMP_NTZ | heredada_o_normalizada | 0 |

### BRONZE.BRZ_LISTADOS_BOLSA

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| TICKER | TEXT | heredada_o_normalizada | 0 |
| SIMBOLO_ORIGINAL | TEXT | origen_transformado | 0 |
| NOMBRE | TEXT | heredada_o_normalizada | 0 |
| CODIGO_BOLSA | TEXT | heredada_o_normalizada | 0 |
| BOLSA | TEXT | creada_dbt | 0 |
| ES_ETF | BOOLEAN | heredada_o_normalizada | 100 |
| ES_PRUEBA | BOOLEAN | heredada_o_normalizada | 100 |
| ARCHIVO | TEXT | heredada_o_normalizada | 0 |
| LOTE_ID | TEXT | heredada_o_normalizada | 0 |
| INGESTA_TS | TIMESTAMP_NTZ | heredada_o_normalizada | 0 |

### BRONZE.BRZ_PRECIOS_DIARIOS

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| TICKER | TEXT | heredada_o_normalizada | 0 |
| FECHA | DATE | heredada_o_normalizada | 0 |
| PRECIO_APERTURA | FLOAT | origen_transformado | 0 |
| PRECIO_MAXIMO | FLOAT | origen_transformado | 0 |
| PRECIO_MINIMO | FLOAT | origen_transformado | 0 |
| PRECIO_CIERRE | FLOAT | origen_transformado | 0 |
| PRECIO_CIERRE_AJUSTADO | FLOAT | origen_transformado | 0 |
| VOLUMEN | FLOAT | origen_transformado | 0 |
| ES_INDICE | BOOLEAN | creada_dbt | 0 |
| LOTE_ID | TEXT | heredada_o_normalizada | 0 |
| INGESTA_TS | TIMESTAMP_NTZ | heredada_o_normalizada | 0 |

### BRONZE.CALENDARIO_NYSE

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| FECHA | DATE | referencia_seed | 0 |
| MEDIA_JORNADA | BOOLEAN | referencia_seed | 0 |

### BRONZE.EQUIVALENCIAS_TICKERS

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| TICKER_ANTIGUO | TEXT | referencia_seed | 0 |
| TICKER_YAHOO | TEXT | referencia_seed | 0 |
| VALIDO_HASTA | DATE | referencia_seed | 0 |
| ESTADO | TEXT | referencia_seed | 0 |

### CALIDAD.DQ_METRICAS

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| DIMENSION | TEXT | creada_dbt | 0 |
| CAPA | TEXT | creada_dbt | 0 |
| METRICA | TEXT | creada_dbt | 0 |
| VALOR | FLOAT | creada_dbt | 0 |
| UNIDAD | TEXT | creada_dbt | 0 |
| DESCRIPCION | TEXT | creada_dbt | 0 |
| CALCULADO_EN | TIMESTAMP_LTZ | creada_dbt | 0 |

### GOLD.DIM_ACCION

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| ACCION_KEY | TEXT | creada_dbt | 0 |
| TICKER | TEXT | heredada_o_normalizada | 0 |
| NOMBRE | TEXT | heredada_o_normalizada | 38.849558 |
| CODIGO_BOLSA | TEXT | heredada_o_normalizada | 38.849558 |
| BOLSA | TEXT | creada_dbt | 0 |
| ES_NYSE | BOOLEAN | creada_dbt | 0 |
| EN_LISTADO_ACTUAL | BOOLEAN | creada_dbt | 0 |
| PRIMERA_FECHA_SP500 | DATE | creada_dbt | 0 |
| ULTIMA_FECHA_SP500 | DATE | creada_dbt | 44.513274 |
| SIGUE_EN_SP500 | BOOLEAN | creada_dbt | 0 |
| PERIODOS_EN_SP500 | NUMBER | creada_dbt | 0 |
| PRIMERA_FECHA_PRECIO | DATE | creada_dbt | 46.19469 |
| ULTIMA_FECHA_PRECIO | DATE | creada_dbt | 46.19469 |
| DIAS_CON_PRECIO | NUMBER | creada_dbt | 0 |
| TIENE_PRECIOS | BOOLEAN | creada_dbt | 0 |

### GOLD.DIM_FECHA

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| FECHA_KEY | NUMBER | creada_dbt | 0 |
| FECHA | DATE | heredada_o_normalizada | 0 |
| ORDEN_BURSATIL | NUMBER | creada_dbt | 0 |
| ANIO | NUMBER | creada_dbt | 0 |
| TRIMESTRE | NUMBER | creada_dbt | 0 |
| MES | NUMBER | creada_dbt | 0 |
| ANIO_MES | NUMBER | creada_dbt | 0 |
| DIA_SEMANA_ISO | NUMBER | creada_dbt | 0 |
| DIA_BURSATIL_DEL_MES | NUMBER | creada_dbt | 0 |
| DIAS_BURSATILES_DEL_MES | NUMBER | creada_dbt | 0 |
| MES_CERRADO | BOOLEAN | creada_dbt | 0 |
| ES_CIERRE_DE_MES | BOOLEAN | creada_dbt | 0 |
| CONJUNTO | TEXT | creada_dbt | 0 |

### GOLD.DIM_MEMBRESIA_SP500

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| PERIODO_KEY | TEXT | heredada_o_normalizada | 0 |
| TICKER | TEXT | heredada_o_normalizada | 0 |
| FECHA_INICIO | DATE | heredada_o_normalizada | 0 |
| FECHA_FIN | DATE | heredada_o_normalizada | 42.663274 |
| VIGENTE | BOOLEAN | heredada_o_normalizada | 0 |
| HUECOS_UNIDOS | NUMBER | heredada_o_normalizada | 0 |

### GOLD.FCT_MERCADO_DIARIO

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| FECHA_KEY | NUMBER | creada_dbt | 0 |
| CIERRE_SP500 | FLOAT | creada_dbt | 0 |
| CIERRE_NYSE_COMPOSITE | FLOAT | creada_dbt | 0 |
| RET_LOG_SP500 | FLOAT | creada_dbt | 0.023557 |
| RET_LOG_NYSE_COMPOSITE | FLOAT | creada_dbt | 0.023557 |
| TASA_IRX_ANUAL_PCT | FLOAT | creada_dbt | 0 |
| TASA_IRX_RELLENADA | BOOLEAN | creada_dbt | 0 |
| RF_DIARIA | FLOAT | creada_dbt | 0 |

### GOLD.FCT_PRECIOS_DIARIOS

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| ACCION_KEY | TEXT | creada_dbt | 0 |
| FECHA_KEY | NUMBER | creada_dbt | 0 |
| PRECIO_APERTURA | FLOAT | origen_transformado | 0 |
| PRECIO_MAXIMO | FLOAT | origen_transformado | 0 |
| PRECIO_MINIMO | FLOAT | origen_transformado | 0 |
| PRECIO_CIERRE | FLOAT | origen_transformado | 0 |
| PRECIO_CIERRE_AJUSTADO | FLOAT | origen_transformado | 0 |
| PRECIO_APERTURA_AJUSTADO | FLOAT | creada_dbt | 0 |
| VOLUMEN | FLOAT | origen_transformado | 0 |
| RET_LOG_DIARIO | FLOAT | creada_dbt | 0.033835 |
| RET_LOG_APERTURA | FLOAT | creada_dbt | 0.033835 |
| RET_LOG_INTRADIA | FLOAT | creada_dbt | 0 |
| RET_LOG_NOCTURNO | FLOAT | creada_dbt | 0.033835 |
| EN_SP500 | BOOLEAN | creada_dbt | 0 |
| PERIODO_SP500_KEY | TEXT | creada_dbt | 2.437906 |
| IMPUTADO | BOOLEAN | creada_dbt | 0 |
| LARGO_HUECO_IMPUTADO | NUMBER | creada_dbt | 100 |
| DESPUES_DE_TRAMO_EXCLUIDO | BOOLEAN | creada_dbt | 0 |
| ES_RETORNO_EXTREMO | BOOLEAN | creada_dbt | 0 |
| CIERRE_FUERA_DE_RANGO | BOOLEAN | creada_dbt | 0 |
| VOLUMEN_CERO | BOOLEAN | creada_dbt | 0 |

### OBT.OBT_ACCION_MES

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| ACCION_KEY | TEXT | creada_spark | 0 |
| TICKER | TEXT | heredada_o_normalizada | 0 |
| NOMBRE | TEXT | heredada_o_normalizada | 0.167473 |
| BOLSA | TEXT | creada_spark | 0 |
| ES_NYSE | BOOLEAN | creada_spark | 0 |
| BOLSA_DESCONOCIDA | BOOLEAN | creada_spark | 0 |
| ANIO_MES | NUMBER | creada_spark | 0 |
| ANIO | NUMBER | creada_spark | 0 |
| MES | NUMBER | creada_spark | 0 |
| CONJUNTO | TEXT | creada_spark | 0 |
| OBJETIVO_CRUZA_CORTE | BOOLEAN | creada_spark | 0 |
| FECHA_ULTIMA_COTIZACION | DATE | creada_spark | 0 |
| COTIZO_AL_CIERRE_DE_MES | BOOLEAN | creada_spark | 0 |
| EN_SP500 | BOOLEAN | creada_spark | 0 |
| SIGUE_EN_SP500 | BOOLEAN | creada_spark | 0 |
| ELEGIBLE | BOOLEAN | creada_spark | 0 |
| PRECIO_CIERRE_AJUSTADO | FLOAT | origen_transformado | 0 |
| RET_LOG_MES | FLOAT | creada_spark | 0.004588 |
| RET_LOG_21D | FLOAT | creada_spark | 0.004588 |
| RET_LOG_252D | FLOAT | creada_spark | 0.004588 |
| MOMENTUM_12_1 | FLOAT | creada_spark | 0.004588 |
| VOL_21D | FLOAT | creada_spark | 0.005735 |
| VOL_63D | FLOAT | creada_spark | 0.005735 |
| VOL_APERTURA_21D | FLOAT | creada_spark | 0.005735 |
| INTRADIA_PROM_21D | FLOAT | creada_spark | 0 |
| NOCTURNO_PROM_21D | FLOAT | creada_spark | 0.004588 |
| DRAWDOWN_252D | FLOAT | creada_spark | 0 |
| VOLUMEN_PROM_21D | FLOAT | creada_spark | 0 |
| DOLARES_NEGOCIADOS_PROM_21D | FLOAT | creada_spark | 0 |
| OBS_252D | NUMBER | creada_spark | 0 |
| DIAS_NEGOCIADOS_MES | NUMBER | creada_spark | 0 |
| DIAS_IMPUTADOS_MES | NUMBER | creada_spark | 0 |
| HUBO_TRAMO_EXCLUIDO_MES | BOOLEAN | creada_spark | 0 |
| HUBO_RETORNO_EXTREMO_MES | BOOLEAN | creada_spark | 0 |
| RET_LOG_SP500_MES | FLOAT | creada_spark | 0 |
| RET_LOG_NYSE_COMPOSITE_MES | FLOAT | creada_spark | 0 |
| RF_MES | FLOAT | creada_spark | 0 |
| TASA_IRX_PROM_MES_PCT | FLOAT | creada_spark | 0 |
| RET_LOG_MES_SIGUIENTE | FLOAT | creada_spark | 0.711189 |
| EXCESO_RET_MES_SIGUIENTE | FLOAT | creada_spark | 0.711189 |
| RET_LOG_SP500_MES_SIGUIENTE | FLOAT | creada_spark | 0 |
| RET_LOG_NYSE_COMPOSITE_MES_SIGUIENTE | FLOAT | creada_spark | 0 |
| RF_MES_SIGUIENTE | FLOAT | creada_spark | 0 |

### OBT.VALIDACION_OBT

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| CONTROL | TEXT | creada_spark | 0 |
| ESPERADO | NUMBER | creada_spark | 0 |
| OBTENIDO | NUMBER | creada_spark | 0 |
| OK | BOOLEAN | creada_spark | 0 |
| EJECUTADO_EN | TIMESTAMP_NTZ | creada_spark | 0 |

### RAW.COMPOSICION_SP500

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| FECHA | DATE | origen | 0 |
| TICKERS | TEXT | origen | 0 |
| FUENTE | TEXT | creada_ingesta | 0 |
| LOTE_ID | TEXT | creada_ingesta | 0 |
| INGESTA_TS | TIMESTAMP_NTZ | creada_ingesta | 0 |

### RAW.INGESTA_LOG

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| LOTE_ID | TEXT | creada_ingesta | 0 |
| TICKER | TEXT | creada_ingesta | 0 |
| FECHA_DESDE | DATE | creada_ingesta | 0 |
| FECHA_HASTA | DATE | creada_ingesta | 0 |
| FILAS | NUMBER | creada_ingesta | 0 |
| ESTADO | TEXT | creada_ingesta | 0 |
| DETALLE | TEXT | creada_ingesta | 88.671759 |
| INGESTA_TS | TIMESTAMP_NTZ | creada_ingesta | 0 |

### RAW.LISTADOS_BOLSA

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| SIMBOLO | TEXT | origen | 0 |
| NOMBRE | TEXT | origen | 0 |
| CODIGO_BOLSA | TEXT | creada_ingesta | 0 |
| ES_ETF | TEXT | creada_ingesta | 100 |
| ES_PRUEBA | TEXT | creada_ingesta | 100 |
| ARCHIVO | TEXT | creada_ingesta | 0 |
| FUENTE | TEXT | creada_ingesta | 0 |
| LOTE_ID | TEXT | creada_ingesta | 0 |
| INGESTA_TS | TIMESTAMP_NTZ | creada_ingesta | 0 |

### RAW.PRECIOS_DIARIOS

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| TICKER | TEXT | origen | 0 |
| FECHA | DATE | origen | 0 |
| OPEN | FLOAT | origen | 0 |
| HIGH | FLOAT | origen | 0 |
| LOW | FLOAT | origen | 0 |
| CLOSE | FLOAT | origen | 0 |
| ADJ_CLOSE | FLOAT | origen | 0 |
| VOLUME | FLOAT | origen | 0 |
| FUENTE | TEXT | creada_ingesta | 0 |
| LOTE_ID | TEXT | creada_ingesta | 0 |
| INGESTA_TS | TIMESTAMP_NTZ | creada_ingesta | 0 |

### SILVER.SLV_ACCIONES

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| TICKER | TEXT | heredada_o_normalizada | 0 |
| NOMBRE | TEXT | heredada_o_normalizada | 38.849558 |
| CODIGO_BOLSA | TEXT | heredada_o_normalizada | 38.849558 |
| BOLSA | TEXT | creada_dbt | 38.849558 |
| ES_NYSE | BOOLEAN | creada_dbt | 0 |
| EN_LISTADO_ACTUAL | BOOLEAN | creada_dbt | 0 |
| PRIMERA_FECHA_SP500 | DATE | creada_dbt | 0 |
| ULTIMA_FECHA_SP500 | DATE | creada_dbt | 44.513274 |
| SIGUE_EN_SP500 | BOOLEAN | creada_dbt | 0 |
| PERIODOS_EN_SP500 | NUMBER | creada_dbt | 0 |
| PRIMERA_FECHA_PRECIO | DATE | creada_dbt | 46.19469 |
| ULTIMA_FECHA_PRECIO | DATE | creada_dbt | 46.19469 |
| DIAS_CON_PRECIO | NUMBER | creada_dbt | 0 |

### SILVER.SLV_CALENDARIO_NYSE

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| FECHA | DATE | heredada_o_normalizada | 0 |
| MEDIA_JORNADA | BOOLEAN | creada_dbt | 0 |
| ORDEN_BURSATIL | NUMBER | creada_dbt | 0 |

### SILVER.SLV_MEMBRESIA_SP500

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| TICKER | TEXT | heredada_o_normalizada | 0 |
| FECHA_INICIO | DATE | creada_dbt | 0 |
| FECHA_FIN | DATE | creada_dbt | 42.663274 |
| VIGENTE | BOOLEAN | creada_dbt | 0 |
| HUECOS_UNIDOS | NUMBER | creada_dbt | 0 |
| PERIODO_KEY | TEXT | creada_dbt | 0 |

### SILVER.SLV_MERCADO_DIARIO

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| FECHA | DATE | heredada_o_normalizada | 0 |
| CIERRE_SP500 | FLOAT | creada_dbt | 0 |
| CIERRE_NYSE_COMPOSITE | FLOAT | creada_dbt | 0 |
| RET_LOG_SP500 | FLOAT | creada_dbt | 0.023557 |
| RET_LOG_NYSE_COMPOSITE | FLOAT | creada_dbt | 0.023557 |
| TASA_IRX_ANUAL_PCT | FLOAT | creada_dbt | 0 |
| TASA_IRX_RELLENADA | BOOLEAN | creada_dbt | 0 |
| RF_DIARIA | FLOAT | creada_dbt | 0 |

### SILVER.SLV_PRECIOS_ACCIONES

| Columna | Tipo | Origen/creación | Faltantes % |
| --- | --- | --- | --- |
| TICKER | TEXT | heredada_o_normalizada | 0 |
| FECHA | DATE | heredada_o_normalizada | 0 |
| PRECIO_APERTURA | FLOAT | origen_transformado | 0 |
| PRECIO_MAXIMO | FLOAT | origen_transformado | 0 |
| PRECIO_MINIMO | FLOAT | origen_transformado | 0 |
| PRECIO_CIERRE | FLOAT | origen_transformado | 0 |
| PRECIO_CIERRE_AJUSTADO | FLOAT | origen_transformado | 0 |
| PRECIO_APERTURA_AJUSTADO | FLOAT | creada_dbt | 0 |
| VOLUMEN | FLOAT | origen_transformado | 0 |
| RET_LOG_DIARIO | FLOAT | creada_dbt | 0.033835 |
| RET_LOG_APERTURA | FLOAT | creada_dbt | 0.033835 |
| RET_LOG_INTRADIA | FLOAT | creada_dbt | 0 |
| RET_LOG_NOCTURNO | FLOAT | creada_dbt | 0.033835 |
| IMPUTADO | BOOLEAN | creada_dbt | 0 |
| LARGO_HUECO_IMPUTADO | NUMBER | creada_dbt | 100 |
| DESPUES_DE_TRAMO_EXCLUIDO | BOOLEAN | creada_dbt | 0 |
| ES_RETORNO_EXTREMO | BOOLEAN | creada_dbt | 0 |
| CIERRE_FUERA_DE_RANGO | BOOLEAN | creada_dbt | 0 |
| VOLUMEN_CERO | BOOLEAN | creada_dbt | 0 |
| LOTE_ID | TEXT | heredada_o_normalizada | 0 |
| INGESTA_TS | TIMESTAMP_NTZ | heredada_o_normalizada | 0 |

## Decisiones y límites para todas las columnas derivadas

La lista completa por cada columna, incluidas las derivadas, está en [decisiones_por_columna.csv](decisiones_por_columna.csv). El perfil de cada una contiene métricas y reglas explícitas de completitud, validez, consistencia y anomalías, o indica No evaluado cuando no existe una regla defendible. No se presenta ausencia de una regla como aprobación de calidad.

Nulos esperados: fecha_fin de membresía vigente; fechas de precios de símbolos sin cobertura; retornos iniciales; objetivos sin mes siguiente; campos no observados en días interpolados. No deben rellenarse con cero ni con medias por conveniencia.

La precisión real sigue sin verificarse externamente. El rango, IQR y coherencia pueden detectar sospechas, pero no prueban que un precio sea correcto. La bolsa actual, equivalencias parciales y universo incompleto limitan el uso financiero. Los perfiles no garantizan ausencia de sesgo de supervivencia o fuga temporal.

## Reproducir

Desde psets/pset-03/pipeline, con credenciales locales y el entorno uv (`uv sync`):

```bash
uv run python scripts/diagnosticar_calidad.py
uv run python scripts/generar_informe_calidad.py
```

Para el diagnóstico de entrada únicamente: `python scripts/diagnosticar_calidad.py --solo-raw` (necesita el seed de calendario si se ejecutan controles de sesiones). Las otras capas se excluyen del perfil, sin ejecutar transformaciones. Ejecutar el diagnóstico sobre RAW después de la ingesta y antes del siguiente dbt build; luego dbt produce staging/Bronze y Silver. Los snapshots guardados permiten comparar antes/después sin confundir sus denominadores.
