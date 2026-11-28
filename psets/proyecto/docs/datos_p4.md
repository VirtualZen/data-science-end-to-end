# Snapshot de PORTAFOLIO_P4 frente al del PSet 3

Fecha: 2026-11-26. Compara la OBT mensual que construyó el pipeline copiado (`pipeline/`, base
`PORTAFOLIO_P4`) con el snapshot con el que se entrenó y registró el champion en el PSet 3.

## Qué snapshot usa cada cosa

| Archivo (en `modelos/data/`, fuera de git) | Tabla de origen | sha256 | Uso |
|---|---|---|---|
| `obt.parquet` + `obt.json` | `PORTAFOLIO_P3.OBT.OBT_ACCION_MES` (2026-11-18) | `c3568917…` | Referencia del entrenamiento: reproduce el champion y sus métricas (46.851 filas de entrenamiento) |
| `obt_p4.parquet` + `obt_p4.json` | `PORTAFOLIO_P4.OBT.OBT_ACCION_MES` (2026-11-27 02:41 UTC) | `e008d6f4…` | Datos del PSet 4: lotes de la API, simulación de producción y monitoreo |

El champion **no se reentrena** con `obt_p4.parquet`. Los dos se leen con `src.datos.cargar(ruta)`, que comprueba el
sha256 del manifiesto. Para regenerar el de P4:

```bash
cd modelos
SNOWFLAKE_DATABASE=PORTAFOLIO_P4 uv run python -m src.datos --salida data/obt_p4.parquet
```

El sha256 cambiará si el pipeline cargó días nuevos.

## Resultado de la comparación

Mismas 87.178 filas, mismas 75 columnas y mismas claves (`accion_key`, `anio_mes`). 75.938 filas tienen al menos un valor
distinto, por tres causas:

| Causa | Columnas | Tamaño | Efecto en el modelo |
|---|---|---|---|
| Yahoo recalcula los precios ajustados en cada descarga | retornos, volatilidades, beta, momentum | ≤ 1,5e-6 en retornos; ≤ 6e-5 en `beta_252d`; ninguna diferencia > 1e-4 | Ninguno (ruido numérico) |
| Dividendos y splits de la semana extra (P4 llega una semana más) | `precio_cierre_ajustado` | Toda la serie de la acción por un factor fijo: SNDK ×0,125; COST ×0,973; AMCR, BBWI, IP, LKQ, PRU, RHI, UPS ×0,985–0,99 | Ninguno: el precio no es feature y los retornos no cambian |
| **GM pasa de NYSE a Nasdaq** | `bolsa`, `es_nyse`, `elegible` | 166 filas de GM (2013-10 a 2026-10) | **GM sale del universo** (ver abajo) |

## Cambio de bolsa de GM

**Qué pasó.** La bolsa de cada acción viene de los listados actuales de Nasdaq Trader (repositorio
`rreichel3/US-Stock-Symbols`, cargado por `extraer_cargar.py` en `RAW.LISTADOS_BOLSA`). `slv_acciones.sql` asigna esa
bolsa a toda la historia de la acción: `es_nyse = (codigo_bolsa = 'N')`. En la carga del PSet 3 (2026-11-18) GM figuraba
en NYSE; en la de P4 (2026-11-26) figura en Nasdaq. Como la bolsa es un dato actual y no histórico, el cambio se aplica a
todos los meses de GM.

**Efecto en los datos.**

| | PSet 3 (`c3568917`) | PSet 4 (`e008d6f4`) |
|---|---|---|
| Filas elegibles de GM | 157 (123 entrenamiento, 34 prueba) | 0 |
| Filas elegibles en entrenamiento (OBT) | 47.258 | 47.135 |
| Filas de entrenamiento del modelo (`preparar` + `dividir`) | 46.851 (122 de GM) | 46.729 |
| Filas de prueba del modelo (hold-out 2024-01 a 2026-10) | 11.326 (34 de GM) | 11.292 |

**Por qué no se corrige.** La regla del PSet 1 es el universo S&P 500 ∩ NYSE. Una acción que deja de cotizar en NYSE
deja de ser candidata, y eso es lo que haría el sistema en producción. Reasignar la bolsa a mano cambiaría la regla
del PSet 1, que está cerrado.

**Limitación conocida.** Usar la bolsa actual para toda la historia introduce un sesgo de supervivencia en la
definición del universo: en el pasado GM sí cotizaba en NYSE. El PSet 2 ya documentó esta limitación para las acciones
sin bolsa conocida (`acciones_sin_bolsa_pct` en `dq_metricas.sql`). Corregirla requiere un historial de listados, que
la fuente no publica.

**Qué hace el PSet 4 con esto.**

- El champion sigue entrenado con el snapshot del PSet 3. Sus métricas registradas se reproducen con `obt.parquet`.
- Desde ahora, la API y la simulación de producción no proponen GM, porque leen `obt_p4.parquet` o `PORTAFOLIO_P4`.
- Es un caso real de **cambio de universo** para el monitoreo (plan.txt, sección 6). La comparación de cargas debe
  alertar cuando una acción cambia de bolsa o de elegibilidad entre dos cargas, además de vigilar la cobertura (hallazgo H1).

## Efecto en el champion

El champion (v1, run `f7596a56…`) se cargó con `models:/portafolio-inversiones-modelo@champion` desde el MLflow de
`pset4-modelos`. Se evaluó en el hold-out 2024-01 a 2026-10:

| Datos | Filas | MAE hold-out |
|---|---|---|
| `obt.parquet` (PSet 3) | 11.326 | **0,0673399888** (igual al registrado; `notebooks/06_champion.ipynb`) |
| `obt.parquet` sin las filas de GM, con GM en el cálculo del mes | 11.292 | 0,0673328527 |
| `obt.parquet` sin GM desde el inicio | 11.292 | 0,0678309511 |
| `obt_p4.parquet` | 11.292 | 0,0678309356 |

Los objetivos de P3 y P4 son idénticos, así que el aumento de 0,0005 sale de las predicciones. Quitar GM del mes
cambia las features que se calculan con todas las acciones del mes: el percentil dentro del mes (`RangoTransversal`) y
`dispersion_mes`. Por esos cambios, un árbol del LightGBM puede cruzar un umbral y mover las predicciones de todo el mes.
Pasa en 7 de 34 meses. En 2024-02 el MAE del mes sube de 0,0482 a 0,0588 y en 2024-11 de 0,0933 a 0,1020; la
predicción que más cambia lo hace en 0,021.
P3 sin GM desde el inicio reproduce P4: el MAE difiere en 1,5e-8 y ninguna predicción en más de 1,9e-4, por el ruido de
Yahoo.

**Para el monitoreo:** el modelo es sensible a la composición del universo de cada mes, no solo a las features de cada
acción. Un cambio de universo como el de GM debe verse como deriva de datos, aunque cada fila esté bien.

## Cómo se comparó

Se exportó P4 a un archivo aparte, para no sobrescribir el snapshot del PSet 3. Luego se unieron los dos por
(`accion_key`, `anio_mes`) y se marcó cada valor distinto, con tolerancia relativa 1e-9 para números. Por último se midió
el tamaño de las diferencias: diferencia absoluta, y cociente de precios por acción, que dentro de cada acción tiene una
desviación típica mediana de 1,8e-7, es decir, un factor constante. También se contaron las filas tras
`preparar` y `dividir` de `src/pipeline.py`.
