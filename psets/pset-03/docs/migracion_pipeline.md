# Copia del pipeline del PSet 2 en `pipeline/`

Fecha: 2026-11-16. Rama `work` (`6f4c141`). Motivo: el PSet 3 necesita volver a correr
el pipeline completo con posibles cambios, y `psets/pset-02/` ya se entregó (tag
`pset-02`), así que no se modifica.

## Qué se copió

Desde `psets/pset-02/` se copiaron 74 archivos versionados a `psets/pset-03/pipeline/`:
`dbt/`, `kestra/`, `spark/`, `scripts/`, `pruebas_locales/`, `docker-compose.yml`,
`pyproject.toml`, `uv.lock`, `requirements.txt`, `.env.example` y `.gitignore`.

No se copiaron, porque son entregables del PSet 2: `docs/` (evidencias, memo, diagramas),
`CD_PSet_2.pdf`, `README_curso.md`, `rubrica.md`, `disclaimer.txt`,
`scripts/generar_memo.py` y `scripts/empaquetar_entrega.py`. Se agregaron
`docs/corrida/.gitkeep` y `docs/calidad/.gitkeep` porque los scripts escriben ahí.

## Antes y después

| Qué | Antes (`psets/pset-02`) | Después (`psets/pset-03/pipeline`) |
|---|---|---|
| Base de Snowflake (valores por defecto, `.env.example`, `snowflake_setup.sql`) | `PORTAFOLIO` | `PORTAFOLIO_P3` |
| Bodega, rol, usuario y llave | `PSET2_WH`, `PSET2_ROL`, `PSET2_SERVICIO` | sin cambio |
| Proyecto de Compose | `name: pset2` | `name: pset3-pipeline` (volúmenes de Postgres y Kestra propios) |
| Imágenes (compose y `containerImage` de los flows) | `pset2-ingesta`, `pset2-dbt`, `pset2-spark` | `pset3-ingesta`, `pset3-dbt`, `pset3-spark` |
| Red de Docker (compose y `networkMode` de `transformar`) | `pset2_red` | `pset3_red` |
| `QUERY_TAG`, `application` de Snowflake, `appName` de Spark, User-Agent | `pset2_*` / `pset2-*` | `pset3_*` / `pset3-*` |
| Nombre del proyecto uv | `pset-02-pipeline` | `pset-03-pipeline`; `uv.lock` y los tres `requirements.txt` con las mismas versiones |
| Líneas `Uso, desde ...` | `psets/pset-02/` | `psets/pset-03/pipeline/` |
| README | README completo del PSet 2 | README corto con lo que cambia; remite a `../../pset-02/README.md` |
| Etiqueta `pset` de los tres flows (y de sus ejecuciones) | `"2"` | `"3"` |
| Namespace de Kestra | `usfq.portafolio` | sin cambio |

## Corrección: fecha del trigger en `ingesta_diaria` (2026-11-17)

La primera ejecución programada en la copia (`1LkyGFQko1nP8uqG4rXaLn`, 16-nov 18:30 de Nueva
York) falló: `extraer_cargar.py diario: error: argument --fecha: invalid fromisoformat value:
'2026-11-16T18:30:00.000000-05:00'`. En Pebble el filtro `| date(...)` solo se aplicaba a
`execution.startDate`, así que `trigger.date` llegaba con hora y zona.

| Antes | Después |
|---|---|
| `{{ inputs.fecha ?? (trigger.date ?? execution.startDate \| date('yyyy-MM-dd')) }}` | `{{ inputs.fecha ?? ((trigger.date ?? execution.startDate) \| date('yyyy-MM-dd', timeZone='America/New_York')) }}` |

El mismo error está en `psets/pset-02/kestra/flows/ingesta_diaria.yml`, que no se corrige
porque ya se entregó; las ejecuciones manuales con el input `fecha` y el backfill no lo tienen.

## Avisos por correo (2026-11-17)

Comprobación previa: la ejecución manual `7SXMpaCiw1t6nUUFgcu7wc` de `ingesta_diaria`,
lanzada sin el input `fecha` (misma expresión que usa el trigger), terminó en `SUCCESS`
con la corrección de la fecha y la etiqueta `pset: 3`.

