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


def test_desktop_large_evidence_does_not_disable_preview(indexed):
    config, _, records = indexed
    _, record = png(config, records[0])
    record['inspection_run'] = {'errors': ['x' * 30000], 'source_faults': []}
    update(config, record)
    result = DesktopService(config).asset(record['asset_id'])
    assert result['payload']['usable'] and result['image']
    assert result['payload']['selected_source']['format'] == 'obj'


def test_ungenerated_preview_is_pending_and_does_not_retain_a_fault(indexed):
    config, _, records = indexed
    record = deepcopy(records[0])
    record['processing'].update(inspection='pending', previews='pending')
    record['previews'] = []
    update(config, record)
    service = DesktopService(config)
    # Cards show preview state only; detail also resolves the usable source package.
    for result in (service.thumbnail(record['asset_id']), service.asset(record['asset_id'])):
        assert result['payload']['preview']['status'] == 'pending'
        assert not result['image']
    assert service.asset(record['asset_id'])['payload']['usable']
    assert not service.preview_faults and not service.item_faults


def test_card_facts_are_measured_values_or_absent(indexed):
    config, _, records = indexed
    record = deepcopy(records[0])
    record['technical'] = {**(record.get('technical') or {}), 'inspected_format': 'glb',
                           'evaluated_instance_totals': {'triangles': 1248, 'vertices': 864}}
    update(config, record)
    card = DesktopService(config).thumbnail(record['asset_id'])['payload']['card']
    assert card == {'format': 'glb', 'triangles': 1248, 'width': None, 'height': None}
    bare = deepcopy(records[1])
    bare['technical'] = {}
    update(config, bare)
    assert DesktopService(config).thumbnail(bare['asset_id'])['payload']['card'] == {
        'format': None, 'triangles': None, 'width': None, 'height': None}


def test_desktop_bridge_round_trips_interface_preferences(indexed):
    config, _, _ = indexed
    bridge = DesktopBridge(config, prestart_worker=False)
    try:
        assert bridge.interface_settings() == {'status': 'ready', 'appearance': 'system', 'inspector_width': 440}
        assert bridge.save_interface_settings('dark', None)['appearance'] == 'dark'
        assert bridge.save_interface_settings(None, 610)['inspector_width'] == 610
        assert bridge.interface_settings() == {'status': 'ready', 'appearance': 'dark', 'inspector_width': 610}
        assert bridge.save_interface_settings('sepia', None)['status'] == 'faulty'
    finally:
        bridge._close()


def test_unattempted_disabled_format_is_excluded_without_a_preview_fault(indexed):
    from local_asset_library.settings import save_general_settings
    config, _, records = indexed
    record = deepcopy(records[0])
    record['processing'].update(inspection='pending', previews='pending')
    record['previews'] = []
    update(config, record)
    save_general_settings(config, 24, ['gltf'])
    service = DesktopService(config)
    assert service.thumbnail(record['asset_id'])['payload']['preview']['status'] == 'excluded'
    assert service.asset(record['asset_id'])['payload']['usable']
    assert not service.preview_faults


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
        assert not bridge._gateway.model_requested
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
        assert response['arguments'] == {'query': 'red object', 'mode': 'combined', 'filters': {}, 'limit': 20}
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


def test_desktop_bridge_saves_description_batch_size_with_general_settings(indexed):
    from local_asset_library.settings import save_general_settings
    config, _, _ = indexed
    save_general_settings(config, 24)  # This fixture has no historical membership budget.
    bridge = DesktopBridge(config)
    try:
        assert bridge.general_settings()['caption_batch_size'] == 8
        saved = bridge.save_general_settings('24', ['fbx', 'gltf', 'obj'], '2')
        assert saved['status'] == 'saved' and saved['caption_batch_size'] == 2
        assert bridge.general_settings()['caption_batch_size'] == 2
        refused = bridge.save_general_settings('24', ['gltf'], '3')
        assert refused['status'] == 'faulty' and 'batch size' in refused['reason']
        assert bridge.general_settings()['caption_batch_size'] == 2
    finally:
        bridge._close()


def test_desktop_bridge_rendering_settings_and_speed_test(indexed):
    config, _, _ = indexed
    bridge = DesktopBridge(config, prestart_worker=False)
    try:
        current = bridge.render_settings()
        assert current['status'] == 'ready' and current['device'] is None and current['plan']['device'] == 'CPU'
        saved = bridge.save_render_settings('cpu', 2, 16)
        assert saved['status'] == 'saved' and (saved['processes'], saved['memory_gib']) == (2, 16)
        refused = bridge.save_render_settings(None, 0, None)
        assert refused['status'] == 'faulty' and 'render processes' in refused['reason']
        assert bridge.render_settings()['processes'] == 2
        assert bridge.render_test('cancel') == {'status': 'idle'}
        started = bridge.render_test('start')
        assert started['status'] == 'faulty' and 'Set up Blender' in started['reason']
    finally:
        bridge._close()
