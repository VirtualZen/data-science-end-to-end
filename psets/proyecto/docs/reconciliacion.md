# Reconciliación de producción, simulación y estrategia (auditoría de Codex, H1 y H2)

Cálculo: `scripts/reconciliacion.py` (no escribe en ningún servicio). Salida: `docs/reconciliacion_negocio.csv`.
Insumos: `docs/predicciones.csv` (lo que la API sirvió en Kestra), los objetivos de
`docs/simulacion/predicciones_simulacion.csv`, la tasa libre de riesgo de la OBT y los retornos diarios de
`modelos/data/obt_dia.parquet` para el tope de portafolio.

## 1. Producción frente a simulación (H2)

Uniendo producción y simulación por (`anio_mes`, `accion_key`): **34 de 35 lotes son idénticos** (predicción, peso y
versión equivalente). Difiere **2026-04**: tras el incidente v7 se reprocesó desde 2026-05 y no desde 2026-04 (error de
operación), así que ese lote quedó servido con **v3**, mientras la simulación lo sirve con r5 (= v8). Máxima diferencia
de predicción 0,02337 y de peso 0,117588. La cartera servida rindió **+5,8 %** neto ese mes; la simulada, **−3,7 %**.
Única alerta distinta: **A9 en 2026-09**, presente solo en la simulación.

**Cuál es cuál.** Producción (`docs/predicciones.csv`, `monitoreo.csv`, `alertas.csv`) es la historia observada, con el
incidente incluido; no se reescribe. La simulación (`docs/simulacion/`) es el contrafactual sin el error. Las 5
decisiones de reentrenamiento (v3, v4, v5, v6 y v8) y sus comparaciones coinciden en las dos.

## 2. Una sola definición de la estrategia (H1)

La API decide **la composición y los pesos relativos**: 10 acciones, pesos 1/vol, 100 % en acciones. La regla completa del
PSet 1 añade fuera de la API el **tope de portafolio** (volatilidad estimada ≤ 1,35 veces la del S&P 500, con
covarianzas diarias de 63 días; el resto queda en efectivo) y el **costo de 15 pb** por rotación. El monitoreo (A8, A9,
`MONITOREO`) y la regla de promoción usan el retorno **bruto**, 100 % invertido y sin costos.

Sobre la trayectoria realmente servida (34 lotes etiquetados):

| Definición | Sharpe anual | US$ 100.000 → |
|---|---|---|
| Monitoreo (bruto, 100 % invertido, sin costos) | 0,15 | 116.291 |
| **Estrategia completa** (tope de portafolio + 15 pb) | **−0,06** | **103.925** |
| Simulación (contrafactual, estrategia completa) | −0,23 | 94.825 |

El tope invirtió menos de 100 % en 9 meses (64,7 % en 2026-02; 72,0 % en 2026-06). La rotación media es de ~1,8 por mes,
así que los costos restan ~0,27 puntos al mes. **Consecuencia:** A8 y A9 vigilan un sustituto optimista de la estrategia;
las cifras de negocio del documento son las de la estrategia completa.

**Limitación declarada y mejora futura (opción B):** unificar en código la exposición y los costos en la API (campo
`exposicion`), en `metricas_lote` y en la promoción, con columnas nuevas en `PREDICCIONES` y `MONITOREO`. Antes de
adoptarla hay que recalcular las 5 decisiones de reentrenamiento con la métrica nueva, porque alguna podría cambiar.
Ninguna política de retirada (R1–R6) se ejecutó en la corrida: el interruptor se demostró, pero los resultados son sin
intervención.

## 3. Julio de 2025: empate en el puesto 10 (segunda revisión de Codex)

Además de 2026-04, la estrategia neta difiere de la simulación en **2025-07** (−0,0916 frente a −0,0898). La causa no es
el lote sintético sino un **empate exacto**: siete acciones tienen la misma predicción (0,051744485993390314) en el
límite del top 10 y solo seis entran (el choque inducido lleva muchas acciones a la misma hoja de los árboles). La API,
en producción y en la simulación, guardó **TFC** (peso 0,0994) y dejó fuera a **FITB**.

`src.negocio.backtest` no lee el peso guardado: lo vuelve a calcular con `pesos_mes` (`nlargest`), que desempata por el
orden de las filas. La reconciliación queda con TFC (bruto −0,0886 = monitoreo; neto −0,0916 con rotación 2,0); el
notebook 06, que calcula la serie `sistema` de `resultado_lotes.csv`, queda con FITB (−0,0898). Es el único de los 35
meses con empate en el límite: en los otros 34 el `backtest` reproduce los pesos guardados (diferencia < 1e-6). El efecto
es de 0,18 puntos en un mes y no cambia las conclusiones. Se declara; la corrección (usar el peso guardado o desempatar
de forma estable por `accion_key`) queda como mejora futura.

Comprobación, sin escribir archivos (desde la raíz del repositorio):

```
uv run --no-project --with pandas python - <<'EOF2'
import json,pandas as pd
p=pd.read_csv('psets/pset-04/docs/predicciones.csv',low_memory=False)
p['vol_63d']=[json.loads(e)['vol_63d'] for e in p.entradas]
g=p[p.anio_mes==202507]; c=g[g.vol_63d<=g.vol_63d.quantile(.8)]
top=c.retorno_predicho.nlargest(10); dec=top.iloc[-1]
print('empatados:',(c.retorno_predicho==dec).sum(),'| dentro del top:',(top==dec).sum())
print(g[g.ticker.isin(['TFC','FITB'])][['ticker','retorno_predicho','peso']].to_string())
EOF2
```
