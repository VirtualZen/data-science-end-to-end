# Propuesta de proyecto: Portafolio de inversiones con volatilidad acotada

**Autor:** Allan Paul Gómez Ehmig (Banner 00351916)
**Fecha:** 2026-10-26, revisada el 2026-11-14 con el feedback del profesor

> Versión en Markdown del memo `PSet1_memo_Gomez_Ehmig_v2` (versión con el feedback). Sigue el orden de las cuatro secciones pedidas en este repositorio; al final se agregan la comparación de ideas y el alcance del semestre, que pedía la guía del PSet 1 que recibí. Ver [`disclaimer.txt`](./disclaimer.txt).

## 1. El problema de negocio y la métrica de éxito

El inversionista minorista arma su portafolio por intuición o por noticias, sin controlar la volatilidad, y suele rendir por debajo del índice. En 2025, el 79% de los fondos activos de grandes empresas de EE. UU. rindió menos que el S&P 500 [8], y en los 10 años hasta diciembre de 2025 el inversionista promedio ganó 8,7% anual frente al 9,9% de sus propios fondos, por comprar y vender en mal momento [13]. El proyecto es una herramienta para el **asesor de inversiones** de una casa de valores o fintech: cada mes le propone un portafolio de acciones del S&P 500 listadas en la NYSE, con la mayor rentabilidad esperada dentro de la volatilidad que su cliente tolera. El asesor revisa la propuesta y pide la aprobación del inversionista.

**Formulación de ciencia de datos.**

| Elemento | Definición |
|---|---|
| Predicción | Retorno esperado de cada acción |
| Unidad de predicción | Acción (ticker) en cada fecha de rebalanceo |
| Target | Retorno logarítmico a 1 mes (21 días hábiles) |
| Horizonte | 1 mes (21 días hábiles), igual al período de rebalanceo mensual: se pronostica exactamente el periodo en que se mantiene el portafolio |
| Métrica técnica | Error de pronóstico (RMSE/MAE) frente al random walk y acierto direccional; prueba Diebold-Mariano [1] |
| Línea base | Random walk (retorno cero) y portafolio aleatorio de igual peso; índices S&P 500 y NYSE Composite (^NYA) [2] |
| Modelos a comparar | A (clásico): ARIMA por acción; random forest o XGBoost con rezagos y volatilidad [3]. B (red / transfer learning): híbrido ARIMA + red (MLP/LSTM) [4]; modelos fundacionales de series de tiempo (Chronos, TimesFM, Moirai) en zero-shot [5]–[7] |
| Umbral de decisión | Se eligen las 10 acciones de mayor retorno predicho cuya volatilidad no supere la máxima tolerable; sus pesos son inversos a su volatilidad. Si la volatilidad del portafolio (covarianza histórica) supera el tope, se reemplaza la acción más volátil por la siguiente de la lista. Solo compras, sin apalancamiento |
| Métrica de éxito (negocio) | Sharpe anualizado, (Rp − Rf)/σp con Rf = letra del Tesoro a 3 meses (^IRX), y drawdown máximo en el periodo de prueba |
| Meta | Sharpe fuera de muestra (desde ene-2024) al menos 0,1 mayor que el del S&P 500 y el del NYSE Composite, y mayor que el del portafolio aleatorio |

**Por qué este umbral y qué error cuesta más.** El tope de volatilidad lo acuerda el asesor con el cliente antes de invertir: el error más caro es proponer un portafolio más riesgoso que lo que el cliente tolera, porque provoca ventas en pánico, justo la pérdida conductual que el proyecto quiere evitar. Por eso el filtro de volatilidad va antes que el ranking por retorno.

**Cómo la acción reduce las pérdidas por comportamiento.** El proceso cambia la decisión impulsiva por reglas acordadas de antemano: 1) se rebalancea solo una vez al mes, en fecha fija, no ante noticias; 2) el tope de volatilidad se acuerda con el cliente antes de invertir; 3) solo se opera si el cambio de pesos supera un umbral mínimo; 4) cada cambio lo propone el asesor con la justificación del modelo y lo aprueba el cliente. El valor está en la disciplina del proceso, no solo en la predicción.

