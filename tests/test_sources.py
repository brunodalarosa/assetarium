"""Independent synthetic directories cover source visibility and safe processing."""
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import sqlite3

import pytest
from PIL import Image

from test_incremental import library
from local_asset_library.config import ConfigError
from local_asset_library import sources
from local_asset_library.catalog import digest, detail, save_json
from local_asset_library.incremental import working, update_record
from local_asset_library.library_index import index_library
from local_asset_library.membership import records
from local_asset_library.mcp_assets import AssetService
from local_asset_library.desktop_service import DesktopService
from local_asset_library.source_operations import ensure_index, publish_source, state, cancel, cancelled, active_operation


@pytest.fixture
def managed(tmp_path):
    legacy, backend = library.__wrapped__(tmp_path)
    config = replace(legacy, source_root=tmp_path / 'managed-sources',
                     sources_registry=legacy.project_root / 'data/library/sources.json')
    one = sources.add(config, str(legacy.source_root / 'one'))
    two = sources.add(config, str(legacy.source_root / 'two'))
    sources.aggregate(config)
    return config, backend, one, two


def ready_source(config, backend, source):
    from local_asset_library.captions import file_hash
    sources.scan_source(config, source)
    scoped = sources.bound(config, source)
    work = working(scoped)
    ensure_index(config, scoped)
    for r in records(work):
        r['technical'] = {'inspected_path': r['files'][0]['path'], 'inspected_sha256': r['files'][0]['sha256'],
                          'inspected_format': 'obj', 'evaluated_instance_totals': {'triangles': 1}, 'armatures': []}
        r['description'] = {'identity': {'label':'item','certainty':'probable'}, 'description':'A red synthetic triangular object. ' * 18,
                            'shape':['triangle'], 'colors':['red'], 'parts':['body'], 'style':['stylized'],
                            'distinguishing_features':[], 'uncertainties':[]}
        r['processing'].update(inspection='complete', previews='complete', caption='complete')
        r['previews'] = []
        for view in ('front','side','three_quarter'):
            relative = f'inspection/{r["asset_id"]}/obj/fixture/{view}.png'
            path = work.output_path('data',relative);path.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB',(32,32),'red').save(path)
            r['previews'].append({'path':'data/'+relative,'sha256':file_hash(path),'view_label':view,
                                  'origin':'rendered','coordinate_convention':'synthetic'})
        r['caption_provenance']={'fingerprint':'synthetic','input_views':[],'visual_faults':[]}
        update_record(work,r)
    with closing(sqlite3.connect(work.output_path('data','embeddings/index.sqlite'))) as db, db:
        from local_asset_library.catalog import encoded
        db.executemany('INSERT OR REPLACE INTO meta VALUES (?,?)', [('contract',encoded(backend.contract)),('contract_fingerprint',encoded(digest(backend.contract)))])
    index_library(work,backend)
    publish_source(scoped)
    sources.aggregate(config)
    sources.scan_source(config,source)
    return work


def test_independent_roots_and_source_owned_results(managed):
    config,backend,one,two=managed
    work=ready_source(config,backend,one)
    ready_source(config,backend,two)
    assert len(records(config))==6
    r=records(work)[0]
    preview=config.output_path('data',r['previews'][0]['path'][5:])
    assert preview.is_relative_to(Path(one['path'])/'metadata-lal')
    assert config.source_file(r['files'][0]['path']).parent==Path(one['path'])
    assert not sources.source_status(config,one)['needs_processing']
    with pytest.raises(ConfigError):config.source_file(one['key']+'/metadata-lal/source.json')


def test_live_toggle_and_agent_gui_agreement(managed):
    config,backend,one,two=managed
    ready_source(config,backend,one);ready_source(config,backend,two)
    desktop,agent=DesktopService(config),AssetService(config)
    r=records(config)[0];key=r['pack_id']
    before=desktop.context()['sources_revision']
    sources.set_enabled(config,key,False)
    assert len(desktop.browse()['items'])==3
    from local_asset_library.retrieval import SearchEngine
    result,_=SearchEngine(config,backend).search('item',mode='combined')
    assert all(r['pack']!=key for r in result['results'])
    assert before!=desktop.context()['sources_revision']
    with pytest.raises(ConfigError):agent.record(r['asset_id'])
    sources.set_enabled(config,key,True)
    assert len(desktop.browse()['items'])==6
    assert agent.record(r['asset_id'])['asset_id']==r['asset_id']
    sources.set_enabled(config,one['key'],False);sources.set_enabled(config,two['key'],False)
    assert not desktop.browse()['items']
    result,_=SearchEngine(config,backend).search('item',mode='combined')
    assert not result['results']


