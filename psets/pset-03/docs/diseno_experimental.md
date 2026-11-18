# Diseño experimental del PSet 3: modelos, validación walk-forward, ensamble y cómputo

Versión del 17-nov-2026. Complementa `plan.txt` (pasos B1–B6, M1–M12) y
`pipeline/docs/series_de_tiempo.md` (diferencias, estacionariedad e intradía).
Unidad de decisión: acción × cierre de mes; objetivo `ret_log_mes_siguiente` (21 días hábiles);
universo: miembros del S&P 500 en la NYSE en esa fecha (~500 por mes, 87.178 filas).

## 0. Conflictos con el PSet 3 que hay que resolver

| Pedido nuevo | Choca con | Propuesta |
|---|---|---|
| Entrega de principio a fin en Colab | El PSet 3 pide un servidor MLflow en `docker-compose.yml` y Model Registry; Colab no corre Docker | Dos modos en `src/entorno.py`: local (servidor MLflow del compose) y Colab (`mlflow` con almacén de archivos en Drive). El Registry se demuestra en local |
| Datos por descarga dinámica | La OBT está en Snowflake con llave privada | Colab lee el snapshot `data/obt.parquet` (sha256) desde Drive (`PSET3_DATOS`); Snowflake solo con secretos de Colab, nunca en el notebook |
| "Usar exclusivamente Adj Close" | Las columnas cierre/apertura y máximo/mínimo que Paul pidió | Son compatibles: los cocientes del mismo día no dependen del ajuste (sección 2) |
| Métrica principal (W3, decidido 18-nov) | El PSet 1 prometió RMSE/MAE frente al RW y acierto direccional; el PDF pide una métrica técnica única | **MAE** es la métrica técnica única para elegir y comparar modelos (robusta a las colas del target: curtosis 9,6 en el EDA), con Diebold-Mariano frente al RW. El **IC de Spearman** por mes se reporta siempre como métrica del ranking (el EDA muestra que el 34,5 % de la varianza es del mes y que la señal entre acciones es débil); RMSE y acierto direccional, como secundarias |
| Ensamble como modelo | El PSet 3 registra un campeón | El ensamble es un candidato más; si gana, se registra como `mlflow.pyfunc` con sus componentes |
| Destilación de fundacionales | Rebalanceo mensual | Con ~500 series al mes la latencia no es un cuello de botella; se mide y se reporta, y la destilación queda para el despliegue (PSet 4) |

## 1. Auditoría de la lista de modelos

| Modelo | Riesgo de fuga | Riesgo de sobreajuste | Cómputo | Acción |
|---|---|---|---|---|
| B1 dummy, B2 RW (0), B3 RW con deriva | B3: la media debe ser solo del pliegue | Ninguno | Trivial | B3 con la media por acción de cada ventana |
| B4–B6 portafolios y los dos índices | `rf_mes_siguiente` y retornos del mes siguiente solo para medir | — | B4: 200 sorteos, segundos | `src/negocio.py` |
| M1 ARIMA por acción | `analisis/` elegía el orden con datos hasta 2023 (A2h); ADF/KPSS sobre toda la muestra también filtra | Bajo (pocos parámetros), pero elegir (p, q) entre 9 modelos por AIC sobreajusta un poco | CPU: ~1 s por acción y año (medido aquí, 1 núcleo, 9 órdenes + 12 orígenes) | Parámetros del año Y con datos hasta el 31-dic de Y−1; filtrado hasta t (`src/modelos/series.py`, prueba de no fuga) |
| M2 RF, M3 XGBoost/LightGBM | Variables con nivel de precio ajustado (`precio_cierre_ajustado`, `dif_cierre_ajustado`): el ajuste por dividendos futuros reescala el pasado | Alto: ~60 mil filas, señal débil, 33 variables | CPU, segundos por ajuste; no necesitan GPU | Solo cocientes y retornos; rango transversal; `min_child_samples` alto; filtro dentro del Pipeline |
| M4 Ridge, M5 MLP | Escalador o imputador ajustados con toda la tabla | MLP: medio | CPU | Pipeline por pliegue (ya probado en `tests/test_pipeline.py`) |
| M6 híbrido ARIMA-GARCH + MLP | Residuos dentro de muestra en las filas de entrenamiento y fuera de muestra en las de validación: la red aprende con residuos "demasiado buenos" | Medio | CPU | Misma construcción para todas las filas (parámetros de Y−1), así no hay diferencia entre entrenamiento y validación |
| M7 híbrido + LSTM | Igual que M6; además normalizar canales con toda la serie | Alto: muchos parámetros para pocos meses | GPU (T4) o MPS; ~minutos por ventana | Normalización solo con la ventana; early stopping con los últimos 12 meses de entrenamiento; Huber |
| M8–M10 Chronos, TimesFM, Moirai | Corpus de preentrenamiento: si incluye precios posteriores a 2023, el hold-out no es fuera de muestra | Ninguno en zero-shot (no se ajusta), pero sí al elegir contexto y escala | GPU o MPS; corren una vez y se guardan | Revisar la ficha de cada modelo y anotar su fecha; resultados en `artefactos/` |
| M11 LLM | Conoce la historia de precios posterior a su corte | — | Costo por llamada | Recomendación: justificar que no aplica, o probar solo una muestra y reportarlo como contaminado |
| Ensamble por rangos | Elegir el estadístico (mediana, mínimo, máximo) o los componentes mirando el hold-out | Medio: un grado de libertad más | Trivial | El estadístico es un hiperparámetro de la validación |

