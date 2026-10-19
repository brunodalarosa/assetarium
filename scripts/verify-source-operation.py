"""Real source coordinator/cancel smoke check using two tiny new cube fixtures."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_asset_library.config import load_config
from local_asset_library.sources import add,remove,bound,scan_source,aggregate,source_status,registry
from local_asset_library.source_operations import start,cancel,operation_status,RUNNING
from local_asset_library.publication import atomic_json

identifier=uuid.uuid4().hex
config=load_config(ROOT/'config.example.toml',ROOT)
aggregate(config)  # Retain/reuse the unchanged real-library projection on detach.
fixture=ROOT.parent/('LAL-source-verification-'+identifier[:10]);fixture.mkdir()
cube='v -1 -1 -1\nv 1 -1 -1\nv 1 1 -1\nv -1 1 -1\nv -1 -1 1\nv 1 -1 1\nv 1 1 1\nv -1 1 1\nf 1 4 3 2\nf 5 6 7 8\nf 1 2 6 5\nf 2 3 7 6\nf 3 4 8 7\nf 4 1 5 8\n'


def gltf_cube():
    # The same cube as a self-contained glTF (embedded buffer), for glTF-only settings.
    import base64,struct
    points=[(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    indices=[i for a,b,c,d in faces for i in (a,b,c,a,c,d)]
    blob=b''.join(struct.pack('<3f',*p) for p in points)+struct.pack('<36H',*indices)
    return json.dumps({'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0}],
        'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1}]}],
        'buffers':[{'byteLength':len(blob),'uri':'data:application/octet-stream;base64,'+base64.b64encode(blob).decode()}],
        'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':96,'target':34962},{'buffer':0,'byteOffset':96,'byteLength':72,'target':34963}],
        'accessors':[{'bufferView':0,'componentType':5126,'count':8,'type':'VEC3','min':[-1,-1,-1],'max':[1,1,1]},
                     {'bufferView':1,'componentType':5123,'count':36,'type':'SCALAR'}]})


# Use a format the saved settings process; unselected formats are scanned but never processed.
from local_asset_library.settings import processing_formats
formats=processing_formats(config)
if not {'obj','gltf'}&set(formats):
    raise SystemExit('Select OBJ or glTF in Settings → General to run this check')
extension,content=('obj',cube) if 'obj' in formats else ('gltf',gltf_cube())
for name in ('cube-one','cube-two'):(fixture/(name+'.'+extension)).write_text(content,encoding='utf-8')
source=add(config,str(fixture));scoped=bound(config,source)
report={'status':'running','fixture':str(fixture),'source':source['key'],'checks':[]}
OUT=ROOT/'data/library/verification'/('source-operation-'+identifier+'.json')


def wait_operation(cancel_current=False):
    deadline=time.monotonic()+900;last=None;requested=False
    while time.monotonic()<deadline:
        operation=operation_status(scoped)
        signature=(operation.get('status'),operation.get('phase'))
        if signature!=last:
            print(json.dumps({'operation':signature,'progress':operation.get('progress')}),flush=True);last=signature
        if cancel_current and not requested and operation.get('stage')=='inspection' and operation.get('current_asset'):
            report['cancel_result']=cancel(scoped);requested=True
        if operation.get('status') not in RUNNING:
            return operation
        time.sleep(.2)
    raise RuntimeError('Source operation did not finish within its verification bound')


try:
    original={p.name:p.read_bytes() for p in fixture.glob('cube-*')}
    scan_source(config,source)
    assert source_status(config,source)['pending']==2
    start(config,'process',source['key'])
    stopped=wait_operation(True);report['cancelled_operation']=stopped
    assert stopped['status']=='cancelled',stopped
    with closing(sqlite3.connect(scoped.output_path('data','library/jobs.sqlite'))) as db:
        assert db.execute("SELECT count(*) FROM jobs WHERE stage='inspection' AND status='complete'").fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM jobs WHERE stage='inspection' AND status='running'").fetchone()[0]==0
    report['checks'].append('Cancel finishes exactly the current inspection and saves its checkpoint')
    assert source_status(config,source)['needs_processing']
    start(config,'process',source['key'])
    completed=wait_operation();report['completed_operation']=completed
    assert completed['status'] in {'complete','complete_with_faults'},completed
    status=source_status(config,source);report['source_status']=status
    assert not status['needs_processing'],status
    assert scoped.output_path('data','library/active.json').exists()
    assert all(p.read_bytes()==original[p.name] for p in fixture.glob('cube-*'))
    with closing(sqlite3.connect(scoped.output_path('data','embeddings/index.sqlite'))) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        report['vectors']=db.execute('SELECT count(*) FROM vectors').fetchone()[0]
        assert report['vectors']==6  # Three image views per cube; importing writes no descriptions.
    assert status['descriptions']['missing']==2,status
    report['checks'].append('Resume reuses completed inspection, processes remaining stages and publishes without descriptions')
    if '--describe' in sys.argv:
        # Optional: loads the local caption model on the GPU for two tiny cubes.
        start(config,'describe',source['key'])
        described=wait_operation();report['describe_operation']=described
        assert described['status'] in {'complete','complete_with_faults'},described
        status=source_status(config,source);report['describe_status']=status
        assert not status['descriptions']['missing'] and not status['needs_processing'],status
        with closing(sqlite3.connect(scoped.output_path('data','embeddings/index.sqlite'))) as db:
            described_vectors=db.execute("SELECT count(*) FROM vectors WHERE channel='description'").fetchone()[0]
        assert described_vectors==status['descriptions']['complete'],(described_vectors,status)
        report['checks'].append('Generate descriptions writes, indexes and publishes descriptions for the source')
    report['checks'].append('Original fixture bytes and published index integrity preserved')
    report['status']='passed'
except BaseException as exc:
    report.update(status='faulty',reason=str(exc))
    raise
finally:
    atomic_json(OUT,report)
    # Detach only this explicitly created verification source; retain all its
    # metadata and evidence, and restore the real 13-source combined catalog.
    if operation_status(scoped).get('status') not in RUNNING:
        remove(config,source['key']);aggregate(config)
        # Its notices stay in the report, not in the owner's notification list.
        from local_asset_library.notifications import load,act
        report['notifications']=[item for item in load(config)['items'] if item['source_id']==source['id']]
        for item in report['notifications']:act(config,'dismiss',item['id'])
        atomic_json(OUT,report)
    print(json.dumps({'status':report['status'],'report':str(OUT),'reason':report.get('reason')},indent=2),flush=True)