def test_scan_add_change_remove_and_card_until_published(managed):
    config,backend,one,_=managed
    work=ready_source(config,backend,one)
    new=Path(one['path'])/'new.obj';new.write_text('v 0 0 0\n')
    status=sources.scan_source(config,one)
    assert status['pending']==1 and status['needs_processing']
    assert len(records(config))==3
    # Merely finishing processing is insufficient: the final scan must also see
    # publication. This helper performs all three steps.
    ready_source(config,backend,one)
    assert len(records(config))==4
    target=Path(one['path'])/'item0.obj';target.write_text('v 0 0 2\n')
    assert sources.scan_source(config,one)['needs_processing']
    assert len(records(config))==3
    new.unlink()
    sources.scan_source(config,one)
    assert len(records(config))==2
    assert (Path(one['path'])/'metadata-lal').is_dir()


def test_remove_and_readd_preserves_identity_and_generated_files(managed):
    config,backend,one,_=managed
    ready_source(config,backend,one)
    ids={r['asset_id'] for r in records(config)}
    sources.remove(config,one['key'])
    assert not records(config)
    restored=sources.add(config,one['path'])
    assert restored['id']==one['id']
    assert {r['asset_id'] for r in records(config)}==ids


def test_source_boundary_and_overlap_rejections(managed,tmp_path):
    config,_,one,_=managed
    for path in (one['path'],str(Path(one['path'])/'nested'),str(config.project_root)):
        Path(path).mkdir(exist_ok=True)
        with pytest.raises(ConfigError):sources.add(config,path)
    with pytest.raises(ConfigError):config.source_file(one['key']+'/../two/item0.obj')
    with pytest.raises(ConfigError):sources.bound(config,one).output_path('data','../escape')


def test_cancel_request_preserves_current_operation(managed):
    import os
    config,_,one,_=managed;scoped=sources.bound(config,one)
    state(scoped,token='fixture',pid=os.getpid(),status='processing',progress=.4)
    assert active_operation(scoped)
    cancel(scoped)
    assert cancelled(scoped,'fixture') and not cancelled(scoped,'different-run')
    assert active_operation(scoped)  # Cancel requests do not kill the worker.
    with pytest.raises(ConfigError):sources.remove(config,one['key'])
    state(scoped,status='cancelled')
    assert not active_operation(scoped)


def test_empty_source_and_metadata_are_excluded_from_scans(managed,tmp_path):
    config,_,_,_=managed
    root=tmp_path/'empty-source';root.mkdir()
    source=sources.add(config,str(root))
    (root/'metadata-lal'/'invented.obj').write_text('not an original')
    result=sources.scan_source(config,source)
    assert result['assets']==0 and not result['needs_processing']
    assert not records(working(sources.bound(config,source)))


def test_cancellation_finishes_current_inspection_and_checkpoints(managed,monkeypatch):
    from local_asset_library import incremental
    config,_,one,_=managed
    sources.scan_source(config,one);scoped=sources.bound(config,one)
    stop=[False];finished=[]
    def inspect(work,record,*args):
        finished.append(record['asset_id'])
        record['processing']['inspection']='complete'
        incremental.update_record(work,record)
        return {'status':'complete'}
    def progress(identifier,completed,total):
        if identifier is None and completed==1:stop[0]=True
    monkeypatch.setattr(incremental,'run_inspection',inspect)
    result=incremental.process(scoped,'inspection',cancelled=lambda:stop[0],progress=progress)
    assert len(finished)==1 and result['cancelled']
    with closing(incremental.ledger(scoped)) as db:
        assert db.execute("SELECT count(*) FROM jobs WHERE status='complete'").fetchone()[0]==1
    assert sources.source_status(config,one)['needs_processing']


