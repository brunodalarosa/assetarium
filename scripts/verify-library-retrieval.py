"""Actual STDIO and GUI bridge parity, bounded responses and owned-worker cleanup."""
import argparse
from pathlib import Path
import json
import os
import queue
import subprocess
import sys
import threading
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_asset_library.config import load_config
from local_asset_library.desktop import DesktopBridge
from local_asset_library.membership import records
from local_asset_library.publication import generation
parser=argparse.ArgumentParser();parser.add_argument('--run-name',required=True);parser.add_argument('--keyword-only',action='store_true');args=parser.parse_args()
if not args.run_name.replace('-','').isalnum():raise ValueError('Invalid run name')
out=ROOT/'data/library/verification'/args.run_name;out.mkdir(parents=True,exist_ok=False)
config=load_config(ROOT/'config.example.toml',ROOT)
bridge=DesktopBridge(config)
stderr=(out/'stderr.log').open('w',encoding='utf-8')
server=subprocess.Popen([str(ROOT/'.venv-mcp/Scripts/python.exe'),str(ROOT/'scripts/asset-mcp.py')],cwd=ROOT.parent,
    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
messages=queue.Queue()
def reader():
    for line in server.stdout:messages.put(line)
    messages.put(None)
threading.Thread(target=reader,daemon=True).start()
sequence=0;wire=[]
def send(method,params=None,notification=False):
    global sequence
    message={'jsonrpc':'2.0','method':method}
    if params is not None:message['params']=params
    if not notification:sequence+=1;message['id']=sequence
    server.stdin.write(json.dumps(message)+'\n');server.stdin.flush()
    if notification:return
    while True:
        line=messages.get(timeout=115)
        if line is None:raise RuntimeError('Server exited before response')
        result=json.loads(line);wire.append(result)
        if result.get('id')==sequence:return result['result']
report={'status':'running','generation':generation(config),'membership':len(records(config)),'cases':[],'faults':[],'owner_relevance_approval':'separate'}
try:
    send('initialize',{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'step8-shared-verifier','version':'1'}})
    send('notifications/initialized',notification=True)
    assert {t['name'] for t in send('tools/list')['tools']}=={'search_assets','get_asset'}
    cases=[{'query':'apple','mode':'keyword'}, {'query':'sedan sports','mode':'keyword'},
        {'query':'a small red apple fruit with a leaf'}, {'query':'a wooden chair with a curved back'},
        {'query':'a low-poly green tree','filters':{'pack':'quaternius_ultimate-nature-pack','format':'blend','max_triangles':5000,'rigged':False}},
        {'query':'spaceship laser submarine'}, {'query':'a red apple with a leaf','mode':'image'},
        {'query':'a red apple with a leaf','mode':'combined'},{'query':'a red apple with a leaf','mode':'description'}]
    if args.keyword_only:cases=cases[:2]
    else:
        apple=next(r for r in records(config) if r['pack_id']=='kenney_food-kit' and r['display_name']=='apple')
        cases.append({'mode':'reference','reference_asset_id':apple['asset_id'],'reference_view':'three_quarter'})
    for case in cases:
        arguments={'mode':'keyword_description','filters':{},'limit':5,**case}
        started=time.monotonic();gui=bridge.search(arguments);gui_seconds=time.monotonic()-started
        assert not gui['is_error'],gui
        started=time.monotonic();actual=send('tools/call',{'name':'search_assets','arguments':arguments});mcp_seconds=time.monotonic()-started
        assert not actual.get('isError'),actual
        payload=json.loads(actual['content'][0]['text'])
        assert gui['payload']==payload
        assert len(actual['content'][0]['text'])<=6000 and len(payload['results'])<=5
        assert payload['generation']==report['generation']
        report['cases'].append({'arguments':arguments,'ids':[r['asset_id'] for r in payload['results']],
            'gui_seconds':gui_seconds,'mcp_seconds':mcp_seconds,'characters':len(actual['content'][0]['text']),
            'truncated':payload['truncated'],'fault_count':payload['fault_count'],'whole_payload_equal':True})
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    malformed=send('tools/call',{'name':'search_assets','arguments':{'query':'apple','limit':6}})
    assert malformed.get('isError')
    report['invalid_limit_rejected']=True
    if not args.keyword_only:
        # Actual image transport and current ID membership, without a claim of model image review.
        detail=send('tools/call',{'name':'get_asset','arguments':{'asset_id':apple['asset_id'],'include_preview':True,'include_metadata':True}})
        assert not detail.get('isError') and any(c['type']=='image' for c in detail['content'])
        report['actual_png_transport']=True
    report['status']='passed'
except BaseException as exc:
    report['status']='faulty';report['faults'].append({'type':type(exc).__name__,'reason':str(exc),'traceback':traceback.format_exc()})
finally:
    bridge._close();server.stdin.close()
    report['server_exit']=server.wait(timeout=20);stderr.close()
    report['gui_closed']=not bridge._thread.is_alive()
    (out/'wire.json').write_text(json.dumps(wire,indent=2),encoding='utf-8')
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
sys.exit(report['status']!='passed')
