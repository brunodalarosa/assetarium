"""Small synthetic sources exercise updates, checkpoints and publication boundaries."""
from contextlib import closing
from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest
from PIL import Image

from test_retrieval import SyntheticBackend
from local_asset_library.catalog import scan, read_database, save_json, detail, digest
from local_asset_library.config import Config, ConfigError
from local_asset_library.incremental import refresh, working, process, publish, update_record, coverage, ledger
from local_asset_library.library_index import index_library
from local_asset_library.membership import records
from local_asset_library.publication import snapshot, generation
from local_asset_library.desktop_service import DesktopService
from local_asset_library.mcp_assets import AssetService
from local_asset_library.retrieval import description_input
from local_asset_library.captions import file_hash


@pytest.fixture
def library(tmp_path):
    root, source = tmp_path / 'project', tmp_path / 'sources'
    root.mkdir(); source.mkdir()
    config = Config(root, source, None)
    for pack in ('one', 'two'):
        (source / pack).mkdir()
        for i in range(3):
            (source / pack / f'item{i}.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
    for path in ('src/local_asset_library/blender_worker.py', 'src/local_asset_library/render_math.py',
                 'src/local_asset_library/caption_backend.py', 'runtime/caption/uv.lock', 'prompts/caption-v2.txt'):
        target = root / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('synthetic contract')
    save_json(root / 'docs/caption-model.json', {'revision': 'synthetic'})
    save_json(root / 'docs/library-membership.json', {'schema_version': 1, 'approved': True, 'packs': ['one','two'], 'approval': 'synthetic'})
    scan(config)
    refresh(config)
    backend = SyntheticBackend()
    save_json(config.output_path('data', 'embeddings/capability.json'), {'contract_fingerprint': digest(backend.contract), 'actual_text_and_image_inference': True})
    return config, backend


def ready(config):
    work = working(config)
    for record in records(work):
        record['processing'].update(inspection='complete', caption='complete', previews='complete')
        record['technical'] = {'inspected_path': record['files'][0]['path'], 'inspected_sha256': record['files'][0]['sha256'], 'inspected_format':'obj', 'evaluated_instance_totals': {'triangles':1}, 'armatures':[]}
        record['description'] = {'identity': {'label':'item','certainty':'probable'}, 'description':'A red synthetic triangular object. ' * 18, 'shape':['triangle'], 'colors':['red'], 'parts':['body'], 'style':['stylized'], 'distinguishing_features':[], 'uncertainties':[]}
        record['suggested_uses'] = []
        record['previews'] = []
        for view in ('front','side','three_quarter'):
            relative = f'test-views/{record["asset_id"]}-{view}.png'
            path = config.output_path('data',relative); path.parent.mkdir(parents=True,exist_ok=True)
            Image.new('RGB',(32,32),'red').save(path)
            record['previews'].append({'path':'data/'+relative,'sha256':file_hash(path),'view_label':view,'origin':'rendered','coordinate_convention':'synthetic'})
        record['caption_provenance']={'fingerprint':'synthetic','input_views':[], 'visual_faults':[]}
        update_record(work,record)
    return work


def test_membership_change_deletion_rename_and_preserved_overlay(library):
    config, _ = library
    work = working(config)
    record = records(work)[0]
    overlay = config.output_path('data',f'captions/corrections/{record["asset_id"]}.json')
    save_json(overlay, {'schema_version':1,'caption_review':'approved','artistic_suitability':'pending','description':{},'suggested_uses':None,'notes':''})
    before=overlay.read_bytes()
    source=config.source_file(record['files'][0]['path'])
    source.rename(source.with_name('renamed.obj'))
    report=refresh(config)
    assert record['asset_id'] in report['deleted'] and len(report['added'])==1
    assert overlay.read_bytes()==before
    assert len(records(work))==6
    source.with_name('renamed.obj').unlink()
    assert len(refresh(config)['deleted'])==1 and len(records(work))==5
    contract=json.loads((config.project_root/'docs/library-membership.json').read_text());contract['packs']=[p for p in ('one','two') if p!=record['pack_id']]
    save_json(config.project_root/'docs/library-membership.json',contract)
    assert refresh(config)['membership']==3


def test_vector_nochange_severity_owner_and_content_invalidation(library):
    config, backend=library
    work=ready(config)
    first=index_library(work,backend)
    calls=len(backend.calls)
    assert first['processed']==24
    record=records(work)[0]
    record['caption_provenance']['visual_faults']=[{'severity':'review_note','evidence':'Uncertain count','reason':'Minor precision'}]
    record['previews'][0]['visual_review']={'owner_artistic_approval':'approved','technical':'passed'}
    update_record(work,record)
    path=config.output_path('data',f'captions/corrections/{record["asset_id"]}.json')
    save_json(path,{'schema_version':1,'caption_review':'approved','artistic_suitability':'pending','description':{},'suggested_uses':None,'notes':''})
    assert index_library(work,backend)['processed']==0 and len(backend.calls)==calls
    record['description']['description']='An effective changed red observation. ' * 18
    update_record(work,record)
    assert index_library(work,backend)['processed']==1 and len(backend.calls)==calls+1
    backend.contract={**backend.contract,'revision':'changed-test-contract'}
    save_json(config.output_path('data','embeddings/capability.json'),{'contract_fingerprint':digest(backend.contract),'actual_text_and_image_inference':True})
    assert index_library(work,backend)['processed']==24


def test_vector_interruption_and_no_unchanged_fault_retry(library):
    config,backend=library
    work=ready(config)
    original=backend.text
    attempts=[]
    def interrupted(text,role='query'):
        attempts.append(text)
        if len(attempts)==2:raise KeyboardInterrupt('synthetic interruption')
        return original(text,role)
    backend.text=interrupted
    with pytest.raises(KeyboardInterrupt):index_library(work,backend)
    with closing(sqlite3.connect(work.output_path('data','embeddings/index.sqlite'))) as db:
        assert db.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]==4
        assert db.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0]==1
    backend.text=original
    result=index_library(work,backend)
    assert sum(o['reused'] for o in result['outcomes'])==4
    row=records(work)[0]
    config.source_file(row['files'][0]['path']).write_bytes(b'changed synthetic source')
    calls=len(backend.calls)
    failed=index_library(work,backend)
    assert sum(o['status']=='failed' for o in failed['outcomes'])==4
    assert index_library(work,backend)['processed']==0 and len(backend.calls)==calls


