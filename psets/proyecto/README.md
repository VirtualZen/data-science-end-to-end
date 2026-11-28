# Proyecto final: portafolio de inversiones en producción (PSets 1–4)

Sistema completo del proyecto (S&P 500 ∩ NYSE, retorno log del mes siguiente, top 10 con pesos 1/vol; las acciones del
S&P 500 que cotizan en el NASDAQ se excluyen por la dificultad de comprarlas, disclaimer 18): datos →
modelo → registro → API → simulación de producción → monitoreo → reentrenamiento con aprobación humana.

Esta carpeta reúne el proyecto completo (PDF del PSet 4, sección 10). Es una copia de los archivos versionados de
`psets/pset-04/` en el tag `pset-04` (sin el enunciado, la rúbrica ni el plan de trabajo del PSet); el código, los
flows, las pruebas y la evidencia son los mismos. Las diferencias con la guía y la plantilla del curso están en
`disclaimer.txt` (puntos 14 y 15: carpetas de la plantilla y versiones de librerías en la CI del curso). `psets/pset-02/` y `psets/pset-03/` no se modifican:
`pipeline/` y `modelos/` son copias (`docs/migracion.md`) que escriben en la base `PORTAFOLIO_P4` de Snowflake.

## Mapa a la estructura del PDF (`proyecto_final/`)

| PDF | Aquí |
|---|---|
| `docker-compose.yml`, `.env.example`, `requirements.txt` | Los tres en la raíz de `proyecto/`. `.env.example` es la plantilla completa (igual a `pipeline/.env.example` + MLflow); `requirements.txt` incluye `modelos/requirements.txt` (exportado de `uv.lock`) + pytest y httpx; la imagen de la API usa `api/requirements.txt`, con las mismas versiones del modelo |
| `.github/workflows/ci.yml`, `cd.yml` | `/.github/workflows/pset4-ci.yml`, `pset4-cd.yml` en la raíz del repositorio (GitHub solo corre los de la raíz) |
| `kestra/{ingesta, produccion_lotes, monitoreo, reentrenamiento}.yml` | `pipeline/kestra/flows/` (`ingesta_diaria`, `backfill_historico`, `transformar`, `avisos`, `produccion_lotes`, `monitoreo`, `reentrenamiento`) |
| `dbt/`, `spark/` | `pipeline/dbt/`, `pipeline/spark/` |
| `src/{datos, pipeline, reentrenar}.py` | `modelos/src/` |
| `notebooks/01–05, 06_simulacion_produccion, 07_analisis_monitoreo` | `modelos/notebooks/` (01–06 del PSet 3; `06_champion` es la recarga del champion del PSet 3) y `08_competidores` (modelo frente a la operación manual, B3, B5 y efectivo en CV, hold-out y simulación) |
| `api/{Dockerfile, main.py, esquemas.py}` | `api/` |
| `monitoreo/{deriva, alertas}.py` | `monitoreo/` (+ `simulacion.py`, `produccion.py`, `tablero.py`, `Dockerfile`) |
| `tests/{fixtures, test_contrato, test_modelo, test_comportamiento}.py` | `tests/` |
| `docs/` | `docs/` (CSV exportados, documentos, figuras, `historial/`) |

## Tres formas de reproducir (auditoría H4)

| Modo | Qué necesita | Qué se obtiene |
|---|---|---|
| **1. Demostración con fixtures** | Solo el clon, `uv` y Docker. Sin cuentas | 53 pruebas (`uv run --project api --frozen pytest tests -v`) y la API con la copia del champion: `docker build -f api/Dockerfile -t pset4-api . && docker run -p 8000:8000 -e MODELO_URI=/fijas/modelo_champion -e API_TOKEN=demo -v "$PWD/tests/fixtures:/fijas:ro" pset4-api` y luego `/salud`, `/modelo` y `/predecir` con `tests/fixtures/lote_2024_01.json` |
| **2. Reconstrucción con datos nuevos** | Cuenta de Snowflake (usuario de servicio), `pipeline/.env`, Docker con ~11 GB | Todo el sistema desde cero, con los pasos de abajo: ingesta, dbt y Spark → snapshot de la OBT → notebooks 01–05 (registran el champion en un MLflow vacío y crean los alias) → `produccion_lotes`. Las cifras cambian, porque Yahoo devuelve datos corregidos y el entrenamiento se repite |
| **3. Evidencia histórica** | No es reproducible de forma exacta sin el registro de MLflow (`modelos/mlflow/`) y los snapshots (`modelos/data/`), que no se versionan | Se entrega como evidencia: `docs/*.csv` (predicciones, monitoreo, alertas, corridas, reentrenamientos), `docs/simulacion/`, los notebooks con salida, las huellas sha256 de los snapshots (`docs/datos_p4.md`) y `docs/reconciliacion.md` |