Riesgos de datos que afectan a todos (ya documentados en `pipeline/docs/limitaciones.md`):
- **Supervivencia (H11):** el 20,8 % de los símbolos sin precios.
- **Bolsa actual, no histórica:** el filtro NYSE mira hoy.
- **Fusiones tratadas como cambio de símbolo (H16).**
- **`sigue_en_sp500`:** describe el presente; nunca entra a X.

Riesgo estadístico global: comparar ~15 modelos y ~90 configuraciones con ~84 meses de validación. El mejor modelo en validación está sesgado hacia arriba. Por eso:
1. Los p-valores se ajustan por Holm.
2. El hold-out se usa una sola vez.
3. Se reporta la desviación entre ventanas junto a cada media.

## 2. Preprocesamiento y estacionariedad

- **Precios:** solo ajustados. Los cocientes del mismo día (cierre/apertura y máximo/mínimo) son iguales con o sin ajuste. Los niveles (`precio_cierre_ajustado`, `dif_cierre_ajustado`) no entran a ningún modelo: dependen de dividendos posteriores a t.
- **Entradas estacionarias:**
  - Retornos logarítmicos y porcentuales.
  - Intradía, nocturno y rango.
  - Volatilidades: móvil, Parkinson y Garman-Klass.
  - Momentum y drawdown.
  - Beta.
  - Volumen relativo.
- **Falta F2:** distancia a medias móviles, en log y en %. Son `ln(P/SMA_w)` y `P/SMA_w − 1` con w = 21, 63 y 200, y lo mismo con EMA. Se agregan en Spark (OBT mensual) con su prueba, como F1.
- **ADF y KPSS:**
  - Se corren por acción en el EDA, con los datos de entrenamiento de la primera ventana.
  - Se esperan dos resultados: ln P con raíz unitaria, y los retornos y cocientes estacionarios.
  - Una variable que falle en más del 20 % de las acciones se transforma o sale.

## 3. Validación walk-forward

Código en `src/validacion.py`; probado en `tests/test_diseno.py`.

```
Datos con variables completas: 2011-01 (252 días de historia) en adelante.
Desarrollo: objetivos hasta 2023-12.  Hold-out: objetivos 2024-01 .. último mes cerrado (~34 meses).

Ventana  Entrenamiento (mes_objetivo)   Embargo   Validación (mes_objetivo)
wf_2017  2011-01 .. 2016-11              2016-12   2017-01 .. 2017-12
wf_2018  2011-01 .. 2017-11              2017-12   2018-01 .. 2018-12
  ...
wf_2023  2011-01 .. 2022-11              2022-12   2023-01 .. 2023-12      (7 ventanas, 84 meses)
```

- **Ventanas:** expansivas por defecto. Fijas de 60 meses como prueba de sensibilidad (`ventana_meses=60`).
- **Embargo de 1 mes:** las ventanas de 21 a 252 días de la última fila de entrenamiento y la primera de validación se solapan.
- **Usos de las ventanas:**
  - **Candidatos (3.6):** las 7 ventanas, con métricas por ventana, media y desviación.
  - **Tuning (3.7):** solo wf_2021, wf_2022 y wf_2023. Equivale a "2×5 en lugar de 10×10": 3 ventanas en vez de 7, y poda tras la primera.
  - **Selección (3.8):** las 7 ventanas para elegir y el hold-out una sola vez. Por defecto con el ajuste hasta 2023-12, como pide el PSet. El re-ajuste anual en 2025 y 2026 con hiperparámetros fijos es solo un análisis de sensibilidad.
