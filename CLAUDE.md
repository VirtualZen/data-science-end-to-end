# CLAUDE.md — reglas para trabajar en este repositorio (MSDS 6003, USFQ)

Allan Paul Gómez Ehmig (00351916). Fork `VirtualZen/data-science-end-to-end`.
Acuerdo completo en el proyecto de Claude: `claude/acuerdo-trabajo-msds6003.md`.

## Regla principal (Paul, 2026-11-17)

**`laboratorios/` es lo que el profesor prefiere.** Sus READMEs, `starter/` y `plantilla-*/`
fijan los estándares de nombres, estructura, estilo de código y entregables. **Desviarse de
ellos requiere una justificación escrita** en el `disclaimer.txt` del PSet (o en el documento
técnico), que diga qué estándar se deja, por qué, y qué evidencia lo sostiene. Ante una
duda, se sigue el laboratorio.

Si la guía del profesor (el PDF del PSet) contradice la del repositorio, se entrega con la
guía recibida y la contradicción se anota en `disclaimer.txt`.

## Estándares que fijan los laboratorios

Estructura (psets/README.md y laboratorios, Ejercicio 3 de cada sesión):
- El proyecto vive en `psets/proyecto/` (docs/, data/{raw,processed}/, ingesta/, infra/,
  orquestacion/, calidad/, warehouse/dbt/, procesamiento/, modelado/, servicio/, monitoreo/).
  Las carpetas `psets/pset-NN/` traen enunciado y rúbrica. Cada PSet se entrega con el tag `pset-NN`.
- PSet 3 en `psets/proyecto/modelado/`: `explorar_proyecto.ipynb`, `features_proyecto.ipynb`,
  `pipeline_proyecto.py`, `modelos_proyecto.ipynb` + `resultados_proyecto.csv`,
  `comparar_proyecto.ipynb` (ensamblaje vs red vs LLM), `experimentos_proyecto.ipynb` +
  `corridas_proyecto.csv`, `validacion_proyecto.ipynb`; y `psets/proyecto/docs/decision_modelo.md`.
- PSet 4: `modelado/test_pipeline_proyecto.py`, `docs/despliegue.md`, `servicio/` (api.py con
  `/salud`, Dockerfile, requirements.txt, test_api.py con TestClient), `monitoreo/`.

Código de modelado (semanas 9 a 11):
- `pipeline_proyecto.py`: `RUTA_DATOS` relativa (`../data/processed/...`), `OBJETIVO`,
  `NUMERICAS`, `CATEGORICAS`, `YA_LISTAS`; funciones `agregar_features(datos)`,
  `cargar_y_dividir(ruta)`, `construir_preparacion()` (ColumnTransformer: imputar mediana +
  StandardScaler; most_frequent + OneHotEncoder(handle_unknown="ignore", sparse_output=False);
  passthrough) y guardia `if __name__ == "__main__"`. Solo las líneas que construyen features.
- Los notebooks importan (`from pipeline_proyecto import cargar_y_dividir, construir_preparacion`),
  nunca copian. Se entregan con Restart + Run All y la salida guardada.
- `Pipeline([("preparar", preparacion), ("modelo", modelo)])`; `random_state=42`;
  tiempo con `time.perf_counter()`.
- Tabla de resultados: una fila por modelo con métrica en entrenamiento y prueba, brecha y
  segundos (`mae_entrenamiento`, `mae_prueba`, `brecha`, `segundos`), escrita por el notebook.
- Línea base justificada (Dummy o regla del dominio, p. ej. "mañana igual que hoy"), modelo
  lineal regularizado, ensamblaje, MLP, y la prueba del LLM sobre 10 filas (o por qué no aplica).
- MLflow: `MLFLOW_TRACKING_URI` desde el entorno (el código no la escribe), `set_experiment`
  con el nombre del proyecto, `log_params` (hiperparámetros, semilla o fecha de corte,
  `huella_datos` = md5[:12] del archivo, filas), `log_metrics`, el pipeline como artefacto,
  tag `candidato` = `final` en la corrida elegida, recuperarla y reproducir la métrica;
  `mlflow.search_runs(...).to_csv("corridas_proyecto.csv", index=False)` sin corridas de prueba.
- Validación: el esquema de los datos (temporal si predice el futuro) **y uno al azar para
  comparar**; tabla con promedio, desviación y cada pliegue; métrica del negocio con el costo
  del error más caro.
- Pruebas: pytest con datos armados a mano, nunca leen `data/`; la CI (`.github/workflows/
  pruebas.yml`) instala el `requirements.txt` de la raíz (Python 3.11, scikit-learn 1.5.2,
  mlflow 2.17.2, pandas 2.2.2, numpy 1.26.4) y corre `pytest psets/proyecto`.
- Los ejercicios imprimen una comprobación por TODO hasta que todas digan `OK`.

## Reglas de trabajo de Paul

- Responder en español y de forma concisa; decir qué archivo se revisó; no inventar resultados.
- Rama `work`, clon `MSDS_6003/data-science-end-to-end-work`. No cambiar la rama `proyecto`.
- `# TODO n` pasa a `# DONE n`; nunca se borra.
- **No hacer commits ni push.** Mensajes de commit descriptivos en los PSets, solo el nombre de
  la carpeta o fase en `laboratorios/`, sin línea de coautoría.
- **No subir contraseñas, tokens ni credenciales**: nunca `.env`, `.env_encoded`, `secrets/`,
  llaves ni la cuenta de Snowflake. `git grep` de secretos antes de cada commit o push.
- `psets/pset-02/` ya se entregó (tag `pset-02`) y no se modifica.
- Cambios del pipeline por el PSet 2 o por columnas nuevas de la OBT: en
  `psets/pset-03/pipeline/`, con antes y después en `docs/migracion_pipeline.md` y su prueba.
- Mantener `psets/pset-03/plan.txt` al día ([x] hecho, [~] parcial, [ ] pendiente, [!] hallazgo;
  (C) Claude, (P) Paul).
- No levantar Spark/Kestra a la vez que MLflow (memoria). No modificar un `.sh` mientras corre.
  Los comandos que se le den a Paul para MLflow incluyen la verificación: `docker ps` sin contenedores
  de Kestra/Spark y `curl -s localhost:5001/health` que responda `OK`.
- **Semilla 42 en todo el proyecto** (`src/entorno.py` `SEMILLA`, notebooks, sorteos, `random_state`).
- MLflow del PSet 3: experimento `portafolio-inversiones`; tags `fase`, `familia` y `modelo` por separado.
  Toda lista de modelos tiene al menos dos líneas base.
- El correo de avisos solo en `.env` (`AVISO_CORREO`), nunca en archivos versionados.
