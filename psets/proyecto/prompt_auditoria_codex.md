# Prompt para Codex: auditoría del PSet 4 (proyecto final)

Copia todo lo que está debajo de la línea y pégalo en Codex, abierto en el clon
`MSDS_6003/data-science-end-to-end-work` (rama `work`).

---

Eres el auditor del PSet 4 (proyecto final) del curso MSDS 6003 de la USFQ, de Allan Paul Gómez Ehmig
(00351916). Responde en español.

## Modo: auditoría, solo lectura

Antes de empezar, lee y aplica `AGENTS.md`, `ESTANDARES_CODIGO.md` (sección "Auditoría de código existente")
y `CLAUDE.md`. En resumen:

- No modifiques ningún archivo: ni código, ni notebooks, ni `plan.txt`, ni documentación, ni datos. No hagas
  commits, push, tags ni PR.
- No ejecutes nada que escriba en Snowflake, MLflow, Kestra o GitHub. No levantes `docker compose`. No abras
  ni muestres `.env`, `.env_encoded`, `secrets/` ni llaves; si encuentras un secreto versionado, repórtalo sin
  copiar su valor.
- Puedes leer todo el repositorio, usar `git log`, `git show`, `git diff`, `git ls-files`, y correr las
  pruebas en un entorno temporal fuera del repositorio, con las cachés desactivadas
  (`-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`).
- Distingue en cada hallazgo si está en GitHub (`origin/work`), solo en commits locales o sin commit.

## Alcance

1. `psets/pset-04/`: la entrega del PSet 4.
2. `psets/proyecto/`: copia del proyecto completo (debe coincidir con `pset-04/` salvo `CD-PSet-4.pdf`,
   `rubrica.md`, `README_curso.md`, `plan.txt`, `README.md`, `.dockerignore` y `conftest.py`).
3. `.github/workflows/pset4-ci.yml`, `pset4-cd.yml` y `pruebas.yml` (solo en relación con las dos carpetas).

Fuera de alcance: `psets/pset-02/` y `psets/pset-03/` (entregados y congelados; solo verifica que no
cambiaron desde sus tags) y `laboratorios/`.

## Fuentes, en orden de autoridad

1. `psets/pset-04/CD-PSet-4.pdf` (manda).
2. `psets/pset-04/disclaimer.txt`: desviaciones justificadas (puntos 1 a 15). Una desviación que está ahí,
   con motivo y evidencia, **no es un hallazgo**; sí lo es si el motivo es falso, la evidencia no existe o
   la desviación no está anotada.
3. `CLAUDE.md` y `ESTANDARES_CODIGO.md`: convenciones del repositorio.
4. `psets/pset-04/plan.txt`: estado declarado por el autor. Contrástalo con la evidencia, no lo des por
   cierto.

## Decisiones ya tomadas (verifica que estén bien hechas, no las cuestiones)

- Entrega en `psets/pset-04/` y copia final en `psets/proyecto/` (disclaimer 1). Estructura del PDF en vez
  de las carpetas de la plantilla del curso (disclaimer 14).
- Kestra y MLflow levantados juntos en un solo `docker-compose.yml` (disclaimer 6).
- Patrón batch mensual; decisión = top 10 de acciones bajo el tope de volatilidad, pesos 1/vol.
- Regla de promoción: último lote etiquetado; margen de negocio = 1 desviación de la CV (0,0134); guarda de
  MAE de 0,0016. A7 = 2 lotes etiquetados seguidos con MAE > 0,0801. Enfriamiento de 3 lotes y calendario
  de 12.
- Lotes 2025-05 a 2025-07 con deriva inducida (`sintetico = TRUE`).
- La operación manual (B7) es un competidor en paralelo; el respaldo sigue siendo B1 + B5.
- Incidente v7 → v8: la v7 se rechazó por un error de captura en la pausa de Kestra y se repitió como v8
  idéntica (disclaimer 12; `docs/reentrenamiento.md`).
- Versiones: el champion usa scikit-learn 1.9.1 y mlflow 3.18.0; `pruebas.yml` del curso usa 1.5.2 y 2.17.2.
  `psets/proyecto/conftest.py` no recoge pruebas si las versiones no coinciden (disclaimer 15).

## Qué revisar

### A. Cumplimiento del PDF, sección por sección

Para cada sección (1 a 11, "Documento técnico", "Repositorio" y "Entregables"), indica: requisito, archivo
y línea que lo cumple, evidencia, y estado (cumple / parcial / no cumple). En particular:

- 2: endpoints `/salud`, `/modelo`, `/predecir`; carga desde `models:/...@champion` sin reconstruir la imagen;
  Pydantic igual a la firma de MLflow; 422 con el campo que falló; acción del PSet 1 en la respuesta;
  registro de cada predicción con id, timestamp, entradas, salida, versión y latencia en `PREDICCIONES`.
- 3: las cuatro familias de pruebas, tolerancia justificada, respaldo, `ci.yml` que instala, construye la
  imagen y corre pytest; fixtures con `mlflow.sklearn.save_model`.
