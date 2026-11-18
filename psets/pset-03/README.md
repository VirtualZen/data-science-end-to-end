# PSet 3 — Experimentación desde la OBT

La guía vigente es `CD_PSet_3.pdf`. Esta carpeta desarrolla incrementalmente el
PSet 2; el README original del curso queda en `README_curso.md`.

El pipeline del PSet 2 está copiado en [`pipeline/`](pipeline/README.md) para volver a
correrlo sin modificar `psets/pset-02/`, que ya se entregó. Escribe en la base
`PORTAFOLIO_P3`; `src/datos.py` lee de ahí (`SNOWFLAKE_DATABASE`). La base
`PORTAFOLIO` queda tal como se entregó en el PSet 2. La integración
final en `psets/proyecto/` se hará al empaquetar el proyecto, sin duplicar datasets.

## Preparación

```bash
uv sync                      # .venv con Python 3.11 y las versiones exactas de uv.lock
cp .env.example .env
# Completar credenciales localmente: nunca agregarlas a git.
uv run python -m src.datos
docker compose up -d --build
```

El entorno es un proyecto uv propio de esta carpeta (`pyproject.toml` + `uv.lock`).
`requirements.txt` no se edita a mano: lo genera `bash exportar_requirements.sh`
desde el lock y lo usan la imagen runner y el registro de MLflow.

MLflow queda en http://localhost:5001, con SQLite como backend y artefactos en
`mlflow/artifacts`; ambos persisten en `mlflow/`, excluido de Git. El snapshot
`data/obt.parquet` tiene un manifiesto con tabla, fecha y SHA-256. No se publica.

## Orden de trabajo

1. `notebooks/01_eda.ipynb`: distribución, faltantes, IQR, Z-score, Spearman y tres hallazgos.
2. `02_features.ipynb`: `dispersion_mes` y mes calendario del objetivo (one-hot), con pruebas de
   disponibilidad y ablación en los pliegues temporales.
3. `03_preparacion_validacion.ipynb`: división única, Pipeline/ColumnTransformer de `src/pipeline.py`,
   TimeSeriesSplit sobre meses (7 × 12 meses, gap 1) con tabla de fechas de corte, comparación de
   esquemas de CV, todas las métricas de regresión (decide el MAE) y la métrica de negocio con ejemplo.
4. `03_baseline_candidatos.ipynb`: líneas base B1–B3, referencias de negocio (B4, B5, índices) y los
   8 candidatos de las 5 familias (Ridge, random forest, LightGBM/XGBoost, MLP y los fundacionales Chronos,
   TimesFM y Moirai en zero-shot), registrados en MLflow (`src/experimentos.py`). El LLM por prompting se
   justifica como no aplicable (fuga por su fecha de corte).
5. `04_tuning.ipynb`: Optuna (TPE, semilla 42) con 30 configuraciones por modelo para Ridge, LightGBM y
   XGBoost, como corridas hijas (`src/tuning.py`).
6. `05_seleccion.ipynb`: champion y challenger por MAE de CV, hold-out evaluado una sola vez, métrica de
   negocio, costo y explicabilidad, Model Registry (`portafolio-inversiones-modelo`) y `docs/corridas.csv`
   (`src/seleccion.py`).
7. `06_champion.ipynb`: recarga limpia de `@champion` que reproduce su MAE del hold-out.

Documento técnico: `docs/PSet3_memo_Gomez_Ehmig.pdf`, con glosario en el anexo A
(`uv run --with reportlab python scripts/generar_memo.py`). Presentación ejecutiva:
`docs/PSet3_presentacion_Gomez_Ehmig.pptx` y su PDF (`node scripts/generar_presentacion.js`, requiere pptxgenjs,
react, react-dom, react-icons y sharp). Reproducibilidad verificada en otra máquina: `docs/reproducibilidad.md`
(`uv run --group modelos python -m src.verificar_reproducibilidad`).

El target es el retorno log del mes siguiente. El corte usa el mes del objetivo:
objetivos hasta diciembre de 2023 en entrenamiento; posteriores en hold-out.
La CV separa meses completos y purga un mes. Imputación y escalado se ajustan
adentro de cada Pipeline/ColumnTransformer. Se excluyen columnas del futuro y
atributos actuales como `sigue_en_sp500` de los predictores.

Los notebooks 02 en adelante necesitan el grupo `modelos` (lightgbm, xgboost):

```bash
uv run --group modelos jupyter execute --inplace notebooks/03_preparacion_validacion.ipynb
```

## Modelos fundacionales (M8–M10): pronósticos zero-shot

Cada uno corre una vez, en un entorno temporal propio (`--no-project`), porque sus paquetes chocan entre sí y con
el lock. Descargan el modelo de Hugging Face la primera vez y dejan `artefactos/fundacional_<modelo>.parquet` y
`.json` (con SHA-256 y latencia). Después, `notebooks/03_baseline_candidatos.ipynb` (sección 6.3) los evalúa con
los mismos pliegues y métricas y los registra en MLflow (`familia = fundacional`).

```bash
uv run --no-project --python 3.11 --with chronos-forecasting --with pandas --with pyarrow python -m src.modelos.fundacionales --modelo chronos
uv run --no-project --python 3.11 --with "timesfm[torch]" --with pandas --with pyarrow python -m src.modelos.fundacionales --modelo timesfm
uv run --no-project --python 3.11 --with "uni2ts @ git+https://github.com/SalesforceAIResearch/uni2ts.git" --with pandas --with "pyarrow>=14,<18" --with fastparquet python -m src.modelos.fundacionales --modelo moirai
```

