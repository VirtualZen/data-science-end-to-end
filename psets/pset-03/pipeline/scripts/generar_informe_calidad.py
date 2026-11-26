"""Renderiza el diagnóstico ya consultado; no modifica datos ni consulta Snowflake."""
import csv,json
from collections import defaultdict
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'docs/calidad'
def read(name):return list(csv.DictReader((D/(name+'.csv')).open()))
def esc(x):return str(x).replace('|','/').replace('\n',' ')
def num(v):return 'No evaluado' if v in ('',None) else f'{float(v):,.6f}'.rstrip('0').rstrip('.')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(esc(x) for x in row)+' |' for row in rows])
profiles=read('perfil_columnas');inventory=read('inventario_columnas');policies=read('decisiones_por_columna');tables=read('perfil_tablas');issues=read('problemas_raw');meta=json.loads((D/'ejecucion.json').read_text())
by={(r['tabla'],r['columna']):r for r in profiles}
raw=[r for r in profiles if r['tabla'].startswith('RAW.')]
lines=['# Calidad y limpieza por tabla y columna — PSet 2',
'Diagnóstico ejecutado: '+meta['fin_utc']+'. Base: `'+meta['base']+'`. '+str(meta['tablas'])+' tablas y '+str(meta['columnas'])+' columnas. Las consultas exactas e identificadores Snowflake están en [consultas.sql](consultas.sql) y [consultas.json](consultas.json).',
'## Alcance y denominadores',
'''El diagnóstico principal consulta las cuatro tablas **RAW, antes de la limpieza dbt**. No utiliza los valores corregidos de Silver/Gold como sustitutos de la calidad de entrada. RAW ya contiene extracción y tipado de ingesta; no permite medir filas que el proveedor nunca devolvió ni errores descartados antes de llegar a Snowflake. El script no limpia ni escribe en Snowflake.

Los perfiles Bronze/Silver/Gold/OBT son una revisión **posterior**, presentada por separado. El calendario NYSE es una referencia para detectar sesiones ausentes. Para retornos y huecos se usa una selección diagnóstica de la última fila RAW por símbolo-fecha, sin persistirla; evita tratar reingestas como días sucesivos.

Faltantes = (nulos + cadenas vacías/solo espacios) / filas de la tabla. Inválidos y contradicciones se calculan sobre las mismas filas; los nulos se cuentan aparte. Cada problema temporal tiene su propio denominador explícito. No se suman porcentajes de reglas que pueden solaparse. `No evaluado` no significa 0% ni que el dato sea correcto. Timestamps INGESTA_TS se comparan en UTC.

La precisión se evalúa con coherencia OHLC, saltos de retorno e IQR; **no se ha contrastado exactitud de precios con una fuente oficial independiente**. Una anomalía estadística no equivale a un valor inválido.''',
'## Hallazgos y decisiones principales']
problemrows=[]
for c in ['ES_ETF','ES_PRUEBA']:
 r=by[('RAW.LISTADOS_BOLSA',c)];problemrows.append([f'{c} no disponible',f"{r['nulos']}/{r['filas']} nulos ({num(r['faltantes_pct'])}%)",'Mantener NULL en Bronze; corregido y ejecutado con dbt.','El JSON no aporta el indicador; desconocido no es false.'])
for c in ['OPEN','CLOSE','VOLUME']:
 r=by[('RAW.PRECIOS_DIARIOS',c)];label='invalidos' if c=='OPEN' else ('inconsistentes' if c=='CLOSE' else 'anomalos');problemrows.append([f'{c}: {label}',f"{r[label]}/{r['filas']} ({num(r[label+'_pct'])}%)",'Silver descarta OHLC inválido; marca cierre fuera de rango/volumen cero. No imputar volumen.','OHLC válido es necesario para log-precios; cierre fuera del rango puede requerir revisión del proveedor. Volumen cero puede ser legítimo en índices/tasa.'])
