"""Perfil reproducible de RAW (antes de limpiar) e inventario de todas las capas.
Solo SELECT: no modifica ni imputa datos. Guarda SQL exacto, query IDs, tasas y políticas.
Uso: python scripts/diagnosticar_calidad.py [--solo-raw]
Credenciales: SNOWFLAKE_* del entorno o .env ignorado por Git.
"""
from __future__ import annotations
import argparse,base64,csv,json,os,re
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import snowflake.connector
R=Path(__file__).resolve().parents[1]
OUT=R/'docs/calidad';OUT.mkdir(exist_ok=True)
KEYS={'RAW.PRECIOS_DIARIOS':['TICKER','FECHA'],'RAW.COMPOSICION_SP500':['LOTE_ID','FECHA'],'RAW.LISTADOS_BOLSA':['LOTE_ID','SIMBOLO','CODIGO_BOLSA'],'RAW.INGESTA_LOG':['LOTE_ID','TICKER'],
'BRONZE.BRZ_PRECIOS_DIARIOS':['TICKER','FECHA'],'BRONZE.BRZ_COMPOSICION_SP500':['FECHA_FOTO','TICKER'],'BRONZE.BRZ_LISTADOS_BOLSA':['TICKER'],
'BRONZE.CALENDARIO_NYSE':['FECHA'],'BRONZE.EQUIVALENCIAS_TICKERS':['TICKER_ANTIGUO','VALIDO_HASTA'],
'SILVER.SLV_PRECIOS_ACCIONES':['TICKER','FECHA'],'SILVER.SLV_MERCADO_DIARIO':['FECHA'],'SILVER.SLV_CALENDARIO_NYSE':['FECHA'],'SILVER.SLV_MEMBRESIA_SP500':['PERIODO_KEY'],'SILVER.SLV_ACCIONES':['TICKER'],
'GOLD.DIM_MEMBRESIA_SP500':['PERIODO_KEY'],'GOLD.DIM_ACCION':['ACCION_KEY'],'GOLD.DIM_FECHA':['FECHA_KEY'],'GOLD.FCT_PRECIOS_DIARIOS':['ACCION_KEY','FECHA_KEY'],'GOLD.FCT_MERCADO_DIARIO':['FECHA_KEY'],
'OBT.OBT_ACCION_MES':['ACCION_KEY','ANIO_MES'],'OBT.OBT_ACCION_DIA':['ACCION_KEY','FECHA'],'OBT.VALIDACION_OBT':['CONTROL'],'CALIDAD.DQ_METRICAS':['METRICA']}
RAW_SOURCE={'PRECIOS_DIARIOS':{'TICKER','FECHA','OPEN','HIGH','LOW','CLOSE','ADJ_CLOSE','VOLUME'},'COMPOSICION_SP500':{'FECHA','TICKERS'},'LISTADOS_BOLSA':{'SIMBOLO','NOMBRE'}}
ALIASES={'PRECIO_APERTURA':'OPEN','PRECIO_MAXIMO':'HIGH','PRECIO_MINIMO':'LOW','PRECIO_CIERRE':'CLOSE','PRECIO_CIERRE_AJUSTADO':'ADJ_CLOSE','VOLUMEN':'VOLUME','FECHA_FOTO':'FECHA','SIMBOLO_ORIGINAL':'SIMBOLO','TICKER_ORIGINAL':'TICKERS','TICKER_COMPOSICION':'TICKERS'}
BASE={'TICKER','FECHA','NOMBRE','CODIGO_BOLSA','ARCHIVO','LOTE_ID','INGESTA_TS','FUENTE','ES_ETF','ES_PRUEBA'}

def q(x):
 if not re.fullmatch('[A-Z_][A-Z_0-9]*',x):raise ValueError('Identificador inesperado')
 return '"'+x+'"'
