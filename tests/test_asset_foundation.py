"""Foundation boundaries, using real tiny PNG bytes and synthetic search vectors."""
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
import json
import os
import sqlite3
import struct
import zlib

import pytest
from PIL import Image

from test_retrieval import SyntheticBackend
from test_incremental import library, ready
from local_asset_library import catalog, catalog_migration, incremental, notifications
from local_asset_library.asset_structure import (
    child_id, new_record, new_subasset, structure, upgrade_record, validate_collection,
)
from local_asset_library.config import Config, ConfigError
from local_asset_library.desktop_service import DesktopService
from local_asset_library.library_cache import library_records
from local_asset_library.library_index import index_library
from local_asset_library.membership import records
from local_asset_library.mcp_assets import AssetService, validate
from local_asset_library.publication import verified_hash
from local_asset_library.retrieval import source_check
from local_asset_library.sources import description_state, import_outcome, processing_summary, write_catalog, write_membership


@pytest.fixture
def media(tmp_path):
    project, source = tmp_path / 'project', tmp_path / 'source'
    project.mkdir(); source.mkdir()
    (source / 'media').mkdir()
    config = Config(project, source, None)
    image = source / 'media/hero.png'
    Image.new('RGBA', (24, 32), (220, 70, 100, 180)).save(image)
    audio = source / 'media/bell.wav'
    audio.write_bytes(b'RIFFsynthetic unsupported audio input')
    image_record = new_record('media', 'media/hero.png', 'png', verified_hash(image), 'image')
    audio_record = new_record('media', 'media/bell.wav', 'wav', verified_hash(audio), 'audio')
    work = incremental.working(config)
    write_catalog(work, [], [image_record, audio_record])
    write_membership(work, [image_record, audio_record])
    backend = SyntheticBackend()
    catalog.save_json(config.output_path('data', 'embeddings/capability.json'), {
        'contract_fingerprint': catalog.digest(backend.contract), 'actual_text_and_image_inference': True})
    return config, backend, image_record, audio_record


def replace_records(config, values):
    target = replace(config, catalog_generation='fixture_candidate')
    write_catalog(target, [], values)
    work = incremental.working(config)
    os.replace(target.output_path('data', 'catalog.sqlite'), work.output_path('data', 'catalog.sqlite'))
    write_membership(work, values)


def make_v1(config):
    """Old table layout and records, without depending on a saved real catalog."""
    path = config.output_path('data', 'catalog.sqlite')
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('ALTER TABLE files RENAME TO files_new')
        db.execute('CREATE TABLE files (path TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(asset_id), '
                   'format TEXT NOT NULL, sha256 TEXT, availability TEXT NOT NULL)')
        db.execute('INSERT INTO files SELECT * FROM files_new')
        db.execute('DROP TABLE files_new')
        db.execute('PRAGMA user_version=1')
        db.execute("UPDATE metadata SET value='1' WHERE key='schema_version'")


def test_identity_sharing_relationships_and_unknown_metadata(media):
    config, backend, parent, _ = media
    child = new_subasset(parent, 'region', 'left-eye', 'image')
    parent['relationships'] = [{'kind': 'contains', 'asset_id': child['asset_id'], 'evidence': 'Explicit synthetic region metadata'}]
    child['type_metadata']['future_region_metadata'] = {'rect': [1, 2, 3, 4], 'unknown': None}
    child['future_extension'] = {'keep': True}
    assert child_id(parent, 'region', 'left-eye') == child['asset_id']
    assert child_id(parent, 'region', 'right-eye') != child['asset_id']
    other = deepcopy(parent); other['asset_id'] = 'asset_' + '0' * 32
    assert child_id(other, 'region', 'left-eye') != child['asset_id']
    replace_records(config, [parent, child])
    work = incremental.working(config)
    assert catalog.detail(work, child['asset_id']) == child
    with closing(catalog.read_database(work)) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 2
        assert db.execute('SELECT count(*) FROM files').fetchone()[0] == 2
        assert db.execute('SELECT count(DISTINCT path) FROM files').fetchone()[0] == 1
    assert structure(child)['direct_media_channel'] is None
    assert incremental.process(config, 'inspection', dry_run=True)['pending'] == 1  # Parent only.
    incremental.process(config, 'inspection')
    index_library(work, backend)
    incremental.publish(config)
    assert catalog.detail(config, child['asset_id']) == child
    assert catalog.detail(config, parent['asset_id'])['relationships'] == parent['relationships']