## 2. Viabilidad técnica

| Dato | Fuente | Estado |
|---|---|---|
| Precios diarios ajustados de las acciones del universo | Yahoo Finance vía `yfinance` [9] | Existe, acceso confirmado (gratuito; uso personal o educativo según Yahoo) |
| Índices S&P 500 (^GSPC) y NYSE Composite (^NYA) | Yahoo Finance vía `yfinance` [9] | Existe, acceso confirmado |
| Tasa libre de riesgo (^IRX, letra del Tesoro a 3 meses) | Yahoo Finance vía `yfinance` [9] | Existe, acceso confirmado |
| Composición histórica del S&P 500, filtrada a la NYSE | GitHub `hanshof/sp500_constituents` [14] | Existe, acceso confirmado (licencia MIT) |
| Respaldo para entrenamiento | Kaggle: S&P 500 stock data (2013–2018) y New York Stock Exchange (2010–2016) [10], [11] | Existe, acceso confirmado; no cubre el periodo de prueba |
| Alternativas sin `yfinance` | Stooq (descarga masiva en CSV) [15]; FINSABER-data en Hugging Face (2000–2024) [16] | Existen, acceso confirmado |
| Perfil de riesgo del cliente (tope de volatilidad) | Lo registra el asesor | No existe todavía: se define con el asesor; para el MVP se usan topes de ejemplo |

**Partición temporal.** Entrenamiento y validación con datos hasta dic-2023; prueba fuera de muestra desde ene-2024 (fecha de corte sujeta a cambios).

**Limpieza.** 1) Universo de cada fecha según la composición histórica (evita el sesgo de supervivencia). 2) Alinear al calendario NYSE con `pandas_market_calendars` [12]: fines de semana y feriados no son faltantes. 3) Huecos aislados con forward-fill (no usa el futuro) o suavizado de Kalman; tickers con huecos largos se excluyen. 4) Outliers de retorno (MAD/z-score) verificados contra eventos reales. 5) Retornos logarítmicos. No se procesan splits por cuenta propia: Yahoo ya entrega precios ajustados por splits y dividendos.

## 3. Viabilidad de negocio

**Qué decisión cambia.** Hoy el asesor arma o ajusta el portafolio por criterio propio o noticias, sin regla de cuándo cambiarlo. Con la herramienta, el asesor recibe cada mes una propuesta de portafolio (acciones y pesos) dentro del tope de volatilidad del cliente.

**Quién decide y cuándo interviene el criterio humano.** El asesor usa la herramienta cada mes y pide la aprobación del inversionista. El criterio humano interviene dos veces: el asesor revisa la propuesta y el inversionista la aprueba o la rechaza. El sistema nunca ejecuta órdenes por su cuenta.

| Paso | Hoy | Con la herramienta |
|---|---|---|
| 1. Perfil del cliente | El asesor define el perfil de riesgo de forma cualitativa | El perfil se traduce en un tope de volatilidad anual acordado y registrado |
| 2. Selección | El asesor o el cliente eligen acciones por criterio propio o por noticias | La herramienta propone 10 acciones y sus pesos dentro del tope |
| 3. Revisión | No hay regla de cuándo cambiar el portafolio | Cada mes, en fecha fija, el asesor revisa la propuesta y los cambios frente al mes anterior |
| 4. Aprobación | El cliente aprueba compras puntuales, a veces por impulso | El asesor pide la aprobación con un resumen: retorno esperado, volatilidad y cambios |
| 5. Ejecución y reporte | Se ejecuta en el bróker; seguimiento informal | Se ejecuta en el bróker; reporte mensual de Sharpe y drawdown frente a los índices |

