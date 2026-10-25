"""Preview authorization, selected-export dependencies, and retained fault evidence."""
from copy import deepcopy
import hashlib

import pytest

from test_retrieval import indexed
from test_mcp_assets import update
from test_sources import managed, ready_source
from local_asset_library.desktop_service import DesktopService
from local_asset_library.interactive_preview import InteractivePreviewService, viewer_shell


def fixture(indexed):
    config, _, records = indexed
    record = deepcopy(records[0])
    service = InteractivePreviewService(DesktopService(config))
    return config, record, service


def dependency(config, record, name, parent, content=b'synthetic texture', reference=None):
    path = config.source_root / 'pack' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    item = {'path': path.relative_to(config.source_root).as_posix(), 'from': parent,
            'sha256': hashlib.sha256(content).hexdigest(), 'status': 'available', 'role': 'texture'}
    if reference:
        item['reference'] = reference
    record['dependencies'].append(item)
    return item


def test_delivers_selected_export_dependency_closure_without_copying_sources(indexed):
    config, record, service = fixture(indexed)
    source = record['files'][0]
    material = dependency(config, record, 'item.mtl', source['path'])
    texture = dependency(config, record, 'textures/red.png', material['path'])
    dependency(config, record, 'alternate-only.png', 'unused-export.fbx')
    update(config, record)
    manifest = service.prepare(record['asset_id'], 'obj', 'legacy')
    assert manifest['status'] == 'ready'
    assert [f['aliases'][0] for f in manifest['files']] == [source['path'].split('/')[-1], 'item.mtl','red.png']
    assert 'path' not in manifest['files'][0]
    import base64
    for index, entry in enumerate(manifest['files']):
        content = service.file(manifest['ticket'], index)
        assert content['status'] == 'ready'
        assert hashlib.sha256(base64.b64decode(content['content'])).hexdigest() == entry['sha256']
    assert service.release(manifest['ticket']) == {'status': 'released'}
    with pytest.raises(ValueError, match='expired'):
        service.file(manifest['ticket'], 0)
    assert not (config.project_root / 'cache').exists()


def test_source_tampering_is_retained_across_sessions_without_retry(indexed, monkeypatch):
    config, record, service = fixture(indexed)
    manifest = service.prepare(record['asset_id'], 'obj', 'legacy')
    config.source_file(record['files'][0]['path']).write_bytes(b'changed source')
    result = service.file(manifest['ticket'], 0)
    assert result['status'] == 'faulty' and 'changed after publication' in result['reason']
    fresh = InteractivePreviewService(DesktopService(config))
    def forbidden(*args, **kwargs):
        raise AssertionError('Unchanged failed input must not be read again')
    monkeypatch.setattr('local_asset_library.interactive_preview.resolved_detail', forbidden)
    assert fresh.prepare(record['asset_id'], 'obj', 'legacy')['fingerprint'] == result['fingerprint']
    assert len(service.fault_path.read_text().splitlines()) == 1


def test_renderer_partial_fault_preserves_source_and_persists_missing_evidence(indexed):
    config, record, service = fixture(indexed)
    original = config.source_file(record['files'][0]['path']).read_bytes()
    manifest = service.prepare(record['asset_id'], 'obj', 'legacy')
    fault = service.fault(manifest['ticket'], 'Texture could not be resolved', ['lost.png'])
    assert fault['missing_files'] == ['lost.png']
    assert service.prepare(record['asset_id'], 'obj', 'legacy')['status'] == 'faulty'
    assert service.service.asset(record['asset_id'])['payload']['usable']
    assert config.source_file(record['files'][0]['path']).read_bytes() == original
    assert service.fault(manifest['ticket'], 'Another callback')['reason'] == fault['reason']