@pytest.mark.parametrize('fault', ['dangling', 'cross_source', 'wrong_id', 'missing_evidence', 'self', 'wrong_file'])
def test_invalid_relationships_do_not_write_a_candidate(media, fault):
    config, _, parent, _ = media
    child = new_subasset(parent, 'frame', 'walk-0', 'image')
    relation = {'kind': 'contains', 'asset_id': child['asset_id'], 'evidence': 'Explicit metadata'}
    parent['relationships'] = [relation]
    if fault == 'dangling':
        relation['asset_id'] = 'asset_' + '1' * 32
    elif fault == 'cross_source':
        child['pack_id'] = 'other'
    elif fault == 'wrong_id':
        child['subasset']['key'] = 'renamed'
    elif fault == 'missing_evidence':
        relation['evidence'] = ''
    elif fault == 'self':
        relation['asset_id'] = parent['asset_id']
    else:
        child['files'][0]['path'] = 'media/another.png'
        child['file_roles'] = {'media/another.png': 'primary'}
    target = replace(config, catalog_generation='rejected_candidate')
    with pytest.raises(ConfigError):
        write_catalog(target, [], [parent, child])
    assert not target.output_path('data', 'catalog.sqlite').exists()


def test_png_dispatch_no_blender_and_audio_remains_explicitly_unsupported(media, monkeypatch):
    config, backend, image, audio = media
    monkeypatch.setattr(incremental, 'discover_blender', lambda *_: pytest.fail('Image dispatched to Blender'))
    assert incremental.process(config, 'inspection')['outcomes'][0]['status'] == 'complete'
    work = incremental.working(config)
    item = catalog.detail(work, image['asset_id'])
    assert item['technical']['width'] == 24 and item['technical']['height'] == 32
    assert item['processing']['caption'] == 'not_applicable'
    assert description_state(item) == 'unavailable'
    assert incremental.process(config, 'caption', dry_run=True)['pending'] == 0
    assert incremental.process(config, 'inspection', dry_run=True)['pending'] == 0
    assert catalog.detail(work, audio['asset_id']) == audio
    assert import_outcome(audio, False)['state'] == 'failed'
    assert not import_outcome(audio, False)['pending_stages']
    assert not structure(audio)['preview_capabilities']['playback']
    result = index_library(work, backend)
    assert result['processed'] == 1 and result['deferred_descriptions'] == 0
    item = catalog.detail(work, image['asset_id'])
    assert import_outcome(item, False)['state'] == 'complete'
    assert not any(config.output_path('data', 'inspection').glob('**/*.png'))


def test_media_publication_reload_shared_api_and_notifications(media):
    config, backend, image, audio = media
    incremental.process(config, 'inspection')
    work = incremental.working(config)
    index_library(work, backend)
    published = incremental.publish(config)
    assert published['membership'] == 2
    assert {r['asset_id'] for r in records(config)} == {image['asset_id'], audio['asset_id']}
    assert library_records(config)[0]['asset_type'] in ('image', 'audio')
    assert next(r for r in library_records(config) if r['asset_id'] == image['asset_id'])['technical']['width'] == 24
    gui, mcp = DesktopService(config), AssetService(config)
    args = {'query': 'hero', 'mode': 'keyword', 'filters': {'asset_type': 'image'}, 'limit': 5}
    assert gui.execute('search_assets', args)[0] == mcp.execute('search_assets', args)[0]
    assert mcp.execute('search_assets', args)[0]['results'][0]['asset_type'] == 'image'
    assert gui.browse(filters={'asset_type': 'image'})['total_count'] == 1
    detail, delivered, _ = mcp.execute('get_asset', {'asset_id': image['asset_id'], 'include_metadata': True,
                                                   'include_preview': True})
    assert delivered and detail['metadata']['asset_structure']['asset_type'] == 'image'
    unsupported, audio_bytes, faults = mcp.execute('get_asset', {'asset_id': audio['asset_id'], 'include_preview': True})
    assert unsupported['preview']['status'] == 'unsupported' and audio_bytes is None and not faults['excluded']
    summary = processing_summary(records(work), {r['asset_id']: r for r in records(config)}, ['gltf'], set())
    assert summary['pending'] == 0 and summary['descriptions']['missing'] == 0
    status = {'id': 'synthetic', 'key': 'media', 'name': 'Media', 'enabled': True, 'scanned': True, **summary}
    assert not notifications.reconcile(config, [status])['items']
    assert incremental.coverage(config)['asset_types']['audio']['stages']['inspection']['unsupported'] == 1
    assert incremental.publish(config)['no_change']


