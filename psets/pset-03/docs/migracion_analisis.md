# Migración de `analisis/` y del plan desde la rama `draft`

Fecha: 2026-11-15. Origen: `origin/draft` (`7ce9444`), `psets/pset-02/analisis/` y
`psets/pset-02/plan.txt` (versión local con J10 e I4 cerrados).

| Qué | Antes | Después |
|---|---|---|
| Scripts y listas | `draft:psets/pset-02/analisis/` (6 `.py`, 1 `.md`, 5 CSV en `listas/`) | `proyecto:psets/pset-03/analisis/`; las listas y el `.md` son idénticos a draft |
| Instrucciones de uso de los `.py` | `Uso, desde psets/pset-02/: python analisis/...` y `pip install ...` | `Uso, desde psets/pset-03/ (uv sync --group analisis): uv run python analisis/...` |
| Destino de la semilla en `equivalencias_tickers.py` | `AQUI.parent / "dbt"/"seeds"` y `/"kestra"/"scripts"` (dentro de pset-02) | `AQUI.parent.parent / "pset-02"`, para seguir alimentando el pipeline del PSet 2 sin crear carpetas en pset-03 |
| Dependencias | `analisis/requirements.txt` y `pyproject.toml` de draft (Python >=3.12, pandas>=3) | Grupo `analisis` en `pset-03/pyproject.toml` (Python 3.11, pandas<3 del proyecto): duckdb>=2,<3, pandas-market-calendars, statsmodels, xgboost, yfinance; `analisis/requirements.txt` no se copia |
| `uv.lock` | sin el análisis | +20 paquetes del grupo `analisis`; ninguna versión existente cambia; `requirements.txt` (runner) sin cambios |
| `.gitignore` | sin reglas de `analisis/` | `analisis/*.duckdb`, `analisis/*.duckdb.bak`, `analisis/*.log` |
| README | "permanece en la rama `draft` ... No se duplica" | apunta a `analisis/`, aclara que es exploratorio y no reemplaza el protocolo de la OBT |
| Plan | `draft:psets/pset-02/plan.txt` | `psets/pset-03/plan.txt` con una cabecera de 3 líneas sobre su origen; el resto sin cambios |

Las cachés `universo.duckdb`, `yahoo.duckdb` y `yahoo_v69_terminal.duckdb.bak` no se
versionan; se regeneran con `construir_listas.py`, `equivalencias_tickers.py` y
`traer_yahoo.py`, o se copian a mano desde la carpeta local de `draft`.

## Separación en `datos/` y `modelos/` (2026-11-17)

En `draft` todo vivía en `psets/pset-02/analisis/`, mezclando la etapa de datos (lo que cubre
el PSet 2) con la de modelado (PSet 3). Se separó por etapa:

| Antes (`analisis/`) | Después |
|---|---|
| `construir_listas.py`, `equivalencias_tickers.py`, `traer_yahoo.py`, `fechas_y_faltantes.py`, `tecnicas_sesgo_y_faltantes.md`, `listas/` | `analisis/datos/` |
| `series_y_arima.py`, `comparar_modelos.py` | `analisis/modelos/` |
| cachés `universo.duckdb`, `yahoo.duckdb`, `*.duckdb.bak`, `*.log` (no versionados) | `analisis/datos/` |
| `--base` por defecto de los scripts de modelos: `analisis/yahoo.duckdb` | `analisis/datos/yahoo.duckdb` |
| semilla de `equivalencias_tickers.py`: `AQUI.parent / "pipeline"` | `AQUI.parent.parent / "pipeline"` (misma carpeta final, `psets/pset-03/pipeline/`) |
| `.gitignore`: `analisis/*.duckdb`, `analisis/*.duckdb.bak`, `analisis/*.log` | `analisis/**/*.duckdb`, `analisis/**/*.duckdb.bak`, `analisis/**/*.log` |
| Líneas `Uso` y rutas en docstrings: `analisis/<script>` | `analisis/datos/<script>` o `analisis/modelos/<script>` |

Las listas CSV y `tecnicas_sesgo_y_faltantes.md` no cambiaron de contenido. Se agregó
`analisis/README.md` con el estado de cada parte.
