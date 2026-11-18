# Análisis exploratorio previo (Yahoo + DuckDB)

Viene de `draft:psets/pset-02/analisis/`, donde la etapa de datos y la de modelado estaban
mezcladas. Es exploratorio: trabaja con un caché local de Yahoo en DuckDB, **no con la OBT**
de Snowflake, así que no cumple el protocolo experimental de `CD_PSet_3.pdf`. La ruta activa
del PSet 3 es `../src/` + `../notebooks/`, que leen la OBT construida por `../pipeline/`.

Dependencias: `uv sync --group analisis` (desde `psets/pset-03/`; xgboost en macOS requiere
`brew install libomp`). Las cachés `*.duckdb` quedan en `datos/` y no se versionan.

## `datos/` — etapa de datos (lo que cubre el PSet 2)

| Archivo | Qué hace | Estado |
|---|---|---|
| `construir_listas.py` | Universo: S&P 500 actual e histórico filtrado a la NYSE → `universo.duckdb` y `listas/*.csv` | Antecedente; `pipeline/` arma el universo en dbt |
| `equivalencias_tickers.py` | Cambios de símbolo (FB → META) → `listas/equivalencias_tickers.csv` y la semilla de `../pipeline/dbt/seeds` y `../pipeline/kestra/scripts` | **Activo**: es la fuente de esa semilla |
| `traer_yahoo.py` | Baja precios de Yahoo al caché `yahoo.duckdb` | Antecedente; `pipeline/` ingesta a RAW con Kestra |
| `fechas_y_faltantes.py` | Calendario NYSE, huecos e imputación (lineal, lineal con ruido, Kalman) | Antecedente; Silver usa forward-fill |
| `tecnicas_sesgo_y_faltantes.md` | Revisión de técnicas de sesgo de supervivencia, huecos y series | Referencia |
| `listas/` | CSV del universo y de equivalencias | Referencia (se regeneran con los scripts) |

Orden: `construir_listas.py` → `equivalencias_tickers.py` → `traer_yahoo.py` → `fechas_y_faltantes.py`.

## `modelos/` — etapa de modelado (PSet 3)

| Archivo | Qué hace | Estado |
|---|---|---|
| `series_y_arima.py` | ARIMA por acción, orden por AIC y BIC | Referencia para la familia ARIMA |
| `comparar_modelos.py` | Random walk, ARIMA, random forest, XGBoost con el corte dic-2023 | Referencia; hay que rehacerlo sobre la OBT en `../src/experimentos.py` |

Leen `datos/yahoo.duckdb` (después de `fechas_y_faltantes.py`). Orden: `series_y_arima.py` →
`comparar_modelos.py`.
