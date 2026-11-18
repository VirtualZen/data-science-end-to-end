# Documentación del pipeline (PSet 3, base PORTAFOLIO_P3)

Copia actualizada de lo que en el PSet 2 está en `psets/pset-02/docs/` (que no se modifica).
Cambios frente al PSet 2: [`../../docs/migracion_pipeline.md`](../../docs/migracion_pipeline.md).

| Archivo | Qué muestra | Cómo se genera |
|---|---|---|
| `arquitectura.png` / `.svg` / `.dot` | Flujo y arquitectura medallón (Raw→Bronze→Silver→Gold→OBT) con Kestra, Spark, avisos por correo, `reconstruir_obt.sh` y el consumo del PSet 3 | A mano en DOT; `dot -Tpng -Gdpi=150 arquitectura.dot -o arquitectura.png` |
| `arquitectura_vertical.png` | El mismo diagrama en vertical (para imprimir o anexos) | `sed 's/rankdir=LR;/rankdir=TB;/' arquitectura.dot \| dot -Tpng -Gdpi=150 -o arquitectura_vertical.png` |
| `modelo_dimensional.png` / `.svg` / `.dot` | Star schema de Gold (FCT_PRECIOS_DIARIOS con OHLC ajustado y diferencias diarias, PSet 3) | DOT, igual que arriba |
| `structurizr/workspace.dsl` | Modelo C4: contexto y contenedores (incluye Gmail, el script de reconstrucción y el modelado del PSet 3) | Structurizr DSL |
| `structurizr/export/` | Mermaid, PlantUML y PNG con leyenda | `bash structurizr/exportar_diagramas.sh` (Docker) |
| `series_de_tiempo.md` | Diferencias aritméticas, porcentuales y logarítmicas; estacionariedad y ARIMA; intradía, rango y volatilidad por rango; qué forma usa cada modelo | A mano |
| `limitaciones.md` | Limitaciones conocidas (supervivencia, huecos, Yahoo, Python 3.8 en Spark, equivalencias y fusiones) con su evidencia | A mano |
| `diccionario_datos.md` | Tablas de Gold, CALIDAD y columnas de la OBT | A mano |
| `calidad/` | Diagnóstico por columna, outliers MAD e informe de calidad de P3 | `scripts/diagnosticar_calidad.py` y `scripts/generar_informe_calidad.py` |
| `calidad/analisis_calidad_pipeline.ipynb` | Análisis de la limpieza por capa (RAW → OBT): % faltantes, inválidos e imputados por columna, flujo de filas, duplicados, OHLC, imputados, OBT final y hallazgos; CSV en `calidad/analisis_pipeline/` | el propio notebook (solo SELECT; `MOTOR=snowflake` o `duckdb`) |
| `corrida/` | Evidencia de la última corrida: conteos, controles, dbt (`run_results.json`, `sources.json`), huecos por ticker, universo por mes, ids de Kestra | `scripts/reconstruir_obt.sh` y `scripts/exportar_metricas.py` |

Para ver y editar el C4 con la UI: `bash structurizr/ver_diagramas.sh` (http://localhost:8080/workspace/1).
