# Técnicas: sesgo de supervivencia, valores faltantes e imputación

Revisión para el PSet 2 (y la etapa Datos del PSet 1). Al final de cada sección está lo que se aplica en este proyecto y dónde.

## 1. Sesgo de supervivencia

**Qué es.** Analizar solo las acciones que siguen existiendo hoy deja fuera a las que se deslistaron, quebraron o salieron del índice, que suelen ser las de peor rendimiento. El resultado infla el retorno y el Sharpe, y subestima las caídas ([QuantVault](https://quantvault.org/problem-2090-survivorship-bias-in-backtesting.html); [CoinAPI](https://www.coinapi.io/learn/glossary/survivorship-bias)).

**Magnitud reportada.**
- En la base CRSP de EE. UU. (1926–2001): 7,4 % anual sin sesgo frente a 9,0 % con sesgo ([LuxAlgo](https://luxalgo.com/blog/survivorship-bias-in-backtesting-explained)).
- En otros trabajos: entre 1 y 3 puntos al año ([Learning TA](https://learning-ta.pages.dev/learn/backtesting-pitfalls)).
- En small caps de India: 4,94 puntos al año ([arXiv 2603.19380](https://arxiv.org/pdf/2603.19380)).
- En el S&P 500, entre un tercio y la mitad del índice cambia cada diez años, así que la lista de hoy es el universo equivocado para casi cualquier prueba histórica ([ABC Trading Group](https://www.abctradinggroup.com/backtesting-pitfalls/)).

**Técnicas.**

| Técnica | Cómo funciona | Uso aquí |
|---|---|---|
| Universo *point-in-time* | En cada fecha de rebalanceo solo se elige entre las acciones que estaban en el índice ese día, incluidas las que después desaparecieron ([CoinAPI](https://www.coinapi.io/learn/glossary/survivorship-bias)) | Sí: composición histórica de chinobing (fotos desde 1996 hasta hoy) y `slv_membresia_sp500` en dbt |
| Incluir las acciones deslistadas con su retorno de salida | Las bases profesionales (CRSP) guardan el retorno de deslistado; si falta, el sesgo persiste aunque el universo sea correcto ([QuantVault](https://quantvault.org/problem-2090-survivorship-bias-in-backtesting.html); [Alpha Architect](https://alphaarchitect.com/2016/08/dealing-with-delistings-a-critical-aspect-for-stock-selection-research/)) | Parcial: Yahoo no conserva la mayoría de las acciones deslistadas ([Backtrex](https://backtrex.com/en/blog/survivorship-bias-trading-backtesting)). Se mide cuántas faltan (`fechas_accion`, `cache_yahoo_consultas` con estado SIN_DATOS) |
| Mapear cambios de símbolo | Una empresa que cambia de símbolo no sale del índice. Si no se mapea, parece salir y otra parece entrar, y se pierde su historia | Sí: `equivalencias_tickers.py` (38 cambios desde 2010) y `ticker_a_yahoo` |
| Prueba de auditoría | Comparar el retorno igual-ponderado del universo de hoy aplicado al pasado con el del universo *point-in-time*. Si la diferencia es positiva, hay sesgo ([QuantVault](https://quantvault.org/problem-2090-survivorship-bias-in-backtesting.html)) | Pendiente (plan, tarea A9): medirlo con el subconjunto núcleo frente al universo histórico |
| Declararlo | Si no se puede eliminar, decirlo en los resultados ([Learning TA](https://learning-ta.pages.dev/learn/backtesting-pitfalls)) | Sí: limitación en el memo |

**Decisión para el proyecto.**
- El universo de cada mes sale de la composición histórica.
- Las acciones que Yahoo ya no tiene se cuentan y se reportan.
- El MVP de 10 acciones puede usar el subconjunto núcleo (193 acciones), declarando que esa elección tiene sesgo.
- La prueba de auditoría cuantifica cuánto sesgo introduce.

## 2. Detección de valores faltantes

En precios diarios, un faltante solo cuenta como tal si el mercado abrió ese día. Un fin de semana o un feriado no son faltantes. Las causas típicas de un faltante real son días sin negociación, iliquidez, huecos de recolección y errores de manejo de datos ([arXiv 2506.01696](https://arxiv.org/pdf/2506.01696)).

Reglas aplicadas en `fechas_y_faltantes.py`:
1. **Calendario NYSE** con `pandas_market_calendars`, como prometió el PSet 1.
2. **Ventana de vida de la acción.** Solo cuentan los días entre su primera y su última cotización. Antes de salir a bolsa o después de deslistarse no hay faltantes.
3. **Valor válido:** cierre ajustado presente y mayor que 0.
4. **Huecos.** Se registran los días seguidos que faltan (`huecos_accion`) y su largo, para separar huecos aislados de tramos largos (suspensiones, cambios de símbolo mal mapeados).
5. **Fechas fuera de calendario.** Se cuentan las filas que caen en días en que la NYSE no abrió (`filas_fuera_de_calendario`). Son errores de validez.

## 3. Técnicas de imputación

| Método | Idea | Ventaja | Riesgo |
|---|---|---|---|
| LOCF / forward-fill | Repetir el último precio observado ([arXiv 2506.01696](https://arxiv.org/pdf/2506.01696)) | No usa el futuro; es común para precios ([Codefinity](https://codefinity.com/es/courses/v2/59da5c05-2ccc-4f73-a859-3112461b9841/44559fbf-074f-4e66-8300-4a60a34b1c9f/02a5cace-9b87-4c00-b3d3-7fcab1ad4fe0)) | Crea retornos cero y después un salto, lo que baja la volatilidad estimada |
| Interpolación lineal del precio | Equivale a repartir el retorno en partes iguales ([arXiv 2506.01696](https://arxiv.org/pdf/2506.01696)) | Robusta en huecos cortos y largos en un caso con AAPL ([Erdős Institute](https://erdosinstitute.org/_files/ugd/eda2b9_479d0ca1ce454cf3950447646f2e832a.pdf)) | Usa el valor posterior: solo sirve para limpiar el histórico |
| Suavizado de Kalman (espacio de estados) | Modelo estructural o ARIMA en espacio de estados, con suavizador ([imputeTS](https://journal.r-project.org/articles/RJ-2017-009)) | Rinde mejor con muchos faltantes ([Yenilmez](https://dergipark.org.tr/en/download/article-cite-file/1657888/type/2)) | Usa el futuro; más costoso |
| MICE con rezagos | Imputación múltiple con variables rezagadas ([arXiv 2506.01696](https://arxiv.org/pdf/2506.01696)) | Aprovecha otras series | Complejo; mucho para el MVP |
| Imputación por modelo (imputeFin) | Muestrea los faltantes de la distribución estimada; permite imputación múltiple ([arXiv 2506.01696](https://arxiv.org/pdf/2506.01696)) | Respeta la dinámica de los retornos | Paquete en R |
| Regresión con acciones correlacionadas | Usar el movimiento de otra acción muy correlacionada ([Erdős Institute](https://erdosinstitute.org/_files/ugd/eda2b9_479d0ca1ce454cf3950447646f2e832a.pdf)) | Usa información del mismo día | Requiere elegir pares |

**Los tres métodos que usa el proyecto** (`fechas_y_faltantes.py`, columnas `*_lineal`, `*_lineal_ruido` y `*_kalman` de `precios_imputados`, para el cierre ajustado y para la apertura ajustada):

1. **Lineal:** interpolación lineal del log-precio. Reparte el retorno del hueco en partes iguales.
2. **Lineal más desvío aleatorio:** la misma recta más un puente browniano, un camino aleatorio que vale cero en los dos extremos del hueco. Usa la volatilidad diaria de la acción, estimada con la MAD para que un salto aislado no la infle. Así se recupera la variabilidad que la recta aplana, sin mover los precios observados antes y después.
3. **Kalman:** suavizador de un modelo de nivel local (caminata aleatoria más ruido) en espacio de estados.

Los tres usan el precio posterior al hueco, así que sirven para limpiar el histórico, no para decidir en tiempo real. Solo se imputan huecos de hasta 5 días hábiles; los tramos más largos se excluyen (`excluir_tramo`).

**Evaluación** (`evaluacion_imputacion` y `evaluacion_imputacion_resumen`). Se borran al azar 10 huecos de 1, 3 y 5 días en series completas y se miden dos cosas:
- el RMSE del log-precio;
- el cociente entre la volatilidad de los retornos imputados alrededor del hueco y la real (1 = la conserva).

Prueba local con 16 series reales de un espejo de Yahoo (no son los datos del proyecto), cierre ajustado:

| Hueco | Lineal RMSE / vol. | Lineal + ruido RMSE / vol. | Kalman RMSE / vol. |
|---|---|---|---|
| 1 día | 0,0216 / 0,66 | 0,0223 / 0,73 | 0,0216 / 0,66 |
| 3 días | 0,0281 / 0,45 | 0,0340 / 0,76 | 0,0281 / 0,45 |
| 5 días | 0,0380 / 0,36 | 0,0450 / 0,69 | 0,0380 / 0,36 |

En la apertura ajustada el patrón es el mismo. Lineal y Kalman dan el menor error pero aplanan la volatilidad: con 5 días, la de los retornos imputados queda en un 36 % de la real. El método con ruido tiene más error puntual pero conserva cerca del 70 %. Esto coincide con el resultado de que la interpolación lineal es robusta ([Erdős Institute](https://erdosinstitute.org/_files/ugd/eda2b9_479d0ca1ce454cf3950447646f2e832a.pdf)), y con que un relleno con ruido de la distribución estimada reproduce mejor la dinámica ([arXiv 2506.01696](https://arxiv.org/pdf/2506.01696)).

**Decisión propuesta** (se confirma con los datos reales):
- **Para variables de nivel o tendencia** (precio, momentum): lineal o Kalman, porque tienen el menor error.
- **Para variables de riesgo** (volatilidad, que define los pesos del portafolio): lineal más ruido, porque no subestima la volatilidad.
- **Robustez:** las tres versiones quedan guardadas para correr el análisis con cada una (por ejemplo, `series_y_arima.py --imputacion lineal_ruido`).

## 4. Series de precios que se analizan

Todas en logaritmos (`series_y_arima.py`, tabla `series_diarias`):

| Serie | Definición | ¿Estacionaria? (prueba local) | Uso |
|---|---|---|---|
| `nivel_cierre` | log del cierre ajustado | No (ADF p ≈ 0,54) | Solo con d = 1, que equivale a `dif_cierre` |
| `nivel_apertura` | log de la apertura ajustada (apertura × cierre ajustado ÷ cierre) | No | Igual que la anterior |
| `dif_cierre` | retorno log de cierre a cierre | Sí | Base del objetivo mensual |
| `dif_apertura` | retorno log de apertura a apertura | Sí | Variable (volatilidad de la apertura) |
| `intradia` | log(cierre ÷ apertura): ganancia o pérdida dentro del día | Sí | Variable; no sirve como objetivo, porque el asesor no opera intradía |
| `nocturno` | log(apertura de hoy ÷ cierre de ayer) | Sí, en el 75 % de las acciones | Variable; `dif_cierre` = `nocturno` + `intradia` |
| `dif_cierre_usd` | diferencia del cierre ajustado en dólares | Sí, pero su varianza crece con el precio | Solo para comparar; se prefiere el log |

La apertura de Yahoo no viene ajustada por splits ni dividendos (con `auto_adjust=False`). Por eso se ajusta con el mismo factor del cierre antes de compararla.

## 5. Normas con que se compara la calidad de las acciones y de los modelos

| Nivel | Norma | Tabla |
|---|---|---|
| Datos | % de días faltantes contra el calendario NYSE, hueco más largo, huecos de más de 5 días, filas fuera de calendario | `fechas_accion`, `huecos_accion` |
| Datos | Cobertura: ¿cubre entrenamiento (desde 2010) y prueba (desde 2024)? ¿Sigue cotizando? | `fechas_accion` |
| Serie | ADF y KPSS (estacionariedad) | `estacionariedad` |
| Ajuste ARIMA | **AIC y BIC** por separado (el BIC castiga más los parámetros y elige modelos más simples), Ljung-Box de los residuos (¿quedan como ruido blanco?), convergencia | `arima_candidatos`, `arima_modelos` |
| Pronóstico mensual | RMSE, MAE, acierto direccional, R² fuera de muestra frente al random walk y Diebold-Mariano (métricas del PSet 1) | `comparacion_modelos`, `comparacion_por_accion` |
| Negocio (siguiente etapa) | Sharpe y drawdown del portafolio frente al S&P 500, al NYSE Composite y a un portafolio aleatorio | Pendiente (PSet 3 o 4) |

El AIC y el BIC sirven para elegir el orden dentro de una misma serie y acción. No sirven para comparar entre acciones ni entre series distintas, porque cada serie tiene su propia escala y su propio número de datos. Entre modelos y acciones se compara con las métricas de pronóstico fuera de muestra.