def test_cancel_embeddings_saves_all_views_of_current_asset(managed):
    config,backend,one,_=managed
    work=ready_source(config,backend,one)
    with closing(sqlite3.connect(work.output_path('data','embeddings/index.sqlite'))) as db, db:
        db.execute('DELETE FROM vectors');db.execute('DELETE FROM jobs')
    stop=[False]
    def progress(identifier,completed,total):
        if identifier is None and completed==1:stop[0]=True
    result=index_library(work,backend,cancelled=lambda:stop[0],progress=progress)
    with closing(sqlite3.connect(work.output_path('data','embeddings/index.sqlite'))) as db:
        assert db.execute('SELECT count(DISTINCT asset_id) FROM vectors').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM vectors').fetchone()[0]==4
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_migration_preserves_identities_pixels_vectors_and_originals(tmp_path,monkeypatch):
    from test_incremental import ready
    from local_asset_library.incremental import publish
    from local_asset_library.source_migration import migrate
    import local_asset_library.source_storage as storage
    legacy,backend=library.__wrapped__(tmp_path)
    work=ready(legacy)
    # Use the actual production inspection layout, rather than the legacy test
    # suite's separate test-views fixture directory.
    for record in records(work):
        for preview in record['previews']:
            old=work.output_path('data',preview['path'][5:])
            rel='inspection/'+record['asset_id']+'/fixture/'+old.name
            target=work.output_path('data',rel);target.parent.mkdir(parents=True,exist_ok=True);old.rename(target)
            preview['path']='data/'+rel
        update_record(work,record)
    index_library(work,backend);publish(legacy)
    before_ids={r['asset_id'] for r in records(legacy)}
    with closing(sqlite3.connect(legacy.output_path('data','embeddings/index.sqlite'))) as db:
        before_vectors=dict(db.execute('SELECT job_id,vector_sha256 FROM vectors'))
    monkeypatch.setattr(storage,'receipt',lambda *args:{'totals':{'allocated_bytes':0}})
    config,report=migrate(legacy)
    assert report['status']=='passed' and report['originals_unchanged']
    assert before_ids=={r['asset_id'] for r in records(config)}
    with closing(sqlite3.connect(config.output_path('data','embeddings/index.sqlite'))) as db:
        assert before_vectors==dict(db.execute('SELECT job_id,vector_sha256 FROM vectors'))
    for source in sources.registry(config)['sources']:
        assert not sources.source_status(config,source)['needs_processing']
    with pytest.raises(ConfigError):migrate(config)


def test_atomic_metadata_writer_supports_long_source_paths(tmp_path):
    from local_asset_library.publication import atomic_json,read_json,filesystem_path
    target=tmp_path/('long-source-'+'a'*55)/('metadata-'+'b'*55)/('history-'+'c'*55)/('report-'+'d'*55+'.json')
    atomic_json(target,{'preserved':'evidence'})
    assert read_json(target)=={'preserved':'evidence'}
    import importlib.util
    spec=importlib.util.spec_from_file_location('source_storage_test',Path(__file__).parents[1]/'scripts/storage-report.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.measure(tmp_path)['status']=='passed'


def test_queued_operation_can_cancel_without_acquiring_processing_lock(managed):
    import os
    from local_asset_library.gpu_queue import lease
    from local_asset_library.source_operations import operation_lease
    config,_,one,_=managed;scoped=sources.bound(config,one)
    state(scoped,token='queued-fixture',pid=os.getpid(),status='queued',progress=0)
    cancel(scoped)
    with lease(config,'held-fixture',resource='operations'):
        with operation_lease(config,scoped,'queued-fixture') as acquired:
            assert not acquired
    assert not active_operation(scoped)


def test_caption_publication_stores_logical_owner_overlay_path(managed,monkeypatch):
    from local_asset_library.incremental import run_caption
    import local_asset_library.incremental as incremental
    import local_asset_library.captions as captions
    config,backend,one,_=managed;work=ready_source(config,backend,one)
    record=records(work)[0]
    outcome={'status':'complete','description':record['description'],'suggested_uses':[], 'attempts':[]}
    monkeypatch.setattr(incremental,'infer_caption',lambda *args,**kwargs:outcome)
    backend.settings={}
    result=run_caption(work,record,'a'*64,backend)
    published=detail(work,record['asset_id'])
    assert published['processing']['caption']=='complete'
    assert published['caption_provenance']['owner_overlay_path']==f'data/captions/corrections/{record["asset_id"]}.json'
    assert work.output_path('data',published['caption_provenance']['owner_overlay_path'][5:]).exists()


def test_combined_publication_is_reused_after_removing_and_readding_source(managed):
    from local_asset_library.publication import generation
    config,backend,one,two=managed
    ready_source(config,backend,one);ready_source(config,backend,two)
    original=generation(config)
    sources.remove(config,one['key']);sources.aggregate(config)
    assert generation(config)!=original
    sources.add(config,one['path']);result=sources.aggregate(config)
    assert result['reused'] and generation(config)==original


def test_unavailable_source_is_not_recreated_and_other_sources_continue(managed,tmp_path):
    from local_asset_library.source_operations import scan_all,start
    config,backend,one,two=managed
    ready_source(config,backend,one);ready_source(config,backend,two)
    original=Path(one['path']);moved=tmp_path/'temporarily-unavailable'
    original.rename(moved)
    scan_all(config,'missing-source-check')
    assert not original.exists()
    assert sources.source_status(config,one)['scan_fault']
    assert len(records(config))==3
    with pytest.raises(ConfigError):start(config,'process',one['key'])
    assert not original.exists()
    moved.rename(original)
    scan_all(config,'returned-source-check')
    assert not sources.source_status(config,one).get('scan_fault')
    assert list((config.project_root/'data/library/source-faults/history').glob(one['id']+'-*.json'))
    assert len(records(config))==6