def test_corruption_isolated_and_not_reinferred(library):
    config,backend=library;work=ready(config);index_library(work,backend)
    with closing(sqlite3.connect(work.output_path('data','embeddings/index.sqlite'))) as db,db:
        db.execute("UPDATE vectors SET vector_sha256='corrupt' WHERE job_id=(SELECT job_id FROM vectors LIMIT 1)")
    calls=len(backend.calls)
    result=index_library(work,backend)
    assert sum(o['status']=='failed' for o in result['outcomes'])==1
    assert len(backend.calls)==calls
    assert index_library(work,backend)['processed']==0


def test_atomic_publication_pins_requests_and_shared_parity(library):
    config,backend=library;work=ready(config);index_library(work,backend)
    first=publish(config)
    with snapshot(config):
        assert generation(config)==first['generation']
        record=records(work)[0];record['display_name']='New presentation';update_record(work,record)
        second=publish(config)
        assert generation(config)==first['generation']
    assert generation(config)==second['generation']
    gui=DesktopService(config);mcp=AssetService(config)
    args={'query':'item','mode':'keyword','filters':{},'limit':5}
    assert gui.execute('search_assets',args)[0]==mcp.execute('search_assets',args)[0]
    assert gui.asset(record['asset_id'],expected_version=first['generation'])['status']=='stale'
    assert gui.browse(page_size=2)['total_count']==6
    assert len(gui.browse(offset=2,page_size=2)['items'])==2


