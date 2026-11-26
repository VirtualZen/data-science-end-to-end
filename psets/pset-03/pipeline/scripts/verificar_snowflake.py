"""Valida el resultado real de PSet 2 con consultas de solo lectura."""
import base64,json,os
from datetime import datetime,timezone
from pathlib import Path
import snowflake.connector
root=Path(__file__).resolve().parents[1]
env=dict(os.environ)
if (root/'.env').exists():
 for line in (root/'.env').read_text().splitlines():
  if '=' in line and not line.lstrip().startswith('#'):
   k,_,v=line.partition('=');env.setdefault(k.strip(),v.strip())
with snowflake.connector.connect(account=env['SNOWFLAKE_ACCOUNT'],user=env['SNOWFLAKE_USER'],private_key=base64.b64decode(env['SNOWFLAKE_PRIVATE_KEY']),role=env.get('SNOWFLAKE_ROLE'),warehouse=env.get('SNOWFLAKE_WAREHOUSE'),database=env.get('SNOWFLAKE_DATABASE','PORTAFOLIO_P3')) as con:
 with con.cursor() as c:
  def one(sql):c.execute(sql);return c.fetchone()
  n,unique,eligible=one("select count(*),count(distinct accion_key,anio_mes),sum(iff(elegible,1,0)) from OBT.OBT_ACCION_MES")
  checks,bad,ts=one("select count(*),sum(iff(ok,0,1)),max(ejecutado_en) from OBT.VALIDACION_OBT")
  columns=one("select count(*) from information_schema.columns where table_schema='OBT' and table_name='OBT_ACCION_MES'")[0]
  # OBT diaria (PSet 3): una fila por fila de GOLD.FCT_PRECIOS_DIARIOS y 33 columnas.
  dia,dia_claves,fct=one("select (select count(*) from OBT.OBT_ACCION_DIA),(select count(distinct accion_key,fecha) from OBT.OBT_ACCION_DIA),(select count(*) from GOLD.FCT_PRECIOS_DIARIOS)")
  dia_columns=one("select count(*) from information_schema.columns where table_schema='OBT' and table_name='OBT_ACCION_DIA'")[0]
  raw,last=one('select count(*),max(ingesta_ts) from RAW.PRECIOS_DIARIOS')
  assert n>0 and n==unique and checks==17 and bad==0 and columns==75 and dia==dia_claves==fct and dia_columns==33
  result={'estado':'OK','verificado_utc':datetime.now(timezone.utc).isoformat(),'obt_filas':int(n),'obt_claves_distintas':int(unique),'obt_elegibles':int(eligible),'obt_columnas':int(columns),'obt_dia_filas':int(dia),'obt_dia_columnas':int(dia_columns),'controles_ok':int(checks),'controles_fallidos':int(bad),'controles_ejecutados_en':str(ts),'raw_filas':int(raw),'ultima_ingesta':str(last),'operacion':'SELECT; sin escrituras'}
(root/'docs/corrida/verificacion_snowflake.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
