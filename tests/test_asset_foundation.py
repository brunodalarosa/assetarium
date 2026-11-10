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
from local_asset_library import catalog, incremental, notifications
from local_asset_library.settings import used_formats
from local_asset_library.asset_structure import child_id, new_record, new_subasset, structure, upgrade_record
from local_asset_library.config import Config, ConfigError
from local_asset_library.desktop_service import DesktopService
from local_asset_library.library_cache import library_records
from local_asset_library.library_index import index_library
from local_asset_library.membership import records
from local_asset_library.mcp_assets import AssetService, validate
from local_asset_library.publication import verified_hash
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
    # Step 2: images have optional descriptions from their derived model input.
    assert item['processing']['caption'] == 'pending'
    assert description_state(item) == 'missing'
    for path in ('src/local_asset_library/caption_backend.py', 'src/local_asset_library/caption_batching.py',
                 'runtime/caption/uv.lock', 'prompts/caption-image-v1.txt'):
        target = config.project_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('synthetic contract')
    catalog.save_json(config.project_root / 'docs/caption-model.json', {'revision': 'synthetic'})
    assert incremental.process(config, 'caption', dry_run=True)['pending'] == 1
    assert incremental.process(config, 'inspection', dry_run=True)['pending'] == 0
    assert catalog.detail(work, audio['asset_id']) == audio
    assert import_outcome(audio, False)['state'] == 'failed'
    assert not import_outcome(audio, False)['pending_stages']
    assert not structure(audio)['preview_capabilities']['playback']
    result = index_library(work, backend)
    assert result['processed'] == 1 and result['deferred_descriptions'] == 1
    item = catalog.detail(work, image['asset_id'])
    assert import_outcome(item, False)['state'] == 'complete'
    # Only bounded derived files are written; the original is never copied.
    derived = sorted(p.name for p in config.output_path('data', 'results/inspection').glob('**/*.png'))
    assert derived == ['model-input.png', 'thumbnail.png']


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
    summary = processing_summary(records(work), {r['asset_id']: r for r in records(config)}, used_formats(config), set())
    assert summary['pending'] == 0 and summary['descriptions']['missing'] == 1
    status = {'id': 'synthetic', 'key': 'media', 'name': 'Media', 'enabled': True, 'scanned': True, **summary}
    # The image's optional description is ready to generate; audio stays unsupported and silent.
    assert len(notifications.reconcile(config, [status])['items']) == 1
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
    assert item['processing']['caption'] == 'pending'
    assert [o['status'] for o in index_library(work, backend)['outcomes'] if o['channel'] == 'image'] == ['failed']
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
