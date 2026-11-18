# Series de tiempo: diferencias, porcentajes y logaritmos

Este documento explica qué columnas de diferencias trae el pipeline (Silver, Gold, `OBT_ACCION_DIA`
y `OBT_ACCION_MES`), por qué hay tres formas de cada una y cuál conviene a cada modelo del PSet 3.
Retoma lo que ya probó `analisis/modelos/series_y_arima.py` (ADF, KPSS y ARIMA por AIC/BIC sobre
`nivel_*`, `dif_*`, `intradia` y `nocturno`).

## 1. Las tres diferencias diarias

Con P(t) el precio ajustado del día t:

| Forma | Fórmula | Columnas | Propiedades |
|---|---|---|---|
| Aritmética | Δ = P(t) − P(t−1) | `dif_cierre_ajustado`, `dif_apertura_ajustada` | En dólares. Su varianza crece con el nivel de precio, así que no es estacionaria en varianza. Además depende del ajuste: cada dividendo o split reescala toda la historia ajustada de Yahoo y cambia las diferencias pasadas (H6) |
| Porcentual (geométrica, simple) | r = P(t)/P(t−1) − 1 | `ret_pct_diario`, `ret_pct_apertura` | No depende del nivel ni del ajuste. Se suma **entre acciones**: el retorno de un portafolio es Σ wᵢ rᵢ. No se suma en el tiempo: el mes es Π(1 + r) − 1. Asimétrica: −50 % y +50 % no se compensan |
| Logarítmica | ℓ = ln P(t) − ln P(t−1) = ln(1 + r) | `ret_log_diario`, `ret_log_apertura` | Se suma **en el tiempo**: el mes es Σ ℓ (por eso `ret_log_mes`). Simétrica y más cercana a la normal. No se suma entre acciones |

Relaciones: r = exp(ℓ) − 1, ℓ ≈ r − r²/2 para retornos pequeños, y Δ = P(t−1) · r. La prueba
`assert_diferencias_diarias_coherentes` verifica las tres en Silver.

Dos consecuencias para el proyecto:

- **El target se queda en logaritmo** (`ret_log_mes_siguiente`): es la suma de los 21 retornos
  diarios del mes y las métricas técnicas (MAE, RMSE, Diebold-Mariano) se calculan sobre él.
- **La métrica de negocio usa porcentajes** (`ret_pct_mes_siguiente`): el retorno del
  portafolio de 10 acciones con pesos 1/vol es Σ wᵢ rᵢ, que solo vale con retornos simples.
  Convertir con exp(ℓ) − 1 después de pronosticar no da la media en porcentaje: por la
  desigualdad de Jensen, E[exp(ℓ)] − 1 ≈ exp(E[ℓ] + σ²/2) − 1.

## 2. Estacionariedad y diferencias en ARIMA

El nivel ln P(t) se comporta como un paseo aleatorio (raíz unitaria): ADF no rechaza la raíz y
KPSS rechaza la estacionariedad. Su primera diferencia es el retorno logarítmico, que sí es
estacionario en media. Por eso:

- ARIMA(p, 1, q) sobre ln P equivale a ARMA(p, q) sobre `ret_log_diario`. Con d = 1 sobre el
  nivel, el pronóstico del mes es la suma de los h pronósticos diarios (h = días bursátiles del
  mes), como hace `analisis/`. Sobre la serie mensual, `ret_log_mes` ya es la diferencia (d = 0).
- ARIMA sobre la diferencia **aritmética** no se recomienda: la varianza no es constante, cambia
  con cada ajuste de Yahoo y el modelo sobrepondera los periodos de precio alto.
- ARIMA sobre la diferencia **porcentual** es posible, pero la suma de pronósticos diarios no da
  el retorno del mes; hay que componerlos. El logaritmo evita ese paso.
- En la práctica, el ARMA de los retornos tiene coeficientes cercanos a cero. Lo esperable es que
  M1 quede cerca del random walk; la prueba Diebold-Mariano lo dirá.

Las pruebas ADF/KPSS se repiten en el EDA (3.1) sobre `OBT_ACCION_DIA` con los datos de
entrenamiento de cada pliegue, para justificar d en M1, M6 y M7.

## 3. Intradía, rango y la hipótesis de inestabilidad