| Archivo | Antes | Después |
|---|---|---|
| `kestra/flows/avisos.yml` | no existía | flow `usfq.avisos.avisos`: trigger de tipo Flow sobre `usfq.portafolio` (estados SUCCESS, WARNING, FAILED, KILLED; excluye `transformar`, que corre como subflow) y tarea `io.kestra.plugin.email.MailExecution` por Gmail; asunto con `Success` o `Fail` al inicio |
| `kestra/subir_flows.sh` | subía 3 flows; si Kestra rechazaba uno, salía sin mensaje (`curl -sf`) | sube también `avisos.yml` y muestra el código HTTP y el mensaje de Kestra si rechaza un flow |
| `scripts/preparar_env.sh` | codificaba `SNOWFLAKE_*` y `FECHA_*` | también `AVISO_*` |
| `.env.example` | sin avisos | `AVISO_CORREO` y `AVISO_CLAVE_APP` vacíos |

El correo y la contraseña de aplicación solo van en `.env` y `.env_encoded`, que no se suben.
Está en un namespace propio para que sus ejecuciones no lo vuelvan a disparar.

## Pruebas de Spark dentro de la imagen (2026-11-17)

Las 6 pruebas de `spark/tests/test_construir_obt.py` se saltaban en el entorno uv porque
`pyspark` está en el grupo opcional `pruebas-locales` (~317 MB) y piden Java 17.

| Archivo | Antes | Después |
|---|---|---|
| `spark/Dockerfile` | una etapa; jars con `ADD <url de Maven>` | etapas `base` (jars), `pruebas` (pytest 8.3.5, `jobs/`, `tests/`) y `runtime` (`jobs/`); jars con `RUN` + cache de BuildKit y pytest con cache de pip |
| `spark/descargar_jars.py` | no existía | baja los dos jars al cache (`/var/cache/spark-jars`) y los copia a `/opt/spark/jars`; reusa lo ya bajado |
| `spark/.dockerignore` | no existía | excluye `__pycache__/`, `.pytest_cache/`, `*.pyc` |
| `docker-compose.yml` | `spark-master` con `build: ./spark` | `target: runtime`; servicio nuevo `spark-pruebas` (perfil `pruebas`, `target: pruebas`, 2 GB) |
| `spark/tests/test_construir_obt.py` | solo uso con uv | docstring con el comando de Docker |

Primera corrida: falló con `TypeError: 'type' object is not subscriptable` en
`descargar_jars.py`, porque la imagen `apache/spark:3.5.3-python3` trae Python 3.8
(`list[str]` requiere 3.9). Se agregó `from __future__ import annotations` y se fijó
pytest 8.3.5 (pytest 8.4+ ya no soporta 3.8).

Segunda corrida: las 6 pruebas dieron `JAVA_GATEWAY_EXITED` por
`UnknownHostException` del nombre del contenedor, porque el servicio tenía
`network_mode: none`. Se quitó esa opción y la etapa `pruebas` fija
`SPARK_LOCAL_IP=127.0.0.1` y `SPARK_LOCAL_HOSTNAME=localhost`.

El contenedor de pruebas verifica que `pyspark` y `java` existen antes de pytest y muestra
los motivos de cualquier skip (`-rs`), para que un resultado verde signifique que se probó.

## H1 y H15: mercado del mes siguiente y sesion en curso (2026-11-17)

**H1.** Las columnas de mercado del mes siguiente del ultimo mes cerrado se calculaban con el
mes en curso (202610 usaba noviembre incompleto; cambiaban con cada ingesta).

| Archivo | Antes | Despues |
|---|---|---|
| `spark/jobs/construir_obt.py`, paso 6 | `lead()` sobre todos los meses de `fct_mercado_diario`, abiertos incluidos | `ret_log_sp500_mes_siguiente`, `ret_log_nyse_composite_mes_siguiente` y `rf_mes_siguiente` solo si el mes siguiente esta cerrado (`mes_cerrado` de `dim_fecha`); si no, nulos (igual que el objetivo de la accion) |
| Controles de la OBT (`VALIDACION_OBT`) | 13 | 14: nuevo "mercado del mes siguiente solo con meses cerrados" |
| `spark/tests/test_construir_obt.py` | 6 pruebas; 13 controles | 7 pruebas; 14 controles; `test_mercado_del_mes_siguiente_solo_con_meses_cerrados` (falla con el codigo anterior: 0.002 en vez de nulo) |