## Reproducir de punta a punta

Requisitos: Docker, `uv`, una cuenta de Snowflake con el usuario de servicio del PSet 2 y `pipeline/.env` completo
(`cp .env.example pipeline/.env` y completar, incluido `API_TOKEN`). Ningún secreto va en git. Desde
`psets/proyecto/`:

```bash
bash pipeline/scripts/preparar_env.sh                                    # .env_encoded para Kestra (incluye API_TOKEN)
docker compose --env-file pipeline/.env --profile herramientas build     # ingesta, dbt, spark, produccion, mlflow, api
docker compose --env-file pipeline/.env up -d                            # kestra, postgres, spark, mlflow, api, tablero
(cd pipeline && bash kestra/subir_flows.sh)                              # los 7 flows
```

1. **Fuente → Raw → Bronze → Silver → Gold → OBT.** En Snowsight: `pipeline/kestra/sql/snowflake_setup.sql` y
   `produccion_setup.sql`. En Kestra (http://localhost:8090): `usfq.portafolio.backfill_historico` (ingesta a RAW y
   subflow `transformar`: dbt build con tests y Spark a `OBT.OBT_ACCION_MES`). Detalle: `pipeline/README.md`.
2. **EDA y modelo.** `modelos/notebooks/01`–`05` (PSet 3). Snapshot de la OBT (el módulo está en `modelos/src`, por eso
   se corre desde `modelos/`; la salida queda en `modelos/data/obt_p4.parquet`, fuera de git):
   `cd modelos && uv run python -m src.datos --salida data/obt_p4.parquet && cd ..` (`docs/datos_p4.md`).
3. **Registro.** Línea base B7 (operación manual): `cd modelos && uv run python -m src.operacion_manual --registrar`.
   MLflow en http://localhost:5001: `portafolio-inversiones-modelo` v1 = champion (LightGBM, run
   `f7596a56…`), v2 = challenger del PSet 3 (Ridge). `06_champion.ipynb` lo recarga y reproduce el MAE.
4. **API.** http://localhost:8000/docs. `GET /salud`, `GET /modelo`, `POST /predecir` (lote del mes → retorno
   predicho, decisión, peso, versión, id, y en paralelo la decisión de la operación manual, B7), `GET /metricas`, `POST /recargar` y `POST /respaldo` (con `X-Token`).
   ```bash
   curl -s -H 'Content-Type: application/json' --data @tests/fixtures/lote_2024_01.json localhost:8000/predecir | head -c 600
   curl -s -H 'Content-Type: application/json' --data '{"anio_mes": 202313, "acciones": []}' localhost:8000/predecir
   ```
5. **Simulación de producción.** Kestra: `usfq.produccion.produccion_lotes` (desde 202312 hasta 202610: 35 lotes; el último, sin objetivo todavía). Cada lote:
   `lote` (OBT → `/predecir` → `PRODUCCION.PREDICCIONES`), `monitoreo` (→ `MONITOREO`, `ALERTAS`, correo si hay
   críticas) y, si la regla se dispara, `reentrenamiento` (MLflow `@challenger` → **pausa** para aprobar en la UI →
   `@champion` y recarga de la API). Análisis: `06_simulacion_produccion.ipynb`, `07_analisis_monitoreo.ipynb` y `08_competidores.ipynb`.
6. **Tablero.** http://localhost:8501 (servicio `tablero` del compose, lee Snowflake). Sin Docker:
   `uv run --project modelos --group tablero streamlit run monitoreo/tablero.py -- --csv` (lee los CSV de `docs/`).