r=by[('RAW.LISTADOS_BOLSA','SIMBOLO')];problemrows.append(['Espacios en símbolos',f"{r['inconsistentes']}/{r['filas']} ({num(r['inconsistentes_pct'])}%)",'TRIM/UPPER y normalización de separadores en dbt.','Evitar pérdidas de joins por formato.'])
r=next(r for r in tables if r['tabla']=='RAW.PRECIOS_DIARIOS');problemrows.append(['Reingestas de precios',f"{r['filas_redundantes']}/{r['filas']} filas redundantes ({num(r['redundantes_pct'])}%)",'Conservar RAW; Bronze elige última ingesta/lote.','Append-only preserva auditoría; duplicado crudo no significa hecho duplicado.'])
for r in issues:problemrows.append([r['problema'],f"{r['afectados']}/{r['denominador']} ({num(r['porcentaje'])}%)",r['accion'],r['justificacion']])
lines.append(table(['Problema','Evidencia','Acción','Justificación'],problemrows))
lines += ['''Las diferencias de cierre ajustado se midieron tanto por igualdad exacta como con tolerancia relativa de 0,01%. No se deben presentar diferencias pequeñas como revisiones económicas confirmadas. Los saltos RAW incluyen intervalos sobre huecos; no son directamente comparables con los retornos diarios extremos de Silver.

El porcentaje de fotos incompletas de RAW usa longitud de la lista original. La métrica de CALIDAD sobre Bronze cuenta símbolos normalizados y deduplicados: por eso puede diferir. La ausencia de sesiones dentro de la vida observada tampoco equivale a días sin precio durante membresía: los universos y denominadores son distintos.''',
'## Perfil de entrada por columna',
'Porcentajes sobre todas las filas de cada tabla RAW. Las reglas exactas y conteos se conservan en [perfil_columnas.csv](perfil_columnas.csv). El cero en precios observados no descarta sesiones ausentes ni empresas sin cobertura.']
for t in [r['tabla'] for r in tables if r['tabla'].startswith('RAW.')]:
 rows=[r for r in raw if r['tabla']==t]
 lines += ['### '+t,table(['Columna','Faltantes %','Inválidos %','Inconsistentes %','Anómalos %'],[[r['columna'],num(r['faltantes_pct']),num(r['invalidos_pct']),num(r['inconsistentes_pct']),num(r['anomalos_pct'])] for r in rows])]
lines += ['''`DETALLE` vacío con estado OK es esperado, no pérdida del precio. `ES_ETF`/`ES_PRUEBA` nulos son ausencia estructural del proveedor. Los tipos ya son los declarados en Snowflake: no se puede estimar aquí una tasa de fallo de parseo anterior a RAW.

Los perfiles temporales por año y segmento (acción/índice/tasa) están en [perfil_raw_por_anio.csv](perfil_raw_por_anio.csv); permiten separar volumen cero en referentes del volumen de acciones. Los precios no se mezclan entre símbolos para evaluar IQR: se calculan retornos por acción, con al menos 20 retornos.''',
'## Políticas de limpieza por columna RAW',
'Estas reglas se aplican en dbt para staging/Bronze y su continuación Silver. El diagnóstico Python solo mide. La política se repite explícitamente por columna para que ningún campo quede sin decisión.']
for t in [r['tabla'] for r in tables if r['tabla'].startswith('RAW.')]:
 rows=[r for r in policies if r['tabla']==t]
 lines += ['### '+t,table(['Columna','Acción implementada','Justificación / límite','Código'],[[r['columna'],r['accion_implementada'],r['justificacion_y_limite'],r['codigo']] for r in rows])]
