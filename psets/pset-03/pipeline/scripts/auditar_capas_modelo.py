"""Audita dependencias medallón y el grano/relaciones Gold. Solo SELECT en Snowflake."""
import base64,json,os,re
from datetime import datetime,timezone
from pathlib import Path
import snowflake.connector
R=Path(__file__).resolve().parents[1];D=R/'docs/corrida'
models={p.stem:(p.parent.name.upper(),p) for p in (R/'dbt/models').rglob('*.sql')}
seeds={p.stem for p in (R/'dbt/seeds').glob('*.csv')}
allowed={'BRONZE':{'RAW','BRONZE'},'SILVER':{'BRONZE','SILVER'},'GOLD':{'SILVER','GOLD'},'CALIDAD':{'RAW','BRONZE','SILVER','GOLD','CALIDAD'}}
edges=[];violations=[];graph={}
for name,(layer,p) in models.items():
 sql=p.read_text();refs=re.findall(r"ref\(['\"]([^'\"]+)['\"]\)",sql);sources=re.findall(r"source\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]\)",sql);graph[name]=[x for x in refs if x in models]
 for ref in refs:
  src=models[ref][0] if ref in models else ('BRONZE' if ref in seeds else 'DESCONOCIDO')
  edges.append({'desde':src+'.'+ref,'hacia':layer+'.'+name})
  if src not in allowed[layer]:violations.append(edges[-1])
 for schema,table in sources:
  edges.append({'desde':schema.upper()+'.'+table,'hacia':layer+'.'+name})
  if schema.upper() not in allowed[layer]:violations.append(edges[-1])
def visit(n,stack,done):
 if n in stack:raise AssertionError('Ciclo dbt: '+n)
 if n in done:return
 for parent in graph[n]:visit(parent,stack|{n},done)
 done.add(n)
done=set()
for n in graph:visit(n,set(),done)
env=dict(os.environ)
for line in (R/'.env').read_text().splitlines():
 if '=' in line and not line.lstrip().startswith('#'):
  k,_,v=line.partition('=');env.setdefault(k.strip(),v.strip())
