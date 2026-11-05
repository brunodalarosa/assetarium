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
            # Distinct bytes: equal inputs share one result (decision 0023), which test_result_store covers.
            (source / pack / f'item{i}.obj').write_text(f'# {pack} {i}\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
    for path in ('src/local_asset_library/blender_worker.py', 'src/local_asset_library/render_math.py',
                 'src/local_asset_library/caption_backend.py', 'src/local_asset_library/caption_batching.py', 'runtime/caption/uv.lock', 'prompts/caption-v2.txt', 'prompts/caption-v3.txt', 'prompts/caption-v4.txt'):
        target = root / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_text('synthetic contract')
    save_json(root / 'docs/caption-model.json', {'revision': 'synthetic'})
    save_json(root / 'docs/library-membership.json', {'schema_version': 1, 'approved': True, 'packs': ['one','two'], 'approval': 'synthetic'})
    scan(config)
    refresh(config)
    backend = SyntheticBackend()
    save_json(config.output_path('data', 'embeddings/capability.json'), {'contract_fingerprint': digest(backend.contract), 'actual_text_and_image_inference': True})
    return config, backend


def view_image(record, view):
    """A red synthetic view whose bytes differ per asset and view, so descriptions are not shared."""
    image = Image.new('RGB', (32, 32), 'red')
    image.putpixel((0, 0), tuple(bytes.fromhex(record['asset_id'][6:12])))
    image.putpixel((1, 0), (len(view), 0, 0))
    return image


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
            view_image(record, view).save(path)
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


def test_deferred_descriptions_publish_images_and_later_index_text(library):
    config, backend = library
    work = ready(config)
    for item in records(work):
        item.update(description=None, caption_provenance=None)
        item['processing']['caption'] = 'pending'
        update_record(work, item)
    result = index_library(work, backend)
    assert result['processed'] == 18 and result['deferred_descriptions'] == 6
    assert len(backend.calls) == 18
    assert {o['status'] for o in result['outcomes']} == {'complete', 'deferred'}
    assert index_library(work, backend, dry_run=True)['pending'] == 0
    assert index_library(work, backend)['processed'] == 0
    with closing(sqlite3.connect(work.output_path('data', 'embeddings/index.sqlite'))) as db:
        assert db.execute("SELECT COUNT(*) FROM jobs WHERE channel='description'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM jobs WHERE status='failed'").fetchone()[0] == 0
    assert all(r['processing']['embeddings'] == 'partial' for r in records(work))
    assert publish(config)['membership'] == 6
    from local_asset_library.caption_quality import caption_summary
    assert all(caption_summary(config, r)['caption_status'] == 'pending' for r in records(work))
    ready(config)
    resumed = index_library(work, backend)
    assert resumed['processed'] == 6 and resumed['deferred_descriptions'] == 0
    assert len(backend.calls) == 24
    assert all(r['processing']['embeddings'] == 'complete' for r in records(work))
    assert publish(config)['membership'] == 6


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
    from local_asset_library import incremental, render_pool
    render_pool.save(config,1,None)  # Exact attempt order; parallel interruption is covered in test_render_pool.
    attempted=[]
    def fake(config,record,fp,resolution=640,formats=None):
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


def test_reused_results_mark_their_stage_complete_after_a_rescan_reset(library, monkeypatch):
    """Grouping export folders changes an asset's file list, so a rescan resets its stages, while the
    rendered file is unchanged: processing reuses the finished result and must mark it complete again."""
    config, _ = library
    from local_asset_library import incremental
    attempted = []
    monkeypatch.setattr(incremental, 'run_inspection', lambda c, r, fp, resolution=640, formats=None:
                        attempted.append(r['asset_id']) or {'status': 'complete'})
    process(config, 'inspection', 6)
    work = working(config)
    for record in records(work):  # What a finished inspection leaves, then the rescan's reset.
        record.update(inspection_run={'status': 'complete'}, technical={'inspected_path': record['files'][0]['path']},
                      previews=[{'path': 'data/fixture.png', 'view_label': 'front'}])
        record['processing'].update(inspection='pending', previews='pending')
        update_record(work, record)
    count = len(attempted)
    dry = process(config, 'inspection', 6, dry_run=True)
    assert dry['retained'] == {'complete': 6} and dry['pending'] == 0 and dry['restored'] == 6
    assert all(r['processing']['inspection'] == 'pending' for r in records(work))  # A dry run changes nothing.
    result = process(config, 'inspection', 6)
    assert result['retained'] == {'complete': 6} and result['restored'] == 6 and len(attempted) == count  # Nothing rendered.
    assert all(r['processing']['inspection'] == r['processing']['previews'] == 'complete' for r in records(work))
    first = records(work)[0]
    first.update(previews=[])
    first['processing'].update(inspection='pending', previews='pending')
    update_record(work, first)
    process(config, 'inspection', 6)
    again = next(r for r in records(work) if r['asset_id'] == first['asset_id'])
    assert again['processing']['inspection'] == 'pending'  # Without its previews nothing is claimed.

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


def test_new_prompt_keeps_completed_v2_captions_and_new_jobs_use_v4(library):
    config,_=library
    work=ready(config)
    from local_asset_library.incremental import caption_input,seed
    for record in records(work):
        record['caption_provenance']['prompt_version']='v2'
        update_record(work,record)
    seed(work)
    old={r['asset_id']:caption_input(work,r) for r in records(work)}
    (config.project_root/'prompts/caption-v4.txt').write_text('Changed future prompt; 10-170 words')
    assert process(config,'caption',dry_run=True)['retained']=={'complete':6}
    assert all(caption_input(work,r)==old[r['asset_id']] for r in records(work))
    record=records(work)[0]
    record.update(description=None,caption_provenance=None)
    record['processing']['caption']='pending'
    assert caption_input(work,record)==caption_input(work,record,prompt_version='v4')
    assert caption_input(work,record)!=caption_input(work,record,prompt_version='v2')
    # A changed old input needs generation under the active prompt, with a
    # fingerprint that matches the version recorded in the new result.
    (config.project_root/'prompts/caption-v2.txt').write_text('Changed old input')
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
    def faulty(config,record,fp,resolution=640,formats=None):
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


class BatchBackend:
    """Synthetic batched caption backend; never loads a model."""
    contract = {'model_id': 'synthetic', 'revision': 'synthetic'}
    settings = {'seed': 0}
    def __init__(self, outputs, fault_on_batch=None):
        self.outputs, self.batches, self.fault_on_batch = iter(outputs), [], fault_on_batch
    def resources(self):
        return {}
    def generate_batch(self, inputs_list, prompt, max_new_tokens):
        from local_asset_library.caption_batching import GpuMemoryError, memory_message
        self.batches.append(len(inputs_list))
        if len(self.batches) == self.fault_on_batch:
            raise GpuMemoryError(memory_message(len(inputs_list)))
        return [(next(self.outputs), {'elapsed_seconds': 0.01}) for _ in inputs_list]


def pending_captions(config):
    from local_asset_library.incremental import seed
    work = ready(config)
    seed(work)
    for record in records(work):
        record.update(description=None, caption_provenance=None)
        record['processing']['caption'] = 'pending'
        update_record(work, record)
    return work


def test_caption_batches_follow_setting_and_isolate_one_bad_output(library):
    from test_captions import caption
    from local_asset_library.settings import save_general_settings
    config, _ = library
    work = pending_captions(config)
    save_general_settings(config, 8, None, 4)
    good = json.dumps(caption())
    backend = BatchBackend([good, '{}', good, good, good, good])
    result = process(config, 'caption', 6, backend=backend)
    assert backend.batches == [4, 2]
    assert result['complete'] == 5 and result['failed'] == 1
    complete = [r for r in records(work) if r['processing']['caption'] == 'complete']
    assert {r['caption_provenance']['generation_mode'] for r in complete} == {'batched-v1'}
    assert sorted(r['caption_provenance']['batch']['assets'] for r in complete) == [2, 2, 4, 4, 4]
    assert {r['caption_provenance']['batch']['size'] for r in complete} == {4}
    # Finished and failed results are retained; neither is generated again.
    again = process(config, 'caption', dry_run=True)
    assert again['pending'] == 0 and again['retained'] == {'complete': 5, 'failed': 1}


def test_completed_sequential_captions_keep_byte_identical_fingerprints(library):
    from local_asset_library.incremental import caption_input, seed
    config, _ = library
    work = ready(config)
    seed(work)
    before = {r['asset_id']: caption_input(work, r) for r in records(work)}
    assert all(before[r['asset_id']] == caption_input(work, r, generation='sequential') for r in records(work))
    # Editing the batching module never re-queues descriptions made one at a time.
    (config.project_root / 'src/local_asset_library/caption_batching.py').write_text('changed batching')
    assert process(config, 'caption', dry_run=True)['retained'] == {'complete': 6}
    assert all(caption_input(work, r) == before[r['asset_id']] for r in records(work))
    record = records(work)[0]
    record.update(description=None, caption_provenance=None)
    record['processing']['caption'] = 'pending'
    assert caption_input(work, record) == caption_input(work, record, generation='batched-v1')
    assert caption_input(work, record) != caption_input(work, record, generation='sequential')
    with pytest.raises(ConfigError, match='generation mode'):
        caption_input(work, record, generation='parallel')


def test_prompt_line_endings_alone_never_requeue_finished_descriptions(library):
    from local_asset_library.incremental import caption_input, seed
    config, _ = library
    work = ready(config)
    prompt = config.project_root / 'prompts/caption-v4.txt'
    text = b'Describe the three views.\nReturn one JSON object; 10-170 words.\n'
    prompt.write_bytes(text)
    for record in records(work):
        record['caption_provenance'].update(prompt_version='v4', prompt_sha256=file_hash(prompt))
        update_record(work, record)
    seed(work)
    before = {r['asset_id']: caption_input(work, r) for r in records(work)}
    # A git checkout may rewrite LF as CRLF (or back); the model reads the same text.
    for content in (text.replace(b'\n', b'\r\n'), text):
        prompt.write_bytes(content)
        assert process(config, 'caption', dry_run=True)['retained'] == {'complete': 6}
        assert all(caption_input(work, r) == before[r['asset_id']] for r in records(work))
    prompt.write_bytes(text.replace(b'\n', b'\r\n') + b'Changed wording.\r\n')
    assert process(config, 'caption', dry_run=True)['pending'] == 6


def test_gpu_memory_stop_keeps_batch_pending_and_records_no_fault(library):
    from test_captions import caption
    from local_asset_library.caption_batching import GpuMemoryError
    from local_asset_library.settings import save_general_settings
    config, _ = library
    work = pending_captions(config)
    save_general_settings(config, 8, None, 4)
    backend = BatchBackend([json.dumps(caption())] * 6, fault_on_batch=2)
    from local_asset_library.description_engines import MemoryLimitError  # The port's error; adapters translate theirs.
    with pytest.raises(MemoryLimitError, match='batch size 4. Lower it in Settings → General'):
        process(config, 'caption', 6, backend=backend)
    status = json.loads(config.output_path('data', 'library/processing-status.json').read_text(encoding='utf-8'))
    assert status['status'] == 'stopped' and 'GPU memory' in status['reason']
    assert sum(r['processing']['caption'] == 'complete' for r in records(work)) == 4
    assert not any(r['processing']['caption'] == 'failed' for r in records(work))
    resumed = process(config, 'caption', dry_run=True)
    assert resumed['pending'] == 2 and resumed['retained'] == {'complete': 4}


def test_cancel_takes_effect_between_batches(library):
    from test_captions import caption
    from local_asset_library.settings import save_general_settings
    config, _ = library
    pending_captions(config)
    save_general_settings(config, 8, None, 2)
    backend = BatchBackend([json.dumps(caption())] * 6)
    seen = []
    result = process(config, 'caption', 6, backend=backend, cancelled=lambda: bool(backend.batches),
                     progress=lambda identifier, completed, total: seen.append((completed, total)))
    assert result['cancelled'] and backend.batches == [2] and len(result['outcomes']) == 2
    assert seen == [(0, 6), (2, 6)]


def test_code_line_endings_alone_never_requeue_finished_work(library):
    from local_asset_library.incremental import caption_input, checkpoint, inspection_input, seed
    config, _ = library
    work = ready(config)
    code = config.project_root / 'src/local_asset_library'
    files = [code / 'caption_backend.py', code / 'caption_batching.py', config.project_root / 'runtime/caption/uv.lock',
             code / 'blender_worker.py', code / 'render_math.py']
    text = b'first line\nsecond line\n'
    for path in files:
        path.write_bytes(text)
    for record in records(work)[::2]:  # Batched descriptions also hash caption_batching.py.
        record['caption_provenance']['generation_mode'] = 'batched-v1'
        update_record(work, record)
    seed(work)
    with closing(ledger(work)) as db:
        for record in records(work):
            checkpoint(db, record['asset_id'], 'inspection', inspection_input(work, record)[3], 'complete', {})
    def fingerprints():
        return {r['asset_id']: (caption_input(work, r), inspection_input(work, r)[3]) for r in records(work)}
    before = fingerprints()
    # A checkout may rewrite any of these as CRLF (or back); Python and uv read the same text.
    for content in (text.replace(b'\n', b'\r\n'), text):
        for path in files:
            path.write_bytes(content)
            for stage in ('caption', 'inspection'):
                assert process(config, stage, dry_run=True)['retained'] == {'complete': 6}
            assert content == text or fingerprints() != before  # Raw bytes alone would re-queue.
    assert fingerprints() == before
    (code / 'blender_worker.py').write_bytes(text + b'changed\n')
    assert process(config, 'inspection', dry_run=True)['pending'] == 6
    assert process(config, 'caption', dry_run=True)['retained'] == {'complete': 6}
    (config.project_root / 'runtime/caption/uv.lock').write_bytes(text.replace(b'\n', b'\r\n') + b'changed\r\n')
    assert process(config, 'caption', dry_run=True)['pending'] == 6


def test_reused_vectors_record_the_search_data_state_again_after_a_rescan_reset(library):
    """Grouping export folders resets the search data flag while every vector still matches: the dry run must
    report it so the real pass records the state again, instead of the source asking for processing forever."""
    config, backend = library
    work = ready(config)
    index_library(work, backend)
    assert all(r['processing']['embeddings'] == 'complete' for r in records(work))
    for record in records(work):
        record['processing']['embeddings'] = 'pending'
        update_record(work, record)
    calls = len(backend.calls)
    dry = index_library(work, None, dry_run=True)
    assert dry['pending'] == 0 and dry['restored'] == 6
    assert all(r['processing']['embeddings'] == 'pending' for r in records(work))  # A dry run writes nothing.
    result = process(config, 'embeddings', 1000)  # No model is loaded: no vector is missing.
    assert result['processed'] == 0 and result['restored'] == 6 and len(backend.calls) == calls
    assert all(r['processing']['embeddings'] == 'complete' for r in records(work))
    assert index_library(work, None, dry_run=True)['restored'] == 0


def test_kept_faults_show_as_failed_again_after_a_rescan_reset(library, monkeypatch):
    """A rescan resets a kept fault's flags to pending; processing restores the failed state without retrying."""
    config, _ = library
    from local_asset_library import incremental, render_pool
    from local_asset_library.sources import import_outcome
    render_pool.save(config, 1, None)
    attempted = []

    def inspect(work, record, fp, resolution=640, formats=None):
        attempted.append(record['asset_id'])
        if record['display_name'] == 'item0':
            raise RuntimeError('synthetic geometry fault')
        # A render that returned failed: inspection complete, previews failed, as publish records it.
        record.update(technical={'inspected_path': record['files'][0]['path']},
                      inspection_run={'status': 'failed', 'errors': ['Empty or off-frame preview detected'],
                                      'result_path': 'data/fixture/result.json'})
        record['processing'].update(inspection='complete', previews='failed')
        incremental.update_record(work, record)
        return {'status': 'failed', 'result_path': 'fixture/result.json', 'errors': ['Empty or off-frame preview detected']}
    monkeypatch.setattr(incremental, 'run_inspection', inspect)
    assert process(config, 'inspection', 6)['failed'] == 6  # Two raised, four returned a failed render.
    work = working(config)
    before = {r['asset_id']: (dict(r['processing']), r.get('stage_faults')) for r in records(work)}
    for record in records(work):  # What a rescan after grouping leaves.
        record['processing'].update(inspection='pending', previews='pending')
        record.pop('stage_faults', None)
        update_record(work, record)
    assert all(import_outcome(r)['state'] == 'pending' for r in records(work))
    dry = process(config, 'inspection', 6, dry_run=True)
    assert dry['pending'] == 0 and dry['retained'] == {'failed': 6} and dry['restored'] == 6
    result = process(config, 'inspection', 6)
    assert result['restored'] == 6 and len(attempted) == 6  # Nothing was retried.
    for record in records(work):
        processing, faults = before[record['asset_id']]
        assert record['processing'] == processing and import_outcome(record)['state'] == 'failed'
        if record['display_name'] == 'item0':
            assert record['stage_faults']['inspection']['error'] == 'synthetic geometry fault'
    assert process(config, 'inspection', 6, dry_run=True)['restored'] == 0