def test_stage_checkpoint_failure_and_resume(library,monkeypatch):
    config,_=library
    from local_asset_library import incremental
    attempted=[]
    def fake(config,record,fp,resolution=640):
        attempted.append(record['asset_id'])
        if len(attempted)==2:raise RuntimeError('synthetic asset fault')
        if len(attempted)==3:raise KeyboardInterrupt('stop')
        return {'status':'complete','synthetic':True}
    monkeypatch.setattr(incremental,'run_inspection',fake)
    with pytest.raises(KeyboardInterrupt):process(config,'inspection',6)
    result=process(config,'inspection',6)
    assert result['retained']=={'complete':1,'failed':1}
    assert len(attempted)==7
    assert process(config,'inspection',6)['selected']==0


def test_dependency_changes_and_dry_run(library):
    config,_=library
    path=config.source_root/'one/item0.obj'
    path.write_text('mtllib item.mtl\nv 0 0 0\n')
    (path.parent/'item.mtl').write_text('newmtl one\nKd 1 0 0\n')
    before=working(config).output_path('data','catalog.sqlite').read_bytes()
    dry=refresh(config,True)
    assert dry['changed'] and before==working(config).output_path('data','catalog.sqlite').read_bytes()
    refresh(config)
    (path.parent/'item.mtl').write_text('newmtl one\nKd 0 1 0\n')
    assert refresh(config)['changed']


def test_larger_browse_bounds_without_hashing_every_asset(library,monkeypatch):
    config,backend=library
    for i in range(300):
        (config.source_root/'one'/f'extra{i}.obj').write_text('v 0 0 0\n')
    refresh(config)
    work=working(config)
    # Empty vectors are allowed for explicit partial publication.
    index_library(work,backend,limit=1000)
    publish(config)
    from local_asset_library import desktop_service
    checked=[]
    original=desktop_service.source_check
    def trace(config,record):checked.append(record['asset_id']);return original(config,record)
    monkeypatch.setattr(desktop_service,'source_check',trace)
    result=DesktopService(config).browse(offset=80,page_size=40)
    assert result['total_count']==306 and len(result['items'])==40 and len(checked)==40
    with pytest.raises(ConfigError):DesktopService(config).browse(page_size=101)


def test_publication_rejects_stale_overlay_and_nochange_is_stable(library):
    config,backend=library;work=ready(config);index_library(work,backend)
    first=publish(config)
    calls=len(backend.calls)
    assert index_library(work,backend)['processed']==0
    assert publish(config)['generation']==first['generation']
    assert len(backend.calls)==calls
    record=records(work)[0]
    correction={'schema_version':1,'description':{'description':'An owner corrected red object. '*18},
                'suggested_uses':None,'caption_review':'pending','artistic_suitability':'pending','notes':''}
    save_json(config.output_path('data',f'captions/corrections/{record["asset_id"]}.json'),correction)
    with pytest.raises(ConfigError,match='Effective description changed'):publish(config)
    assert generation(config)==first['generation']
    assert index_library(work,backend)['processed']==1
    assert publish(config)['generation']!=first['generation']


def test_caption_settings_are_independent_from_owner_and_budget(library):
    config,_=library;work=ready(config)
    from local_asset_library.incremental import caption_input,seed
    seed(work)
    before=process(config,'caption',dry_run=True)
    assert before['pending']==0 and before['retained']=={'complete':6}
    model=config.project_root/'docs/caption-model.json'
    value=json.loads(model.read_text());value.update(license='metadata only',model_budget_bytes=1,official_sources=['metadata'])
    save_json(model,value)
    record=records(work)[0]
    record['caption_provenance']['visual_faults']=[{'severity':'warning','evidence':'Synthetic meaningful claim','reason':'Selection could be misled'}]
    update_record(work,record)
    assert process(config,'caption',dry_run=True)['pending']==0
    assert process(config,'inspection',dry_run=True)['pending']==6
    value['revision']='new-model-contract';save_json(model,value)
    assert process(config,'caption',dry_run=True)['pending']==6