- **ARIMA-GARCH:** su tabla no depende de la ventana. Se calcula una vez (parámetros del año Y con datos hasta Y−1) y sirve para todas.
- **Prohibido:** KFold aleatorio, GroupKFold por acción, escalar, imputar o seleccionar variables fuera del Pipeline, y tocar el hold-out para cualquier decisión.

## 4. Búsqueda de hiperparámetros

Con Optuna (`src/tuning.py`), por cuatro razones:
- Poda por ventana.
- Espacios condicionales.
- Gráficas de optimización, que se piden.
- Cada trial puede ser una corrida hija de MLflow.

Configuración:
- **Muestreador y poda:** TPE con semilla 42 (la del proyecto, `src/entorno.py`) y `MedianPruner(n_startup_trials=8)`.
- **Objetivo:** maximizar el IC medio de las 3 ventanas de tuning.
- **Mejora real:** la mejora sobre la configuración por defecto se compara con la desviación entre ventanas.

| Modelo | Espacio (escala) |
|---|---|
| Todos los tabulares | `k` del filtro ∈ {10, 20, todas}; rango transversal ∈ {sí, no} |
| LightGBM / XGBoost | n_estimators 100–1500 (log), learning_rate 0,005–0,2 (log), num_leaves 8–128 (log) o max_depth 2–8, min_child 50–2000 (log), subsample 0,5–1, colsample 0,3–1, lambda 0,001–100 (log) |
| Random forest | n_estimators 100–600 (log), max_depth 3–20, min_samples_leaf 20–2000 (log), max_features 0,1–1 |
| Ridge | alpha 0,001–10⁴ (log) |
| MLP | capas (16–256, 8–128) (log), alpha 10⁻⁶–0,1 (log), learning_rate_init 10⁻⁴–10⁻² (log) |
| LSTM híbrida (si queda entre los 3 mejores) | oculto {16, 32, 64}, capas 1–2, abandono 0–0,5, tasa 10⁻⁴–3·10⁻³ (log), L ∈ {21, 63, 126} días, Huber δ {0,02, 0,05, 0,1} |

Mínimo del PSet: 3 modelos × 30 configuraciones = 90 corridas hijas.

## 5. Métricas y pruebas

Código en `src/evaluacion.py`.

- **Técnicas:**
  - MAE, RMSE, acierto direccional y R² fuera de muestra frente al RW.
  - IC de Spearman por mes: media, desviación, ICIR, t y porcentaje de meses positivos.
- **Pruebas sobre series mensuales:** no sobre filas, porque las acciones de un mes están correlacionadas.
  - **Contra el RW:** Diebold-Mariano con corrección HLN sobre la pérdida cuadrática media del mes, y Wilcoxon sobre la misma pérdida.
  - **Entre modelos:** Diebold-Mariano sobre la pérdida y Wilcoxon sobre el IC mensual.
  - **Ajuste:** Holm sobre todos los p-valores de una misma tabla.
  - **Supuesto:** las dos pruebas suponen meses independientes. El IC tiene poca autocorrelación, pero hay que revisarla en el EDA.
- **Negocio** (`src/negocio.py`):
  - Regla: top 10 con pesos 1/vol (`vol_63d` por defecto) y tope de volatilidad.
  - Medidas: retorno simple, turnover con pesos que se mueven con los precios, costo en pb por unidad de turnover (10 pb por defecto), Sharpe neto y bruto, drawdown y retorno anual neto.
  - Referencias: B4 (200 sorteos) y B6.

## 6. Ensamble transversal

Código en `src/ensamble.py`.

1. Cada modelo da un puntaje.
2. Dentro del mes, el puntaje pasa a rango normalizado: rango/n, donde 1/n es el mejor.
3. Con M modelos, para cada acción se toma uno de tres estadísticos de orden:
   - **Mediana** r₍₍M+1₎/2₎: consenso.
   - **Mínimo** r₍₁₎: cobertura; basta con que un modelo la ponga arriba.
   - **Máximo** r₍M₎: filtro conservador; todos deben ponerla arriba.

El pedido escribe r₍₃₎ porque supone M = 3. El código usa r₍M₎ y acepta cualquier k. Componentes propuestos: el mejor tabular, el híbrido y el mejor fundacional. El estadístico y los componentes se eligen en las 7 ventanas.

## 7. Presupuesto de cómputo

Fase pesada (Mac M4, una vez; resultados en `artefactos/` con sha256, `src/entorno.py`):

