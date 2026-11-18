"""Evidencia de grano, cobertura y almacenamiento de Gold/OBT; solo SELECT."""
import base64, json, os
from datetime import datetime, timezone
from pathlib import Path
import snowflake.connector
R = Path(__file__).resolve().parents[1]
env = dict(os.environ)
for line in (R / '.env').read_text().splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        k, _, v = line.partition('='); env.setdefault(k.strip(), v.strip())
queries = {
 'almacenamiento': "SELECT table_schema, table_name, row_count, bytes FROM information_schema.tables WHERE table_schema IN ('GOLD','OBT') AND table_type='BASE TABLE' ORDER BY 1,2",
 'grano': "SELECT COUNT(*) filas, COUNT(DISTINCT accion_key,anio_mes) claves, COUNT_IF(accion_key IS NULL OR anio_mes IS NULL) claves_nulas, COUNT_IF(elegible) elegibles FROM OBT.OBT_ACCION_MES",
 'meses': "SELECT MIN(anio_mes) desde, MAX(anio_mes) hasta, COUNT_IF(ret_log_mes_siguiente IS NULL) objetivos_nulos FROM OBT.OBT_ACCION_MES",
 'base_gold': "SELECT COUNT(*) filas FROM (SELECT p.accion_key,d.anio_mes FROM GOLD.FCT_PRECIOS_DIARIOS p JOIN GOLD.DIM_FECHA d ON p.fecha_key=d.fecha_key WHERE d.mes_cerrado GROUP BY 1,2)",
 'claves_faltantes_o_extra': "WITH base AS (SELECT DISTINCT p.accion_key,d.anio_mes FROM GOLD.FCT_PRECIOS_DIARIOS p JOIN GOLD.DIM_FECHA d ON p.fecha_key=d.fecha_key WHERE d.mes_cerrado) SELECT COUNT(*) diferencias FROM base b FULL OUTER JOIN OBT.OBT_ACCION_MES o ON b.accion_key=o.accion_key AND b.anio_mes=o.anio_mes WHERE b.accion_key IS NULL OR o.accion_key IS NULL",
 'controles': "SELECT * FROM OBT.VALIDACION_OBT ORDER BY control"
}
result = {'verificado_utc':datetime.now(timezone.utc).isoformat(), 'operacion':'SELECT', 'resultados':{}, 'consultas':[]}
with snowflake.connector.connect(account=env['SNOWFLAKE_ACCOUNT'],user=env['SNOWFLAKE_USER'],private_key=base64.b64decode(env['SNOWFLAKE_PRIVATE_KEY']),role=env.get('SNOWFLAKE_ROLE'),warehouse=env.get('SNOWFLAKE_WAREHOUSE'),database=env.get('SNOWFLAKE_DATABASE','PORTAFOLIO_P3'),session_parameters={'TIMEZONE':'UTC','QUERY_TAG':'pset3_auditoria_obt'}) as con:
    with con.cursor() as c:
        for name, sql in queries.items():
            c.execute(sql)
            result['resultados'][name] = [dict(zip([x[0].lower() for x in c.description],row)) for row in c.fetchall()]
            result['consultas'].append({'nombre':name,'sql':sql,'query_id':c.sfqid})
g = result['resultados']['grano'][0]
assert g['filas'] == g['claves'] == result['resultados']['base_gold'][0]['filas'] and g['claves_nulas'] == 0
assert result['resultados']['claves_faltantes_o_extra'][0]['diferencias'] == 0
assert len(result['resultados']['controles']) == 17 and all(r['ok'] for r in result['resultados']['controles'])
(R/'docs/corrida/auditoria_obt.json').write_text(json.dumps(result,indent=2,default=str))
print(json.dumps(result['resultados'],indent=2,default=str))
