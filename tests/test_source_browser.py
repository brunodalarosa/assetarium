"""Source previews use published records without changing enabled search membership."""
from pathlib import Path

import pytest

from test_sources import managed, ready_source
from local_asset_library import sources
from local_asset_library.desktop import DesktopBridge
from local_asset_library.desktop_service import DesktopService
from local_asset_library.interactive_preview import InteractivePreviewService
from local_asset_library.publication import generation
from local_asset_library.source_browser import SourceBrowser


def browser(config):
    main = DesktopService(config)
    preview = InteractivePreviewService(main)
    return main, preview, SourceBrowser(config, preview)


def test_disabled_source_browsing_reuses_inspection_without_enabling_search(managed):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    ready_source(config, backend, two)
    sources.set_enabled(config, one['key'], False)
    before = config.sources_registry.read_bytes()
    main, _, contents = browser(config)
    assert {i['pack'] for i in main.browse()['items']} == {two['key']}
    page = contents.call('browse', one['key'], 0, 2)
    assert page['total_count'] == 3 and len(page['items']) == 2
    assert not page['source']['enabled'] and not page['model_loaded']
    identifier = page['items'][0]['asset_id']
    assert contents.call('thumbnail', one['key'], identifier, page['generation'])['image']
    detail = contents.call('asset', one['key'], identifier, 'obj', 'front', page['generation'])
    assert detail['payload']['usable'] and detail['image']
    assert detail['payload']['presentation']['name'] == page['items'][0]['name']
    assert config.sources_registry.read_bytes() == before
    assert main.backend is None and contents.session(one['key'])[1][0].backend is None
    with pytest.raises(ValueError, match='disabled'):
        main.asset(identifier)


def test_source_pages_are_complete_ordered_and_disjoint(managed):
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    _, _, contents = browser(config)
    first = contents.call('browse', one['key'], 0, 2)
    last = contents.call('browse', one['key'], 2, 2)
    ids = [i['asset_id'] for p in [first, last] for i in p['items']]
    assert len(ids) == len(set(ids)) == first['total_count'] == 3
    assert contents.call('browse', one['key'], 3, 2)['items'] == []
    assert contents.call('browse', one['key'], 0, 2) == first
    for args in [(-1, 40), (0, 101), ('0', 40)]:
        with pytest.raises(ValueError):
            contents.call('browse', one['key'], *args)


def test_unprocessed_source_has_clear_read_only_state(managed):
    config, _, one, _ = managed
    _, _, contents = browser(config)
    result = contents.call('browse', one['key'], 0, 40)
    assert not result['available'] and result['items'] == []
    assert 'Scan and process' in result['reason']
    assert not sources.bound(config, one).output_path('data', 'catalog.sqlite').exists()
    sources.scan_source(config, one)
    result = contents.call('browse', one['key'], 0, 40)
    assert not result['available'] and 'Process this source' in result['reason']


def test_other_source_removed_source_and_stale_versions_cannot_be_inspected(managed):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    ready_source(config, backend, two)
    _, _, contents = browser(config)
    page = contents.call('browse', one['key'], 0, 40)
    identifier = page['items'][0]['asset_id']
    with pytest.raises(ValueError):
        contents.call('asset', two['key'], identifier)
    assert contents.call('asset', one['key'], identifier, None, 'front', 'old')['status'] == 'stale'
    assert contents.call('prepare', one['key'], identifier, 'obj', 'old')['status'] == 'stale'
    sources.remove(config, one['key'])
    for operation, args in [('browse', (0, 40)), ('asset', (identifier,)), ('thumbnail', (identifier,))]:
        with pytest.raises(ValueError, match='not registered'):
            contents.call(operation, one['key'], *args)


def test_preview_tickets_and_fault_evidence_are_shared_but_source_scoped(managed):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    ready_source(config, backend, two)
    main, history, contents = browser(config)
    page = contents.call('browse', one['key'], 0, 40)
    identifier = page['items'][0]['asset_id']
    manifest = contents.call('prepare', one['key'], identifier, 'obj', page['generation'])
    assert manifest['status'] == 'ready'
    ticket = manifest['ticket']
    assert contents.call('file', one['key'], ticket, 0)['status'] == 'ready'
    with pytest.raises(ValueError, match='session expired'):
        contents.call('file', two['key'], ticket, 0)
    fault = contents.call('fault', one['key'], ticket, 'Synthetic retained viewer fault')
    assert fault['status'] == 'faulty'
    assert history.faults and Path(history.fault_path).is_file()
    assert contents.call('prepare', one['key'], identifier, 'obj', page['generation'])['retained']
    assert history.prepare(identifier, 'obj', generation(config))['retained']
    contents.call('release', one['key'], ticket)
    assert not contents.session(one['key'])[1][1].tickets