def test_malformed_png_is_attempted_once_and_does_not_claim_vectors(media):
    config, backend, image, _ = media
    path = config.source_file('media/hero.png')
    path.write_bytes(b'Not an image, despite the PNG extension')
    image['files'][0]['sha256'] = verified_hash(path)
    replace_records(config, [image])
    failed = incremental.process(config, 'inspection')
    assert failed['outcomes'][0]['status'] == 'failed'
    assert incremental.process(config, 'inspection')['pending'] == 0
    work = incremental.working(config)
    assert index_library(work, backend)['processed'] == 0
    item = catalog.detail(work, image['asset_id'])
    assert item['processing']['embeddings'] == 'pending'
    assert not import_outcome(item, False)['pending_stages']
    assert item['stage_faults']['inspection']


def test_png_decoder_limit_is_an_isolated_fault_without_large_allocation(media):
    config, _, image, _ = media
    path = config.source_file('media/hero.png')
    data = bytearray(path.read_bytes())
    data[16:24] = struct.pack('>II', 20000, 20000)
    data[29:33] = struct.pack('>I', zlib.crc32(data[12:29]) & 0xffffffff)
    path.write_bytes(data)
    image['files'][0]['sha256'] = verified_hash(path)
    replace_records(config, [image])
    assert incremental.process(config, 'inspection')['outcomes'][0]['status'] == 'failed'
    assert incremental.process(config, 'inspection')['pending'] == 0


@pytest.mark.parametrize('change', ['source', 'missing_dependency', 'changed_dependency', 'missing_preview'])
def test_image_faults_retain_partial_results_without_unchanged_retry(media, monkeypatch, change):
    config, backend, image, _ = media
    dependency = config.source_root / 'media/associated.txt'
    dependency.write_text('initial supplied dependency')
    image['dependencies'] = [{'path': 'media/associated.txt', 'sha256': verified_hash(dependency),
                              'status': 'available', 'role': 'other', 'from': 'media/hero.png'}]
    replace_records(config, [image])
    incremental.process(config, 'inspection')
    work = incremental.working(config)
    index_library(work, backend)
    incremental.publish(config)
    if change == 'source':
        config.source_file('media/hero.png').write_bytes(b'changed PNG bytes')
    elif change == 'missing_dependency':
        dependency.unlink()
    elif change == 'changed_dependency':
        dependency.write_text('changed supplied dependency')
    else:
        config.source_file('media/hero.png').unlink()
    failed = incremental.process(config, 'inspection')
    assert failed['outcomes'][0]['status'] == 'failed'
    assert incremental.process(config, 'inspection')['pending'] == 0
    item = catalog.detail(work, image['asset_id'])
    assert item['technical'] and item['previews'] and item['stage_faults']['inspection']
    assert item['processing']['caption'] == 'not_applicable'
    assert index_library(work, backend)['outcomes'][0]['status'] == 'failed'
    assert not AssetService(config).execute('search_assets', {'query': 'hero', 'mode': 'keyword'})[0]['results']