def pct(n,d):return round(100*float(n)/d,6) if d else None
def dump(name,rows):
 if not rows:return
 with (OUT/(name+'.csv')).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def lineage(schema,table,col):
 if schema=='RAW':
  if col in RAW_SOURCE.get(table,set()):return 'origen','Yahoo/yfinance' if table=='PRECIOS_DIARIOS' else ('chinobing' if table=='COMPOSICION_SP500' else 'rreichel3')
  return 'creada_ingesta','kestra/scripts/extraer_cargar.py'
 if table in {'CALENDARIO_NYSE','EQUIVALENCIAS_TICKERS'}:return 'referencia_seed','dbt/seeds/'+table.lower()+'.csv'
 if table=='DIM_MEMBRESIA_SP500':return 'heredada_o_normalizada','SILVER.SLV_MEMBRESIA_SP500; publicada en Gold'
 if col in ALIASES:return 'origen_transformado',ALIASES[col]+'; ver SQL de la tabla'
 if col in BASE:return 'heredada_o_normalizada','RAW/tabla anterior; ver SQL'
 return ('creada_spark' if schema=='OBT' else 'creada_dbt'),('spark/jobs/construir_obt.py' if schema=='OBT' else 'dbt/models/'+schema.lower()+'/'+table.lower()+'.sql')

