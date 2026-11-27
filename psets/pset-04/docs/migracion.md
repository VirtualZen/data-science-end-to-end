# Copia del PSet 3 en `pipeline/` y `modelos/`

Fecha: 2026-11-26. Rama `work` (`4e7e870`). Motivo: el PSet 4 puede necesitar cambios en el
pipeline y en el modelado, y `psets/pset-02/` y `psets/pset-03/` ya se entregaron (tags
`pset-02` y `pset-03`), así que no se modifican. Es el mismo procedimiento con que el PSet 3
copió el pipeline del PSet 2 (`../../pset-03/docs/migracion_pipeline.md`).

## Qué se copió

| Destino | Origen | Archivos versionados | No se copió |
|---|---|---|---|
| `pipeline/` | `psets/pset-03/pipeline/` | 112 | evidencias de corridas anteriores (`docs/corrida/`, `docs/calidad/`); quedan sus `.gitkeep` |
| `modelos/` | `psets/pset-03/` (modelado) | 45: `src/`, `notebooks/`, `tests/`, `artefactos/`, `pyproject.toml`, `uv.lock`, `requirements.txt`, `exportar_requirements.sh`, `Dockerfile`, `Dockerfile.runner`, `docker-compose.yml`, `.env.example`, `.gitignore`, `.dockerignore` | `docs/` (entregables y evidencias del PSet 3), `scripts/` (generan el memo y la presentación del PSet 3), `analisis/` (antecedente, ver `../../pset-03/analisis/README.md`), `plan.txt` |

Archivos locales copiados, fuera de git (`.gitignore`): `pipeline/.env`, `pipeline/.env_encoded`,
`pipeline/secrets/`, `modelos/.env`, `modelos/data/obt*.parquet|json` (snapshot de la OBT del PSet 3)
y `modelos/mlflow/` (MLflow completo: 3 experimentos, 142 corridas de `portafolio-inversiones` y el
Model Registry). Las credenciales se copiaron sin abrirlas; en los `.env` solo cambió
`SNOWFLAKE_DATABASE`, y `.env_encoded` se regeneró con `bash scripts/preparar_env.sh`.

## Antes y después

| Qué | Antes (`psets/pset-03`) | Después (`psets/pset-04`) |
|---|---|---|
| Base de Snowflake (valores por defecto, `.env.example`, `.env`, `snowflake_setup.sql`) | `PORTAFOLIO_P3` | `PORTAFOLIO_P4` |
| Bodega, rol, usuario y llave | `PSET2_WH`, `PSET2_ROL`, `PSET2_SERVICIO` | sin cambio |
| Compose del pipeline | `name: pset3-pipeline` | `name: pset4-pipeline` (volúmenes de Postgres y Kestra propios) |
| Imágenes (compose y `containerImage` de los flows) | `pset3-ingesta`, `pset3-dbt`, `pset3-spark`, `pset3-spark-pruebas` | `pset4-*` |
| Red de Docker (compose y `networkMode` de `transformar`) | `pset3_red` | `pset4_red` |
| `QUERY_TAG`, `application` de Snowflake, `appName` de Spark, User-Agent | `pset3_*` / `pset3-*` | `pset4_*` / `pset4-*` |
| Etiqueta `pset` de los flows | `"3"` | `"4"` |
| Proyecto uv del pipeline | `pset-03-pipeline` | `pset-04-pipeline` (`uv.lock` regenerado, mismas versiones) |
| Proyecto uv del modelado | `pset-03-modelado` en `psets/pset-03/` | `pset-04-modelos` en `psets/pset-04/modelos/` (mismas versiones) |
| Compose de MLflow | `name: pset3` | `name: pset4-modelos` (contenedor `pset4-modelos-mlflow-1`, alineado con `pset4-pipeline`; mismo puerto 5001, no levantar los dos a la vez) |
| Ubicación del modelado | raíz de `psets/pset-03/` (`../.env` desde `pipeline/`) | `psets/pset-04/modelos/` (`../modelos/.env` desde `pipeline/`) |
| `scripts/reconstruir_obt.sh` | verifica `../.env` y hace el snapshot en `..` | verifica `../modelos/.env` y hace el snapshot en `../modelos` |
| Namespace de Kestra | `usfq.portafolio` | sin cambio |