- 4: regla de promoción con métrica de negocio y variación entre pliegues; rollback por alias; versión en
  cada fila de `PREDICCIONES`.
- 5: lotes ≥ 8, horizonte respetado (el objetivo llega después de la predicción), deriva inducida
  documentada exactamente.
- 6: métricas de sistema, modelo y datos; PSI con umbral justificado y KS/chi² como respaldo; deriva
  conceptual contra la CV; tabla 6.2; plantilla de alertas; `monitoreo.yml`; tablero.
- 7: disparador por desempeño y por calendario; `reentrenamiento.yml` con los 8 pasos; `cd.yml` a GHCR con el
  hash; por qué el modelo no se despliega solo; evidencia del ciclo sobre el lote con deriva.
- 8: subgrupos, costo de cada error y quién lo asume, ≥ 3 criterios de retirada, interruptor, revisión del
  juicio humano.
- 9 y 10: métrica de negocio lote a lote contra la línea base y no hacer nada; trazabilidad PREDICCIONES →
  versión → run_id → snapshot de la OBT → Gold; `docs/cambios.md`.
- 11 y documento técnico: ≤ 12 páginas sin anexos; enlace del video; presentación de 10 a 12 diapositivas
  sin métricas técnicas sueltas; anexos con los memos de los PSets 1 a 3.
- Repositorio: `docs/predicciones.csv`, `monitoreo.csv`, `alertas.csv`, `corridas.csv` (de
  `mlflow.search_runs`, incluidas las de reentrenamiento) y `reentrenamientos.csv` (filtrado por
  `fase='reentrenamiento'`); notebooks con salida guardada.

### B. Coherencia entre código, datos exportados y documentos

- Las cifras del memo (`docs/PSet4_memo_Gomez_Ehmig.pdf`), la presentación, `docs/*.md` y el notebook 07
  coinciden con los CSV exportados de producción (`docs/monitoreo.csv`, `alertas.csv`,
  `reentrenamientos.csv`) y con `docs/simulacion/*.csv`. Señala cualquier número que no cuadre.
- Las 5 decisiones de reentrenamiento (v3, v4, v5, v6, v8) coinciden en `reentrenamientos.csv`,
  `docs/reentrenamiento.md`, `tests/test_produccion.py::test_regla_de_promocion_casos_reales` y el memo.
- Las alertas de `alertas.csv` coinciden con la explicación de falsas alarmas de `docs/monitoreo.md`.
- `psets/proyecto/` coincide con `psets/pset-04/` (usa `diff -rq` con las exclusiones del Alcance).

### C. Calidad del código (según `ESTANDARES_CODIGO.md`)

`api/`, `monitoreo/`, `modelos/src/reentrenar.py`, `modelos/src/operacion_manual.py`, `scripts/`,
`pipeline/kestra/flows/{produccion_lotes,monitoreo,reentrenamiento}.yml`,
`pipeline/kestra/sql/produccion_setup.sql`, `docker-compose.yml`, `tests/`. Busca: fugas de información del
futuro (objetivo o meses posteriores en la inferencia), idempotencia de las escrituras por lote, manejo de
errores del respaldo, validación de entradas, secretos en el código, semilla 42, rutas absolutas,
`# TODO` sin `DONE`, y pruebas que no prueban lo que dicen.

### D. Reproducibilidad y CI

- Corre las pruebas en un entorno temporal:
  `uv run --project psets/pset-04/api --frozen pytest psets/pset-04/tests -q -p no:cacheprovider` y lo
  mismo para `psets/proyecto`. Esperado: 45 pasan en cada una.
- Simula `pruebas.yml`: un entorno con scikit-learn 1.5.2, mlflow 2.17.2, pandas 2.2.2 y numpy 1.26.4;
  `pytest psets/proyecto` debe terminar con código 5 y explicar el motivo.
- Revisa que `README.md` permita reproducir de cero en el orden del PDF (fuente → Raw → … →
  reentrenamiento), que `.env.example` cubra todas las variables del compose sin valores, y que
  `requirements.txt` de la raíz de `pset-04/` instale lo necesario.
- Comprueba con `git` que `psets/pset-02/` y `psets/pset-03/` no cambiaron desde sus tags.

## Formato del informe

1. **Resumen**: rama, commit auditado, qué está en GitHub y qué no, y un veredicto de una línea.
2. **Hallazgos**, ordenados por prioridad (P0 bloqueante, P1 urgente, P2 defecto ordinario, P3 menor). Por
   cada uno: archivo:línea, sección del PDF, escenario reproducible, resultado esperado, resultado observado,
   impacto y si es defecto confirmado o riesgo por verificar. No conviertas preferencias de estilo en
   defectos.
3. **Tabla de cumplimiento del PDF** (sección, requisito, evidencia, estado).
4. **Lo que verificaste y cómo** (comandos y resultados) y **lo que no pudiste verificar** (por ejemplo, lo
   que exige Snowflake, Kestra o la imagen en GHCR).
5. **Desviaciones del disclaimer**: cuáles están bien justificadas y cuáles no.

Entrega el informe solo en tu respuesta; no lo escribas en un archivo del repositorio.