**Cómo se mide el resultado.** Con el Sharpe anualizado y el drawdown máximo del portafolio en el periodo de prueba, frente al S&P 500, al NYSE Composite y a un portafolio aleatorio, con comisiones y spread incluidos en el backtest. Como referencia económica sobre una cartera de US$ 100.000: la brecha conductual de 1,2 puntos equivale a unos US$ 1.200 al año [13]; la meta de Sharpe + 0,1 con la volatilidad del índice (≈15% anual) equivale a unos US$ 1.500 al año; un fondo indexado del S&P 500 cuesta 0,03% al año, unos US$ 30 [17]. La herramienta solo vale si su mejora neta de costos supera esa alternativa pasiva.

## 4. Riesgos principales

Los seis riesgos más relevantes, de mayor a menor severidad (la numeración es la del registro completo de riesgos del proyecto).

| N.º | Tipo | Supuesto que rompe | Cómo se verifica | Severidad | Respuesta si ocurre |
|---|---|---|---|---|---|
| 4 | Técnico | Que los retornos a 1 mes sean predecibles: el modelo puede no superar al random walk fuera de muestra | Validación en ventanas móviles hasta dic-2023, prueba desde ene-2024 y prueba Diebold-Mariano | Alta | Reformular el objetivo hacia gestión de riesgo (control de volatilidad) |
| 8 | Negocio | Que el usuario prefiera el portafolio a un fondo indexado barato: la mayoría de fondos activos rinde menos que el S&P 500 [8] | Comparar el Sharpe del portafolio con el de un fondo indexado del S&P 500 en el mismo periodo | Alta | Recomendar el índice cuando el modelo no aporte mejora |
| 2 | Técnico | Que los registros estén completos: hay huecos y fechas faltantes | Porcentaje de huecos por ticker y su distribución en el tiempo | Media | Forward-fill o Kalman en huecos aislados; excluir tickers con huecos largos |
| 3 | Técnico | Que la fuente traiga el universo completo (sesgo de supervivencia) | Comparar los tickers con la composición histórica del S&P 500 en la NYSE | Media | Construir el universo de cada fecha con la composición histórica |
| 6 | Negocio | Que el inversionista siga las recomendaciones [13] | Simular escenarios en los que sigue o no las recomendaciones | Media | Pocos cambios por rebalanceo y mostrar el costo histórico de no seguirlas |
| 7 | Negocio | Que los costos de transacción sean menores que la ganancia esperada | Incluir comisiones y spread en el backtest y comparar retorno neto con bruto | Media | Rebalancear solo si el cambio de pesos supera un umbral mínimo |

## Comparación de ideas (de la guía del PSet 1 recibida)

Se evaluaron tres ideas con seis criterios (Alto 3, Medio 2, Bajo 1).

| Criterio | Idea 1: Recomendación de productos de crédito | Idea 2: Retención de personal crítico | Idea 3: Portafolio de inversiones |
|---|---|---|---|
| Valor de negocio | Alto (3) | Alto (3) | Medio (2) |
| Acceso a datos | Medio (2) | Bajo (1) | Alto (3) |
| Target | Alto (3) | Medio (2) | Medio (2) |
| Acción | Alto (3) | Medio (2) | Alto (3) |
| Evaluación | Medio (2) | Medio (2) | Alto (3) |
| Alcance | Medio (2) | Medio (2) | Medio (2) |
| **Total** | **15** | **12** | **15** |

**Decisión: idea 3.** Su target es Medio porque el retorno se observa pero es casi impredecible (riesgo 4), y con eso empata con la idea 1. Se desempata por acceso a datos: la idea 3 usa precios públicos reales, mientras que la idea 1 debe simular endeudamiento, mora y respuesta a campaña. La evaluación es Alta porque es clara aunque el resultado sea negativo: si el modelo no supera al random walk, el backtest y la prueba lo muestran.

## Alcance del semestre (MVP)

