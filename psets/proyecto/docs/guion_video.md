# Guion del video de demostración (≤ 7 min)

Antes de grabar: Docker abierto, `pipeline/.env` con `API_TOKEN`, flows subidos, una terminal en `psets/pset-04` con
`V=$PWD`, pestañas abiertas: Kestra (localhost:8090), MLflow (localhost:5001), API (localhost:8000/docs), Snowsight.
Correr `produccion_lotes` completo **antes** de grabar (tarda); en el video se muestran sus ejecuciones y se lanza una
corta. Tiempos aproximados.

| Min | Qué mostrar | Comandos / clics | Qué decir |
|---|---|---|---|
| 0:00–0:40 | **Levantar** | `docker compose --env-file pipeline/.env up -d` y `docker compose --env-file pipeline/.env ps` | Un solo compose: Kestra, Postgres, Spark, MLflow y la API. |
| 0:40–1:50 | **Ingesta → OBT** | Kestra: `usfq.portafolio.ingesta_diaria` → Execute (o mostrar una ejecución reciente); abrir el Gantt: ingesta → subflow `transformar` (dbt build, Spark). Snowsight: `select count(*) from PORTAFOLIO_P4.OBT.OBT_ACCION_MES` | Reintentos, dbt prueba antes de que Spark escriba la OBT. |
| 1:50–2:40 | **Predicción válida e inválida** | `curl -s localhost:8000/modelo`; `curl -s -H 'Content-Type: application/json' --data @tests/fixtures/lote_2024_01.json localhost:8000/predecir \| head -c 700`; `curl -s -H 'Content-Type: application/json' --data '{"anio_mes": 202313, "acciones": []}' localhost:8000/predecir` | 200 con decisión, peso, versión e id; 422 que dice qué campo falló. |
| 2:40–3:30 | **Rollback** | `curl -s localhost:8000/modelo` (v actual) → `docker compose --env-file pipeline/.env --profile herramientas run --rm produccion python -m monitoreo.produccion --api http://api:8000 revertir` → `curl -s localhost:8000/modelo`; MLflow: alias movidos | Se cambia la versión moviendo el alias; la imagen no se reconstruye. |
| 3:30–4:30 | **Lote con deriva → alerta** | Kestra: ejecución de `usfq.produccion.monitoreo` del lote 202505 (alertas A4, A8); Snowsight: `select * from PORTAFOLIO_P4.PRODUCCION.ALERTAS where anio_mes between 202505 and 202507`; correo recibido; tablero (`streamlit run monitoreo/tablero.py`) | Lote sintético de crisis; el sistema lo detecta en el primer mes. |
| 4:30–5:50 | **Reentrenamiento con pausa** | Kestra: la ejecución de `usfq.produccion.reentrenamiento` de la llegada 202508 (lote con deriva: log `resumen` con NO promover, Resume con `aprobado=false` y su motivo) y la de 202604 (PROMOVER → Resume `aprobado=true`); MLflow: la versión nueva con @champion; `curl -s localhost:8000/modelo` | El modelo nuevo no se despliega solo: una persona aprueba y recién ahí cambia el champion. |
| 5:50–6:40 | **Interruptor de respaldo** | `curl -s -X POST -H "X-Token: $API_TOKEN" "localhost:8000/respaldo?activar=true"`; predecir de nuevo (`usado: respaldo...`); `curl -s -X POST -H "X-Token: $API_TOKEN" "localhost:8000/respaldo?activar=false"`; sin token → 401 | Freno de mano: responde la alternativa simple, marcada. |
| 6:40–7:00 | Cierre | GitHub Actions en verde e imagen en GHCR | CI/CD; enlace en el documento técnico. |

Para `$API_TOKEN` en la terminal: `export API_TOKEN=$(grep '^API_TOKEN=' pipeline/.env | cut -d= -f2-)` (no mostrar el valor en
pantalla).
