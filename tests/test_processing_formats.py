"""Format preferences gate work while retaining complete inventory and results."""
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import sqlite3

import pytest

from test_incremental import library, ready
from test_sources import managed, ready_source
from test_overnight import overnight
from local_asset_library import sources, source_operations, incremental
from local_asset_library.catalog import detail
from local_asset_library.config import ConfigError
from local_asset_library.inspection import choose_source
from local_asset_library.incremental import working, process, inspection_input, update_record
from local_asset_library.library_index import index_library
from local_asset_library.membership import records
from local_asset_library.publication import atomic_json
from local_asset_library.settings import (GIB, processing_formats, general_settings, save_general_settings,
                                          settings_path, processing_eligible)


def select(config, formats):
    return save_general_settings(config, 24, formats)


def test_legacy_defaults_roundtrip_pause_and_storage_only_save(library):
    config, _ = library
    atomic_json(settings_path(config), {'schema_version': 1, 'storage_budget_bytes': 24 * GIB})
    assert processing_formats(config) == ['fbx', 'gltf', 'obj']
    assert select(config, ['gltf'])['processing_formats'] == ['gltf']
    assert save_general_settings(config, 25)['processing_formats'] == ['gltf']
    rebound = replace(config, source_key='one', metadata_root=config.source_root / 'one/metadata-lal')
    assert processing_formats(rebound) == ['gltf']
    select(config, [])
    assert general_settings(config)['processing_formats'] == []


@pytest.mark.parametrize('formats', ['gltf', ['glb'], ['blend'], ['gltf', 'gltf'], [True], {}, False])
def test_invalid_format_settings_preserve_the_saved_file(library, formats):
    config, _ = library
    select(config, ['obj'])
    before = settings_path(config).read_bytes()
    with pytest.raises(ConfigError, match='checkboxes'):
        select(config, formats)
    assert settings_path(config).read_bytes() == before


def test_source_selection_filters_alternates_and_pilot_override():
    asset = {'pack': 'kenney_food-kit', 'name': 'apple', 'files': [
        {'path': 'apple.fbx', 'format': 'fbx', 'availability': 'available'},
        {'path': 'apple.glb', 'format': 'glb', 'availability': 'available'},
        {'path': 'apple.obj', 'format': 'obj', 'availability': 'available'}]}
    assert choose_source(asset, ['gltf'])[0]['format'] == 'glb'
    assert choose_source(asset, ['obj'])[0]['format'] == 'obj'
    with pytest.raises(ConfigError, match='no available'):
        choose_source(asset, [])


def test_scan_and_live_status_count_all_formats_without_creating_work(managed):
    config, _, one, _ = managed
    root = Path(one['path'])
    for extension, content in [('fbx', b'synthetic'), ('blend', b'synthetic'), ('gltf', b'{"asset":{"version":"2.0"}}'), ('glb', b'synthetic')]:
        (root / ('extra.' + extension)).write_bytes(content)
    select(config, ['gltf'])
    scanned = sources.scan_source(config, one)
    assert scanned['format_counts'] == {'fbx': 1, 'gltf': 2, 'obj': 3, 'blend': 1}
    assert scanned['pending'] == 2
    scoped = sources.bound(config, one)
    status_file = scoped.output_path('data', 'library/source-status.json')
    catalog_file = working(scoped).output_path('data', 'catalog.sqlite')
    before = (status_file.read_bytes(), catalog_file.read_bytes())
    revision = sources.revision(config)
    select(config, [])
    paused = sources.source_status(config, one)
    assert paused['processing_paused'] and not paused['needs_processing'] and paused['pending'] == 0
    assert paused['format_counts'] == scanned['format_counts']
    assert sources.revision(config) != revision
    select(config, ['fbx'])
    assert sources.source_status(config, one)['pending'] == 1
    assert before == (status_file.read_bytes(), catalog_file.read_bytes())
    # Disabled source membership does not remove inventory counts in Settings.
    sources.set_enabled(config, one['key'], False)
    assert sources.source_status(config, one)['format_counts'] == scanned['format_counts']


def test_grouped_asset_counts_once_per_format_and_inspects_enabled_file(managed):
    config, _, one, _ = managed
    root = Path(one['path']) / 'Models'
    for folder, extension in [('OBJ format', 'obj'), ('FBX format', 'fbx'), ('GLTF format', 'gltf')]:
        directory = root / folder
        directory.mkdir(parents=True)
        for name in ('chair', 'table'):
            (directory / (name + '.' + extension)).write_text('{"asset":{"version":"2.0"}}' if extension == 'gltf' else 'synthetic')
    select(config, ['fbx'])
    status = sources.scan_source(config, one)
    assert status['format_counts'] == {'fbx': 2, 'gltf': 2, 'obj': 5}
    assert status['assets'] == 5 and status['pending'] == 2
    work = working(sources.bound(config, one))
    grouped = next(r for r in records(work) if len(r['files']) == 3)
    assert inspection_input(work, grouped)[1]['format'] == 'fbx'
    # Both encodings of glTF on one logical asset are one family count.
    grouped['files'].append(dict(grouped['files'][0], format='glb', path='alternate.glb'))
    summary = sources.processing_summary([grouped], {}, ['gltf'])
    assert summary['format_counts'] == {'fbx': 1, 'gltf': 1, 'obj': 1}


