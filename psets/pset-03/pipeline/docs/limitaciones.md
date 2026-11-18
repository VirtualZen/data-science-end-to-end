# Limitaciones conocidas del pipeline (PSet 3, PORTAFOLIO_P3)

Cada punto tiene su número de hallazgo en `psets/pset-03/plan.txt`. Ninguno impide usar la
OBT, pero todos deben citarse en el EDA o en las limitaciones del memo del PSet 3.

| H | Limitación | Evidencia | Qué se hace |
|---|---|---|---|
| H11 | **Sesgo de supervivencia.** Yahoo no tiene precios de muchas acciones que ya no cotizan. | 160 de 768 símbolos de la composición (20,8 %) sin ningún precio; cobertura del universo con precio: 75,6 % en 2010, 90,6 % en 2020, 99,2 % en 2026 (`corrida/huecos_por_ticker.csv`, `corrida/universo_por_mes.csv`) | Se mide (CALIDAD.DQ_HUECOS_POR_TICKER y DQ_UNIVERSO_POR_FECHA) y se lleva al EDA; prueba de auditoría A9 en el notebook 01 |
| H5 | **Años sin datos por acción.** La carga histórica baja cada año solo a los miembros del índice; una acción que sale y vuelve tiene años vacíos. | 11.331 días excluidos por tramos largos (`dias_excluidos`) | Silver deja nulo el retorno al reanudar (`despues_de_tramo_excluido`); la OBT lo marca en `hubo_tramo_excluido_mes` |
| H6 | **Precios ajustados de Yahoo cambian levemente entre descargas.** | PORTAFOLIO vs PORTAFOLIO_P3: hasta 0,0005 USD en precios y 1,6e-6 en retornos | La OBT no es reproducible bit a bit; la referencia del PSet 3 es el snapshot con sha256 (`data/obt.json`) |
| H7 | **Spark corre con Python 3.8**, no 3.11 como las demás imágenes. | Imagen oficial `apache/spark:3.5.3-python3` | Se mantiene la versión de Spark; el código de `spark/` y sus pruebas son compatibles con 3.8 (pytest 8.3.5) |
| H4 | **Equivalencias de tickers sin fuente formal.** 14 de 38 cambios de la semilla tienen estado `manual`. | Verificados con fuentes públicas el 17-nov: EQR→VMRK (cambio del 18-ago-2026) y PSKY→SKYD (oct-2026). Los demás (PX→LIN, BHGE→BKR, SYMC→GEN, BBT→TFC, ARNC→HWM, CTL→LUMN, COG→CTRA, VIAC/PARA→SKYD, ABC→COR, CDAY→DAY, FLT→CPAY) son cambios de nombre o fusiones públicas conocidas | Documentado; ver H16 para las fusiones |
| H16 | **Fusiones tratadas como cambio de símbolo.** Cuando una empresa es absorbida, la serie del símbolo nuevo puede ser la de la otra empresa. | EQR→VMRK: VMRK tiene precios desde 2010 y se usan para toda la membresía de EQR, mientras AVB (la otra parte de la fusión) queda con 1 día con precio. BMS→AMCR: los años de Bemis (2010-2014) toman precios de Amcor (AMCR con 19 % de huecos) | Decisión (17-nov): se mantienen y se documentan aquí; el EDA y el memo lo citan como limitación |
| H15 | **Sesión en curso.** Una ingesta manual con la bolsa abierta guardaba el precio del momento. | 17-nov: ~470 símbolos con la fila del día revisada | Corregido: `extraer_cargar.py` no guarda la sesión de hoy antes de las 16:30 de Nueva York |
| — | **Composición histórica incompleta en algunas fechas.** | Prueba `assert_cobertura_sp500_por_dia`: 1.615 casos con menos de 495 miembros (WARN, igual que en el PSet 2) | Se tolera como advertencia; la fuente (chinobing) tiene fotos incompletas |
| — | **Bolsa actual, no histórica.** | 439 de 1.130 acciones con `bolsa_desconocida` | El filtro NYSE del PSet 1 usa la bolsa actual; documentado en el diccionario |
