# Diccionario de datos (PSet 3, base PORTAFOLIO_P3)

Parte del diccionario del PSet 2 (`psets/pset-02/docs/diccionario_datos.md`); aquí solo cambia
lo marcado como **nuevo** o **cambia**. El inventario por columna está en
[calidad/README.md](calidad/README.md), [inventario_columnas.csv](calidad/inventario_columnas.csv)
y [decisiones_por_columna.csv](calidad/decisiones_por_columna.csv).

## Silver y Gold de precios (**cambia**: OHLC ajustado y diferencias diarias)

| Objeto | Clave/grano | Medidas y atributos |
|---|---|---|
| DIM_ACCION | accion_key, una acción/símbolo normalizado | ticker, nombre, bolsa actual, fechas de precio/membresía, disponibilidad |
| DIM_FECHA | fecha_key (AAAAMMDD), un día bursátil | fecha, año, mes, anio_mes, cierre de mes, mes_cerrado, conjunto temporal |
| DIM_MEMBRESIA_SP500 | periodo_key, un intervalo por símbolo | ticker, fecha_inicio, fecha_fin, vigente, huecos_unidos |
| FCT_PRECIOS_DIARIOS | accion_key + fecha_key | OHLC, OHLC ajustado (**nuevo**: máximo y mínimo), volumen, diferencias diarias en tres formas (**nuevo**), membresía, marcas de calidad |
| FCT_MERCADO_DIARIO | fecha_key | cierre y retorno de S&P 500 / NYSE Composite, ^IRX y tasa diaria aproximada |

Columnas diarias de `SLV_PRECIOS_ACCIONES` y `FCT_PRECIOS_DIARIOS` (las mismas en las dos).
Las tres formas de diferencia y por qué se usa cada una están en [series_de_tiempo.md](series_de_tiempo.md).

| Grupo | Columnas | Fórmula / restricción |
|---|---|---|
| OHLCV de Yahoo | precio_apertura, precio_maximo, precio_minimo, precio_cierre, volumen | Sin ajustar; fecha = día bursátil (las barras diarias no traen hora; el cierre es a las 16:00 de Nueva York) |
| OHLC ajustado | precio_cierre_ajustado, precio_apertura_ajustado, precio_maximo_ajustado (**nuevo**), precio_minimo_ajustado (**nuevo**) | factor = cierre ajustado / cierre; máximo y mínimo solo en días observados (nulos si imputado) |
| Cierre a cierre | dif_cierre_ajustado (**nuevo**), ret_pct_diario (**nuevo**), ret_log_diario | aritmética P(t) − P(t−1) en USD; porcentual P(t)/P(t−1) − 1; logarítmica ln P(t) − ln P(t−1) |
| Apertura a apertura | dif_apertura_ajustada (**nuevo**), ret_pct_apertura (**nuevo**), ret_log_apertura | Igual, con la apertura ajustada |
| Cierre vs apertura del día | ret_pct_intradia (**nuevo**), ret_log_intradia | (cierre − apertura) / apertura y ln(cierre / apertura) |
| Apertura vs cierre anterior | ret_pct_nocturno (**nuevo**), ret_log_nocturno | ret_log_diario = ret_log_nocturno + ret_log_intradia (prueba `assert_diferencias_diarias_coherentes`) |
| Máximo vs mínimo del día | rango_pct_hl (**nuevo**), rango_log_hl (**nuevo**) | (máximo − mínimo) / mínimo y ln(máximo / mínimo); ≥ 0; nulos si imputado. No necesitan ajuste: el factor se cancela en el cociente del mismo día |

En un día imputado (forward-fill) el retorno de cierre es 0 y el intradía repite el del último
día observado con el nocturno de signo contrario, de modo que la suma sigue siendo 0. Los
promedios y sumas de la OBT usan solo días observados.

## CALIDAD

| Objeto | Grano | Contenido |
|---|---|---|
| DQ_METRICAS | una métrica | 22 métricas por dimensión (completitud, validez, consistencia, unicidad, oportunidad) |
| DQ_HUECOS_POR_TICKER (**nuevo**) | un símbolo de la composición histórica | dias_miembro, dias_miembro_con_precio, pct_huecos_miembro, primera/ultima_cotizacion, dias_vida, dias_vida_con_precio, dias_imputados, dias_excluidos, sin_precios |
| DQ_UNIVERSO_POR_FECHA (**nuevo**) | un día bursátil | miembros_composicion, miembros_con_precio, miembros_sin_precio, miembros_nyse, miembros_bolsa_desconocida, pct_cobertura |

Las dos tablas nuevas cumplen lo que el PSet 1 prometió para la etapa de datos (porcentaje de
huecos por ticker y universo de cada fecha frente a la composición histórica) y cuadran con
`dias_miembro_sin_precio_pct` de DQ_METRICAS (prueba `assert_huecos_coherentes_con_dq_metricas`).

## OBT_ACCION_MES

Grano: `accion_key` + `anio_mes` (AAAAMM), meses cerrados. 75 columnas: las 43 del PSet 2 y 32
nuevas del PSet 3 (tabla de abajo). Precios en USD, volumen en acciones. Cada variable de precio
nueva va en logaritmo (`*_log_*`, aditiva en el tiempo) y en porcentaje (`*_pct_*`, aditiva
entre acciones de un portafolio); la tasa libre de riesgo es tasa simple aproximada.

