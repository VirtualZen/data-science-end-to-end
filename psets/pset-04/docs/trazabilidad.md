# Trazabilidad de una predicción (PDF 10.6)

Cadena: **PREDICCIONES → versión del modelo → run_id → snapshot de la OBT → tablas Gold**. Se demuestra con
`scripts/trazabilidad.py`, que solo lee `docs/predicciones.csv` y `docs/corridas.csv` (exportados de Snowflake y de
MLflow) y no escribe nada:

```
cd psets/pset-04
python3 scripts/trazabilidad.py
python3 scripts/trazabilidad.py 7b1778862d0848c5b7b3ac42e4102846
```

Sin argumentos rastrea la primera predicción de cada versión servida en la corrida de Kestra:

| Versión servida | Lotes | run_id | Corrida | Datos de entrenamiento |
|---|---|---|---|---|
| v1 | 2023-12 a 2024-11 | `f7596a565f8a458492057238f245cf89` | `M3_lightgbm` (tuning del PSet 3) | `PORTAFOLIO_P3.OBT.OBT_ACCION_MES`, snapshot 2026-11-18T05:21:27Z, corte 2023-12-31, 46.851 filas, sha256 `c35689172397…` |
| v3 | 2024-12 a 2026-04 | `cb970bac89414859b1d6128db2e8c157` | `reentrenamiento-202410`, motivo «calendario (12 lotes)» | `PORTAFOLIO_P4.OBT.OBT_ACCION_MES`, huella `2f169ec3f682`, ventana expansiva hasta 2024-10, 50.355 filas |
| v8 | 2026-05 en adelante | `9cd9145026cf4d73a70655351609f22d` | `reentrenamiento-202602`, motivo «rendimiento (A7)» | misma OBT y huella, ventana expansiva hasta 2026-02, 55.705 filas |

Las tres OBT se construyen con `pipeline/spark/jobs/construir_obt.py` desde las tablas Gold `FCT_PRECIOS_DIARIOS`,
`FCT_MERCADO_DIARIO`, `DIM_ACCION` y `DIM_FECHA` (modelos dbt en `pipeline/dbt/models/gold/`; esquema en
`docs/modelo_dimensional.png`). Cada fila de `PREDICCIONES` guarda además la huella de la OBT del lote (`huella_obt`).

**Limitación declarada (auditoría H7).** Para v1 el snapshot está identificado por tabla, fecha y sha256. Para v3 y v8
la huella `2f169ec3f682` identifica las claves y las features de la OBT de P4, pero no incluye el objetivo, y no se guardó
un manifiesto del conjunto de entrenamiento: el conjunto se reconstruye filtrando esa OBT hasta `hasta_anio_mes` con la
ventana expansiva, y coincide mientras la OBT no cambie. La mejora (huella con objetivo y manifiesto como artefacto de
MLflow) está en el documento técnico, sección 10.
