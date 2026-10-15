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
for name in ('cube-one.obj','cube-two.obj'):(fixture/name).write_text(cube,encoding='utf-8')
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
    original={p.name:p.read_bytes() for p in fixture.glob('*.obj')}
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
    assert all(p.read_bytes()==original[p.name] for p in fixture.glob('*.obj'))
    with closing(sqlite3.connect(scoped.output_path('data','embeddings/index.sqlite'))) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        report['vectors']=db.execute('SELECT count(*) FROM vectors').fetchone()[0]
        assert report['vectors']==8  # Three image views and one description per cube.
    report['checks'].append('Resume reuses completed inspection, processes remaining stages and publishes')
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
    print(json.dumps({'status':report['status'],'report':str(OUT),'reason':report.get('reason')},indent=2),flush=True)