def test_dependency_basename_ambiguity_is_not_silently_resolved(indexed):
    config, record, service = fixture(indexed)
    source = record['files'][0]['path']
    dependency(config, record, 'a/map.png', source, b'first')
    dependency(config, record, 'b/map.png', source, b'second')
    update(config, record)
    result = service.prepare(record['asset_id'], 'obj', 'legacy')
    assert result['status'] == 'faulty' and 'Ambiguous' in result['reason']


def test_existing_texture_override_adds_reference_alias_without_changing_source(indexed):
    config, record, service = fixture(indexed)
    source = record['files'][0]['path']
    dep = dependency(config, record, 'bound.png', source)
    dep['texture_overrides'] = [{'original_path': r'C:\author\materials\original.png'}]
    update(config, record)
    manifest = service.prepare(record['asset_id'], 'obj', 'legacy')
    assert manifest['files'][1]['aliases'] == ['bound.png','original.png']


def test_rejects_unknown_ids_paths_indexes_and_stale_generations(indexed):
    config, record, service = fixture(indexed)
    with pytest.raises(ValueError):
        service.prepare('../source.obj', 'obj', 'legacy')
    assert service.prepare(record['asset_id'], 'obj', 'old-generation')['status'] == 'stale'
    manifest = service.prepare(record['asset_id'], 'obj', 'legacy')
    for index in [-1, 3, True, '../source.obj']:
        with pytest.raises(ValueError, match='index'):
            service.file(manifest['ticket'], index)
    with pytest.raises(ValueError, match='expired'):
        service.file('../other-file', 0)


def test_file_limits_are_recorded_faults(indexed, monkeypatch):
    config, record, service = fixture(indexed)
    monkeypatch.setattr('local_asset_library.interactive_preview.MAX_FILE_BYTES', 1)
    result = service.prepare(record['asset_id'], 'obj', 'legacy')
    assert result['status'] == 'faulty' and '64 MiB' in result['reason']
    assert not service.tickets


def test_dependency_path_escape_is_recorded_without_delivery(indexed):
    config, record, service = fixture(indexed)
    record['dependencies'] = [{'path':'../outside.png','from':record['files'][0]['path'],
                              'status':'available','role':'texture','sha256':'0'*64}]
    update(config,record)
    response=service.prepare(record['asset_id'],'obj','legacy')
    assert response['status']=='faulty' and 'relative without parent traversal' in response['reason']
    assert not service.tickets


def test_ticket_cannot_read_from_a_source_disabled_after_preparation(managed):
    from local_asset_library import sources
    from local_asset_library.membership import records
    from local_asset_library.publication import generation
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    record = records(config)[0]
    service = InteractivePreviewService(DesktopService(config))
    manifest = service.prepare(record['asset_id'], 'obj', generation(config))
    assert manifest['status'] == 'ready'
    sources.set_enabled(config, one['key'], False)
    with pytest.raises(ValueError, match='disabled'):
        service.file(manifest['ticket'], 0)


def test_corrupt_fault_history_disables_only_3d_delivery(indexed):
    config, record, service = fixture(indexed)
    service.fault_path.parent.mkdir(parents=True)
    service.fault_path.write_text('incomplete fault history\n')
    fresh = InteractivePreviewService(DesktopService(config))
    assert fresh.prepare(record['asset_id'],'obj','legacy')['status'] == 'faulty'
    assert fresh.service.browse()['items']
    assert service.fault_path.read_text() == 'incomplete fault history\n'


def test_shell_is_self_contained_and_bundles_offline_decoder():
    shell = viewer_shell()['html']
    assert '/* VIEWER_' not in shell and '/* DRACO_' not in shell
    assert 'connect-src data: blob:' in shell
    from html.parser import HTMLParser
    class Resources(HTMLParser):
        external = []
        def handle_starttag(self, tag, attrs):
            if tag == 'script' and dict(attrs).get('src') or tag == 'link':
                self.external.append((tag,attrs))
    resources = Resources()
    resources.feed(shell)
    assert not resources.external
    assert 'DracoDecoderModule' in shell and 'wasmBinary: binary' in shell
    assert len(shell) < 3_000_000
