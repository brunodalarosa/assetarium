"""Identity by recognition (decision 0023): IDs are assigned once and kept through moves and reorganizations."""
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
