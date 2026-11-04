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


def test_blocked_work_names_its_fix_and_missing_entries_have_a_separate_review(managed, monkeypatch):
    config, backend, one, _ = managed
    sources.scan_source(config, one)
    monkeypatch.setattr(library_view, 'blockers', lambda config: {'previews': {
        'reason': 'Blender is not set up', 'fix': 'Set up Blender', 'stages': ['inspection', 'previews'], 'types': ['model_3d']}})
    items = library_view.folder_items(config, one['key'], show_files=False)['items']
    assert {(i['state'], i['reason']) for i in items} == {('blocked', 'Blender is not set up')}
    (Path(one['path']) / 'item0.obj').unlink()
    sources.scan_source(config, one)
    items = library_view.folder_items(config, one['key'], show_files=False)['items']
    assert not [i for i in items if i['state'] == 'missing']
    review = library_view.unavailable(config, one['key'])
    assert review['total'] == 1 and review['items'][0]['name'] == 'item0'
    assert review['items'][0]['state'] == 'missing'
    assert library_view.folder_items(config, one['key'], filters={'types': ['image']}, show_files=False)['items'] == []
    assert library_view.tree(config)['folders'][0]['nodes'][0]['missing'] == 1
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


def test_assets_assetarium_will_not_process_are_skipped_not_counted_as_pending(managed, monkeypatch):
    from local_asset_library import processing_queue
    from local_asset_library.settings import save_general_settings
    config, backend, one, _ = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    save_general_settings(config, 24, ['obj'])
    (Path(one['path']) / 'Only.blend').write_text('blend')  # A model file type with no format toggle: listed, not processed.
    sources.scan_source(config, one)
    root = next(n for n in next(f for f in library_view.tree(config)['folders'] if f['key'] == one['key'])['nodes'] if n['path'] == '')
    found = processing_queue.resolve(config, 'previews', {'key': one['key'], 'path': ''})
    assert root['skipped'] == 1 and root['pending'] == len(found['ids'])  # The button's count is what the queue would run.
    items = {i['name']: i for i in library_view.folder_items(config, one['key'], show_files=False)['items']}
    assert items['Only']['state'] == 'skipped' and items['Only']['reason'].startswith('Not processed')


def test_alternate_files_belong_to_each_physical_folder_once(managed, monkeypatch):
    from local_asset_library.incremental import working, update_record
    from local_asset_library import processing_queue
    from local_asset_library.settings import save_general_settings
    config, _, one, _ = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    sources.scan_source(config, one)
    work = working(sources.bound(config, one))
    record = sources.read_records(work)[0]
    original = record['files'][0]
    record['files'] = [dict(original, path=one['key'] + '/Kit/' + fmt + '/bench.' + fmt, format=fmt)
                       for fmt in ('fbx', 'glb', 'obj')]
    update_record(work, record)
    for fmt in ('fbx', 'glb', 'obj'):
        items = library_view.folder_items(config, one['key'], 'Kit/' + fmt, show_files=False)
        assert items['assets'] == 1
        card = items['items'][0]
        assert card['asset_id'] == record['asset_id'] and card['source_format'] == fmt
        assert card['formats'] == [fmt] and card['path'].endswith('/bench.' + fmt)
        assert processing_queue.resolve(config, 'previews', {'key': one['key'], 'path': 'Kit/' + fmt})['ids'] == [record['asset_id']]
    parent = library_view.folder_items(config, one['key'], 'Kit', show_files=False)
    assert parent['assets'] == 1 and parent['items'][0]['source_format'] is None
    nodes = {n['path']: n for n in library_view.tree(config)['folders'][0]['nodes']}
    assert all(nodes['Kit/' + fmt]['assets'] == 1 for fmt in ('fbx', 'glb', 'obj'))
    assert nodes['Kit']['assets'] == 1
    save_general_settings(config, 24, ['gltf', 'obj'])
    assert not library_view.folder_items(config, one['key'], 'Kit/fbx', show_files=False)['items']
    assert library_view.folder_items(config, one['key'], 'Kit', show_files=False)['assets'] == 1


def test_review_distinguishes_existing_files_and_forgetting_requires_current_confirmation(managed):
    from local_asset_library import library_store
    config, _, one, _ = managed
    root = Path(one['path'])
    (root / 'Kit').mkdir()
    (root / 'Kit/gone.obj').write_text('v 7 8 9')
    sources.scan_source(config, one)
    original = (root / 'Kit/gone.obj').read_text()
    (root / 'Kit/gone.obj').unlink()
    sources.scan_source(config, one)
    review = library_view.unavailable(config, one['key'], 'Kit')
    assert review['total'] == 1
    (root / 'Kit/gone.obj').write_text(original)
    assert library_view.unavailable(config, one['key'], 'Kit')['items'][0]['state'] == 'unrecognized'
    bridge = DesktopBridge(config, prestart_worker=False)
    try:
        assert bridge.folder_action('forget_missing', one['key'], 'Kit')['status'] == 'faulty'
        assert bridge.folder_action('forget_missing', one['key'], 'Kit', {'revision': 'outdated'})['status'] == 'faulty'
        assert len(library_store.missing_assets(config)) == 1
        assert bridge.folder_action('forget_missing', one['key'], 'Kit', {'revision': review['revision']})['forgotten'] == 1
        assert not library_store.missing_assets(config)
        assert (root / 'Kit/gone.obj').read_text() == original
    finally:
        bridge._close()


def test_a_model_made_from_a_format_that_is_off_says_so_and_can_turn_it_on(managed, monkeypatch):
    from local_asset_library.incremental import working, update_record
    from local_asset_library.settings import format_off, processing_formats, save_general_settings, turn_format_on
    from local_asset_library.source_operations import publish_source
    config, backend, one, _ = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    ready_source(config, backend, one)
    work = working(sources.bound(config, one))
    record = sources.read_records(work)[0]
    obj = record['files'][0]
    fbx = dict(obj, path=obj['path'][:-4] + '.fbx', format='fbx')
    record['files'] = [fbx, obj]
    record['primary_inspection_path'] = fbx['path']
    record['technical'] = dict(record['technical'], inspected_path=fbx['path'], inspected_format='fbx')
    update_record(work, record)
    publish_source(sources.bound(config, one))
    sources.aggregate(config)
    assert format_off(record, ['fbx', 'obj']) is None and format_off(record, ['gltf']) is None  # On, or hidden.
    save_general_settings(config, 24, ['obj'])
    hold = format_off(record, ['obj'])
    assert hold['format'] == 'fbx' and hold['reason'].startswith(f"Previews were made from {fbx['path'].rsplit('/', 1)[-1]}, and FBX is off")
    items = {i['asset_id']: i for i in library_view.folder_items(config, one['key'], show_files=False)['items']}
    card = items[record['asset_id']]
    assert card['state'] == 'format_off' and card['reason'] == hold['reason']  # Never shown as Ready, never silent.
    bridge = DesktopBridge(config, prestart_worker=False)
    try:
        detail = bridge.asset(record['asset_id'])
        assert detail['payload']['presentation']['format_off']['format'] == 'fbx', detail.get('reason')
        assert bridge.turn_format_on('fbx')['status'] == 'saved'
    finally:
        bridge._close()
    assert processing_formats(config) == ['fbx', 'obj']
    assert turn_format_on(config, 'glb')['processing_formats'] == ['fbx', 'gltf', 'obj']
    items = {i['asset_id']: i for i in library_view.folder_items(config, one['key'], show_files=False)['items']}
    assert items[record['asset_id']]['state'] == 'ready'