def policy(table,c):
 """Política implementada; no confundir propuestas pendientes con acciones ejecutadas."""
 if c in {'ES_ETF','ES_PRUEBA'}:return ('No disponible en el JSON: RAW nulo; Bronze conserva NULL y solo convierte Y/N conocidos.','No es evidencia de que no sea ETF/prueba; no usar para certificar tipo. Silver admite desconocidos y solo excluye prueba conocida.','dbt/models/bronze/brz_listados_bolsa.sql')
 if c in {'OPEN','HIGH','LOW','CLOSE','ADJ_CLOSE','PRECIO_APERTURA','PRECIO_MAXIMO','PRECIO_MINIMO','PRECIO_CIERRE','PRECIO_CIERRE_AJUSTADO','PRECIO_APERTURA_AJUSTADO'}:
  return ('Bronze tipa/deduplica. Silver excluye observaciones de acciones con OHLC nulo/no positivo o high<low; rellena hacia adelante (forward-fill) solo log-cierre y log-apertura ajustados en huecos internos de hasta 5 sesiones. OHLC originales no se imputan. ^IRX se trata como tasa, no como precio.','No inventar extremos OHLC. Forward-fill marcado, como fija el PSet 1: el valor imputado no usa precios futuros (el largo del hueco sí mira el siguiente día observado para decidir imputar o excluir). Huecos largos se excluyen y retorno posterior queda nulo.','dbt/models/bronze/brz_precios_diarios.sql; dbt/models/silver/slv_precios_acciones.sql')
 if c in {'VOLUME','VOLUMEN','VOLUMEN_PROM_21D','DOLARES_NEGOCIADOS_PROM_21D'}:return ('No imputar ni interpolar volumen; cero se marca en Silver. Negativos se diagnostican; no hay filtro explícito actual. Promedios Spark ignoran nulos.','Cero y desconocido no equivalen; imputar distorsiona liquidez. Si aparecen negativos, corregir en dbt antes de usar.','dbt/models/silver/slv_precios_acciones.sql; spark/jobs/construir_obt.py')
 if c in {'TICKER','SIMBOLO','TICKER_COMPOSICION','TICKER_ORIGINAL','SIMBOLO_ORIGINAL','TICKERS'}:return ('No imputar identificadores. dbt normaliza, explota listas y aplica equivalencias temporales; elimina claves nulas según cada modelo y deduplica. Conserva símbolo original cuando corresponde.','Una identidad inventada produce joins falsos; equivalencias parciales no garantizan identidad permanente.','dbt/models/bronze/')
 if c in {'NOMBRE','BOLSA','CODIGO_BOLSA','ES_NYSE','BOLSA_DESCONOCIDA','EN_LISTADO_ACTUAL'}:return ('No inferir bolsa histórica. Mantener nombre/código desconocidos; Gold etiqueta bolsa desconocida y es_nyse=false; OBT marca bolsa_desconocida.','Listado actual: ausencia no implica que nunca cotizó en NYSE; no completar con una moda.','dbt/models/silver/slv_acciones.sql; dbt/models/gold/dim_accion.sql')
 if c in {'TASA_IRX_ANUAL_PCT','RF_DIARIA','RF_MES','TASA_IRX_PROM_MES_PCT','TASA_IRX_RELLENADA'}:return ('Rellenar ^IRX hacia adelante con último valor observado; marcar relleno; sin backfill desde el futuro. RF=IRX/100/252 y suma mensual.','Feriados de bonos distintos a NYSE; no interpolar con tasas futuras. Rango -1 a 20 es plausibilidad, no exactitud.','dbt/models/silver/slv_mercado_diario.sql')
 if c in {'FECHA_INICIO','FECHA_FIN','VIGENTE','HUECOS_UNIDOS','PERIODO_KEY','PERIODO_SP500_KEY','EN_SP500','SIGUE_EN_SP500','PRIMERA_FECHA_SP500','ULTIMA_FECHA_SP500','PERIODOS_EN_SP500'}:return ('Derivar intervalos; fecha_fin nula indica vigente; unir huecos de hasta 7 días naturales. No completar membresías sin fuente.','Nulos de intervalo abierto son esperados. Unir huecos supone omisión y puede ocultar una salida real; contraste pendiente.','dbt/models/silver/slv_membresia_sp500.sql; dbt/models/silver/slv_acciones.sql')
 if 'SIGUIENTE' in c:return ('Calcular objetivo/referente futuro; no imputar. Target de acción nulo sin mes siguiente consecutivo.','Nulo esperado al final de la serie; nunca utilizar estas columnas como predictor.','spark/jobs/construir_obt.py')
 if c.startswith(('RET_','VOL_','MOMENTUM','DRAWDOWN','INTRADIA','NOCTURNO')):return ('Derivar de observaciones válidas; no rellenar retornos ni features en PSet 2. Señalar retornos extremos, no borrarlos automáticamente.','Nulos iniciales o tras huecos son esperados. Volatilidad excluye imputados; transformaciones de ML pertenecen a PSet 3.','dbt/models/silver/; spark/jobs/construir_obt.py')
 if c in {'FECHA','FECHA_FOTO','FECHA_DESDE','FECHA_HASTA','INGESTA_TS','LOTE_ID','FUENTE','ARCHIVO','DETALLE','ESTADO','FILAS'}:return ('No imputar ni interpolar metadatos; tipar fechas y conservar trazabilidad. DETALLE vacío es normal para OK.','No inventar fechas/lotes. Fecha ausente impide ubicar la observación; logs no son precios.','kestra/scripts/extraer_cargar.py; dbt/models/bronze/')
 if 'FECHA_PRECIO' in c:return ('Derivar min/max solo cuando existen precios; conservar nulos para acciones sin cobertura.','Nulo no equivale a fecha cero ni ausencia histórica de negociación.','dbt/models/silver/slv_acciones.sql')
 return ('Conservar o recalcular mediante la fórmula de la columna; sin imputación adicional en PSet 2.','Campo derivado/seed/control: no aplicar media o interpolación genérica; revisar la fórmula y nulos esperados.','spark/jobs/construir_obt.py' if table.startswith('OBT.') else 'dbt/models/ o dbt/seeds/ (ver inventario)')

