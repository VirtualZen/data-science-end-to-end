# Presentación de negocio: Portafolio de inversiones

**Autor:** Allan Paul Gómez Ehmig (Banner 00351916)
**Archivo de la presentación:** `PSet1_pitch_Gomez_Ehmig_v2.pptx` / `.pdf` (versión con el feedback, 2026-11-14)

> Contenido de cada lámina de la presentación entregada. La guía del PSet 1 que recibí pedía de 10 a 15 láminas con la secuencia I a VII que sigue; este repositorio pide de 5 a 8. Ante la contradicción se mantiene la versión entregada (ver [`disclaimer.txt`](./disclaimer.txt)). La última columna indica a qué diapositiva de la guía de este repositorio corresponde cada lámina.

| Lámina | Título | Contenido | Diapositiva de la guía del repo |
|---|---|---|---|
| 1 | I. Título | Portafolio de inversiones: una herramienta para que el asesor de inversiones proponga cada mes a su cliente un portafolio de acciones del S&P 500 listadas en la NYSE, con la mayor rentabilidad esperada dentro de la volatilidad que el cliente tolera. Motivación: 79% de los fondos activos no le ganó al S&P 500 en 2025 y el inversionista promedio pierde 1,2 puntos al año por decidir en mal momento | 1. Título |
| 2 | II. Problema y oportunidad (1) | Qué ocurre hoy (el portafolio se arma y se cambia por intuición o noticias), a quién afecta (al inversionista y al asesor que le propone el portafolio) y qué decisión se toma (qué comprar, en qué proporción y cuándo cambiarlo) | 2. Problema y oportunidad |
| 3 | II. Problema y oportunidad (2) | 79% (SPIVA) y 1,2 pp (Morningstar), con el gráfico del retorno del inversionista (8,7%) frente al de sus fondos (9,9%). Las reglas fijas (rebalanceo solo una vez al mes, tope de volatilidad acordado y umbral mínimo de cambio) reemplazan las compras y ventas impulsivas | 2. Problema y oportunidad |
| 4 | III. Solución propuesta | Qué se construye: módulo de datos, pronóstico del retorno a 1 mes, armado del portafolio (10 acciones con pesos inversos a su volatilidad, dentro del tope) y backtest con monitoreo. Cómo opera cada mes: precios y pronósticos en fecha fija, la herramienta propone, el asesor revisa y pide la aprobación del inversionista, se ejecuta en el bróker y se mide frente a los índices | 3. Solución propuesta |
| 5 | IV. Viabilidad: técnica y de negocio (1) | Datos públicos y confirmados (yfinance; alternativas Stooq, FINSABER y Kaggle), validación contra el random walk y un portafolio aleatorio, despliegue en contenedor (infraestructura local y de la USFQ), y la partición: entrenamiento hasta dic-2023, prueba desde ene-2024 | 4. Evidencia de viabilidad |
| 6 | IV. Viabilidad: técnica y de negocio (2) | Diagrama de carriles (inversionista, asesor, herramienta) con los 6 pasos del proceso mensual. El criterio humano interviene dos veces: el asesor revisa y el inversionista aprueba | 4. Evidencia de viabilidad |
| 7 | IV. Viabilidad: técnica y de negocio (3) | Justificación económica sobre una cartera de US$ 100.000: US$ 1.200 al año de brecha conductual, US$ 1.500 al año de la meta de Sharpe + 0,1, US$ 30 al año del fondo indexado. Condición de valor: la mejora neta de costos debe superar al fondo indexado | 4. Evidencia de viabilidad |
| 8 | V. Riesgos (1) | Riesgos técnicos más relevantes, de mayor a menor severidad: no superar al random walk (Alta), registros incompletos (Media), sesgo de supervivencia (Media) | 5. Riesgos principales |
| 9 | V. Riesgos (2) | Riesgos de negocio más relevantes: un fondo indexado barato es más atractivo (Alta), el inversionista no sigue las recomendaciones (Media), los costos de transacción anulan la ganancia (Media) | 5. Riesgos principales |
| 10 | VI. Qué se necesita para avanzar (1) | Investigación de fuentes: datasets con datos de Yahoo que evitan el screen scraping o `yfinance`, con su cobertura de 2024 en adelante y su estado de verificación | 6. Qué se necesita para avanzar |
| 11 | VI. Qué se necesita para avanzar (2) | Qué necesito del patrocinador. Aprobación: alcance del MVP, criterio de éxito y corte de datos. Información: entrevista con un asesor, perfiles de riesgo típicos y comisiones reales. Recursos: contenedor en la infraestructura de IA de la USFQ y horas de GPU | 6. Qué se necesita para avanzar |
| 12 | VI. Qué se necesita para avanzar (3) | MVP del semestre (propuesta mensual de 10 acciones con pesos), fuera de alcance y un entregable verificable por etapa | 6. Qué se necesita para avanzar |
| 13 | VII. Anexos (1) | Por qué esta idea: matriz de las tres ideas; empate 15 a 15 con crédito, desempate por acceso a datos reales | 7-8. Apoyo adicional |
| 14 | VII. Anexos (2) | Formulación de ciencia de datos y modelos a comparar, en una sola lámina | 7-8. Apoyo adicional |
| 15 | VII. Anexos (3) | Referencias | 7-8. Apoyo adicional |

El pie de cada lámina dice: «Allan Paul Gomez Ehmig - 00351916 - 2026.10.26 (rev. 2026.11.14) · Sales pitch: Portafolio de inversiones». La versión con el feedback trae, además, dos láminas de «Anexo de revisión» con el registro de cambios, que no forman parte de las 15 láminas de la entrega.

**Consistencia con la propuesta.** Los datos, la predicción (retorno a 1 mes), el umbral (10 acciones con pesos inversos a su volatilidad dentro del tope), la métrica (Sharpe y drawdown) y los riesgos son los mismos de [`plantilla-documento-propuesta.md`](./plantilla-documento-propuesta.md) y del Canvas en [`README.md`](./README.md).