| Grupo | Columnas | Interpretación / restricción |
|---|---|---|
| Identidad | accion_key, ticker, nombre | Clave y etiquetas; no son variables numéricas |
| Bolsa | bolsa, es_nyse, bolsa_desconocida | Bolsa actual, no histórica (439 de 1.130 acciones con bolsa desconocida) |
| Tiempo | anio_mes, anio, mes, fecha_ultima_cotizacion | Última observación del mes cerrado |
| Protocolo | conjunto, objetivo_cruza_corte | Separación por fecha; el PSet 3 divide por mes del objetivo |
| Elegibilidad | cotizo_al_cierre_de_mes, en_sp500, sigue_en_sp500, elegible | sigue_en_sp500 describe el presente: no entra a X. `elegible` = en_sp500 y (es_nyse o bolsa_desconocida) y cotizo_al_cierre_de_mes y obs_252d >= 200 y dias_negociados_mes >= 15 y volumen_prom_21d > 0 (H18, PSet 3) |
| Nivel y retorno | precio_cierre_ajustado, ret_log_mes, ret_log_21d, ret_log_252d, momentum_12_1 | Ventanas hasta la fila (prueba de no fuga en spark/tests) |
| Riesgo | vol_21d, vol_63d, vol_apertura_21d, drawdown_252d | Volatilidad anualizada con raíz de 252 |
| Intradía | intradia_prom_21d, nocturno_prom_21d | Promedios de retornos intradía/nocturnos |
| Liquidez | volumen_prom_21d, dolares_negociados_prom_21d | Promedios de volumen y volumen × cierre |
| Cobertura | obs_252d, dias_negociados_mes, dias_imputados_mes | Conteos; ventanas por filas |
| Calidad | hubo_tramo_excluido_mes, hubo_retorno_extremo_mes | Huecos largos excluidos y retornos extremos (umbral 0,40) |
| Mercado actual | ret_log_sp500_mes, ret_log_nyse_composite_mes, rf_mes, tasa_irx_prom_mes_pct | Referentes del mes que termina |
| Objetivo | ret_log_mes_siguiente, exceso_ret_mes_siguiente | Futuros: nunca en los predictores |
| Referentes futuros (**cambia**) | ret_log_sp500_mes_siguiente, ret_log_nyse_composite_mes_siguiente, rf_mes_siguiente | Solo evaluación ex post. Desde H1 son nulos si el mes siguiente no ha cerrado (antes usaban el mes en curso) |

**Columnas nuevas del PSet 3** (`spark/jobs/construir_obt.py`; pruebas en `spark/tests`):

| Grupo | Columnas | Cálculo |
|---|---|---|
| Retorno en % | ret_pct_mes | exp(ret_log_mes) − 1 |
| Rezagos (PSet 1: "con rezagos") | ret_log_mes_lag1..3, ret_pct_mes_lag1..3 | Retorno de 1, 2 y 3 meses antes; nulo si algún mes no es consecutivo |
| Intradía y nocturno del mes | intradia_log_mes, intradia_pct_mes, nocturno_log_mes, nocturno_pct_mes | Suma de ln(cierre/apertura) y de ln(apertura/cierre anterior) en días con retorno; intradia_log_mes + nocturno_log_mes = ret_log_mes |
| Intradía en 21 días | intradia_pct_prom_21d, nocturno_pct_prom_21d, vol_intradia_21d | Promedios en %, y desviación del intradía anualizada |
| Rango máximo-mínimo | rango_log_hl_mes, rango_pct_hl_mes, rango_log_hl_prom_21d, rango_pct_hl_prom_21d, rango_log_hl_prom_63d, rango_pct_hl_prom_63d | Promedio del rango diario en el mes, en 21 y en 63 días |
| Cambio del rango (inestabilidad) | cambio_rango_log_hl_mes, cambio_rango_pct_hl_mes, cambio_rango_log_hl_21_63, cambio_rango_pct_hl_21_63 | Rango del mes frente al mes anterior (diferencia en log, cociente − 1 en %) y rango de 21 días frente al de 63 |
| Volatilidad por rango | vol_parkinson_21d, vol_garman_klass_21d | Parkinson (1980): √(prom ln(H/L)² / 4 ln 2 · 252); Garman-Klass (1980): √(prom[½ ln(H/L)² − (2 ln 2 − 1) ln(C/O)²] · 252) |
| Mercado | beta_252d, exceso_sp500_log_mes, exceso_sp500_pct_mes | cov(r, r_S&P)/var(r_S&P) en 252 días observados; retorno del mes menos el del S&P 500 |
| Volumen relativo | volumen_relativo_log_21_252, volumen_relativo_pct_21_252 | ln y cociente − 1 de volumen_prom_21d / volumen promedio de 252 días |
| Objetivo en % (futuro) | ret_pct_mes_siguiente | exp(ret_log_mes_siguiente) − 1; solo para la métrica de negocio (el portafolio suma retornos simples), nunca en X |

## OBT_ACCION_DIA (**nuevo**)

Grano: `accion_key` + `fecha` (un día bursátil), las mismas filas de `GOLD.FCT_PRECIOS_DIARIOS`.
33 columnas: accion_key, ticker, fecha, anio_mes, conjunto, mes_cerrado, en_sp500, imputado,
despues_de_tramo_excluido, es_retorno_extremo, el OHLCV sin ajustar y ajustado, las
diferencias diarias de cierre y apertura en sus tres formas, intradía, nocturno y rango en % y
log, ret_log_sp500 y rf_diaria. Es la entrada de los modelos de series (ARIMA, híbridos y
fundacionales): trae también los días posteriores a cada cierre de mes, así que el modelo debe
cortar la serie en la fecha de origen antes de pronosticar.

El objetivo queda nulo si no hay mes siguiente cerrado para la acción. Los nulos de las variables
se imputan dentro de cada pliegue de entrenamiento en el PSet 3, no con toda la OBT.