7. **Exportar las tablas a `docs/`** (para el documento):
   ```bash
   docker compose --env-file pipeline/.env --profile herramientas run --rm -v "$PWD/docs:/salida" produccion python -m monitoreo.produccion exportar --destino /salida
   ```

Memoria: con todo arriba Docker usa ~11 GB (Spark 8 GB). Spark solo hace falta en `transformar`; para la simulación
basta `up -d postgres kestra mlflow api tablero` (`disclaimer.txt`, punto 6).

## Carpetas de la plantilla del curso

La plantilla de `psets/proyecto/` trae carpetas por etapa (vacías, con `.gitkeep`). El proyecto conserva la
estructura del PDF del PSet 4 (que manda sobre la del repositorio) y las carpetas de la plantilla quedan como
índice:

| Plantilla | Dónde está |
|---|---|
| `ingesta/`, `orquestacion/`, `infra/` | `pipeline/kestra/` (flows, imagen de ingesta, scripts) y `docker-compose.yml` |
| `calidad/`, `warehouse/` | `pipeline/dbt/` (modelos y tests de dbt: Bronze → Silver → Gold) |
| `procesamiento/` | `pipeline/spark/` (OBT) |
| `modelado/` | `modelos/` (`src/`, `notebooks/`) |
| `servicio/` | `api/` |
| `monitoreo/` | `monitoreo/` |
| `data/raw`, `data/processed` | Snowflake (`PORTAFOLIO_P4`); snapshot local en `modelos/data/` (no se versiona) |
| `docs/` | `docs/` |

## Versiones de librerías y la CI del curso

`.github/workflows/pruebas.yml` (del curso) corre `pytest psets/proyecto` con el `requirements.txt` de la raíz del
repositorio: scikit-learn 1.5.2, mlflow 2.17.2, pandas 2.2.2, numpy 1.26.4. El champion se entrenó y registró con
scikit-learn 1.9.1, mlflow 3.18.0, pandas 3.1.1 y numpy 2.4.6 (`api/uv.lock`, `modelos/uv.lock`): con las versiones
del curso no carga el modelo ni corren las pruebas. `conftest.py` compara las versiones instaladas con las del
proyecto y, si no coinciden, no recoge las pruebas (pytest sale con código 5, que `pruebas.yml` acepta) y lo dice en
el resumen. Las pruebas sí corren con el entorno correcto en `pset4-ci.yml`, sobre esta carpeta y sobre `pset-04/`:

```bash
uv run --project api --frozen pytest tests -v
```

## Pruebas y CI/CD

```bash
uv sync --project api --frozen
uv run --project api --frozen pytest tests -v        # 53 pruebas, sin MLflow ni Snowflake
```

`tests/fixtures/` tiene la copia del champion (`mlflow.sklearn.save_model`, generada por `generar_fixtures.py` desde el
registro), el hold-out con objetivo y un lote válido. `pset4-ci.yml` corre las pruebas, construye la imagen y la
prueba arrancada (200 y 422) en cada push o PR que toque `psets/pset-04/` o `psets/proyecto/` (una corrida por carpeta). `pset4-cd.yml`, al integrar en `master`,
publica `ghcr.io/virtualzen/pset4-api:<hash>`; `API_TAG=<hash> docker compose ... up -d --no-build api` usa esa imagen.

## Trazabilidad de una predicción

`PREDICCIONES.id_prediccion` → `modelo_version` y `run_id` (MLflow: params `huella_datos` y snapshot; artefacto del
pipeline) → `huella_obt` (md5[:12] de la OBT leída en el lote) → `OBT.OBT_ACCION_MES` (`anio_mes`, `accion_key`) →
tablas Gold (`GOLD.FCT_PRECIOS_DIARIOS`, `DIM_ACCION`) de las que Spark la construyó (`pipeline/spark/`).

## Documentos

`docs/despliegue.md` · `simulacion.md` · `guion_video.md` · `monitoreo.md` · `reentrenamiento.md` · `criterio_retirada.md` ·
`cambios.md` · `datos_p4.md` · `migracion.md` · `reconciliacion.md` · documento técnico `PSet4_memo_Gomez_Ehmig.pdf` · presentación
`PSet4_presentacion_Gomez_Ehmig.pdf` · `historial/` (memos y pitch de los PSets 1–3).
