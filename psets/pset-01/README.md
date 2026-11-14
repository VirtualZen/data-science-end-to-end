# PSet 1: Propuesta del proyecto (entrega de Allan Paul Gómez Ehmig)

**Proyecto:** Portafolio de inversiones con volatilidad acotada (idea 3 de tres evaluadas)
**Autor:** Allan Paul Gómez Ehmig (Banner 00351916)
**Fecha:** 2026-10-26, revisada el 2026-11-14 con el feedback del profesor

> Las instrucciones del PSet 1 que recibí en clase son distintas de las de este repositorio. Esta carpeta cubre lo que pide el repositorio, pero cuando hay contradicción se mantiene lo que ya se entregó. El detalle está en [`disclaimer.txt`](./disclaimer.txt). El enunciado original de este README sigue en el repositorio del curso y en el historial de git.

## Qué hay en esta carpeta

| Entregable del repo | Dónde está | Estado |
|---|---|---|
| 1. Canvas de Viabilidad y Riesgos | Sección «Canvas» de este README | Completo, con la versión del feedback |
| 2. Documento de propuesta | [`plantilla-documento-propuesta.md`](./plantilla-documento-propuesta.md) (versión en Markdown del memo `PSet1_memo_Gomez_Ehmig_v2`) | Completo |
| 3. Presentación de negocio | [`plantilla-presentacion-negocio.md`](./plantilla-presentacion-negocio.md) (contenido de cada lámina de `PSet1_pitch_Gomez_Ehmig_v2`) | Completo |
| 4. Ambiente del proyecto (`Dockerfile`, `requirements.txt`, `ingesta/`, `infra/`) | `../proyecto/` | Pendiente: no estaba en la guía recibida; se construye como base del PSet 2 |
| Rúbrica | [`rubrica.md`](./rubrica.md) | Sin cambios (es la del curso) |

Los archivos originales (memo en Word y PDF, Excel de comparación y presentación) no están en el repositorio; están en la carpeta del curso en Google Drive (`PSet01/feedback/`).

## Canvas de Viabilidad y Riesgos (versión final)

Basado en el marco P(S) = P(T) × P(C), el AI Canvas y el método premortem.

### 1. Problema y usuario

El asesor de inversiones arma y cambia el portafolio de sus clientes por intuición o noticias, sin controlar la volatilidad; el inversionista suele rendir por debajo del índice y pierde rentabilidad por comprar y vender en mal momento.

### 2. Viabilidad técnica, parte 1: predicción

El retorno logarítmico a 1 mes (21 días hábiles) de cada acción del S&P 500 listada en la NYSE, en cada fecha de rebalanceo mensual. El horizonte es igual al período de rebalanceo.

### 3. Viabilidad técnica, parte 2: datos

- [x] **Ya existe, acceso confirmado:** precios diarios ajustados, índices ^GSPC y ^NYA y tasa ^IRX en Yahoo Finance vía `yfinance`; composición histórica del S&P 500 en GitHub (`hanshof/sp500_constituents`); respaldo en Kaggle (2010–2018), Stooq y FINSABER-data (2000–2024).
- [ ] **Existe, sin acceso confirmado:** dos datasets de Kaggle actualizados a diario con datos de Yahoo (andrewmvd, tanavbajaj); falta verificar su contenido y licencia.
- [ ] **No existe todavía:** el tope de volatilidad de cada cliente; lo registra el asesor. Para el MVP se usan topes de ejemplo.

### 4. Viabilidad de negocio, parte 1: acción

Hoy el asesor decide qué acciones comprar, en qué proporción y cuándo cambiarlas, por criterio propio o noticias. Con la predicción, cada mes en fecha fija se propone un portafolio de 10 acciones con pesos inversos a su volatilidad, dentro del tope del cliente, y solo se rebalancea si el cambio de pesos supera un umbral mínimo.

### 5. Viabilidad de negocio, parte 2: juicio

El asesor de inversiones (casa de valores o fintech) revisa la propuesta y pide la aprobación del inversionista. El sistema nunca actúa solo: no ejecuta órdenes. El criterio humano interviene dos veces: el asesor revisa y el inversionista aprueba o rechaza.

### 6. Viabilidad de negocio, parte 3: resultado

Sharpe anualizado, (Rp − Rf)/σp con Rf = ^IRX, y drawdown máximo del portafolio en el periodo de prueba (desde ene-2024), con costos de transacción incluidos. Meta: Sharpe al menos 0,1 mayor que el del S&P 500 y el del NYSE Composite, y mayor que el de un portafolio aleatorio.

### 7. Riesgos

**Riesgo 1 (técnico, severidad Alta)**
- Supuesto que rompe: que el retorno a 1 mes sea predecible; el modelo puede no superar al random walk fuera de muestra.
- Evidencia que lo confirmaría o descartaría: validación en ventanas móviles hasta dic-2023, prueba desde ene-2024 y prueba Diebold-Mariano frente al random walk. Un estudio de 2026 con modelos fundacionales encontró mejoras pequeñas y rara vez significativas sobre el random walk.
- Qué tan grave sería: alta; el proyecto se reorientaría a gestión de riesgo (control de volatilidad).

**Riesgo 2 (negocio, severidad Alta)**
- Supuesto que rompe: que el usuario prefiera el portafolio a un fondo indexado barato; en 2025, el 79% de los fondos activos rindió menos que el S&P 500 (SPIVA).
- Evidencia que lo confirmaría o descartaría: comparar el Sharpe del portafolio, neto de costos, con el de un fondo indexado del S&P 500 (gastos de 0,03%) en el mismo periodo.
- Qué tan grave sería: alta; si el modelo no aporta mejora, la recomendación honesta es el índice.

Los riesgos de severidad Media (registros incompletos, sesgo de supervivencia, que el inversionista no siga las recomendaciones y costos de transacción) están en la sección 4 de la propuesta.