| Tarea | Medido / estimado | Dónde |
|---|---|---|
| ARIMA-GARCH: ~8.000 acción-años × 9 órdenes + 12 orígenes | ~1 s por acción-año en 1 núcleo (medido) → ~2,2 h en serie, ~15 min con 9 procesos del M4 | M4 (`joblib`); en Colab, ~1 h con 2 vCPU |
| Chronos-Bolt small: ~87 mil ventanas de 512 días | Por medir (la latencia queda en MLflow) | M4 con MPS o Colab T4 |
| TimesFM / Moirai | Igual; cada uno en su propio entorno (sus dependencias chocan) | Colab T4 |
| LSTM: 7 ventanas × ~30 épocas | Por medir; ~60 mil secuencias de 63 × 5 por ventana | M4 (MPS) o T4 |

Fase de entrega (Colab gratis, 2 vCPU, 12,7 GB de RAM y T4). Carga los artefactos y corre el resto:
- **Tabulares:** 7 ventanas × 8 modelos con ~60 mil filas y 33 variables. Minutos.
- **Optuna:** 3 × 30 × 3 ventanas = 270 ajustes con poda. Unos 15–30 min con LightGBM en 2 vCPU (estimado).
- **Diagnósticos:** t-SNE de 5.000 puntos (~1 min) y gráficas.
- **Memoria:** `OBT_ACCION_DIA` (1,8 M × 33) ocupa ~0,5 GB en float64. En Colab se carga solo si se recalcula la fase pesada.

## 8. Estructura del código

```
psets/pset-03/
├── src/
│   ├── entorno.py          rutas relativas, PSET3_DATOS, dispositivo cuda/mps/cpu, semillas, artefactos con sha256   [probado]
│   ├── datos.py            snapshot de la OBT desde Snowflake (falta: OBT_ACCION_DIA)                                  [existía]
│   ├── validacion.py       ventanas walk-forward con embargo, verificación de fuga, hold-out                         [probado]
│   ├── pipeline.py         Pipeline de la versión anterior (17 variables); se reemplaza por modelos/tabulares.py     [existía]
│   ├── modelos/
│   │   ├── tabulares.py    Pipelines: rango transversal → imputar → escalar → SelectKBest → modelo (B1, B2, M2–M5)  [probado]
│   │   ├── series.py       ARIMA-GARCH por acción sin fuga (M1 y entradas de M6/M7), joblib                          [probado]
│   │   ├── redes.py        LightningModule LSTM híbrida, early stopping, historia para curvas (M7)                   [compila; se prueba en la Mac]
│   │   └── fundacionales.py Chronos con cuantiles y latencia; TimesFM y Moirai pendientes (M8–M10)                   [compila; se prueba en la Mac]
│   ├── ensamble.py         rangos transversales y estadísticos de orden                                              [probado]
│   ├── evaluacion.py       MAE, RMSE, IC, Diebold-Mariano HLN, Wilcoxon, Holm                                         [probado]
│   ├── negocio.py          top 10 con 1/vol, turnover, costos, Sharpe, drawdown, portafolios aleatorios              [probado]
│   ├── tuning.py           Optuna (TPE + poda) con espacios por modelo                                               [probado con datos sintéticos]
│   ├── diagnostico.py      t-SNE 2D, gráficas de Optuna, curvas de aprendizaje                                       [Optuna probado]
│   └── experimentos.py     registro en MLflow (existía; se adapta a las ventanas walk-forward)
├── notebooks/  01_eda · 02_features · 03_baseline_candidatos · 04_tuning · 05_seleccion  (+ 00_colab_entrega)
├── artefactos/ arima_garch.parquet, fundacionales_*.parquet, lstm_*.pt (+ .json con sha256)
└── tests/      test_pipeline.py, test_diseno.py (16 pruebas)
```

Dependencias (`pyproject.toml`):
- **`modelos`:** statsmodels, arch, optuna, lightgbm y xgboost.
- **`redes`:** torch y lightning; está en el lock y se instala en la Mac o en Colab.
- **Fundacionales:** fuera del lock, cada uno con su `pip` en Colab.

## 9. Decisiones pendientes (Paul)

1. ~~Métrica principal~~: decidido 18-nov (W3): MAE como métrica técnica única; IC de Spearman por mes siempre reportado.
2. Costo por transacción (10 pb propuesto), tope de volatilidad y `vol_21d` o `vol_63d` para los pesos.
3. Colab: snapshot en Drive o lectura de Snowflake con secretos.
4. Variables F2: distancia a SMA/EMA (21, 63, 200).
5. LLM (M11): justificar que no aplica o probar una muestra.