def test_source_changes_are_reverified_between_requests_even_with_restored_mtime(library):
    config,backend=library;work=ready(config);index_library(work,backend);publish(config)
    service=AssetService(config)
    args={'query':'item','mode':'keyword','filters':{},'limit':5}
    first=service.execute('search_assets',args)[0]
    record=records(config)[0]
    path=config.source_file(record['files'][0]['path']);original=path.read_bytes();stamp=path.stat()
    changed=original.replace(b'v 1 0 0',b'v 2 0 0')
    path.write_bytes(changed)
    import os
    os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
    second=service.execute('search_assets',args)[0]
    assert record['asset_id'] not in {r['asset_id'] for r in second['results']}
    assert second['fault_count']>=1


def test_gpu_lease_is_bounded_and_released(library):
    config,_=library
    from local_asset_library.gpu_queue import lease
    with lease(config,'synthetic-owner',timeout=0):
        with pytest.raises(ConfigError,match='queue busy'):
            with lease(config,'second-owner',timeout=0):pass
    with lease(config,'after-release',timeout=0):pass


def test_settings_change_does_not_retry_unchanged_source_fault(library,monkeypatch):
    config,_=library
    from local_asset_library import incremental
    calls=[]
    def faulty(config,record,fp,resolution=640):
        calls.append(record['asset_id'])
        raise RuntimeError('unchanged synthetic geometry fault')
    monkeypatch.setattr(incremental,'run_inspection',faulty)
    first=process(config,'inspection',6)
    assert first['failed']==6 and len(calls)==6
    later=process(config,'inspection',6,resolution=960)
    assert later['selected']==0 and later['retained']=={'failed':6} and len(calls)==6
    path=config.source_root/'one/item0.obj';path.write_text('v 2 0 0\n')
    refresh(config)
    assert process(config,'inspection',6,resolution=960)['selected']==1


def test_library_review_writer_preserves_results_owner_and_vectors(library,monkeypatch):
    import runpy
    import sys
    from local_asset_library import config as config_module
    config,backend=library;work=ready(config)
    record=records(work)[0]
    result_path=config.output_path('data',f'captions/library/{record["asset_id"]}/synthetic.json')
    record['caption_provenance']['result_path']='data/'+result_path.relative_to(config.project_root/'data').as_posix()
    save_json(result_path,{'status':'complete','description':record['description'],'suggested_uses':[],
                          'provenance':record['caption_provenance']})
    update_record(work,record)
    index_library(work,backend)
    calls=len(backend.calls);raw=result_path.read_bytes()
    notes=config.output_path('data','review-input.json')
    save_json(notes,{'scope':'synthetic review only','assets':{record['asset_id']:{'observations':'Synthetic red shape agrees.',
        'findings':[{'severity':'review_note','evidence':'Exact facet count is uncertain.','reason':'Minor precision.'}]}}})
    monkeypatch.setattr(config_module,'load_config',lambda *_:config)
    monkeypatch.setattr(sys,'argv',['record_caption_review.py','library','--notes',str(notes)])
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/record_caption_review.py'),run_name='__main__')
    assert stopped.value.code==0
    from local_asset_library.caption_quality import caption_summary
    current=detail(work,record['asset_id'])
    assert caption_summary(work,current)['caption_status']=='review_note'
    assert result_path.read_bytes()==raw
    assert index_library(work,backend)['processed']==0 and len(backend.calls)==calls
    saved=list(config.output_path('data','library/reviews').glob('*.json'))
    assert len(saved)==1 and json.loads(saved[0].read_text())['receipts'][0]['original_provenance']==record['caption_provenance']