queries=[];checks={}
with snowflake.connector.connect(account=env['SNOWFLAKE_ACCOUNT'],user=env['SNOWFLAKE_USER'],private_key=base64.b64decode(env['SNOWFLAKE_PRIVATE_KEY']),role=env.get('SNOWFLAKE_ROLE'),warehouse=env.get('SNOWFLAKE_WAREHOUSE'),database=env.get('SNOWFLAKE_DATABASE','PORTAFOLIO_P3'),session_parameters={'TIMEZONE':'UTC','QUERY_TAG':'pset3_auditoria_capas_grano'}) as con:
 def run(name,sql):
  with con.cursor() as c:
   c.execute(sql);cols=[d[0].lower() for d in c.description];rows=[dict(zip(cols,r)) for r in c.fetchall()];queries.append({'nombre':name,'query_id':c.sfqid,'sql':sql});checks[name]=rows;return rows
 run('objetos',"SELECT table_schema,table_name,table_type FROM information_schema.tables WHERE table_schema IN ('RAW','BRONZE','SILVER','GOLD') ORDER BY 1,2")
 for table,key in [('DIM_ACCION','accion_key'),('DIM_FECHA','fecha_key'),('DIM_MEMBRESIA_SP500','periodo_key'),('FCT_PRECIOS_DIARIOS','accion_key,fecha_key'),('FCT_MERCADO_DIARIO','fecha_key')]:
  condition=' OR '.join(k+' IS NULL' for k in key.split(','))
  run(table,f'SELECT COUNT(*) filas, COUNT(DISTINCT {key}) claves_unicas,COUNT_IF({condition}) claves_nulas FROM GOLD.{table}')
 run('joins_precios',"""SELECT COUNT(*) filas_join,COUNT_IF(a.accion_key IS NULL) accion_huerfana,COUNT_IF(d.fecha_key IS NULL) fecha_huerfana,COUNT_IF(p.periodo_sp500_key IS NOT NULL AND m.periodo_key IS NULL) periodo_huerfano,COUNT_IF(p.en_sp500<>(p.periodo_sp500_key IS NOT NULL)) membresia_inconsistente,COUNT_IF(m.periodo_key IS NOT NULL AND (m.ticker<>a.ticker OR d.fecha<m.fecha_inicio OR d.fecha>COALESCE(m.fecha_fin,'9999-12-31'::DATE))) periodo_fuera_intervalo,COUNT_IF(NOT p.en_sp500) filas_fuera_sp500,COUNT_IF(p.imputado) filas_imputadas,MIN(d.fecha) desde,MAX(d.fecha) hasta FROM GOLD.FCT_PRECIOS_DIARIOS p LEFT JOIN GOLD.DIM_ACCION a ON p.accion_key=a.accion_key LEFT JOIN GOLD.DIM_FECHA d ON p.fecha_key=d.fecha_key LEFT JOIN GOLD.DIM_MEMBRESIA_SP500 m ON p.periodo_sp500_key=m.periodo_key""")
 run('join_mercado',"SELECT COUNT(*) filas_join,COUNT_IF(d.fecha_key IS NULL) fecha_huerfana FROM GOLD.FCT_MERCADO_DIARIO m LEFT JOIN GOLD.DIM_FECHA d ON m.fecha_key=d.fecha_key")
 run('conservacion_silver',"SELECT (SELECT COUNT(*) FROM SILVER.SLV_PRECIOS_ACCIONES) precios_silver,(SELECT COUNT(*) FROM GOLD.FCT_PRECIOS_DIARIOS) precios_gold,(SELECT COUNT(*) FROM SILVER.SLV_MERCADO_DIARIO) mercado_silver,(SELECT COUNT(*) FROM GOLD.FCT_MERCADO_DIARIO) mercado_gold")
 run('solapes_membresia',"SELECT COUNT(*) pares_solapados FROM GOLD.DIM_MEMBRESIA_SP500 a JOIN GOLD.DIM_MEMBRESIA_SP500 b ON a.ticker=b.ticker AND a.periodo_key<b.periodo_key AND a.fecha_inicio<=COALESCE(b.fecha_fin,'9999-12-31'::DATE) AND b.fecha_inicio<=COALESCE(a.fecha_fin,'9999-12-31'::DATE)")
 run('restricciones_gold',"SELECT table_name,constraint_type FROM information_schema.table_constraints WHERE table_schema='GOLD' ORDER BY 1,2")
 run('atributos_temporales',"SELECT COUNT_IF(codigo_bolsa IS NULL) bolsa_desconocida,COUNT(*) acciones FROM GOLD.DIM_ACCION")
 run('join_hechos_por_fecha',"SELECT COUNT(*) filas_join FROM GOLD.FCT_PRECIOS_DIARIOS p JOIN GOLD.FCT_MERCADO_DIARIO m ON p.fecha_key=m.fecha_key")
for t in ['DIM_ACCION','DIM_FECHA','DIM_MEMBRESIA_SP500','FCT_PRECIOS_DIARIOS','FCT_MERCADO_DIARIO']:
 x=checks[t][0];assert x['filas']==x['claves_unicas'] and (x['claves_nulas'] or 0)==0
j=checks['joins_precios'][0]
assert j['filas_join']==checks['FCT_PRECIOS_DIARIOS'][0]['filas']
for k in ['accion_huerfana','fecha_huerfana','periodo_huerfano','membresia_inconsistente','periodo_fuera_intervalo']:assert (j[k] or 0)==0
assert (checks['join_mercado'][0]['fecha_huerfana'] or 0)==0
assert checks['join_mercado'][0]['filas_join']==checks['FCT_MERCADO_DIARIO'][0]['filas']
x=checks['conservacion_silver'][0];assert x['precios_silver']==x['precios_gold'] and x['mercado_silver']==x['mercado_gold']
assert checks['solapes_membresia'][0]['pares_solapados']==0
result={'verificado_utc':datetime.now(timezone.utc).isoformat(),'modo':'SELECT y revisión estática del SQL actual; sin escrituras Snowflake','dependencias':edges,'violaciones_direccion_capas':violations,'dag_sin_ciclos':True,'controles_grano_integridad':'OK','gold':'dos hechos y tres dimensiones Gold; todas las relaciones de consumo del hecho resueltas dentro de Gold','excepcion':None,'resultados':checks}
(D/'auditoria_capas_modelo.json').write_text(json.dumps(result,indent=2,default=str));(D/'auditoria_capas_modelo.sql').write_text('\n\n'.join('-- '+x['nombre']+'; query_id='+x['query_id']+'\n'+x['sql']+';' for x in queries))
print(json.dumps(result,indent=2,default=str))