**H15.** Las ingestas manuales del 17-nov a las 11:33 y 12:34 de Nueva York guardaron la fila
del 2026-11-17 con el precio del momento (~470 simbolos, cambio de hasta 0,8%, factor de
ajuste sin cambio). Se corregia sola con la corrida de las 18:30, pero un cierre de mes
ingestado durante la sesion quedaria en la OBT con un precio parcial.

| Archivo | Antes | Despues |
|---|---|---|
| `kestra/scripts/extraer_cargar.py` | guardaba todas las filas que devolvia Yahoo | `ultima_sesion_cerrada()` y `quitar_sesion_en_curso()`: no guarda fechas posteriores a la ultima sesion cerrada (hoy solo despues de las 16:30 de Nueva York); lo registra en el log |
| `kestra/tests/test_sesion_en_curso.py` | no existia | 4 pruebas (antes y despues del cierre, cambio de dia en UTC, hora sin zona, tabla vacia) |
| `scripts/auditar_obt.py`, `scripts/verificar_snowflake.py` | exigen 13 controles | exigen 14 |
| `scripts/reconstruir_obt.sh` | no existia | pruebas, imagenes, `transformar`, evidencias, Compose abajo y snapshot, en un paso |
| `README.md` (pipeline) | sin estos temas | secciones "Reconstruir la OBT" y la regla de la sesion en curso |

## Avisos de reconstruir_obt.sh (2026-11-17)

| Archivo | Antes | Despues |
|---|---|---|
| `scripts/notificar.py` | no existia | envia `Success`/`Fail: <tarea>` por Gmail con `AVISO_*` de `.env`; sin credenciales o sin red avisa por pantalla y no falla (probado con un servidor SMTP falso) |
| `scripts/reconstruir_obt.sh` | sin avisos; `transformar` sin etiquetas | `trap` al salir: `Fail` con el paso en curso y el id de `transformar`; `Success` al final con el snapshot; `transformar` se lanza con `?labels=origen:manual`; termina con error si el control de H1 falla |
| `kestra/flows/avisos.yml` | un trigger; `transformar` excluido siempre | segundo trigger `transformar_manual`: `transformar` con la etiqueta `origen: manual` (las ejecuciones como subflow no la llevan) |

## H10, H11 y H13: huecos por ticker, universo por fecha y prueba de no fuga (2026-11-17)

| Archivo | Antes | Despues |
|---|---|---|
| `dbt/models/calidad/dq_huecos_por_ticker.sql` | no existia (solo el agregado `dias_miembro_sin_precio_pct`) | una fila por simbolo de la composicion: dias como miembro, con precio, `pct_huecos_miembro`, dias de vida, imputados, excluidos y `sin_precios` (sesgo de supervivencia) |
| `dbt/models/calidad/dq_universo_por_fecha.sql` | no existia | una fila por dia bursatil: miembros segun la composicion, con precio, en la NYSE hoy, con bolsa desconocida y `pct_cobertura` |
| `dbt/models/calidad/_calidad.yml` | solo `dq_metricas` | `unique`/`not_null` en ambas y `relationships` fecha -> `dim_fecha` |
| `dbt/tests/assert_huecos_coherentes_con_dq_metricas.sql` | no existia | las dos tablas suman lo mismo y coinciden con `dias_miembro_sin_precio_pct` (tolerancia 0,01 pp) |
| `scripts/exportar_metricas.py` | 5 CSV | + `huecos_por_ticker.csv` y `universo_por_mes.csv` (promedio mensual del universo por fecha) |
| `spark/tests/test_construir_obt.py` | sin prueba de fuga | `test_variables_de_noviembre_no_usan_datos_posteriores`: cambiar los retornos posteriores al cierre de noviembre no cambia ninguna variable de esa fila, solo el objetivo. Falla si una ventana mira un dia adelante (probado con `rowsBetween(-20, 1)`) |

Probado en DuckDB con la muestra de `pruebas_locales` (3 acciones): modelos y pruebas nuevas en
PASS; la prueba de coherencia pasa. El ERROR de `not_null_slv_mercado_diario_cierre_sp500` en
esa muestra ya existia (usa VTI/QQQ como sustitutos de los indices). Pruebas de Spark: 8 pasan.

## H12: primera carga sin intervencion manual (2026-11-17)

CD_PSet_2 pide que la ingesta pueda realizarse sin intervencion manual; la primera carga se
lanzaba a mano con `backfill_historico`. Decision de Paul: que la ingesta diaria la haga sola.