def predicates(table,c,typ):
 col=q(c);invalid=None;cons=None;anomaly=None
 if typ in {'TEXT','VARCHAR'}:cons=f'{col} <> TRIM({col})'
 if c in {'ES_ETF','ES_PRUEBA'} and table.startswith('RAW.'):invalid=f"{col} NOT IN ('Y','N')"
 elif c=='CODIGO_BOLSA':invalid=f"{col} NOT IN ('N','A','Q','P','Z','V')"
 elif c=='ESTADO' and table=='RAW.INGESTA_LOG':invalid=f"{col} NOT IN ('OK','SIN_DATOS','ERROR')"
 elif c=='ESTADO' and table.endswith('EQUIVALENCIAS_TICKERS'):invalid=f"{col} NOT IN ('verificado','detectado','manual')"
 elif c in {'VOLUME','VOLUMEN','FILAS','DIAS_CON_PRECIO','OBS_252D','DIAS_NEGOCIADOS_MES','DIAS_IMPUTADOS_MES'}:invalid=f'{col}<0'
 elif c=='MES':invalid=f'{col} NOT BETWEEN 1 AND 12'
 elif c=='DIA_SEMANA_ISO':invalid=f'{col} NOT BETWEEN 1 AND 7'
 elif c.startswith('VOL_'):invalid=f'{col}<0'
 elif c=='DRAWDOWN_252D':invalid=f'{col} NOT BETWEEN -1 AND 0'
 elif c=='INGESTA_TS':invalid=f'{col}>CURRENT_TIMESTAMP()::TIMESTAMP_NTZ'
 elif c in {'FECHA','FECHA_FOTO'} and not table.endswith('CALENDARIO_NYSE'):invalid=f'{col}>CURRENT_DATE()'
 if table=='RAW.PRECIOS_DIARIOS':
  if c in {'OPEN','HIGH','LOW','CLOSE','ADJ_CLOSE'}:
   invalid=f"IFF(TICKER='^IRX', {col} < -1 OR {col}>20, {col}<=0)"
   cons={'HIGH':'HIGH<LOW','LOW':'LOW>HIGH','OPEN':'OPEN>HIGH*1.001 OR OPEN<LOW*0.999','CLOSE':'CLOSE>HIGH*1.001 OR CLOSE<LOW*0.999'}.get(c)
  if c=='VOLUME':cons='VOLUME<>TRUNC(VOLUME)';anomaly='VOLUME=0'
 if c=='FECHA_HASTA' and table=='RAW.INGESTA_LOG':cons='FECHA_HASTA<FECHA_DESDE'
 if c in {'RET_LOG_DIARIO','RET_LOG_APERTURA'}:anomaly=f'ABS({col})>0.4'
 return invalid,cons,anomaly

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--solo-raw',action='store_true');a=ap.parse_args()
 env=dict(os.environ)
 if (R/'.env').exists():
  for line in (R/'.env').read_text().splitlines():
   if '=' in line and not line.lstrip().startswith('#'):
    k,_,v=line.partition('=');env.setdefault(k.strip(),v.strip())
 started=datetime.now(timezone.utc).isoformat();queries=[]
 con=snowflake.connector.connect(account=env['SNOWFLAKE_ACCOUNT'],user=env['SNOWFLAKE_USER'],private_key=base64.b64decode(env['SNOWFLAKE_PRIVATE_KEY']),role=env.get('SNOWFLAKE_ROLE'),warehouse=env.get('SNOWFLAKE_WAREHOUSE'),database=env.get('SNOWFLAKE_DATABASE','PORTAFOLIO_P3'),session_parameters={'QUERY_TAG':'pset3_diagnostico_calidad','STATEMENT_TIMEOUT_IN_SECONDS':240,'TIMEZONE':'UTC'})
 def run(sql):
  with con.cursor() as cur:
   cur.execute(sql);rows=cur.fetchall();cols=[d[0].lower() for d in cur.description];queries.append({'id':cur.sfqid,'sql':sql});return [dict(zip(cols,row)) for row in rows]
 try:
  cols=run("SELECT table_schema,table_name,column_name,data_type,ordinal_position FROM information_schema.columns WHERE table_schema IN ('RAW','BRONZE','SILVER','GOLD','OBT','CALIDAD') ORDER BY 1,2,5")
  grouped=defaultdict(list)
  for c in cols:
   t=c['table_schema']+'.'+c['table_name']
   if t in KEYS and (not a.solo_raw or c['table_schema']=='RAW'):grouped[t].append(c)
  profiles=[];inventory=[];policies=[];tables=[]
  for t,columns in grouped.items():
   expr=['COUNT(*) AS N'];rules=[]
   for i,c in enumerate(columns):
    col=q(c['column_name']);typ=c['data_type'];null=f'{col} IS NULL';blank=f"{col} IS NOT NULL AND TRIM({col})=''" if typ in {'TEXT','VARCHAR'} else 'FALSE'
    invalid,cons,anomaly=predicates(t,c['column_name'],typ);rules.append((invalid,cons,anomaly))
    for k,pred in [('nul',null),('blank',blank),('inv',invalid),('cons',cons),('anom',anomaly)]:expr.append((f'COALESCE(COUNT_IF({pred}),0)' if pred else 'NULL')+f' AS {k}{i}')
    expr += [f'COUNT(DISTINCT {col}) AS distinct{i}']
    if typ not in {'TEXT','VARCHAR','BOOLEAN'}:expr += [f'MIN({col}) AS min{i}',f'MAX({col}) AS max{i}']
   row=run('SELECT '+', '.join(expr)+' FROM '+t)[0];n=int(row['n'])
   for i,c in enumerate(columns):
    name=c['column_name'];kind,origin=lineage(c['table_schema'],c['table_name'],name);action,why,where=policy(t,name)
    inventory.append({'tabla':t,'columna':name,'tipo':c['data_type'],'clase':kind,'procedencia':origin})
    policies.append({'tabla':t,'columna':name,'accion_implementada':action,'justificacion_y_limite':why,'codigo':where})
    rec={'tabla':t,'columna':name,'filas':n,'nulos':row[f'nul{i}'],'vacios':row[f'blank{i}'],'faltantes_pct':pct(row[f'nul{i}']+row[f'blank{i}'],n),'distintos_no_nulos':row[f'distinct{i}'],'minimo':str(row.get(f'min{i}','')),'maximo':str(row.get(f'max{i}',''))}
    for k,label,pred in zip(['inv','cons','anom'],['invalidos','inconsistentes','anomalos'],rules[i]):
     rec[label]=row[f'{k}{i}'];rec[label+'_pct']=pct(row[f'{k}{i}'],n) if pred else None;rec['regla_'+label]=pred or 'No evaluado: sin regla específica'
    rec['precision_externa']='No contrastada con fuente oficial independiente'
    profiles.append(rec)
   keys=','.join(q(k) for k in KEYS[t]);dup=run(f'SELECT COALESCE(SUM(n-1),0) AS redundantes, COUNT_IF(n>1) AS claves_repetidas FROM (SELECT {keys},COUNT(*) n FROM {t} GROUP BY {keys})')[0]
   tables.append({'tabla':t,'filas':n,'columnas':len(columns),'clave':','.join(KEYS[t]),'filas_redundantes':int(dup['redundantes']),'redundantes_pct':pct(dup['redundantes'],n)})
   print(t,n,'filas;',len(columns),'columnas',flush=True)
  dump('inventario_columnas',inventory);dump('perfil_columnas',profiles);dump('decisiones_por_columna',policies);dump('perfil_tablas',tables)
  # Lente diagnóstica sobre RAW: última observación por clave, sin persistir limpieza.
  raw="""SELECT * FROM RAW.PRECIOS_DIARIOS WHERE TICKER IS NOT NULL AND FECHA IS NOT NULL
  QUALIFY ROW_NUMBER() OVER(PARTITION BY UPPER(TRIM(TICKER)),FECHA ORDER BY INGESTA_TS DESC,LOTE_ID DESC)=1"""
  checks=[]
  def check(name,dimension,sql,action,why):
   r=run(sql)[0];checks.append({'problema':name,'dimension':dimension,'afectados':int(r['afectados']),'denominador':int(r['total']),'porcentaje':pct(r['afectados'],r['total']),'accion':action,'justificacion':why})
  check('Claves precio con revisiones de cierre ajustado','consistencia',"SELECT COUNT_IF(v>1) afectados,COUNT(*) total FROM (SELECT TICKER,FECHA,COUNT(DISTINCT ADJ_CLOSE) v FROM RAW.PRECIOS_DIARIOS GROUP BY 1,2)",'Conservar carga reciente en Bronze; conservar RAW.','Puede ser revisión retrospectiva de Yahoo; no confundir reingesta idéntica con conflicto.')
  check('Revisiones de cierre ajustado mayores a 0.01% relativo','consistencia',"SELECT COUNT_IF(hi/NULLIF(lo,0)-1>0.0001) afectados,COUNT(*) total FROM (SELECT TICKER,FECHA,MIN(ADJ_CLOSE) lo,MAX(ADJ_CLOSE) hi FROM RAW.PRECIOS_DIARIOS WHERE ADJ_CLOSE>0 GROUP BY 1,2)",'Conservar versión reciente y RAW para auditoría.','Descarta diferencias menores a 0.01%; no prueba error, puede reflejar ajustes retrospectivos.')
  check('Saltos absolutos log-precio >0.40 en RAW último por clave','precision',f"""WITH p AS ({raw}), r AS (SELECT TICKER, ADJ_CLOSE, LAG(ADJ_CLOSE) OVER(PARTITION BY TICKER ORDER BY FECHA) prev FROM p WHERE TICKER NOT LIKE '^%') SELECT COUNT_IF(ABS(LN(NULLIF(IFF(ADJ_CLOSE>0,ADJ_CLOSE,NULL),0)/NULLIF(IFF(prev>0,prev,NULL),0)))>0.4) afectados,COUNT_IF(ADJ_CLOSE>0 AND prev>0) total FROM r""",'Marcar y revisar; no winsorizar ni borrar automáticamente.','Proxy de plausibilidad; incluye saltos entre observaciones separadas por huecos, no solo retornos diarios.')
  check('Retornos fuera de 1.5 IQR por acción (mínimo 20 retornos)','precision',f"""WITH p AS ({raw}), lagged AS (SELECT TICKER,ADJ_CLOSE,LAG(ADJ_CLOSE) OVER(PARTITION BY TICKER ORDER BY FECHA) prev FROM p WHERE TICKER NOT LIKE '^%'), r AS (SELECT TICKER,LN(NULLIF(IFF(ADJ_CLOSE>0,ADJ_CLOSE,NULL),0)/NULLIF(IFF(prev>0,prev,NULL),0)) ret FROM lagged), quant AS (SELECT TICKER,PERCENTILE_CONT(0.25) WITHIN GROUP(ORDER BY ret) q1,PERCENTILE_CONT(0.75) WITHIN GROUP(ORDER BY ret) q3,COUNT(ret) n FROM r GROUP BY 1) SELECT COUNT_IF(r.ret<q.q1-1.5*(q.q3-q.q1) OR r.ret>q.q3+1.5*(q.q3-q.q1)) afectados,COUNT(*) total FROM r JOIN quant q USING(TICKER) WHERE r.ret IS NOT NULL AND q.n>=20""",'Señal diagnóstica; conservar y revisar, no recortar automáticamente.','IQR por acción evita mezclar escalas de precios; colas financieras reales pueden ser atípicas. Incluye saltos sobre huecos.')
  # Outliers con z-score robusto (PSet 1: "MAD/z-score verificados contra eventos reales").
  # z = 0,6745 * (r - mediana) / MAD por accion; umbral 3,5 (Iglewicz y Hoaglin). Solo marca.
  # Solo retornos entre sesiones consecutivas (<= 7 dias naturales, cubre fines de semana y
  # feriados): la ingesta historica deja anios sin datos de acciones que no eran miembros
  # (p. ej. JBL antes de 2023) y un LAG sin filtro mediria saltos de varios anios. Silver
  # tampoco calcula esos retornos (despues_de_tramo_excluido).
  mad_base=f"""WITH p AS ({raw}), lagged AS (SELECT TICKER,FECHA,ADJ_CLOSE,LAG(ADJ_CLOSE) OVER(PARTITION BY TICKER ORDER BY FECHA) prev,LAG(FECHA) OVER(PARTITION BY TICKER ORDER BY FECHA) prev_fecha FROM p WHERE TICKER NOT LIKE '^%'), r AS (SELECT TICKER,FECHA,LN(NULLIF(IFF(ADJ_CLOSE>0,ADJ_CLOSE,NULL),0)/NULLIF(IFF(prev>0,prev,NULL),0)) ret FROM lagged WHERE FECHA-prev_fecha<=7), med AS (SELECT TICKER,MEDIAN(ret) m,COUNT(ret) n FROM r GROUP BY 1), dev AS (SELECT r.TICKER,r.FECHA,r.ret,ABS(r.ret-med.m) d FROM r JOIN med USING(TICKER) WHERE r.ret IS NOT NULL AND med.n>=20), mad AS (SELECT TICKER,MEDIAN(d) mad FROM dev GROUP BY 1), z AS (SELECT dev.TICKER,dev.FECHA,dev.ret,0.6745*dev.d/NULLIF(mad.mad,0) z FROM dev JOIN mad USING(TICKER))"""
  check('Retornos con z-score robusto (MAD) mayor a 3.5 por acción, sesiones consecutivas (mínimo 20 retornos)','precision',mad_base+" SELECT COUNT_IF(z>3.5) afectados,COUNT(*) total FROM z",'Marcar y cotejar con eventos reales (ver outliers_mad_por_fecha.csv); no recortar automáticamente.','Criterio del PSet 1. MAD es robusto a las colas; muchos casos el mismo día indican un evento de mercado, no un error de datos.')
  dump('outliers_mad_top',run(mad_base+" SELECT TICKER ticker,FECHA fecha,ROUND(ret,5) ret_log,ROUND(z,2) z_robusto FROM z WHERE z>3.5 ORDER BY z DESC LIMIT 30"))
  dump('outliers_mad_por_fecha',run(mad_base+" SELECT FECHA fecha,COUNT(*) acciones_marcadas,ROUND(AVG(ret),5) ret_log_promedio FROM z WHERE z>3.5 GROUP BY 1 ORDER BY 2 DESC LIMIT 20"))
  check('Sesiones sin fila durante la vida observada de cada acción','completitud',f"""WITH p AS ({raw}), vida AS (SELECT TICKER,MIN(FECHA) inicio,MAX(FECHA) fin FROM p WHERE TICKER NOT LIKE '^%' GROUP BY 1), grilla AS (SELECT v.TICKER,c.FECHA FROM vida v JOIN BRONZE.CALENDARIO_NYSE c ON c.FECHA BETWEEN v.inicio AND v.fin) SELECT COUNT_IF(p.TICKER IS NULL) afectados,COUNT(*) total FROM grilla g LEFT JOIN p ON g.TICKER=p.TICKER AND g.FECHA=p.FECHA""",'Silver construye grilla; forward-fill hasta cinco sesiones internas; excluye huecos mayores.','No supone precios antes de primera o después de última cotización; no cubre acciones sin ningún precio.')
  check('Precios de acciones fuera del calendario NYSE','validez',f"""WITH p AS ({raw}) SELECT COUNT_IF(c.FECHA IS NULL) afectados,COUNT(*) total FROM p LEFT JOIN BRONZE.CALENDARIO_NYSE c ON p.FECHA=c.FECHA WHERE p.TICKER NOT LIKE '^%' AND p.FECHA>='2010-01-01'""",'Excluir al unir con calendario en Silver.','Fin de semana/feriado no constituye una sesión faltante.')
  check('Fotos de composición con menos de 495 símbolos','completitud',"""WITH c AS (SELECT * FROM RAW.COMPOSICION_SP500 QUALIFY DENSE_RANK() OVER(ORDER BY INGESTA_TS DESC,LOTE_ID DESC)=1) SELECT COUNT_IF(ARRAY_SIZE(SPLIT(TICKERS,','))<495) afectados,COUNT(*) total FROM c WHERE FECHA>='2010-01-01'""",'No inventar constituyentes; documentar cobertura.','Umbral diagnóstico: 500 empresas no significa siempre 500 símbolos.')
  check('Símbolos del listado con múltiples bolsas en última carga','consistencia',"""WITH l AS (SELECT * FROM RAW.LISTADOS_BOLSA QUALIFY DENSE_RANK() OVER(ORDER BY INGESTA_TS DESC,LOTE_ID DESC)=1) SELECT COUNT_IF(n>1) afectados,COUNT(*) total FROM (SELECT SIMBOLO,COUNT(DISTINCT CODIGO_BOLSA) n FROM l GROUP BY 1)""",'Bronze conserva una fila por símbolo con prioridad de archivo.','La prioridad es técnica, no verificación de la bolsa correcta; revisar si hay conflictos.')
  check('Símbolos sin precios devueltos en bitácora','completitud',"SELECT COUNT_IF(ESTADO='SIN_DATOS') afectados,COUNT(*) total FROM RAW.INGESTA_LOG",'Conservar SIN_DATOS y medir cobertura; no imputar toda una historia.','Denominador solicitudes registradas, no empresas únicas.')
  check('Errores agotados en bitácora','consistencia',"SELECT COUNT_IF(ESTADO='ERROR') afectados,COUNT(*) total FROM RAW.INGESTA_LOG",'Retry en Kestra y revisión del lote.','Una corrida exitosa puede tolerar hasta 10% de grupos fallidos; ver porcentaje real.')
  dump('problemas_raw',checks)
  # Control de la corrección: si la fuente desconoce todos los flags, staging no los inventa.
  by={(r['tabla'],r['columna']):r for r in profiles}
  if not a.solo_raw:
   for flag in ['ES_ETF','ES_PRUEBA']:
    if by[('RAW.LISTADOS_BOLSA',flag)]['faltantes_pct']==100:
     assert by[('BRONZE.BRZ_LISTADOS_BOLSA',flag)]['faltantes_pct']==100
  assert all(r['nulos']+r['vacios']<=r['filas'] for r in profiles)

  # Segmentos: separa acciones, índices y tasa; conserva ventanas históricas.
  temporal=run("""SELECT YEAR(FECHA) anio, CASE WHEN TICKER='^IRX' THEN 'tasa' WHEN TICKER LIKE '^%' THEN 'indice' ELSE 'accion' END segmento,COUNT(*) filas,COUNT_IF(ADJ_CLOSE IS NULL) cierre_ajustado_nulo,COUNT_IF(VOLUME IS NULL) volumen_nulo,COUNT_IF(VOLUME=0) volumen_cero,ROUND(100.0*COUNT_IF(ADJ_CLOSE IS NULL)/NULLIF(COUNT(*),0),6) cierre_nulo_pct FROM RAW.PRECIOS_DIARIOS GROUP BY 1,2 ORDER BY 1,2""")
  dump('perfil_raw_por_anio',temporal)
  meta={'inicio_utc':started,'fin_utc':datetime.now(timezone.utc).isoformat(),'base':env.get('SNOWFLAKE_DATABASE','PORTAFOLIO_P3'),'zona_sesion':'UTC (INGESTA_TS se almacena como UTC sin zona)','modo':'solo SELECT; no se escribe Snowflake','alcance':'RAW profundo; otras capas perfil descriptivo posterior' if not a.solo_raw else 'RAW','tablas':len(tables),'columnas':len(inventory),'porcentaje':'100 * afectados / filas de tabla, salvo denominador explícito de problemas_raw','advertencia':'RAW ya incluye extracción y tipado de ingesta; no es el archivo original sin procesar. Consultas secuenciales, no snapshot transaccional único. Blancos/nulos no incluidos en inválidos. Precisión real no verificada contra proveedor independiente.'}
  (OUT/'ejecucion.json').write_text(json.dumps(meta,indent=2));(OUT/'consultas.json').write_text(json.dumps(queries,indent=2));(OUT/'consultas.sql').write_text('\n\n'.join('-- query_id: '+x['id']+'\n'+x['sql']+';' for x in queries))
 finally:con.close()
 print('Diagnóstico terminado:',OUT)
if __name__=='__main__':main()
