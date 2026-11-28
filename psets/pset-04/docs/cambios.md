# Cambios hechos por las observaciones de los PSets anteriores

## PSet 1 (revisión del 14-nov-2026, archivos `_v2` de `psets/pset-01/feedback/`)

| Observación del profesor | Antes | Después | Archivos donde se cambió o se ve |
|---|---|---|---|
| 1A Comparación y selección de ideas | Matriz con target "Alto" para el portafolio (16 puntos) | Target "Medio" por el riesgo de no superar al random walk (15 puntos); desempate por acceso a datos reales | `psets/pset-01/feedback/CD_PSet_1_00351916_v2.xlsx`; en el PSet 4, `monitoreo/simulacion.py` y `docs/simulacion/resumen_negocio.csv` (siempre contra B1, B5 y efectivo) |
| 2A Problema y formulación | Predicción y decisión poco atadas | Cadena problema → predicción (retorno log a 1 mes) → decisión (top 10, 1/vol) → acción → resultado | `PSet1_memo_Gomez_Ehmig_v2` (sección 3); `api/main.py` y `api/esquemas.py`: `POST /predecir` devuelve predicción **y** decisión (incluir, peso) |
| 3B Viabilidad de negocio | Cifras del pitch estimadas | Meta: Sharpe ≥ índice + 0,1, con costos | `PSet1_pitch_Gomez_Ehmig_v2`; `scripts/generar_memo.py` (sección 9) y `docs/simulacion/resultado_lotes.csv` |
| 4B Alcance del semestre | Entregables poco acotados | Entregables por fase; ejecución automática fuera de alcance | `PSet1_memo_Gomez_Ehmig_v2` (sección 4); `docs/criterio_retirada.md` (sección 5): el sistema propone, no ejecuta |
| H Horizonte (decisión propia) | Horizonte distinto del rebalanceo | Horizonte = rebalanceo = 1 mes | `PSet1_memo_Gomez_Ehmig_v2`; `pipeline/spark/` (objetivo `ret_log_mes_siguiente`); `docs/despliegue.md` (batch mensual) |

**Cifras del pitch del PSet 1 reemplazadas** (`scripts/generar_memo.py`, sección 9; `scripts/generar_presentacion.js`).
El pitch suponía un Sharpe que superaba al índice por 0,1. Con datos: en el hold-out real el champion logró Sharpe neto
0,87 frente a 0,68 de B5 (PSet 3). En la simulación del PSet 4 (35 lotes, tres de crisis inducida), el champion sin
reentrenar logró 0,05 frente a −0,13 de B5 y un retorno anual de 3,7 % frente a 4,3 % del efectivo; con los
reentrenamientos que aprobó la regla del PDF, −0,23. La meta del pitch no se cumple.

## Decisiones actualizadas en el PSet 4

| Decisión | Antes | Después | Archivos |
|---|---|---|---|
| Universo | GM en NYSE | GM sale del universo (pasó a Nasdaq en los listados actuales) | `docs/datos_p4.md` |
| Preparación al servir | `preparar` + `dividir` (exigen objetivo, interpolan con meses posteriores) | `preparar_inferencia`: sin objetivo ni meses posteriores | `monitoreo/simulacion.py`, `tests/test_produccion.py` |
| Competidores (pedido de Paul, 27-nov) | B1–B5 del PSet 3 | + "operación manual": 10 acciones de mejor Sharpe de 12 meses bajo la volatilidad aprobada, evaluada en CV, hold-out real y simulación, y en todo el flujo como línea base B7 (MLflow, API en paralelo, PREDICCIONES, MONITOREO, alerta A9, tablero); cambia la recomendación | `modelos/src/operacion_manual.py`, `api/main.py`, `monitoreo/`, `tests/test_operacion_manual.py`, `modelos/notebooks/08_competidores.ipynb`, `docs/simulacion/competidores.csv` |
| Recomendación del PSet 3 | Operar con B3 o B5 y el modelo en paralelo | Operar con la operación manual y el modelo en paralelo | `scripts/generar_memo.py` (secciones 9 y 10), `scripts/generar_presentacion.js` |
| Juicio humano (PSet 1) | El cliente aprueba cada propuesta | Se mantiene y se agrega la aprobación de cada cambio de modelo | `docs/criterio_retirada.md`, `pipeline/kestra/flows/reentrenamiento.yml` |

## PSet 2 (tag `pset-02`, 100/100 sin observaciones)

Sin observaciones del profesor. Cambios propios por coherencia con el PSet 1 revisado (registrados en
`psets/pset-02/disclaimer.txt`): imputación por forward-fill de hasta 5 sesiones, z-score robusto (MAD) para marcar
outliers, fuentes documentadas. En el PSet 4: hallazgos H1 (pérdida silenciosa en la primera `ingesta_diaria`) y H2 (GM
pasa de NYSE a Nasdaq en los listados actuales, `docs/datos_p4.md`), que se documentan y no se corrigen a mano.

## PSet 3 (tag `pset-03`, 100/100 sin observaciones)

Sin observaciones del profesor. Cambios propios: el memo se corrigió antes de entregar (Ridge con las 35 features,
nota BMS/AMCR, objetivo = retorno y no volatilidad). En el PSet 4 el champion se usa tal cual (v1); la reproducción de
su MAE en el hold-out (0,0673399888) es una prueba de CI (`tests/test_modelo.py`).