Para probar antes de la corrida completa, agregar `--limite 500`.
`uni2ts` fija NumPy 1.26, por eso Moirai necesita `pyarrow<18` (las versiones nuevas exigen NumPy 2). TimesFM en
CPU tarda ~110 ms por serie: se corre solo para los meses de validación con `--desde 201612 --hasta 202311`.

## Permisos de los archivos copiados por Claude (`chmod 644`)

Los archivos que Claude escribe en esta carpeta desde su entorno (`device_commit_files`) llegan a la Mac
con permisos `-rw-------` (solo el dueño los lee). Eso basta para `uv run` en la Mac, pero los
contenedores de Docker (Spark, Kestra, dbt) corren con otro usuario y fallan con `PermissionError` al
leerlos: así falló la prueba de `reconstruir_obt.sh` el 18-nov. Después de cada copia hay que darles
lectura para todos:

```bash
chmod 644 ruta/al/archivo1 ruta/al/archivo2
```

Para corregir de una vez todo lo que haya quedado en 600 sin tocar los secretos, que deben seguir en 600:

```bash
find . -type f -perm 600 ! -name '*.p8' ! -name '.env' ! -name '.env_encoded' ! -name '*.duckdb' ! -path '*/.venv/*' ! -path '*/secrets/*' -exec chmod 644 {} +
```

Git no guarda la diferencia entre 600 y 644 (solo el bit de ejecución), así que este paso no aparece en
`git status`.

## Estado y límites

La estructura está preparada; no es una entrega completa de PSet 3. No se ha
elegido ganador, consumido hold-out ni inventado corridas.csv o un memo final.
Faltan quinta familia, ablación, experimento LLM, 90 configuraciones, métrica de
negocio alineada con PSet 1, selección/registro y memo de hasta 6 páginas.
Antes de entrenar, revisar ajustes retrospectivos de precios, bolsa actual,
interpolación y cobertura del universo documentados en el memo del PSet 2.

El trabajo previo de análisis (antes en la rama `draft`, `psets/pset-02/analisis/`)
está en `analisis/`, separado en `analisis/datos/` (etapa de datos, la que cubre el
PSet 2) y `analisis/modelos/` (etapa de modelado), con su grupo de dependencias
(`uv sync --group analisis`). Ver [`analisis/README.md`](analisis/README.md).
Es exploratorio: parte de Yahoo con cachés DuckDB locales (no versionadas) y no
satisface el protocolo experimental de la OBT que exige el PDF; sirve como
referencia para elegir familias y técnicas. El plan de trabajo está en `plan.txt`.
Los notebooks finales se entregan con Restart y Run All y salidas guardadas.

### Comprobaciones realizadas

Los notebooks 01 a 06 se ejecutaron completos con el snapshot de 87.178 filas (sha256 `c3568917…`), con
salidas y gráficos guardados. Entrenamiento: 46.851 filas (objetivos hasta 2023-12); hold-out: 11.326 filas
(2024-01 a 2026-10). `pytest tests` corre 28 pruebas de fuga, cortes, pipeline y regla de negocio.

MLflow se construyó en Docker. Se configura con un solo worker y límite de 1 GB para reducir
consumo. No ejecutar a la vez que Spark en el entorno de 8 GB: durante la
verificación la coexistencia de ambos provocó un OOM de Kestra.

## Verificación funcional aislada

Primero ejecuta `docker compose down` desde `pipeline/`, sin `-v`; Snowflake
conserva las tablas. Los notebooks no necesitan Kestra ni Spark: solo leen la OBT
ya materializada en `PORTAFOLIO_P3` (snapshot de `src/datos.py`). `pipeline/` solo
hace falta para reconstruirla.

```bash
docker compose down
docker compose --profile verificacion build
docker compose up -d mlflow
GIT_COMMIT="$(git rev-parse HEAD)" GIT_DIRTY=true \
  docker compose --profile verificacion run --rm verificar
docker compose down
```

`src/verificar_entorno.py` consulta Snowflake, crea un snapshot nuevo, ejecuta
EDA/features y registra media, retorno cero y Ridge con CV temporal en un
experimento separado, `portafolio-verificacion-entorno`. Registra y recarga
Ridge con alias `verificacion` en `portafolio-verificacion-modelo`, y comprueba
que reproduce su RMSE de entrenamiento. No asigna champion, no elige ganador,
no utiliza el hold-out y no sustituye las 98 corridas mínimas del PDF.
La evidencia de esa prueba queda en `docs/verificacion/`.

## Cadencia de negocio y futura inferencia

Según PSet 1 revisado, la inferencia y propuesta de compra son mensuales; los datos se actualizan diariamente en PSet 2. El reporte de desempeño también es mensual. No se establece una frecuencia de reentrenamiento ni se implementa aquí un scheduler productivo de scoring. `preparar()` filtra targets nulos para entrenamiento: la futura inferencia necesitará conservar esas filas del mes cerrado sin usar columnas futuras. Ver [temporalidad y disponibilidad del cierre](../pset-02/docs/temporalidad_batch.md).