def test_verified_source_metadata_change_rebinds_without_embedding(library):
    config,backend=library;work=ready(config);index_library(work,backend)
    record=records(work)[0];calls=len(backend.calls)
    source=config.source_root/record['pack_id']/'alternate.obj'
    source.write_text('v 1 0 0\n')
    record['files'].append({'path':source.relative_to(config.source_root).as_posix(),'format':'obj','sha256':file_hash(source),'availability':'available'})
    update_record(work,record)
    result=index_library(work,backend)
    assert result['processed']==0 and len(backend.calls)==calls
    assert all(o['reused'] for o in result['outcomes'])


def test_batch_busy_does_not_start_or_fault_search_worker(library):
    import asyncio
    from local_asset_library.gpu_queue import lease
    from local_asset_library.mcp_server import Gateway
    config,_=library
    gateway=Gateway(config)
    with lease(config,'batch-synthetic',timeout=0):
        with pytest.raises(ConfigError,match='queue busy'):
            asyncio.run(gateway.semantic('search_assets',{'query':'item'}))
        assert gateway.worker is None and gateway.worker_fault is None
    asyncio.run(gateway.close())


def test_unrelated_publication_keeps_unchanged_preview_fault(library,monkeypatch):
    config,backend=library;work=ready(config)
    record=records(work)[0]
    record['previews']=[p for p in record['previews'] if p['view_label']!='three_quarter']
    update_record(work,record);index_library(work,backend);publish(config)
    service=DesktopService(config);calls=[];original=service.preview
    def traced(record,view):calls.append(view);return original(record,view)
    monkeypatch.setattr(service,'preview',traced)
    first=service.asset(record['asset_id'])
    assert first['payload']['preview']['status']=='faulty'
    record['display_name']='Changed presentation metadata';update_record(work,record);publish(config)
    second=service.asset(record['asset_id'])
    assert second['payload']['preview']['status']=='faulty' and calls==['three_quarter']
    assert second['payload']['presentation']['name']=='Changed presentation metadata'


def test_corrupt_catalog_item_isolated_without_repair(library):
    config,backend=library;work=ready(config);index_library(work,backend)
    record=records(work)[0]
    with closing(sqlite3.connect(work.output_path('data','catalog.sqlite'))) as db,db:
        db.execute('UPDATE assets SET record=? WHERE asset_id=?',('{broken JSON',record['asset_id']))
    items=records(work)
    bad=next(r for r in items if r['asset_id']==record['asset_id'])
    assert bad['availability']=='faulty' and bad['description'] is None and bad['metadata_fault']['raw_record_sha256']
    payload=AssetService(work).execute('search_assets',{'query':'item','mode':'keyword','limit':5})[0]
    assert record['asset_id'] not in {r['asset_id'] for r in payload['results']} and payload['fault_count']==1
    assert len(DesktopService(work).browse()['items'])==6
    with closing(sqlite3.connect(work.output_path('data','catalog.sqlite'))) as db:
        assert db.execute('SELECT record FROM assets WHERE asset_id=?',(record['asset_id'],)).fetchone()[0]=='{broken JSON'


def test_unknown_or_unbound_measurements_do_not_qualify(library):
    config,_=library;work=ready(config)
    from local_asset_library.retrieval import matches
    record=records(work)[0]
    assert matches(record,{'max_triangles':2,'rigged':False})
    record['technical']['armatures']=None
    assert not matches(record,{'rigged':False})
    record['technical']['inspected_sha256']='not-bound'
    assert not matches(record,{'max_triangles':100})


def test_dead_worker_status_is_interrupted_without_reprocessing(library,monkeypatch):
    config,backend=library
    work=ready(config);index_library(work,backend)
    from local_asset_library import gpu_queue
    save_json(config.output_path('data','library/processing-status.json'),
              {'status':'running','stage':'caption','pid':12345,'completed':2,'selected':6})
    monkeypatch.setattr(gpu_queue,'process_alive',lambda pid:False)
    status=DesktopService(work).context()['processing_status']
    assert status['status']=='interrupted' and status['completed']==2
    assert json.loads(config.output_path('data','library/processing-status.json').read_text())['status']=='running'
