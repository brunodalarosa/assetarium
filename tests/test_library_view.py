"""The Asset sources tab's data: folders, packs, work states, blocked work and missing assets (decision 0023)."""
from pathlib import Path

from test_sources import managed, ready_source  # noqa: F401 -- fixtures
from local_asset_library import library_view, sources
from local_asset_library.desktop import DesktopBridge


def test_tree_counts_coverage_and_new_and_items_carry_states(managed, monkeypatch):
    config, backend, one, two = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    ready_source(config, backend, one)
    (Path(one['path']) / 'Kit_1.0').mkdir()
    (Path(one['path']) / 'Kit_1.0/License.txt').write_text('CC0')
    (Path(one['path']) / 'Kit_1.0/new.obj').write_text('v 0 0 0\n')
    library_view.record_visit(config, one['key'])
    sources.scan_source(config, one)
    found = library_view.tree(config)
    folder = next(f for f in found['folders'] if f['key'] == one['key'])
    nodes = {n['path']: n for n in folder['nodes']}
    assert nodes['']['assets'] == 4 and nodes['']['kind'] == 'library'
    assert nodes['Kit_1.0']['kind'] == 'pack' and nodes['Kit_1.0']['new'] == 1 and nodes['Kit_1.0']['coverage'] == 0
    assert nodes['']['previews'] == 3
    items = library_view.folder_items(config, one['key'])
    states = {i['name']: i['state'] for i in items['items'] if not i.get('file')}
    assert states['new'] == 'no_previews' and states['item0'] == 'ready'
    assert any(i.get('file') and i['name'] == 'License.txt' for i in items['items'])  # Other files come last, faded.
    inside = library_view.folder_items(config, one['key'], 'Kit_1.0', show_files=False)
    assert [i['name'] for i in inside['items']] == ['new'] and inside['items'][0]['pack']['path'] == 'Kit_1.0'


def test_blocked_work_names_its_fix_and_missing_assets_stay_listed(managed, monkeypatch):
    config, backend, one, _ = managed
    sources.scan_source(config, one)
    monkeypatch.setattr(library_view, 'blockers', lambda config: {'previews': {
        'reason': 'Blender is not set up', 'fix': 'Set up Blender', 'stages': ['inspection', 'previews'], 'types': ['model_3d']}})
    items = library_view.folder_items(config, one['key'], show_files=False)['items']
    assert {(i['state'], i['reason']) for i in items} == {('blocked', 'Blender is not set up')}
    (Path(one['path']) / 'item0.obj').unlink()
    sources.scan_source(config, one)
    items = library_view.folder_items(config, one['key'], show_files=False)['items']
    assert [i['name'] for i in items if i['state'] == 'missing'] == ['item0']
    assert next(f for f in library_view.tree(config)['folders'] if f['key'] == one['key'])['attention'] == ['Files missing']


def test_bridge_folder_answers_rescan_and_paths_stay_inside_the_folder(managed, monkeypatch):
    config, _, one, _ = managed
    sources.scan_source(config, one)
    bridge = DesktopBridge(config, prestart_worker=False)
    started = []
    monkeypatch.setattr(bridge, '_start_source_operation', lambda operation, key: started.append((operation, key)) or {'status': 'started'})
    try:
        assert bridge.folder_action('make_pack', one['key'], '')['status'] == 'started'
        assert bridge.folder_action('exclude', one['key'], 'Old')['status'] == 'started'
        assert sources.excluded_folders(sources.bound(config, one)) == ['Old']
        assert bridge.folder_action('include', one['key'], 'Old')['status'] == 'started'
        assert started == [('scan', one['key'])] * 3
        assert bridge.path_action('reveal', one['key'], '../two')['status'] == 'faulty'
        assert bridge.library_tree()['status'] == 'ready'
    finally:
        bridge._close()