| Archivo | Antes | Despues |
|---|---|---|
| `kestra/scripts/extraer_cargar.py`, modo `diario` | siempre la ventana de ~7 dias habiles | `correr_diario()`: si `RAW.PRECIOS_DIARIOS` esta vacia, historico desde `ANIO_INICIO` (2010) hasta la fecha, un anio por vez (`tramos_historico()`), igual que `backfill_historico`; si no, la ventana diaria de siempre |
| `kestra/tests/test_primera_carga.py` | no existia | 4 pruebas: tramos por anio, RAW vacia -> historico, RAW con datos -> ventana diaria, lunes -> referencias |
| `kestra/flows/ingesta_diaria.yml` (descripcion) y `README.md` paso 5 | backfill manual | primera carga automatica; `backfill_historico` queda para recargar rangos |

La tarea de ingesta tiene `timeout: PT2H`; el backfill completo del 16-nov tardo ~18 minutos.

## Documentacion, diagramas y pruebas de orquestacion (2026-11-17)

| Archivo | Antes | Despues |
|---|---|---|
| `docs/arquitectura.dot/.png/.svg`, `arquitectura_vertical.png` | solo en `pset-02/docs` (PORTAFOLIO, pset2-*, sin avisos) | copia actualizada: PORTAFOLIO_P3, imagenes pset3-*, flow `avisos` y Gmail, `reconstruir_obt.sh`, primera carga automatica, sesion en curso, CALIDAD ampliada, 14 controles, `spark-pruebas` y consumo del PSet 3 |
| `docs/modelo_dimensional.*` | solo en `pset-02/docs` | copia; Gold sin cambios (nota PORTAFOLIO_P3) |
| `docs/structurizr/workspace.dsl` y `export/` | solo en `pset-02/docs` | C4 actualizado: sistema externo Gmail, sistema "Modelado del PSet 3", contenedor `reconstruir_obt.sh`, relaciones de avisos; validado y exportado con el CLI de Structurizr (Mermaid, PlantUML, PNG) |
| `docs/diccionario_datos.md`, `docs/README.md` | solo en `pset-02/docs` | diccionario con CALIDAD nueva y el cambio de H1; indice de la carpeta |
| `kestra/flows/ingesta_diaria.yml` | sin forma de probar los reintentos | input `simular_falla` (BOOL, por defecto false): la tarea falla antes de bajar datos |
| `scripts/probar_ingesta_y_reintentos.sh` | no existia | V2.4 (ingesta manual y la del cron) y V2.5 (falla simulada con reintentos) con evidencia en `docs/corrida/kestra_pruebas.json` |

## F1: OHLCV, diferencias diarias y variables nuevas para los modelos (2026-11-17)

Pedido de Paul: todas las columnas propuestas, en porcentaje y en logaritmo, con OHLCV completo y
las diferencias diarias aritmeticas, porcentuales y logaritmicas. Explicacion de cada forma en
`pipeline/docs/series_de_tiempo.md`; columnas en `pipeline/docs/diccionario_datos.md`.

