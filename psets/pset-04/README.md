# PSet 4 — Despliegue, monitoreo y comunicación del modelo

La guía vigente es `CD-PSet-4.pdf` (el proyecto final). El README original del curso queda en
`README_curso.md` y la rúbrica del repo en `rubrica.md`; las diferencias con el PDF están en
`disclaimer.txt`. El plan y su avance están en `plan.txt`.

Como en el PSet 3, lo entregado no se modifica: `psets/pset-02/` y `psets/pset-03/` quedan tal como se
entregaron. Esta carpeta trae copias para poder cambiarlas (detalle en
[`docs/migracion.md`](docs/migracion.md)):

| Carpeta | Qué es | Cómo se usa |
|---|---|---|
| [`pipeline/`](pipeline/README.md) | Copia de `pset-03/pipeline/`: Kestra, dbt, Spark y la OBT | Escribe en la base `PORTAFOLIO_P4` de Snowflake |
| [`modelos/`](modelos/README.md) | Copia del modelado del PSet 3: `src/`, `notebooks/`, `tests/` y MLflow | Lee la OBT de `PORTAFOLIO_P4`; MLflow local en `modelos/mlflow/` con el champion del PSet 3 |

Lo nuevo del PSet 4 (API, pruebas, simulación de producción, monitoreo, reentrenamiento, tablero y
documentos) se agrega en esta carpeta. Al terminar, todo se arma en `psets/proyecto/` para la corrida
completa.
