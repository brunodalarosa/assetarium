"""Small synthetic faults and shared policy checks; never modify or preprocess real assets."""
import asyncio
from copy import deepcopy
import json
import threading
import time

from PIL import Image
import pytest

from test_retrieval import indexed
from test_mcp_assets import update
from local_asset_library.captions import file_hash
from local_asset_library.desktop import DesktopBridge
from local_asset_library.desktop_service import DesktopService
from local_asset_library.mcp_assets import AssetService
from local_asset_library.mcp_server import Gateway


def png(config, record, view='three_quarter'):
    record = deepcopy(record)
    path = config.output_path('data', record['asset_id'] + '-' + view + '.png')
    Image.new('RGBA', (32, 24), '#abc123').save(path)
    record['previews'] = [{'path': 'data/' + path.name, 'sha256': file_hash(path), 'view_label': view}]
    update(config, record)
    return path, record


def test_browse_no_embedding_and_shared_filters(indexed):
    config, backend, records = indexed
    service = DesktopService(config)
    result = service.browse()
    assert result['pilot_count'] == len(records) == len(result['items'])
    assert service.backend is None and not result['model_loaded']
    filtered = service.browse({'pack': 'even', 'format': 'obj', 'max_triangles': 100, 'rigged': False})
    assert len(filtered['items']) == 6
    with pytest.raises(ValueError):
        service.browse({'color': 'red'})
    with pytest.raises(ValueError):
        service.browse([])


def test_partial_faults_missing_preview_no_substitute_or_retry(indexed, monkeypatch):
    config, _, records = indexed
    _, record = png(config, records[0], 'front')
    record['inspection_run'] = {'source_faults': [{'kind': 'synthetic geometry fault', 'count': 1}]}
    update(config, record)
    service = DesktopService(config)
    calls = []
    original = service.preview
    def traced(record, view):
        calls.append(view)
        return original(record, view)
    monkeypatch.setattr(service, 'preview', traced)
    first = service.asset(record['asset_id'])
    second = service.asset(record['asset_id'])
    assert first['payload']['usable'] and second['payload']['usable']
    assert first['payload']['preview']['status'] == 'faulty' and first['image'] is None
    assert calls == ['three_quarter']
    assert service.asset(record['asset_id'], view='front')['image']
    item = next(i for i in service.browse()['items'] if i['asset_id'] == record['asset_id'])
    assert item['source_faulty'] and first['payload']['presentation']['source_faults']


def test_unavailable_item_visible_and_other_items_survive(indexed):
    config, _, records = indexed
    config.source_file(records[0]['files'][0]['path']).write_bytes(b'synthetic stale source')
    service = DesktopService(config)
    result = service.browse()
    faulty = next(i for i in result['items'] if i['asset_id'] == records[0]['asset_id'])
    assert len(result['items']) == 40 and faulty['availability'] == 'faulty'
    assert len([i for i in result['items'] if i['availability'] == 'available']) == 39
    detail = service.asset(records[0]['asset_id'])
    assert detail['payload']['status'] == 'faulty' and detail['payload']['presentation']['name']
    assert not detail['image']


def test_detail_separates_measured_observations_suggestions_review(indexed):
    config, _, records = indexed
    _, record = png(config, records[0])
    info = DesktopService(config).asset(record['asset_id'])['payload']['presentation']
    assert info['technical']['inspected_format'] == 'obj'
    assert 'SECRET SPECULATIVE USE' in info['suggested_uses']
    assert 'SECRET SPECULATIVE USE' not in json.dumps(info['observations'])
    assert info['owner_review'] == 'pending' and info['owner_artistic_approval'] == 'pending'
    assert info['scale'].startswith('Unknown physical scale')


def test_live_owner_review_and_null_suggestions_preserve_generated_uses(indexed):
    config, _, records = indexed
    _, record = png(config, records[0])
    path = config.output_path('data', 'captions/corrections/' + record['asset_id'] + '.json')
    path.parent.mkdir(parents=True)
    overlay = {'schema_version': 1, 'description': {}, 'suggested_uses': None,
               'caption_review': 'approved', 'artistic_suitability': 'rejected', 'notes': 'Synthetic review'}
    path.write_text(json.dumps(overlay), encoding='utf-8')
    before = path.read_bytes()
    info = DesktopService(config).asset(record['asset_id'])['payload']['presentation']
    assert info['owner_review'] == 'approved' and info['owner_artistic_approval'] == 'rejected'
    assert info['suggested_uses'] == record['suggested_uses']
    assert path.read_bytes() == before


def test_desktop_rejects_coercible_non_object_and_false_source_format(indexed):
    config, _, records = indexed
    bridge = DesktopBridge(config)
    try:
        response = bridge.search([['query', 'red object']])
        assert response['payload']['status'] == 'faulty'
        assert 'non-object' in response['reason']
        assert bridge._gateway.worker is None
    finally:
        bridge._close()
    with pytest.raises(ValueError):
        DesktopService(config).asset(records[0]['asset_id'], source_format=0)


def test_desktop_default_exact_shared_shortlist_and_close(indexed, monkeypatch):
    config, backend, _ = indexed
    real_init = Gateway.__init__
    def init(gateway, *args, **kwargs):
        real_init(gateway, *args, **kwargs)
        async def semantic(name, arguments):
            payload, image, evidence = AssetService(config, backend=backend).execute(name, arguments)
            return {'payload': payload, 'image': image, 'evidence': evidence, 'is_error': False}
        gateway.semantic = semantic
    monkeypatch.setattr(Gateway, '__init__', init)
    bridge = DesktopBridge(config)
    try:
        response = bridge.search({'query': 'red object'})
        expected, _, _ = AssetService(config, backend=backend).execute('search_assets', response['arguments'])
        assert response['arguments'] == {'query': 'red object', 'mode': 'keyword_description', 'filters': {}, 'limit': 5}
        assert response['payload'] == expected
        # Endpoint works while a separate slow operation is running; model work is not on GUI main thread.
        async def slow():
            await asyncio.sleep(.1)
        future = asyncio.run_coroutine_threadsafe(slow(), bridge._loop)
        assert bridge.browse()['pilot_count'] == 40
        future.result()
        assert bridge._thread.ident != threading.get_ident()
    finally:
        bridge._close()
    assert not bridge._thread.is_alive()
    assert json.loads((bridge._gateway.audit_root / 'lifecycle.json').read_text())['closed']