Sin cambios a propósito: los notebooks (`modelos/notebooks/`) conservan sus salidas del PSet 3,
que mencionan `PORTAFOLIO_P3`; se vuelven a ejecutar en el PSet 4. Los diagramas renderizados
(`.svg`, `.png`, `docs/structurizr/export/`) y la nota histórica de `spark/jobs/construir_obt.py`
(variables F1 del PSet 3) también quedan como estaban; los diagramas se regeneran con la arquitectura
del PSet 4. La variable de entorno `PSET3_DATOS` de `src/entorno.py` conserva su nombre.

## Verificación de la copia

- `uv lock --check` al día en `pipeline/` y `modelos/`.
- `modelos/`: `uv run python -m pytest -q tests` → 28 pruebas pasan.
- `pipeline/`: `uv run python -m pytest -q kestra/tests` → 11 pruebas pasan.
- `git status psets/pset-02 psets/pset-03` → sin cambios.
- Registro copiado (`modelos/mlflow/tracking.db`): `portafolio-inversiones-modelo` v1 alias `champion`
  (LightGBM, run `f7596a565f8a458492057238f245cf89`) y v2 alias `challenger` (Ridge, run
  `75f75a7030154008a54e502bf2e4d18b`), los mismos del PSet 3.

## Base nueva PORTAFOLIO_P4

`PORTAFOLIO_P4` se creó una vez con `pipeline/kestra/sql/snowflake_setup.sql` (rol `ACCOUNTADMIN`, en Snowsight). Se
llenó con el pipeline (`pipeline/README.md`) el 2026-11-26: backfill histórico 2019-2026 y luego solo 2025, por el
hallazgo H1 de `plan.txt`, más `transformar`. El snapshot nuevo es `modelos/data/obt_p4.parquet`. `modelos/data/obt.parquet`
sigue siendo el del PSet 3, que es la referencia del champion. La comparación entre los dos y el cambio de bolsa de GM
están en [`datos_p4.md`](datos_p4.md).

## Cambios del PSet 4 sobre las copias (2026-11-27)

| Archivo | Antes | Después | Verificación |
|---|---|---|---|
| `pipeline/scripts/preparar_env.sh` | Pasa a `.env_encoded` las variables `SNOWFLAKE_*`, `FECHA_*` y `AVISO_*` | También `API_TOKEN` (secreto de Kestra para `/recargar` en `reentrenamiento.yml`) | `grep -c '^SECRET_API_TOKEN=' pipeline/.env_encoded` = 1 |
| `pipeline/kestra/subir_flows.sh` | Sube 4 flows | Sube 7: + `monitoreo`, `reentrenamiento` y `produccion_lotes` (namespace `usfq.produccion`) | Paul: la salida del script en el Mac |
| `pipeline/kestra/flows/` | 4 flows | + `monitoreo.yml`, `reentrenamiento.yml`, `produccion_lotes.yml` | Lógica probada con `monitoreo/produccion.py` en modo local (35 lotes); los flows, en Kestra |
| `pipeline/kestra/sql/` | `snowflake_setup.sql` | + `produccion_setup.sql` (esquema `PRODUCCION` y sus 4 tablas) | Paul: Snowsight |
| `modelos/src/reentrenar.py` | No existía | Reentrenamiento, comparación, regla de promoción, registro y promoción | `tests/`, notebook 06 |
| `modelos/src/operacion_manual.py` | No existía | Competidor "operación manual" (usa `src.negocio.backtest` y `pesos_mes`, sin cambiarlos) | `tests/test_operacion_manual.py`, notebook 08 |
| `modelos/src/pipeline.py` | — | Sin cambios: la preparación de inferencia está en `monitoreo/simulacion.py` e importa `derivar` | — |
| `docker-compose.yml` (raíz de `pset-04`) | Dos compose (`pipeline/`, `modelos/`) | Uno con Kestra, Postgres, Spark, MLflow, API, tablero e imágenes de tarea; reusa los volúmenes `pset4-pipeline_*` | Paul: `docker compose up` |
| `modelos/pyproject.toml`, `uv.lock`, `requirements.txt`, `exportar_requirements.sh` | Sin Streamlit; el Dockerfile lo instalaba aparte (`pip install ... "streamlit==1.67.0"`, sus dependencias sin fijar) | Grupo `tablero` con `streamlit==1.67.0` en el lock; el export incluye `--group tablero`. Agrega solo altair 6.3.0, pydeck 0.9.3, streamlit 1.67.0 y watchdog 7.1.1; ninguna otra versión cambia | `diff` de los paquetes de `uv.lock` antes y después |
