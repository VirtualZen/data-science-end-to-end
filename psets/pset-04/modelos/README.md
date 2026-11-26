# Modelado del PSet 4 (copia del PSet 3)

Copia de `psets/pset-03/` (solo el modelado: `src/`, `notebooks/`, `tests/`, `artefactos/` y el
entorno uv), para poder cambiarlo en el PSet 4 sin tocar lo entregado. La explicación completa del
experimento está en [`../../pset-03/README.md`](../../pset-03/README.md); los cambios de la copia, en
[`../docs/migracion.md`](../docs/migracion.md).

| | `psets/pset-03` (entregado) | `psets/pset-04/modelos` |
|---|---|---|
| Base de Snowflake (`SNOWFLAKE_DATABASE`) | `PORTAFOLIO_P3` | `PORTAFOLIO_P4` |
| Proyecto uv | `pset-03-modelado` | `pset-04-modelos` (mismas versiones) |
| Compose de MLflow | `pset3`, puerto 5001 | `pset4`, puerto 5001 (no levantar los dos a la vez) |
| MLflow | `pset-03/mlflow/` | `modelos/mlflow/`: copia local, mismos run_id, versiones y alias |

El registro trae `portafolio-inversiones-modelo` v1 `@champion` (LightGBM, run
`f7596a565f8a458492057238f245cf89`) y v2 `@challenger` (Ridge). `mlflow/`, `data/` y `.env` no se
suben a git.

Desde `psets/pset-04/modelos/`:

```bash
uv sync --group modelos
uv run python -m pytest -q tests          # 28 pruebas
docker compose up -d mlflow               # MLflow en http://localhost:5001
uv run python -m src.datos                # snapshot de la OBT desde PORTAFOLIO_P4 (cuando exista)
```
