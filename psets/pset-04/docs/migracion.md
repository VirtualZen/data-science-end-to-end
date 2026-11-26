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
| Compose de MLflow | `name: pset3` | `name: pset4` (mismo puerto 5001; no levantar los dos a la vez) |
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

## Pendiente antes de usar la base nueva

`PORTAFOLIO_P4` todavía no existe en Snowflake. Se crea una vez con
`pipeline/kestra/sql/snowflake_setup.sql` (rol `ACCOUNTADMIN`, en Snowsight) y se llena con el
pipeline (`pipeline/README.md`): backfill histórico, `transformar` y snapshot nuevo de la OBT.