| Archivo | Antes | Después |
|---|---|---|
| `dbt/models/silver/slv_precios_acciones.sql` | OHLC sin ajustar, cierre y apertura ajustados; solo retornos log (diario, apertura, intradia, nocturno) | + `precio_maximo_ajustado`, `precio_minimo_ajustado` (nulos en dias imputados); `dif_cierre_ajustado`, `dif_apertura_ajustada` (aritmeticas, USD); `ret_pct_diario`, `ret_pct_apertura`, `ret_pct_intradia`, `ret_pct_nocturno` (= exp(log) − 1); `rango_pct_hl`, `rango_log_hl` |
| `dbt/models/gold/fct_precios_diarios.sql` | 21 columnas | + las 12 columnas nuevas de Silver (33) |
| `dbt/models/silver/_silver.yml` | sin pruebas de rango ni de retorno simple | `rango_log_hl` ≥ 0, `rango_pct_hl` ≥ 0, `ret_pct_diario` ≥ −1 |
| `dbt/tests/assert_diferencias_diarias_coherentes.sql` | no existia | pct = exp(log) − 1, log diario = nocturno + intradia, dif = P(t−1)·pct, rango ≥ |intradia|, sin rango en dias imputados |
| `spark/jobs/construir_obt.py` | OBT_ACCION_MES con 43 columnas; 14 controles | 75 columnas (32 nuevas: `ret_pct_mes`, rezagos 1–3 en log y %, intradia y nocturno del mes, rango maximo-minimo del mes y de 21/63 dias, su cambio, Parkinson, Garman-Klass, `vol_intradia_21d`, `beta_252d`, exceso sobre el S&P 500, volumen relativo, `ret_pct_mes_siguiente`); nueva `OBT_ACCION_DIA` (accion x dia, 33 columnas: OHLCV y diferencias) para los modelos de series; 17 controles (join diario x mercado, filas y grano de la OBT diaria) |
| `spark/tests/test_construir_obt.py` | 8 pruebas | 13: % = exp(log) − 1, intradia_mes + nocturno_mes = ret_log_mes, rezagos solo con meses consecutivos, Parkinson/Garman-Klass/exceso/volumen relativo con valores conocidos, OBT diaria con las filas de Gold |
| `scripts/verificar_snowflake.py` | 14 controles, 43 columnas | 17 controles, 75 columnas, OBT diaria con las filas de `FCT_PRECIOS_DIARIOS` y 33 columnas |
| `scripts/auditar_obt.py` | 14 controles | 17 |
| `scripts/exportar_metricas.py`, `scripts/diagnosticar_calidad.py` | sin OBT diaria | conteo y llave (`ACCION_KEY`, `FECHA`) de `OBT.OBT_ACCION_DIA` |
| `kestra/flows/transformar.yml` | descripcion: escribe OBT_ACCION_MES | escribe OBT_ACCION_MES y OBT_ACCION_DIA |
| Diagramas (`arquitectura`, `modelo_dimensional`, C4) | OBT mensual, 14 controles | OBT diaria, 17 controles, diferencias en Silver/Gold; renders regenerados |

Decision: en la suma mensual, intradia y nocturno solo cuentan los dias con retorno de cierre
(el primer dia de la serie no tiene cierre anterior); asi intradia_log_mes + nocturno_log_mes =
ret_log_mes exacto. La primera version dejaba ese dia y en la muestra local el error llegaba a 0,02.

Verificacion aqui: dbt en DuckDB (muestra de `pruebas_locales`): las 4 pruebas nuevas pasan; el
unico error es `not_null_slv_mercado_diario_cierre_sp500`, propio de la muestra (sin ^GSPC real).
Spark local sobre esa muestra: 17/17 controles, 330 filas y 75 columnas en la OBT mensual, 6.918
filas y 33 columnas en la diaria, identidad del mes con error 0. pytest de Spark: 13 passed.
Falta en la Mac: `bash scripts/reconstruir_obt.sh` (imagenes, dbt, Spark y snapshot en PORTAFOLIO_P3).

## Progreso de las ejecuciones de Kestra en los scripts (2026-11-17)

| Archivo | Antes | Después |
|---|---|---|
| `scripts/progreso_kestra.py` | no existia | estado en stdout y, en stderr, una linea por consulta: hora, inicio, transcurrido, tareas terminadas/total con la tarea en curso y su intento, duracion esperada (mediana de las ultimas 5 ejecuciones SUCCESS del flow), fin estimado y lo que falta |
| `scripts/reconstruir_obt.sh` (espera de `transformar`) | `curl` + `printf '%s '` del estado: `RUNNING RUNNING ...` | `python3 scripts/progreso_kestra.py`, una linea de progreso cada 20 s |
| `scripts/probar_ingesta_y_reintentos.sh` (`esperar`) | igual, cada 30 s | igual que arriba, cada 30 s |

## Memoria de Spark tras F1 (2026-11-17)

`transformar` 5qK1iyr0GzaHsbKepN8qZd: `obt_spark` fallo en sus 2 intentos (~10 min cada uno) al
calcular un shuffle; la OBT anterior quedo intacta. El ejecutor tiene 2 GB y un nucleo.