La hipótesis de Paul (17-nov) es que los cambios en el porcentaje cierre/apertura y
máximo/mínimo anticipan cambios o inestabilidad. Esa idea tiene respaldo:

- **La volatilidad se agrupa** (heterocedasticidad condicional, la base de ARCH/GARCH): a días
  de rangos amplios le siguen días de rangos amplios. Predecir la volatilidad es mucho más
  factible que predecir el signo del retorno.
- **Los estimadores por rango son más eficientes** que la desviación de los cierres: Parkinson
  (1980) usa ln(H/L); Garman y Klass (1980) agregan ln(C/O). Con el mismo número de días tienen
  menos error que `vol_21d`.
- **Intradía y nocturno separan información**: el salto nocturno recoge noticias fuera de
  horario (resultados, macro) y el intradía, la negociación del día.

Columnas para probarla:

| Idea | Diario (`OBT_ACCION_DIA`) | Mensual (`OBT_ACCION_MES`) |
|---|---|---|
| Cierre frente a apertura | `ret_pct_intradia`, `ret_log_intradia` | `intradia_pct_mes`, `intradia_log_mes`, `intradia_pct_prom_21d`, `intradia_prom_21d`, `vol_intradia_21d` |
| Apertura frente a cierre anterior | `ret_pct_nocturno`, `ret_log_nocturno` | `nocturno_pct_mes`, `nocturno_log_mes`, `nocturno_pct_prom_21d`, `nocturno_prom_21d` |
| Máximo frente a mínimo | `rango_pct_hl`, `rango_log_hl` | `rango_pct_hl_mes`, `rango_log_hl_mes`, promedios de 21 y 63 días |
| **Cambio** del rango | (diferencia de `rango_log_hl` entre días, si hace falta) | `cambio_rango_log_hl_mes`, `cambio_rango_pct_hl_mes`, `cambio_rango_log_hl_21_63`, `cambio_rango_pct_hl_21_63` |
| Volatilidad por rango | — | `vol_parkinson_21d`, `vol_garman_klass_21d` |

Cómo se evalúa en el PSet 3 (pasos F1 y 3.2 del plan): Spearman de cada columna con el target
y con |target| (inestabilidad), e importancia por ablación en la CV. Si el rango predice
|retorno| pero no el retorno, su valor está en la regla de negocio (tope de volatilidad y pesos
1/vol), no en el ranking de las 10 acciones.

## 4. Logaritmo o porcentaje en cada modelo

| Modelo | Usar | Motivo |
|---|---|---|
| Árboles (M2 random forest, M3 XGBoost) | Cualquiera de las dos | Invariantes a transformaciones monótonas; tener las dos solo duplica columnas |
| Ridge (M4) y MLP (M5) | Logaritmo | Más simétrico y con colas más cortas; las dos juntas son casi colineales |
| ARIMA e híbridos (M1, M6, M7) | Logaritmo diario o mensual | Sección 2 |
| Fundacionales (M8–M10) | Logaritmo de los retornos, o el nivel ln P si el modelo lo pide | Se entrenaron con series de distinta escala; se documenta cuál se usó |
| Métrica de negocio | Porcentaje | Sección 1 |

Como el PSet 3 pide la misma preparación para todos los candidatos tabulares, la lista de
features se decide en 3.2 por ablación: por defecto, las versiones en logaritmo, con las de
porcentaje disponibles para el EDA y para comprobar que el resultado no cambia.

## Referencias

- M. Parkinson, "The Extreme Value Method for Estimating the Variance of the Rate of Return,"
  *Journal of Business*, vol. 53, no. 1, pp. 61–65, 1980.
- M. B. Garman y M. J. Klass, "On the Estimation of Security Price Volatilities from Historical
  Data," *Journal of Business*, vol. 53, no. 1, pp. 67–78, 1980.
- T. Bollerslev, "Generalized Autoregressive Conditional Heteroskedasticity," *Journal of
  Econometrics*, vol. 31, no. 3, pp. 307–327, 1986.
- R. J. Hyndman y G. Athanasopoulos, *Forecasting: Principles and Practice*, 3.ª ed., OTexts,
  2021, cap. 9 (estacionariedad, diferencias y ARIMA).
