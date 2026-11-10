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


def first(config, contents, source):
    """One asset of the folder and the version its browsing session reads."""
    record = sources.read_records(sources.bound(config, source))[0]
    return record['asset_id'], generation(contents.session(source['key'])[0].config)


def test_disabled_source_browsing_reuses_inspection_without_enabling_search(managed):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    ready_source(config, backend, two)
    sources.set_enabled(config, one['key'], False)
    before = sources.registry(config)
    main, _, contents = browser(config)
    assert {i['pack'] for i in main.browse()['items']} == {two['key']}
    identifier, version = first(config, contents, one)
    assert contents.call('thumbnail', one['key'], identifier, version)['image']
    detail = contents.call('asset', one['key'], identifier, 'obj', 'front', version)
    assert detail['payload']['usable'] and detail['image']
    assert sources.registry(config) == before  # Browsing never changes which folders are enabled.
    assert main.backend is None and contents.session(one['key'])[0].backend is None
    with pytest.raises(ValueError, match='disabled'):
        main.asset(identifier)


def test_other_source_removed_source_and_stale_versions_cannot_be_inspected(managed):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    ready_source(config, backend, two)
    _, _, contents = browser(config)
    identifier, _ = first(config, contents, one)
    with pytest.raises(ValueError):
        contents.call('asset', two['key'], identifier)
    assert contents.call('asset', one['key'], identifier, None, 'front', 'old')['status'] == 'stale'
    assert contents.call('prepare', one['key'], identifier, 'obj', 'old')['status'] == 'stale'
    sources.remove(config, one['key'])
    for operation, args in [('asset', (identifier,)), ('thumbnail', (identifier,))]:
        with pytest.raises(ValueError, match='not registered'):
            contents.call(operation, one['key'], *args)


def test_preview_tickets_and_fault_evidence_are_shared_but_source_scoped(managed):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    ready_source(config, backend, two)
    main, history, contents = browser(config)
    identifier, version = first(config, contents, one)
    manifest = contents.call('prepare', one['key'], identifier, 'obj', version)
    assert manifest['status'] == 'ready'
    ticket = manifest['ticket']
    assert contents.call('file', one['key'], ticket, 0)['status'] == 'ready'
    with pytest.raises(ValueError, match='session expired'):
        contents.call('file', two['key'], ticket, 0)
    fault = contents.call('fault', one['key'], ticket, 'Synthetic retained viewer fault')
    assert fault['status'] == 'faulty'
    assert history.faults and Path(history.fault_path).is_file()
    assert contents.call('prepare', one['key'], identifier, 'obj', version)['retained']
    assert history.prepare(identifier, 'obj', generation(config))['retained']
    contents.call('release', one['key'], ticket)
    assert not contents.session(one['key'])[1].tickets


def test_source_bridge_routes_the_existing_services(managed):
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    sources.set_enabled(config, one['key'], False)
    bridge = DesktopBridge(config)
    try:
        identifier, version = first(config, bridge._source_browser, one)
        assert bridge.source_thumbnail(one['key'], identifier, version)['image']
        assert bridge.source_asset(one['key'], identifier, 'obj', 'front', version)['image']
        manifest = bridge.source_preview_prepare(one['key'], identifier, 'obj', version)
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
    # Discovery makes the vanished asset Missing (decision 0032): kept with its last record until forgotten.
    sources.scan_source(config, one)
    from local_asset_library.library_view import folder_items, unavailable
    assert record['asset_id'] not in {i.get('asset_id') for i in folder_items(config, one['key'])['items']}
    missing = next(i for i in unavailable(config, one['key'])['items'] if i['asset_id'] == record['asset_id'])
    assert missing['state'] == 'missing' and missing['paths']
    published = sources.read_records(sources.bound(config, one))
    assert record['asset_id'] in {r['asset_id'] for r in published}  # Its published evidence is untouched.


def test_reveal_locates_the_original_through_the_source_boundary(managed, monkeypatch):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    ready_source(config, backend, two)
    _, _, contents = browser(config)
    identifier, _ = first(config, contents, one)
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