@pytest.mark.parametrize('caption', ['pending', 'failed'])
def test_model_description_failures_stay_optional_after_schema_upgrade(library, caption):
    config, backend = library
    # Align the explicit vector double so this tests channel availability rather
    # than the unrelated cosine floor (the default double's images are orthogonal).
    backend.image = lambda path: backend.text('synthetic aligned image', role='document')
    work = ready(config)
    for item in records(work):
        item = upgrade_record(item)
        item['description'] = None
        item['processing']['caption'] = caption
        item['caption_provenance'] = {'error': 'retained synthetic generation failure'} if caption == 'failed' else None
        if caption == 'failed':
            item['stage_faults'] = {'caption': {'error': 'retained synthetic generation failure'}}
        incremental.update_record(work, item)
    result = index_library(work, backend)
    assert result['vectors'] == 18
    incremental.publish(config)
    current = records(work)
    assert all(import_outcome(item, False)['state'] == 'complete' for item in current)
    summary = processing_summary(current, {r['asset_id']: r for r in records(config)}, ['obj'], set())
    assert summary['failed'] == 0 and summary['pending'] == 0
    assert summary['descriptions']['failed' if caption == 'failed' else 'missing'] == 6
    for mode in ('keyword', 'combined', 'image'):
        result, _, faults = AssetService(config, backend=backend).execute('search_assets', {'query': 'item0', 'mode': mode})
        assert result['results'] and not [f for f in faults['excluded'] if f.get('channel') == 'description'], (mode, faults)
    if caption == 'failed':
        item = current[0]
        detail = AssetService(config).execute('get_asset', {'asset_id': item['asset_id'], 'include_metadata': True})[0]
        assert detail['metadata']['stage_faults']['caption']['error'] == 'retained synthetic generation failure'
    else:
        status = {'id': 's', 'key': 'one', 'name': 'One', 'enabled': True, 'scanned': True, **summary}
        assert notifications.reconcile(config, [status])['items'][0]['missing'] == 6


def test_old_catalog_migration_preserves_outputs_ids_overlay_and_fingerprints(library):
    config, backend = library
    work = ready(config)
    item = records(work)[0]
    item['unknown_future_field'] = {'preserved': True}
    item['owner_overlay'] = {'original': 'not interpreted by migration'}
    incremental.update_record(work, item)
    make_v1(work)
    before = records(work)
    fingerprints = [(source_check(work, r), incremental.inspection_input(work, r)[3]) for r in before]
    original_id = before[0]['asset_id']
    result = catalog_migration.migrate_working_catalog(work, 2 * 1024**2)
    assert result['status'] == 'complete'
    after = records(work)
    assert before[0]['asset_id'] == after[0]['asset_id'] == original_id
    for old, new in zip(before, after):
        assert all(new[key] == value for key, value in old.items() if key != 'schema_version')
        assert new['schema_version'] == 2
    assert fingerprints == [(source_check(work, r), incremental.inspection_input(work, r)[3]) for r in after]
    assert catalog_migration.migrate_working_catalog(work, 1)['status'] == 'unchanged'
    with pytest.raises(ConfigError, match='working'):
        catalog_migration.migrate_working_catalog(config, 2 * 1024**2)


def test_migration_budget_and_failed_replacement_preserve_original(library, monkeypatch):
    config, _ = library
    work = incremental.working(config)
    make_v1(work)
    original = verified_hash(work.output_path('data', 'catalog.sqlite'), fresh=True)
    with pytest.raises(ConfigError, match='reserve'):
        catalog_migration.migrate_working_catalog(work, 1)
    def fail_replace(*_):
        raise OSError('Synthetic interrupted switch')
    monkeypatch.setattr(catalog_migration.os, 'replace', fail_replace)
    # atomic_json also uses os.replace: allow its receipts, interrupt only the DB switch.
    monkeypatch.setattr(catalog_migration, 'atomic_json', lambda path, value: catalog.save_json(path, value))
    with pytest.raises(OSError, match='interrupted'):
        catalog_migration.migrate_working_catalog(work, 2 * 1024**2)
    assert verified_hash(work.output_path('data', 'catalog.sqlite'), fresh=True) == original
    assert list(work.output_path('data', 'catalog.sqlite').parent.glob('migration-*.sqlite'))
    receipts = list(config.output_path('data', 'library/migrations').glob('*.json'))
    assert json.loads(receipts[0].read_text())['status'] == 'failed'


def test_schema_and_bounded_api_reject_unknown_values(media):
    config, _, image, _ = media
    work = incremental.working(config)
    for invalid in ('video', 'image/*', '', ['image']):
        with pytest.raises(ConfigError):
            validate('search_assets', {'query': 'hero', 'filters': {'asset_type': invalid}})
    malformed = deepcopy(image); malformed['structure_version'] = 99
    parsed = catalog.parse_record(image['asset_id'], 'media', 'hero', catalog.encoded(malformed))
    assert parsed['metadata_fault'] and parsed['availability'] == 'faulty'
    with closing(sqlite3.connect(work.output_path('data', 'catalog.sqlite'))) as db:
        db.execute('PRAGMA user_version=99')
    with pytest.raises(ConfigError, match='schema version'):
        catalog.read_database(work)
