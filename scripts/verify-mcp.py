"""Real STDIO protocol test. This is deliberately NOT evidence of agent use."""
from pathlib import Path
import base64
import argparse
import hashlib
import json
import queue
import subprocess
import threading
import time

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--run-name',default='final')
args=parser.parse_args()
import re
if not re.fullmatch('[a-z0-9-]{1,32}',args.run_name):raise SystemExit('Invalid test run name')
out=root/'data/mcp/protocol'/args.run_name
out.mkdir(parents=True,exist_ok=False)
stderr=(out/'stderr.log').open('w',encoding='utf-8')
existing_runs={d.name for d in (root/'data/mcp/runs').glob('*')}
p=subprocess.Popen([str(root/'.venv-mcp/Scripts/python.exe'),str(root/'scripts/asset-mcp.py')],
    cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True,encoding='utf-8')
messages=queue.Queue()
def reader():
    for line in p.stdout: messages.put(line)
    messages.put(None)
threading.Thread(target=reader,daemon=True).start()
seq=0
checks=[]
wire=[]
def send(method,params=None,notification=False):
    global seq
    message={'jsonrpc':'2.0','method':method}
    if params is not None: message['params']=params
    if not notification:
        seq+=1
        message['id']=seq
    p.stdin.write(json.dumps(message)+'\n');p.stdin.flush()
    if notification: return None
    while True:
        line=messages.get(timeout=120)
        if line is None: raise RuntimeError('Unexpected server exit')
        response=json.loads(line)  # Any diagnostic on stdout makes this fail.
        wire.append(response)
        if response.get('id')==seq: return response
def call(name,args,error=False):
    response=send('tools/call',{'name':name,'arguments':args})
    assert 'result' in response,response
    result=response['result']
    assert bool(result.get('isError'))==error,result
    payload=json.loads(result['content'][0]['text'])
    assert payload['serialized_characters']==len(result['content'][0]['text'])
    assert len(result['content'][0]['text'])<=payload['character_cap']
    return payload,result
try:
    init=send('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'local-assets-protocol-check','version':'1'}})
    assert init['result']['serverInfo']['name']=='local_asset_library'
    send('notifications/initialized',notification=True)
    listed=send('tools/list')['result']['tools']
    assert {t['name'] for t in listed}=={'search_assets','get_asset'}
    checks.append('initialization and exact two-tool discovery')
    search,_=call('search_assets',{'query':'apple','mode':'keyword'})
    assert 0<len(search['results'])<=5
    candidate=search['results'][0]['asset_id']
    checks.append('keyword search / deterministic search cap')
    details,content=call('get_asset',{'asset_id':candidate,'include_preview':True,'include_metadata':True})
    assert details['usable'] and details['selected_source']['resolved_path']
    img=next(c for c in content['content'] if c['type']=='image')
    blob=base64.b64decode(img['data'],validate=True)
    assert hashlib.sha256(blob).hexdigest()==details['preview']['sha256'] and len(blob)<=512*1024
    (out/'preview.png').write_bytes(blob)
    checks.append('get_asset details, dependencies, real PNG ImageContent')
    for args in [{'asset_id':'../outside.glb'}, {'asset_id':'C:\\outside.glb'},
                 {'asset_id':'\\\\server\\share\\asset.glb'}, {'asset_id':'asset_'+'a'*32},
                 {'asset_id':candidate,'path':'../outside'}, {'asset_id':candidate,'source_format':'exe'}]:
        call('get_asset',args,error=True)
    for args in [{'query':'apple','limit':41},{'query':'apple','limit':True},
                 {'query':'apple','filters':{'format':'../obj'}},{'query':'apple','filters':{'color':'red'}},
                 {'query':'apple','filters':{'pack':'../pack'}},{'query':'x'*1025},
                 {'mode':'reference','reference_asset_id':'data/preview.png'}]:
        call('search_assets',args,error=True)
    call('copy_asset',{},error=True)
    checks.append('malformed IDs, absolute/UNC/traversal/path inputs, unknown tools/filters, caps')
    semantic,_=call('search_assets',{'query':'a small round red apple fruit with a leaf','limit':5})
    assert semantic['mode']=='combined' and semantic['results']
    checks.append('verified embedding worker and approved semantic default')
    p.stdin.close()
    code=p.wait(timeout=20)
    assert code==0,code
    lifecycles=[json.loads(f.read_text()) for f in (root/'data/mcp/runs').glob('*/lifecycle.json')
                if f.parent.name not in existing_runs]
    assert len(lifecycles)==1, 'Expected exactly one new server audit'
    life=lifecycles[0]  # Windows virtual-environment launcher PID differs from Python PID.
    assert life['closed'] and life['worker_returncode']==0
    checks.append('clean EOF shutdown of server and persistent worker')
    report={'status':'passed','checks':checks,'tool_calls':len([r for r in wire if 'result' in r and 'content' in r['result']]),
            'protocol':init['result']['protocolVersion'],'server_pid':p.pid,'lifecycle':life,
            'agent_use':False,'image_bytes':len(blob)}
except Exception as exc:
    report={'status':'faulty','reason':repr(exc),'checks_completed':checks,'agent_use':False}
    if p.poll() is None:
        p.stdin.close()
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:p.kill();p.wait()
finally:
    stderr.close()
    # Large binary blocks excluded from human evidence; original image saved separately.
    for r in wire:
        for c in r.get('result',{}).get('content',[]):
            if c.get('type')=='image':c['data']='<saved PNG; base64 omitted from report>'
    (out/'wire.json').write_text(json.dumps(wire,indent=2)+'\n',encoding='utf-8')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
if report['status']!='passed':raise SystemExit(1)