| Archivo | Antes | Después |
|---|---|---|
| `kestra/flows/transformar.yml` y `docker-compose.yml` (`spark-job`) | `--executor-memory 2g --driver-memory 1g` | `--executor-memory 5g --driver-memory 2g`: la poda sola no alcanzo; la segunda corrida (6RmZOc1H6gG5yuD6xzblhr) fallo igual con `SparkOutOfMemoryError: [UNABLE_TO_ACQUIRE_MEMORY]`. Docker Desktop tiene 15,6 GB |
| `docker-compose.yml` (`spark-worker`), `.env.example` y el `.env` local | `SPARK_WORKER_MEMORY` 2g | 6g (el worker tiene que poder dar los 5 GB del ejecutor) |
| `scripts/progreso_kestra.py` | mediana de las 5 ultimas SUCCESS que devolvia la busqueda | filtra tambien flow, namespace y estado del lado del cliente (durante un RETRYING la mediana salto de 3 min a 4 s) |
| `spark/jobs/construir_obt.py` | las ventanas arrastraban las 33 columnas del hecho diario | `select` de las 25 que usan las ventanas y el resumen del mes, justo despues del join con el mercado; la OBT diaria se arma aparte. Mismas 75 columnas y 17 controles (13 pruebas OK; muestra local: identidad del mes con error 0) |

### Worker de 2 GB y uso de nucleos

`transformar` 4mLKrXy4A61Cpqu63pZ0ii, ya con el worker de 6 GB, paso 14 controles (incluida OBT_ACCION_DIA con 1.832.433 filas) en 6 min y se detuvo a mano desde la interfaz de Kestra antes de escribir.

`transformar` 5pxO2lQcvsKRSKX1CXmoyS quedo 50 min en `Initial job has not accepted any resources`
y se detuvo a mano (KILLED). La interfaz de Spark mostro el worker con 2048 MB aunque `.env` y
`docker compose config` resolvian 6g: el contenedor no se habia recreado con el valor nuevo. Tras
`docker compose up -d --force-recreate spark-worker` registro 6144 MB y el ejemplo Pi con un
ejecutor de 5 GB termino en 2 s.

Docker Desktop tiene 16 CPU y 15,6 GB, y el job usaba un solo nucleo. Presupuesto de memoria:
Kestra ~2 GB, Postgres ~0,3 GB, demonios master y worker ~1 GB cada uno, driver 2 GB, ejecutor
7 GB + ~10 % de overhead, en total unos 14 GB.

| Archivo | Antes | Después |
|---|---|---|
| `kestra/flows/transformar.yml` y `docker-compose.yml` (`spark-job`) | `--executor-memory 5g`, `spark.executor.cores=1`, `spark.cores.max=1` | `--executor-memory 7g`, 4 nucleos, `spark.sql.shuffle.partitions=32` (particiones mas chicas, menos memoria por tarea) y AQE explicito |
| `docker-compose.yml` (`spark-worker`), `.env.example` y el `.env` local | `SPARK_WORKER_CORES` 2, `SPARK_WORKER_MEMORY` 6g | 4 y 8g |
| `spark/jobs/construir_obt.py` (mercado mensual) | `Window.orderBy("anio_mes")`: Spark repetia el WARN `No Partition Defined for Window operation` en cada accion que recalcula el mercado | `Window.partitionBy(F.lit(1)).orderBy("anio_mes")`: mismo resultado (unas 200 filas, una particion); 13 pruebas OK |

Riesgo: con 4 tareas a la vez, cada una dispone de ~1,75 GB del ejecutor frente a 5 GB con un
nucleo. Si vuelve `UNABLE_TO_ACQUIRE_MEMORY`, el siguiente paso es 2 nucleos con el mismo ejecutor.

Resultado: `transformar` 3bCTRKESZAhdNt1G86o1Co termino en SUCCESS (6 min 44 s en total; `obt_spark`
5 min 56 s, de los cuales ~1 min 46 s es la escritura en Snowflake). El ejecutor recibio 4 nucleos y 7 GB,
sin errores de memoria y sin el WARN `No Partition Defined`. Hasta el ultimo control de OBT_ACCION_DIA tardo
4 min 08 s, frente a 5 min 32 s con 1 nucleo (corrida 4mLKrXy4A61Cpqu63pZ0ii). Verificacion: 17 controles OK,
OBT_ACCION_MES 87.178 filas y 75 columnas (58.628 elegibles), OBT_ACCION_DIA 1.832.433 filas y 33 columnas.

### H18: elegible exige volumen

El EDA (`notebooks/01_eda.ipynb`) encontro una fila elegible con precio plano y sin negociacion: AMCR 2014-08
(`vol_21d` = 0, `volumen_prom_21d` = 0), relleno de la fuente antes de que la accion cotizara. Aprobado por Paul el 18-nov.