def test_every_stage_skips_disabled_assets_without_loading_backend(library, monkeypatch):
    config, backend = library
    work = ready(config)
    index_library(work, backend)
    before_records = records(work)
    with closing(sqlite3.connect(work.output_path('data', 'embeddings/index.sqlite'))) as db:
        vectors = db.execute('SELECT * FROM vectors ORDER BY job_id').fetchall()
        jobs = db.execute('SELECT * FROM jobs ORDER BY job_id').fetchall()
    select(config, ['gltf'])
    calls = len(backend.calls)
    monkeypatch.setattr(incremental, 'run_inspection', lambda *a, **kw: pytest.fail('Disabled source reached inspection'))
    monkeypatch.setattr(incremental, 'run_caption', lambda *a, **kw: pytest.fail('Disabled source reached captions'))
    for stage in ('inspection', 'caption', 'embeddings'):
        preview = process(config, stage, dry_run=True)
        assert preview['pending'] == 0
        result = process(config, stage, backend=backend)
        assert not result['outcomes']
    assert len(backend.calls) == calls and records(work) == before_records
    with closing(sqlite3.connect(work.output_path('data', 'embeddings/index.sqlite'))) as db:
        assert db.execute('SELECT * FROM vectors ORDER BY job_id').fetchall() == vectors
        assert db.execute('SELECT * FROM jobs ORDER BY job_id').fetchall() == jobs


def test_failed_enabled_source_is_retained_across_format_changes(managed, monkeypatch):
    config, _, one, _ = managed
    root = Path(one['path']) / 'Models'
    for folder, extension in [('FBX format', 'fbx'), ('GLTF format', 'gltf')]:
        directory = root / folder
        directory.mkdir(parents=True)
        (directory / ('chair.' + extension)).write_text('{"asset":{"version":"2.0"}}' if extension == 'gltf' else 'synthetic')
    select(config, ['fbx'])
    sources.scan_source(config, one)
    scoped = sources.bound(config, one)
    calls = []
    def faulty(work, record, fp, resolution, formats=None):
        calls.append(inspection_input(work, record, formats=formats)[1]['format'])
        raise RuntimeError('Synthetic geometry fault')
    monkeypatch.setattr(incremental, 'run_inspection', faulty)
    assert process(scoped, 'inspection')['failed'] == 1
    assert calls == ['fbx']
    failed = next(r for r in records(working(scoped)) if len(r['files']) == 2)
    assert failed['primary_inspection_path'].endswith('.fbx')
    select(config, ['gltf'])
    assert process(scoped, 'inspection')['selected'] == 0
    select(config, ['fbx'])
    assert process(scoped, 'inspection')['retained'] == {'failed': 1}
    assert calls == ['fbx']
    (root / 'FBX format/chair.fbx').write_text('changed synthetic input')
    sources.scan_source(config, one)
    assert process(scoped, 'inspection')['failed'] == 1
    assert calls == ['fbx', 'fbx']


def test_indexing_enabled_assets_preserves_disabled_vectors_and_pinned_source(library):
    config, backend = library
    work = ready(config)
    index_library(work, backend)
    rows = records(work)
    skipped = rows[0]
    # An already inspected OBJ also has FBX available. Only enabling FBX must
    # not regenerate this asset or caption/encode its old OBJ preview.
    skipped['files'].append(dict(skipped['files'][0], format='fbx', path='one/alternate.fbx'))
    assert not processing_eligible(skipped, ['fbx'])
    before = inspection_input(work, skipped)[3]
    select(config, ['fbx'])
    assert inspection_input(work, skipped)[3] == before
    select(config, ['obj'])
    # A separate disabled record remains in membership and its vectors survive
    # new work on the remaining enabled records.
    disabled = rows[1]
    disabled['files'][0]['format'] = 'blend'
    update_record(work, disabled)
    enabled = rows[2]
    enabled['description']['description'] += ' Added visual detail.'
    update_record(work, enabled)
    with closing(sqlite3.connect(work.output_path('data', 'embeddings/index.sqlite'))) as db:
        old = db.execute('SELECT * FROM vectors WHERE asset_id=? ORDER BY job_id', (disabled['asset_id'],)).fetchall()
    assert index_library(work, backend)['processed'] == 1
    with closing(sqlite3.connect(work.output_path('data', 'embeddings/index.sqlite'))) as db:
        assert db.execute('SELECT * FROM vectors WHERE asset_id=? ORDER BY job_id', (disabled['asset_id'],)).fetchall() == old
        assert disabled['asset_id'] in json.loads(db.execute("SELECT value FROM meta WHERE key='pilot_ids'").fetchone()[0])


def test_pausing_preserves_failure_report_and_avoids_starting_source_worker(managed, monkeypatch):
    config, backend, one, _ = managed
    work = ready_source(config, backend, one)
    row = records(work)[0]
    row['processing']['previews'] = 'failed'
    update_record(work, row)
    before = sources.importing_failures(config)
    assert before['assets'] == 1
    select(config, [])
    monkeypatch.setattr(source_operations.subprocess, 'Popen', lambda *a, **kw: pytest.fail('No formats should start no worker'))
    with pytest.raises(ConfigError, match='paused'):
        source_operations.start(config, 'process', one['key'])
    assert not sources.source_status(config, one)['needs_processing']
    assert sources.importing_failures(config) == before
    states = []
    monkeypatch.setattr(source_operations, 'state', lambda *a, **kw: states.append(kw))
    monkeypatch.setattr(source_operations, 'scan_source', lambda *a: pytest.fail('Paused processing should not scan or load a runtime'))
    source_operations.process_source(config, one, 'paused-test')
    assert 'paused' in states[-1]['phase']


def test_overnight_selection_and_previously_planned_tasks_obey_formats(overnight):
    from local_asset_library.overnight import plan, create_run, caption_batch, outcomes
    config, _, _ = overnight
    run = create_run(config)
    assert plan(config)['selected'] == 2
    select(config, ['gltf'])
    assert plan(config)['selected'] == 0
    caption_batch(config, run, lambda *a: pytest.fail('Disabled sources should load no caption model'))
    assert {result['status'] for result in outcomes(config, run).values()} == {'skipped'}
