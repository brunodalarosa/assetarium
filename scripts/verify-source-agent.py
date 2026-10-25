"""Fresh real STDIO client: preview delivery and live semantic source toggles."""
import base64
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_asset_library.config import load_project_config
from local_asset_library.sources import get_source,set_enabled
from local_asset_library.publication import atomic_json

config=load_project_config(ROOT)
source=get_source(config,'kenney_car-kit')
OUT=ROOT/'data/library/verification'/('source-agent-'+uuid.uuid4().hex);OUT.mkdir()
log=(OUT/'stderr.log').open('w',encoding='utf-8')
process=subprocess.Popen([str(ROOT/'.venv-mcp/Scripts/python.exe'),str(ROOT/'scripts/asset-mcp.py')],
    cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf-8',
    creationflags=subprocess.CREATE_NO_WINDOW)
messages=queue.Queue();sequence=0
def read():
    for line in process.stdout:messages.put(line)
    messages.put(None)
threading.Thread(target=read,daemon=True).start()
def send(method,params=None,notification=False):
    global sequence
    value={'jsonrpc':'2.0','method':method}
    if params is not None:value['params']=params
    if not notification:sequence+=1;value['id']=sequence
    process.stdin.write(json.dumps(value)+'\n');process.stdin.flush()
    if notification:return
    while True:
        response=messages.get(timeout=120)
        if response is None:raise RuntimeError('Agent server exited')
        result=json.loads(response)
        if result.get('id')==sequence:return result['result']
def call(name,args):
    result=send('tools/call',{'name':name,'arguments':args})
    if result.get('isError'):raise RuntimeError(result['content'][0]['text'])
    return json.loads(result['content'][0]['text']),result
report={'status':'running','checks':[],'server_pid':process.pid}
try:
    send('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'source-visibility-check','version':'1'}})
    send('notifications/initialized',notification=True)
    args={'query':'sedan','mode':'keyword','filters':{'pack':source['key']},'limit':2}
    before,_=call('search_assets',args);assert before['results']
    candidate=before['results'][0]['asset_id']
    details,result=call('get_asset',{'asset_id':candidate,'include_preview':True})
    assert details['usable']
    image=next(c for c in result['content'] if c['type']=='image')
    (OUT/'preview.png').write_bytes(base64.b64decode(image['data'],validate=True))
    report['checks'].append('Fresh agent server resolves original source and real migrated PNG preview')
    args.update(query='a small low polygon sedan car',mode='combined')
    first,_=call('search_assets',args);assert first['results']
    set_enabled(config,source['key'],False)
    hidden,_=call('search_assets',args);assert not hidden['results']
    set_enabled(config,source['key'],True)
    restored,_=call('search_assets',args)
    assert [r['asset_id'] for r in restored['results']]==[r['asset_id'] for r in first['results']]
    report['checks'].append('One running server/embedding worker reflects disable and re-enable in semantic search')
    report['status']='passed'
except BaseException as exc:
    report.update(status='faulty',reason=str(exc));raise
finally:
    set_enabled(config,source['key'],source['enabled'])
    process.stdin.close()
    report['server_exit_code']=process.wait(timeout=20)
    log.close();atomic_json(OUT/'report.json',report)
    print(json.dumps({'status':report['status'],'report':str(OUT/'report.json'),'reason':report.get('reason')},indent=2))