| Archivo | Antes | Después |
|---|---|---|
| `spark/jobs/construir_obt.py` | `elegible` = en_sp500 y (es_nyse o bolsa_desconocida) y cotizo_al_cierre_de_mes y obs_252d >= 200 y dias_negociados_mes >= 15, escrito dentro de `construir()` | la misma condicion en `condicion_elegible()` mas `volumen_prom_21d > 0` (nulo cuenta como no elegible) |
| `spark/tests/test_construir_obt.py` | 13 pruebas | 14: `test_elegible_exige_volumen_positivo` (con volumen, cero, nulo, historia corta) |
| `docs/diccionario_datos.md` | `elegible` sin definicion explicita | definicion completa con la regla nueva |

Efecto esperado: 1 fila menos de entrenamiento (46.926 -> 46.925). Se aplica al reconstruir la OBT (`scripts/reconstruir_obt.sh`) y tomar un snapshot nuevo.

## Cambios fuera de `pipeline/`

| Archivo | Antes | Después |
|---|---|---|
| `src/datos.py` | `TABLA='PORTAFOLIO.OBT.OBT_ACCION_MES'` | `tabla()` usa `SNOWFLAKE_DATABASE`, por defecto `PORTAFOLIO_P3` |
| `src/datos.py` (F1) | solo OBT_ACCION_MES; no revisaba columnas | `--grano mes|dia` (OBT_ACCION_DIA -> `data/obt_dia.parquet`, clave accion_key+fecha); `fetch_pandas_all` para las 1,8 M filas; `exportar` y `cargar` fallan si faltan columnas de F1 (snapshot viejo) |
| `src/pipeline.py` (F1) | `BASE` de 17 variables + 2 derivadas (19); sin catalogo de columnas | catalogo `OBT_MES` (43 del PSet 2 + 32 de F1 = 75) y `OBT_DIA` (33); `FEATURES` = 17 + 16 de F1 en logaritmo + 2 derivadas (35); `F1_PCT` (15) fuera de los predictores (misma variable que la log); `FUGA` (11) nunca entra; `preparar` avisa si el snapshot no tiene F1 |
| `src/modelos/tabulares.py` | `FEATURES_F1` con su propia lista de 33 | importa `FEATURES_OBT` de `src/pipeline.py` (fuente unica; mismas 33) |
| `.env.example` | sin `SNOWFLAKE_DATABASE` | `SNOWFLAKE_DATABASE=PORTAFOLIO_P3` |
| `analisis/equivalencias_tickers.py` | escribía la semilla en `../pset-02/dbt/seeds` y `../pset-02/kestra/scripts` | la escribe en `pipeline/dbt/seeds` y `pipeline/kestra/scripts` |
| `.dockerignore` | sin `pipeline/` ni `analisis/` | los excluye del contexto de la imagen de MLflow |
| `pyproject.toml` | pytest sin `testpaths` | `testpaths = ["tests"]` |
| `docs/separacion_alcance.json` | fuente `OBT.OBT_ACCION_MES`; escrituras en Snowflake: "Ninguna" | fuente `PORTAFOLIO_P3.OBT.OBT_ACCION_MES`; notebooks y `src/` no escriben, `pipeline/` escribe solo en `PORTAFOLIO_P3` (se conserva el valor anterior en `antes`) |
| `README.md`, Verificación funcional aislada | "la única dependencia compartida es la OBT ya materializada en Snowflake" | los notebooks solo leen la OBT de `PORTAFOLIO_P3`; `pipeline/` solo hace falta para reconstruirla |
| `README.md` | "docker compose down desde `../pset-02/`" | desde `pipeline/`; nota sobre la copia y `PORTAFOLIO_P3` |

## Consecuencia para el snapshot

`data/obt.parquet` y los notebooks actuales provienen de `PORTAFOLIO.OBT.OBT_ACCION_MES`
(sha256 `f66dd033…`). Al correr el pipeline copiado y luego `uv run python -m src.datos`,
el snapshot pasará a `PORTAFOLIO_P3.OBT.OBT_ACCION_MES` y el manifiesto lo registrará.

## Verificación

- `uv lock` en `pipeline/`: mismas versiones que `pset-02` (salvo el nombre del proyecto).
- `uv run pytest` en `pipeline/`: 3 pasan y 1 se salta (Spark sin pyspark/Java).
- `uv run pytest` en `pset-03`: 3 pasan.
- `docker compose config` con `.env.example` y claves de prueba: válido.
- `git grep` de secretos: solo nombres de variables en `scripts/preparar_env.sh`.
