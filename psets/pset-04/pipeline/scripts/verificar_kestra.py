"""Publica flows del checkout, inicia una ejecución o exporta estados sin secretos."""
import argparse, json, os
from pathlib import Path
import requests
p=argparse.ArgumentParser(); p.add_argument('accion',choices=['publicar','ejecutar','estado','detener','desencolar','logs']); p.add_argument('--flow',default='ingesta_diaria'); p.add_argument('--id'); a=p.parse_args()
root=Path(__file__).resolve().parents[1]; out=root/'docs/corrida'; out.mkdir(exist_ok=True)
s=requests.Session(); s.auth=(os.environ['KESTRA_USUARIO'],os.environ['KESTRA_CLAVE'])
base=os.environ.get('KESTRA_API','http://host.docker.internal:8090/api/v1/main')
def call(method,path,**kw):
 r=s.request(method,base+path,timeout=60,**kw); r.raise_for_status(); return r
if a.accion=='publicar':
 for name in ['transformar','ingesta_diaria','backfill_historico']:
  endpoint='/flows/usfq.portafolio/'+name
  exists=s.get(base+endpoint,timeout=30).status_code==200
  call('PUT' if exists else 'POST',endpoint if exists else '/flows',data=(root/f'kestra/flows/{name}.yml').read_bytes(),headers={'Content-Type':'application/x-yaml'})
  print(name,'publicado')
elif a.accion=='logs':
 if not a.id: p.error('--id requerido')
 data=call('GET','/logs/'+a.id,params={'minLevel':'ERROR'}).json()
 result=json.dumps(data,indent=2)
 for key,value in os.environ.items():
  if any(x in key for x in ['KEY','PASSWORD','CLAVE','ACCOUNT']) and len(value)>6: result=result.replace(value,'[REDACTADO]')
 (out/('kestra_errores_'+a.id+'.json')).write_text(result)
 print(result[-6000:])
elif a.accion=='desencolar':
 if not a.id: p.error('--id requerido')
 call('POST','/executions/'+a.id+'/actions/force-run'); print('Ejecución forzada:',a.id)
elif a.accion=='detener':
 if not a.id: p.error('--id requerido')
 call('DELETE','/executions/'+a.id+'/actions/kill'); print('Terminación solicitada:',a.id)
elif a.accion=='ejecutar':
 files={'fecha':(None,'2026-11-13')} if a.flow=='ingesta_diaria' else {'anio_desde':(None,'2026'),'anio_hasta':(None,'2026')}
 j=call('POST','/executions/usfq.portafolio/'+a.flow,files=files).json()
 (out/f'kestra_{a.flow}_id.txt').write_text(j['id']+'\n'); print('id:',j['id'])
else:
 if a.id:
  j=call('GET','/executions/'+a.id).json(); items=[j]
 else: items=call('GET','/executions/search',params={'namespace':'usfq.portafolio','size':50,'sort':'state.startDate:desc'}).json().get('results',[])
 clean=[{**{k:j.get(k) for k in ['id','namespace','flowId','state']}, 'tasks':[{k:t.get(k) for k in ['taskId','state']} for t in j.get('taskRunList',[])]} for j in items]
 (out/'kestra_estados.json').write_text(json.dumps(clean,indent=2))
 for row in clean:
  print(row['id'],row['flowId'],row['state']['current'],[(t['taskId'],t['state']['current']) for t in row['tasks']])