**Producto.** Una propuesta de portafolio mensual para el asesor: 10 acciones con su peso (inverso a su volatilidad), la volatilidad esperada del portafolio dentro del tope del cliente y los cambios frente al mes anterior. El código se despliega en un contenedor en la infraestructura local y en la de la USFQ.

**Fuera de alcance.** Ejecución automática de órdenes; derivados; acciones fuera del S&P 500 o que no coticen en la NYSE; procesamiento propio de splits; optimización media-varianza o por aversión al riesgo; ventas en corto y apalancamiento.

| Etapa | Entregable | Cómo se verifica |
|---|---|---|
| Datos | Dataset limpio acción-fecha, diccionario de datos y notebook de descarga y limpieza | Porcentaje de huecos por ticker; universo de cada fecha comparado con la composición histórica |
| Exploración / features | Notebook de exploración y tabla de features: retornos rezagados, volatilidad y momentum | Ninguna feature usa información posterior a la fecha de rebalanceo |
| Modelo | Notebook que compara los modelos A y B con las líneas base, con validación hasta dic-2023 | Tabla de RMSE/MAE, acierto direccional y prueba Diebold-Mariano |
| Despliegue | Contenedor que genera la propuesta de portafolio mensual (acciones, pesos y volatilidad) | Una ejecución reproducible produce el archivo de propuesta para una fecha dada |
| Monitoreo | Backtest desde ene-2024 con costos de transacción y reporte de Sharpe y drawdown | Comparación con la meta de Sharpe frente a los índices y al portafolio aleatorio |

## Referencias

1. "Pretrained Time-Series Foundation Models for Financial Return Forecasting," arXiv:2606.27100, 2026. <https://arxiv.org/pdf/2606.27100>
2. Wikipedia, "NYSE Composite." <https://en.wikipedia.org/wiki/NYSE_Composite>
3. statsmodels developers, "statsmodels: Statistical models in Python." <https://www.statsmodels.org>
4. H. K. Choi, "Stock Price Correlation Coefficient Prediction with ARIMA-LSTM Hybrid Model," arXiv:1808.01560, 2018. <https://ar5iv.labs.arxiv.org/html/1808.01560>
5. Amazon Science, "Chronos: Pretrained models for time series forecasting." <https://github.com/amazon-science/chronos-forecasting>
6. Google Research, "TimesFM." <https://github.com/google-research/timesfm>
7. Salesforce AI Research, "uni2ts (Moirai)." <https://github.com/SalesforceAIResearch/uni2ts>
8. S&P Dow Jones Indices, "SPIVA U.S. Year-End 2025." <https://www.spglobal.com/spdji/en/spiva/article/spiva-us-year-end-2025/>
9. R. Aroussi, "yfinance." <https://github.com/ranaroussi/yfinance>
10. camnugent, "S&P 500 stock data," Kaggle. <https://www.kaggle.com/datasets/camnugent/sandp500>
11. dgawlik, "New York Stock Exchange," Kaggle. <https://www.kaggle.com/datasets/dgawlik/nyse>
12. R. Sheftel, "pandas_market_calendars." <https://github.com/rsheftel/pandas_market_calendars>
13. Morningstar, "Mind the Gap." <https://www.morningstar.com/business/insights/research/mind-the-gap?con=15948>
14. hanshof, "sp500_constituents." <https://github.com/hanshof/sp500_constituents>
15. QuantStart, "An Introduction to Stooq Pricing Data." <https://www.quantstart.com/articles/an-introduction-to-stooq-pricing-data>
16. waylonli, "FINSABER-data," Hugging Face. <https://huggingface.co/datasets/waylonli/FINSABER-data>
17. Vanguard, "Vanguard S&P 500 ETF (VOO) fact sheet," sep-2026. <https://workplace.vanguard.com/iippdf/pdfs/FS0968R.pdf>

Todas las URL fueron consultadas entre el 26-oct-2026 y el 14-nov-2026.