lines += ['## Staging en dbt y tratamientos posteriores',
'''- `brz_precios_diarios.sql`: tipos, identidad, nombres normalizados, descarte de claves nulas y última versión por símbolo-fecha. No calcula medias globales ni reemplaza precios.
- `brz_composicion_sp500.sql`: última carga, explosión de TICKERS, normalización y equivalencias temporales, con conservación del símbolo original y deduplicación.
- `brz_listados_bolsa.sql`: última carga, normalización, exclusión de instrumentos fuera del alcance, deduplicación y conversión Y/N; los flags desconocidos permanecen NULL. Se corrigió la imputación implícita anterior a false.
- Silver: grilla NYSE, exclusión de observaciones inválidas de acciones, forward-fill de log-cierre/log-apertura ajustados para huecos internos de hasta cinco sesiones; no se imputan máximos, mínimos, OHLC original ni volumen. Los huecos mayores se excluyen y no se calcula un retorno que los atraviese.
- Mercado Silver: ^IRX se rellena hacia adelante con el último valor; las series ^GSPC/^NYA no se interpolan. ^IRX es una tasa: no aplicar indiscriminadamente la regla precio > 0.
- Membresía Silver: une huecos de hasta siete días naturales; requiere revisión externa porque es una hipótesis de omisión, no identidad histórica certificada.
- Gold/OBT: derivan claves, medidas, ventanas y flags; no sustituyen el saneamiento de staging. Los objetivos futuros no se imputan. La imputación estadística de features para modelos queda en PSet 3, dentro de entrenamiento.

El forward-fill no usa precios posteriores (criterio del PSet 1); solo el largo del hueco, que decide imputar o excluir, mira el siguiente día observado. Antes (hasta el 15-nov-2026) se interpolaba linealmente con el vecino posterior; el snapshot registraba 0% de días imputados, así que el cambio no altera las cifras. Los outliers se diagnostican con z-score robusto (MAD > 3,5) y 1,5 IQR por acción; outliers_mad_top.csv y outliers_mad_por_fecha.csv permiten cotejarlos con eventos reales.''',
'## Fuentes adicionales y repositorios',
table(['Fuente','Uso real','Repositorio / archivo','Límite'],[
 ['Yahoo Finance / yfinance','OHLCV ajustado y no ajustado, ^GSPC, ^NYA, ^IRX','https://github.com/ranaroussi/yfinance','API no oficial; ajustes retrospectivos y cobertura incompleta'],
 ['Composición histórica S&P 500','Miembros por foto; permite incluir empresas que salieron','https://github.com/chinobing/historical_sp500_constituents — sp_500_historical_components.csv','Fotos incompletas y fuentes cambiantes; no acredita historia oficial'],
 ['Listados actuales de bolsa','Símbolo y nombre; código N/Q/A asignado por carpeta de origen','https://github.com/rreichel3/US-Stock-Symbols — nyse/nyse_full_tickers.json, nasdaq/nasdaq_full_tickers.json, amex/amex_full_tickers.json','No aporta bolsa histórica ni indicadores ETF/prueba en el extractor usado'],
 ['Calendario NYSE','Sesiones y medias jornadas; denominador de huecos','https://github.com/rsheftel/pandas_market_calendars — scripts/generar_calendario_nyse.py → dbt/seeds/calendario_nyse.csv','Referencia de calendario, no proveedor de precios'],
 ['Equivalencias de ticker','Cambio de símbolo con fecha de validez y estado','dbt/seeds/equivalencias_tickers.csv; copia en kestra/scripts/','Referencia local, no repositorio externo independiente ni validación universal; estados verificado/detectado/manual']]),
'## Inventario: datos de origen y columnas del proceso',
'Inventario completo: [inventario_columnas.csv](inventario_columnas.csv). `origen` identifica campos externos; `creada_ingesta` metadatos/bitácora o indicadores ausentes del JSON; `origen_transformado` y `heredada_o_normalizada` conservan información previa; `creada_dbt`/`creada_spark` identifican derivados; `referencia_seed` son datos auxiliares. La clasificación es funcional, no un linaje SQL automático exhaustivo de cada expresión.',
table(['Tabla','Filas','Columnas','Clave','Redundantes %'],[[r['tabla'],r['filas'],r['columnas'],r['clave'],num(r['redundantes_pct'])] for r in tables])]
for t in [r['tabla'] for r in tables]:
 rows=[r for r in inventory if r['tabla']==t]
 lines += ['### '+t,table(['Columna','Tipo','Origen/creación','Faltantes %'],[[r['columna'],r['tipo'],r['clase'],num(by[(t,r['columna'])]['faltantes_pct'])] for r in rows])]
lines += ['## Decisiones y límites para todas las columnas derivadas',
'La lista completa por cada columna, incluidas las derivadas, está en [decisiones_por_columna.csv](decisiones_por_columna.csv). El perfil de cada una contiene métricas y reglas explícitas de completitud, validez, consistencia y anomalías, o indica No evaluado cuando no existe una regla defendible. No se presenta ausencia de una regla como aprobación de calidad.',
'''Nulos esperados: fecha_fin de membresía vigente; fechas de precios de símbolos sin cobertura; retornos iniciales; objetivos sin mes siguiente; campos no observados en días interpolados. No deben rellenarse con cero ni con medias por conveniencia.

La precisión real sigue sin verificarse externamente. El rango, IQR y coherencia pueden detectar sospechas, pero no prueban que un precio sea correcto. La bolsa actual, equivalencias parciales y universo incompleto limitan el uso financiero. Los perfiles no garantizan ausencia de sesgo de supervivencia o fuga temporal.''',
'## Reproducir',
'''Desde psets/pset-03/pipeline, con credenciales locales y el entorno uv (`uv sync`):

```bash
uv run python scripts/diagnosticar_calidad.py
uv run python scripts/generar_informe_calidad.py
```

Para el diagnóstico de entrada únicamente: `python scripts/diagnosticar_calidad.py --solo-raw` (necesita el seed de calendario si se ejecutan controles de sesiones). Las otras capas se excluyen del perfil, sin ejecutar transformaciones. Ejecutar el diagnóstico sobre RAW después de la ingesta y antes del siguiente dbt build; luego dbt produce staging/Bronze y Silver. Los snapshots guardados permiten comparar antes/después sin confundir sus denominadores.''']
(D/'README.md').write_text('\n\n'.join(lines)+'\n')
print('Informe generado:',D/'README.md')
