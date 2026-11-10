"""Identity by recognition (decision 0032): IDs are assigned once and kept through moves and reorganizations."""
import json
from pathlib import Path
import shutil

import pytest

from test_sources import managed, ready_source  # noqa: F401 -- fixtures
from local_asset_library import asset_collections, library_store, sources
from local_asset_library.config import ConfigError
from local_asset_library.incremental import working
from local_asset_library.membership import records


def ids(config, source):
    return {r['source_relative_identity']: r['asset_id'] for r in records(working(sources.bound(config, source)))}


def kinds(config, asset_id):
    return [entry['kind'] for entry in library_store.history(config, asset_id)]


def test_a_moved_file_keeps_its_id_and_a_vanished_one_goes_missing_until_forgotten(managed):
    config, _, one, _ = managed
    sources.scan_source(config, one)
    before = ids(config, one)
    root = Path(one['path'])
    (root / 'Moved').mkdir()
    shutil.move(root / 'item0.obj', root / 'Moved/item0.obj')
    status = sources.scan_source(config, one)
    after = ids(config, one)
    assert after['Moved/item0.obj'] == before['item0.obj'] and status['recognized']['moved'] == 1
    assert kinds(config, before['item0.obj']) == ['moved']
    (root / 'item1.obj').unlink()
    status = sources.scan_source(config, one)
    assert status['missing'] == 1 and before['item1.obj'] not in ids(config, one).values()
    missing = library_store.missing_assets(config, one['id'])
    assert [m['asset_id'] for m in missing] == [before['item1.obj']] and missing[0]['record']['display_name'] == 'item1'
    # The same bytes coming back elsewhere are that asset again, not a new one.
    (root / 'Back').mkdir()
    (root / 'Back/item1.obj').write_text('# one 1\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
    sources.scan_source(config, one)
    assert ids(config, one)['Back/item1.obj'] == before['item1.obj'] and not library_store.missing_assets(config, one['id'])
    (root / 'Back/item1.obj').unlink()
    sources.scan_source(config, one)
    assert library_store.forget_missing(config, one['id']) == 1
    assert not library_store.missing_assets(config, one['id']) and kinds(config, before['item1.obj'])[-1] == 'forgotten'
    with pytest.raises(ConfigError):
        library_store.forget_missing(config, one['id'])


def test_a_duplicate_gets_its_own_id_and_an_edit_keeps_the_id(managed):
    config, _, one, _ = managed
    sources.scan_source(config, one)
    before = ids(config, one)
    root = Path(one['path'])
    shutil.copy(root / 'item0.obj', root / 'copy.obj')
    status = sources.scan_source(config, one)
    after = ids(config, one)
    assert status['recognized']['duplicate'] == 1 and after['copy.obj'] not in before.values()
    assert library_store.history(config, after['copy.obj'])[0]['evidence']['of'] == before['item0.obj']
    (root / 'item2.obj').write_text('v 9 9 9\n')
    status = sources.scan_source(config, one)
    assert ids(config, one)['item2.obj'] == before['item2.obj'] and status['recognized']['edited'] == 1
    record = next(r for r in records(working(sources.bound(config, one))) if r['asset_id'] == before['item2.obj'])
    assert record['processing']['inspection'] == 'pending'  # Edited content needs processing again.


def test_a_missing_asset_whose_file_returns_keeps_its_id_and_a_copy_found_first_gets_another(managed, tmp_path):
    config, _, one, _ = managed
    sources.scan_source(config, one)
    original = ids(config, one)['item0.obj']
    root = Path(one['path'])
    shutil.move(root / 'item0.obj', tmp_path / 'item0.obj')  # The drive is briefly gone.
    assert sources.scan_source(config, one)['missing'] == 1
    shutil.copy(tmp_path / 'item0.obj', root / 'item0.obj')
    (root / 'a').mkdir()
    shutil.copy(tmp_path / 'item0.obj', root / 'a/item0.obj')  # Sorts before the original.
    status = sources.scan_source(config, one)
    after = ids(config, one)
    assert after['item0.obj'] == original and after['a/item0.obj'] != original and len(set(after.values())) == len(after)
    assert status['recognized']['returned'] == 1 and status['recognized']['moved'] == 0
    assert not library_store.missing_assets(config, one['id'])


def test_a_folder_added_around_others_replaces_them_and_keeps_ids_overlays_and_collections(managed, tmp_path):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    sources.scan_source(config, two)
    first, second = ids(config, one), ids(config, two)
    item = first['item0.obj']
    overlay = config.output_path('data', f'captions/corrections/{item}.json')
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text(json.dumps({'schema_version': 1, 'description': {}, 'suggested_uses': None, 'caption_review': 'approved',
                                   'artistic_suitability': 'pending', 'notes': 'kept'}))
    collection = asset_collections.create(config, 'Keep', members=[item])['collection_id']
    inner = Path(one['path']) / 'inner'
    inner.mkdir()
    with pytest.raises(sources.Covered) as covered:
        sources.add(config, str(inner))  # Inside a library folder: already covered.
    assert covered.value.folder['key'] == one['key']
    inner.rmdir()
    parent = sources.add(config, str(Path(one['path']).parent))
    assert sorted(parent['replaced']) == sorted([one['key'], two['key']])
    assert [s['key'] for s in sources.registry(config)['sources']] == [parent['key']]
    sources.scan_source(config, parent)
    now = ids(config, parent)
    assert {now['one/' + k]: v for k, v in first.items()} == {v: v for v in first.values()}
    assert {now['two/' + k] for k in second} == set(second.values())
    carried = next(r for r in records(working(sources.bound(config, parent))) if r['asset_id'] == item)
    assert carried['processing']['inspection'] == 'complete' and carried['files'][0]['path'] == parent['key'] + '/one/item0.obj'
    assert json.loads(config.output_path('data', f'captions/corrections/{item}.json').read_text())['notes'] == 'kept'
    assert asset_collections.member_ids(config, collection) == [item]
    assert not any(p.is_dir() for p in Path(one['path']).iterdir())  # Still nothing written into the folders.


def test_a_folder_added_around_another_keeps_its_answers_under_the_new_path(managed):
    config, _, one, two = managed
    root = Path(one['path'])
    (root / 'Kit/Unity FBX').mkdir(parents=True)
    (root / 'Kit/Unity FBX/copy.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
    sources.set_excluded_folders(config, one['key'], ['Unity*', 'Kit/Old'])
    library_store.save_answer(config, one['id'], 'Kit', 'pack_name', 'Starter Kit')
    library_store.save_answer(config, one['id'], '', 'image_kind', 'texture')
    sources.scan_source(config, one)
    assert not any('Unity' in k for k in ids(config, one))
    settings = sources.bound(config, one).output_path('data', 'source.json')
    value = json.loads(settings.read_text())
    value['texture_folder'] = {'folder': 'Kit/Textures', 'single_copies': True, 'utc': 'x'}
    value['export_decisions'] = [{'id': library_store.digest({'anchor': 'Kit', 'folders': ['FBX', 'OBJ'], 'manifest': 'm'}),
                                  'anchor': 'Kit', 'folders': ['FBX', 'OBJ'], 'reference': 'FBX', 'names': 2,
                                  'name_manifest_sha256': 'm', 'decision': 'group', 'utc': 'x'}]
    settings.write_text(json.dumps(value))
    parent = sources.add(config, str(root.parent))
    scoped = sources.bound(config, parent)
    assert sources.excluded_folders(scoped) == ['one/Unity*', 'one/*/Unity*', 'one/Kit/Old']
    assert sources.texture_folder(scoped)['folder'] == 'one/Kit/Textures'
    moved = sources.export_decisions(scoped)[0]
    assert moved['anchor'] == 'one/Kit' and moved['id'] == library_store.digest({'anchor': 'one/Kit', 'folders': ['FBX', 'OBJ'], 'manifest': 'm'})
    answers = {(a['path'], a['kind']): a['value'] for a in library_store.answers(config, parent['id'])}
    assert answers[('one/Kit', 'pack_name')] == 'Starter Kit' and answers[('one', 'image_kind')] == 'texture'
    assert library_store.answers(config, one['id'])  # The child keeps its own rows.
    sources.scan_source(config, parent)
    assert not any('Unity' in k for k in ids(config, parent))  # Still skipped: never walked, hashed or imported.
    assert sources.excluded_folders(sources.bound(config, sources.get_source(config, parent['key'])))  # Saved, not just returned.

def test_an_image_keeps_its_id_in_a_folder_added_around_it(managed):
    """Image records carry the current schema; a kept ID no longer matches its pack-and-path formula and is valid."""
    from PIL import Image
    config, _, one, two = managed
    (Path(one['path']) / 'Icons').mkdir()  # Away from the models, so it is a 2D asset, not a texture.
    Image.new('RGB', (8, 8), 'blue').save(Path(one['path']) / 'Icons/icon.png')
    sources.scan_source(config, one)
    image = next(r for r in records(working(sources.bound(config, one))) if r.get('asset_type') == 'image')
    parent = sources.add(config, str(Path(one['path']).parent))
    assert sources.scan_source(config, parent)['assets'] == 7
    assert image['asset_id'] in ids(config, parent).values()


def test_removing_and_adding_a_folder_again_restores_its_identity(managed):
    config, _, one, _ = managed
    sources.scan_source(config, one)
    before = ids(config, one)
    sources.remove(config, one['key'])
    assert one['key'] not in [s['key'] for s in sources.registry(config)['sources']]
    again = sources.add(config, one['path'])
    assert again['id'] == one['id'] and again['key'] == one['key']
    sources.scan_source(config, again)
    assert ids(config, again) == before


def test_an_unreachable_folder_is_offline_and_keeps_its_assets(managed):
    config, _, one, _ = managed
    sources.scan_source(config, one)
    before = ids(config, one)
    moved = Path(one['path']).with_name('unplugged')
    Path(one['path']).rename(moved)
    try:
        status = sources.source_status(config, one)
        assert status['offline'] and not library_store.missing_assets(config, one['id'])
        with pytest.raises(ConfigError):
            sources.scan_source(config, one)
        assert not library_store.missing_assets(config, one['id'])  # Offline is not Missing.
    finally:
        moved.rename(one['path'])
    assert not sources.source_status(config, one)['offline']
    sources.scan_source(config, one)
    assert ids(config, one) == before


def test_the_new_folders_own_answer_wins_a_conflict_and_says_so():
    child = {'name': 'Castle Kit'}
    settings = {'texture_folder': {'folder': 'Shared', 'single_copies': False}, 'excluded_folders': ['Castle Kit/Unity*']}
    notes = sources.carry_settings(settings, {'texture_folder': {'folder': 'Tex', 'single_copies': True},
                                              'excluded_folders': ['Unity*']}, child, 'Castle Kit')
    assert settings['texture_folder']['folder'] == 'Shared' and notes == ['Texture folder of “Castle Kit”: the new library folder’s own choice was kept']
    assert settings['excluded_folders'] == ['Castle Kit/Unity*', 'Castle Kit/*/Unity*']  # Merged, without duplicates.
