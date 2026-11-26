# Reproducibilidad del PSet 3

El PDF pide que el repositorio permita reproducir cada experimento ("una corrida que no puedes reproducir no cuenta
como evidencia"). Esto es lo que se verificó el 18 de noviembre de 2026.

## 1. Mismo resultado en otra máquina

`src/verificar_reproducibilidad.py` vuelve a calcular, sin MLflow, el MAE de CV de cuatro corridas y lo compara con
el registrado. Se ejecutó en una máquina distinta de la original: Linux x86_64, con el entorno creado desde cero con
`uv sync --frozen --group modelos` a partir de `uv.lock`. Las corridas originales se hicieron en macOS (Apple M4).
Los datos fueron el mismo snapshot (sha256 `c3568917…`, 46.851 filas de entrenamiento). Resultado en
`docs/reproducibilidad.csv`:

| Corrida | MAE CV registrado | MAE CV reproducido | Diferencia |
|---|---|---|---|
| B1 media | 0,0641024239 | 0,0641024239 | 0 |
| M4 Ridge | 0,0680905033 | 0,0680905033 | 4 × 10⁻¹⁵ |
| M3 LightGBM por defecto | 0,0705919 | 0,0706407 | 4,9 × 10⁻⁵ |
| **M3 LightGBM ajustado (champion)** | 0,0635543868 | 0,0635543868 | **0** |

- B1, Ridge y el champion se reproducen exactamente; 4 × 10⁻¹⁵ es redondeo de coma flotante.
- LightGBM por defecto difiere en 4,9 × 10⁻⁵: es el 0,2 % de su desviación entre pliegues (0,022). Ocurre porque
  LightGBM suma en paralelo con todos los núcleos, y el orden de las sumas cambia entre procesadores. No cambia ninguna
  conclusión ni ningún orden entre modelos. Para el PSet 4: fijar `deterministic=True` y `n_jobs` en LightGBM.

## 2. Mismo modelo desde el registro

`notebooks/06_champion.ipynb` carga `models:/portafolio-inversiones-modelo@champion` en un kernel limpio, predice el
hold-out y obtiene MAE 0,0673399888, igual al registrado en la corrida `final` del champion.

## 3. Qué fija cada corrida

| Elemento | Dónde |
|---|---|
| Datos | Tabla de origen, fecha del snapshot y sha256 como parámetros; manifiesto `datos/snapshot_mes.json` como artefacto |
| Código | Tag `git_commit` y `git_dirty` |
| Semilla | 42 en todo (`src/entorno.py`): modelos, Optuna (TPE), sorteos de B4 |
| Entorno | `uv.lock`, `requirements.txt` exportado del lock (incluye el grupo `modelos`), y los requisitos de cada modelo registrado |
| Pliegues | `TimeSeriesSplit` sobre meses, sin aleatoriedad (`src/pipeline.py`, `pliegues`) |
| Modelo | Pipeline completo con firma y ejemplo de entrada (`mlflow.sklearn.log_model`) |

## 4. Límites

- **El snapshot no se sube a Git** (`data/` está en `.gitignore`): se vuelve a crear desde Snowflake con
  `uv run python -m src.datos`. Si el pipeline cargó días nuevos, el sha256 cambia. Las filas de entrenamiento (objetivos
  hasta 2023-12) no cambian mientras los datos históricos sigan iguales, pero conviene comparar el sha256 del manifiesto
  antes de comparar métricas.
- **Los fundacionales** se reproducen desde sus pronósticos guardados (`artefactos/fundacional_*.parquet`, con sha256 en
  el `.json`). Volver a generarlos depende de la versión del modelo en Hugging Face, de su entorno aislado y del
  hardware (MPS en la Mac).
- **El servidor MLflow es local**: la evidencia exportable es `docs/corridas.csv`.