def test_source_bridge_routes_the_existing_services(managed):
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    sources.set_enabled(config, one['key'], False)
    bridge = DesktopBridge(config)
    try:
        page = bridge.source_browse(one['key'])
        identifier = page['items'][0]['asset_id']
        assert bridge.source_thumbnail(one['key'], identifier, page['generation'])['image']
        assert bridge.source_asset(one['key'], identifier, 'obj', 'front', page['generation'])['image']
        manifest = bridge.source_preview_prepare(one['key'], identifier, 'obj', page['generation'])
        assert bridge.source_preview_file(one['key'], manifest['ticket'], 0)['status'] == 'ready'
        bridge.source_preview_release(one['key'], manifest['ticket'])
        assert bridge._gateway.worker is None
        assert bridge.browse()['items'] == []
    finally:
        bridge._close()


def test_faulty_saved_assets_remain_visible_with_inspection_evidence(managed):
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    _, _, contents = browser(config)
    record = sources.read_records(sources.bound(config, one))[0]
    config.source_file(record['files'][0]['path']).unlink()
    # Discovery excludes the missing file from searches but preserves its saved evidence.
    sources.scan_source(config, one)
    page = contents.call('browse', one['key'], 0, 40)
    item = next(item for item in page['items'] if item['asset_id'] == record['asset_id'])
    assert item['source_faulty'] and item['availability'] == 'faulty'
    detail = contents.call('asset', one['key'], record['asset_id'])
    assert detail['payload']['status'] == 'faulty'
    assert detail['payload']['presentation']['name'] == record['display_name']
    assert not detail['image']


def test_reveal_locates_the_original_through_the_source_boundary(managed, monkeypatch):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    ready_source(config, backend, two)
    _, _, contents = browser(config)
    identifier = contents.call('browse', one['key'], 0, 40)['items'][0]['asset_id']
    record = sources.read_records(sources.bound(config, one))[0]
    located = contents.call('reveal', one['key'], record['asset_id'])
    expected = config.source_file(record['files'][0]['path'])
    assert Path(located['path']) == expected and expected.is_file() and located['format'] == record['files'][0]['format']
    assert contents.call('reveal', one['key'], record['asset_id'], located['format'])['path'] == located['path']
    with pytest.raises(ValueError, match='format is not available'):
        contents.call('reveal', one['key'], record['asset_id'], 'fbx')
    with pytest.raises(ValueError):
        contents.call('reveal', two['key'], identifier)  # another source's asset is not browsable here


def test_reveal_bridge_launches_explorer_once_and_reports_a_missing_file(managed, monkeypatch):
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    launched = []
    monkeypatch.setattr('local_asset_library.desktop.show_in_explorer', launched.append)
    bridge = DesktopBridge(config)
    try:
        record = sources.read_records(sources.bound(config, one))[0]
        result = bridge.source_reveal(one['key'], record['asset_id'])
        assert result['status'] == 'revealed' and launched == [str(config.source_file(record['files'][0]['path']))]
        library = bridge.reveal(record['asset_id'])  # The combined library resolves the same original.
        assert library['status'] == 'revealed' and launched[-1] == launched[0] and len(launched) == 2
        config.source_file(record['files'][0]['path']).unlink()
        missing = bridge.source_reveal(one['key'], record['asset_id'])
        assert missing['status'] == 'faulty' and 'missing' in missing['reason'] and len(launched) == 2
        assert bridge.source_reveal(one['key'], 'not-an-asset')['status'] == 'faulty'
        assert bridge.reveal('not-an-asset')['status'] == 'faulty' and len(launched) == 2
    finally:
        bridge._close()


def test_show_in_explorer_is_windows_only(monkeypatch):
    from local_asset_library import desktop
    monkeypatch.setattr(desktop.os, 'name', 'posix')
    with pytest.raises(ValueError, match='only available on Windows'):
        desktop.show_in_explorer('C:/assets/a.fbx')
