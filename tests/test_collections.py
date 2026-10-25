"""Collections and owner tags: virtual bundles across sources, agent edits and exports (decision 0012)."""
import json
from io import BytesIO
from pathlib import Path
import threading

import pytest
from PIL import Image

from test_sources import managed, ready_source  # noqa: F401  (fixture and helper)
from local_asset_library import asset_collections as collections, asset_tags, notifications, sources
from local_asset_library.collection_export import (checked_target, markdown, package, report_html, sample_sheet)
from local_asset_library.config import ConfigError
from local_asset_library.desktop_service import DesktopService
from local_asset_library.mcp_assets import AssetService, validate
from local_asset_library.membership import records
from local_asset_library.retrieval import SearchEngine


@pytest.fixture
def ready(managed):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    ready_source(config, backend, two)
    ids = [r['asset_id'] for r in records(config)]
    return config, backend, one, two, ids


def test_collections_bundle_assets_across_sources_with_labels_notes_and_undo(ready):
    config, _, one, two, ids = ready
    picked = [i for i in ids if records(config)[ids.index(i)]['pack_id'] == one['key']][:1] + \
             [i for i in ids if records(config)[ids.index(i)]['pack_id'] == two['key']][:2]
    created = collections.create(config, '  Aquarium   creatures ', 'Small fish\nfor the minigame', picked)
    identifier = created['collection_id']
    assert created['added'] == 3 and created['name'] == 'Aquarium creatures'
    with pytest.raises(ConfigError, match='already exists'):
        collections.create(config, 'AQUARIUM CREATURES')
    assert collections.add(config, identifier, picked[:1])['already_present'] == 1
    collections.set_item(config, identifier, picked[1], label='Coin', notes='Spawns every 3 s\nworth 10')
    other = collections.create(config, 'Shop', '', picked[1:2])['collection_id']
    collections.set_item(config, other, picked[1], label='money')
    value = collections.detail(config, identifier)
    assert [e['asset_id'] for e in value['items']] == picked
    assert value['items'][1]['label'] == 'Coin' and value['items'][1]['notes'].endswith('worth 10')
    assert collections.detail(config, other)['items'][0]['label'] == 'money'  # Labels belong to one collection.
    assert {e['source_key'] for e in value['items']} == {one['key'], two['key']}
    removed = collections.remove(config, identifier, picked[:2])['removed']
    assert [e['asset_id'] for e in collections.detail(config, identifier)['items']] == picked[2:]
    assert collections.restore(config, identifier, removed)['restored'] == 2
    restored = collections.detail(config, identifier)['items']
    assert [e['asset_id'] for e in restored] == picked and restored[1]['label'] == 'Coin'
    # Originals and source results are untouched: only the app-owned file changed.
    assert collections.path(config).is_relative_to(config.project_root / 'data/library')
    assert not any('collection' in p.name for p in Path(one['path']).rglob('*'))


def test_membership_survives_disabled_and_removed_sources_with_reasons(ready):
    config, _, one, two, ids = ready
    identifier = collections.create(config, 'Mixed', '', ids)['collection_id']
    sources.set_enabled(config, one['key'], False)
    items = collections.detail(config, identifier)['items']
    disabled = [e for e in items if e['source_key'] == one['key']]
    assert disabled and all(e['availability'] == 'source_only' and 'disabled' in e['reason'] for e in disabled)
    sources.remove(config, two['key'])
    items = collections.detail(config, identifier)['items']
    gone = [e for e in items if e['source_key'] == two['key']]
    assert gone and all(e['availability'] == 'unavailable' and 'removed' in e['reason'] for e in gone)
    assert len(items) == len(ids)  # Entries, labels and notes are kept, never silently dropped.


def test_source_browser_assets_can_join_while_unknown_ids_are_refused(ready):
    config, _, one, _, ids = ready
    sources.set_enabled(config, one['key'], False)
    hidden = [r['asset_id'] for r in records(sources.bound(config, one))]
    with pytest.raises(ConfigError, match='not in the library'):
        collections.create(config, 'Hidden', '', hidden[:1])
    created = collections.create(config, 'Hidden', '', hidden[:1], source_key=one['key'])
    assert collections.detail(config, created['collection_id'])['items'][0]['availability'] == 'source_only'
    with pytest.raises(ConfigError):
        collections.add(config, created['collection_id'], ['asset_' + '0' * 32])


def test_collection_and_tag_filters_scope_search_and_browse(ready):
    config, backend, _, _, ids = ready
    identifier = collections.create(config, 'Two', '', ids[:2])['collection_id']
    result, _ = SearchEngine(config, backend).search('item', mode='combined', filters={'collection': identifier}, limit=40)
    assert {r['asset_id'] for r in result['results']} == set(ids[:2])
    asset_tags.change(config, ids[3:5], add=['Fish', 'small'])
    result, _ = SearchEngine(config, backend).search('item', mode='combined', filters={'tag': 'fish'}, limit=40)
    assert {r['asset_id'] for r in result['results']} == set(ids[3:5])
    browse = DesktopService(config).browse({'collection': identifier})
    assert [i['asset_id'] for i in browse['items']] == sorted(ids[:2], key=[i['asset_id'] for i in DesktopService(config).browse()['items']].index)
    with pytest.raises(ConfigError):
        SearchEngine(config, backend).search('item', mode='keyword', filters={'collection': 'col_' + '0' * 16})
    with pytest.raises(ConfigError):
        validate('search_assets', {'query': 'x', 'filters': {'collection': '../x'}})


def test_collections_tab_search_matches_names_and_contents(ready):
    config, _, _, _, ids = ready
    fruit = collections.create(config, 'Fruit stand', 'Market props', ids[:2])['collection_id']
    other = collections.create(config, 'Dungeon', '', ids[2:4])['collection_id']
    collections.set_item(config, other, ids[3], label='Strawberry trap', notes='')
    asset_tags.change(config, [ids[0]], add=['berry'])
    names = lambda query: [c['name'] for c in collections.summaries(config, query)['collections']]
    assert names('strawberry') == ['Dungeon']
    assert names('market') == ['Fruit stand']
    assert names('berry') == ['Dungeon', 'Fruit stand']  # Tag and label substring; newest first.
    assert set(names('triangular')) == {'Dungeon', 'Fruit stand'}  # Generated descriptions are searched too.
    hit = next(c for c in collections.summaries(config, 'strawberry')['collections'])
    assert hit['match'] == {'collection': False, 'assets': 1, 'names': [collections.detail(config, other)['items'][1]['name']]}
    listing = collections.summaries(config, '', containing=ids[0])['collections']
    assert {c['name']: c['contains'] for c in listing} == {'Dungeon': False, 'Fruit stand': True}
    assert all(len(c['cover']) == 2 for c in listing)


def test_tags_are_asset_level_unique_and_bounded(ready):
    config, _, _, _, ids = ready
    asset_tags.change(config, [ids[0]], add=['Coin', 'coin ', 'UI  icon'])
    assert asset_tags.tags_for(config, ids[0]) == ['Coin', 'UI icon']
    asset_tags.change(config, [ids[0], ids[1]], add=['gold'], remove=['COIN'])
    assert asset_tags.tags_for(config, ids[0]) == ['UI icon', 'gold']
    assert {t['tag']: t['assets'] for t in asset_tags.known(config)} == {'gold': 2, 'UI icon': 1}
    asset_tags.change(config, [ids[0]], replace=[])
    assert asset_tags.tags_for(config, ids[0]) == []
    for bad in (['a,b'], ['x' * 33], ['']):
        with pytest.raises(ConfigError):
            asset_tags.change(config, [ids[0]], add=bad)
    with pytest.raises(ConfigError):
        asset_tags.change(config, [ids[0]], add=[f't{i}' for i in range(25)])


def test_damaged_files_are_kept_and_reported_not_reset(ready):
    config = ready[0]
    collections.path(config).parent.mkdir(parents=True, exist_ok=True)
    collections.path(config).write_text('{broken', encoding='utf-8')
    with pytest.raises(ConfigError, match='kept unchanged'):
        collections.create(config, 'New')
    assert collections.path(config).read_text(encoding='utf-8') == '{broken'


def test_concurrent_writers_never_lose_edits(ready):
    config, _, _, _, ids = ready
    identifier = collections.create(config, 'Race', '')['collection_id']
    errors = []
    def add(member):
        try:
            collections.add(config, identifier, [member])
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)
    threads = [threading.Thread(target=add, args=(i,)) for i in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors and set(collections.member_ids(config, identifier)) == set(ids)


def test_agent_tools_create_and_edit_but_never_delete(ready):
    config, _, _, _, ids = ready
    agent = AssetService(config)
    call = lambda name, args: agent.execute(name, args)[0]
    created = call('edit_collection', {'action': 'create', 'name': 'Aquarium creatures', 'asset_ids': ids[:3],
                                       'label': 'Fish', 'description': 'Small fishes only'})
    identifier = created['collection_id']
    assert created['added'] == 3
    listed = call('list_collections', {'query': 'aquarium'})
    assert listed['collections'][0]['collection_id'] == identifier and 'not an asset' in listed['meaning']
    call('edit_collection', {'action': 'set_item', 'collection_id': identifier, 'asset_ids': [ids[0]], 'notes': 'Boss\nfish'})
    call('edit_collection', {'action': 'remove', 'collection_id': identifier, 'asset_ids': [ids[2]]})
    page = call('get_collection', {'collection_id': identifier, 'limit': 1})
    assert page['asset_count'] == 2 and page['next_offset'] == 1 and page['items'][0]['notes'] == 'Boss\nfish'
    assert call('get_collection', {'collection_id': identifier, 'offset': 1})['next_offset'] is None
    call('tag_assets', {'asset_ids': ids[:1], 'add': ['boss']})
    detail = call('get_asset', {'asset_id': ids[0]})
    assert detail['tags'] == ['boss'] and detail['collections'][0]['label'] == 'Fish'
    for bad in ({'action': 'delete', 'collection_id': identifier}, {'action': 'create', 'collection_id': identifier, 'name': 'x'},
                {'action': 'set_item', 'collection_id': identifier, 'asset_ids': ids[:1]}, {'action': 'add', 'collection_id': identifier}):
        with pytest.raises(ConfigError):
            call('edit_collection', bad)
    notice = next(i for i in notifications.load(config)['items'] if i['kind'] == 'collection_changed')
    assert notice['collection_id'] == identifier and not notice['read']
    collections.delete(config, identifier)  # The app deletes after the owner confirms.
    assert not any(i['kind'] == 'collection_changed' for i in notifications.load(config)['items'])
    with pytest.raises(ConfigError):
        call('get_collection', {'collection_id': identifier})


def test_every_tool_is_described_and_only_collection_writes_are_writable():
    from local_asset_library.mcp_assets import SCHEMAS, WRITE_TOOLS
    from local_asset_library.mcp_server import DESCRIPTIONS, INSTRUCTIONS
    # Besides collections, only the session-gated setup writes (decision 0016) may change anything.
    assert set(DESCRIPTIONS) == set(SCHEMAS) and WRITE_TOOLS == {'edit_collection', 'tag_assets', 'apply_setup', 'propose_setup', 'finish_setup'}
    assert 'delete' not in SCHEMAS['edit_collection']['properties']['action']['enum']
    assert 'not assets' in INSTRUCTIONS and 'read-only' in INSTRUCTIONS


def test_exports_reference_original_paths_and_escape_owner_text(ready, tmp_path):
    config, _, _, _, ids = ready
    identifier = collections.create(config, 'Export <me>', 'Line one', ids[:3])['collection_id']
    collections.set_item(config, identifier, ids[0], label='<script>x</script>', notes='Uses | pipes')
    value = collections.detail(config, identifier)
    data = package(config, value)
    first = data['members'][0]['files']
    assert first['status'] == 'available' and Path(first['selected_source']).is_file()
    assert data['kind'] == 'assetarium_collection' and json.loads(json.dumps(data))['asset_count'] == 3
    thumbs = {ids[0]: _png()}
    sheet = Image.open(BytesIO(sample_sheet(value, thumbs)))
    assert sheet.format == 'PNG' and sheet.width >= 760
    text, images = markdown(value, data, thumbs, 'Export me-thumbnails')
    assert '](<Export me-thumbnails/01-' in text and len(images) == 1 and 'Uses \\| pipes' not in text.split('## 1.')[1]
    assert first['selected_source'] in text
    page = report_html(value, data, thumbs)
    assert '<script>' not in page and '&lt;script&gt;' in page and 'Export &lt;me&gt;' in page
    with pytest.raises(ConfigError):
        checked_target(config, tmp_path / 'outside.json', 'json')
    assert checked_target(config, config.storage_root('data') / 'exports/x/y.png', 'png').suffix == '.png'


def test_desktop_bridge_collection_round_trip(ready):
    from local_asset_library.desktop import DesktopBridge
    config, _, one, _, ids = ready
    bridge = DesktopBridge(config, prestart_worker=False)
    try:
        before = bridge.changes()['collections']
        created = bridge.collection_action('create', None, {'name': 'Bridge', 'description': '', 'asset_ids': ids[:2]})
        identifier = created['collection_id']
        assert bridge.changes()['collections'] != before
        hidden = [r['asset_id'] for r in records(sources.bound(config, one))][2]
        assert bridge.collection_action('add', identifier, {'asset_ids': [hidden], 'source_key': one['key']})['added'] in (0, 1)
        assert bridge.collection_action('set_item', identifier, {'asset_id': ids[1], 'label': 'Coin'})['label'] == 'Coin'
        assert bridge.collection_action('frobnicate', identifier)['status'] == 'faulty'
        assert bridge.collection_action('create', None, {'name': 'bridge'})['status'] == 'faulty'
        found = bridge.collection_search(identifier, {'query': 'coin', 'mode': 'keyword'})
        assert found['status'] == 'results' and found['items'][0]['asset_id'] == ids[1] and found['items'][0]['match'] == 'text'
        assert found['search']['status'] != 'faulty' and found['search']['arguments']['filters'] == {'collection': identifier}
        assert not bridge._gateway.model_requested  # Keyword search inside a collection never loads a model.
        assert bridge.set_asset_tags(ids[0], ['fish', 'Fish', 'small'])['tags'][ids[0]] == ['fish', 'small']
        assert bridge.asset_tags(ids[0])['tags'] == ['fish', 'small']
        listing = bridge.collections('', ids[1])['collections']
        assert listing[0]['contains'] and listing[0]['asset_count'] == 3
        target = config.storage_root('data') / 'exports/collections/bridge'
        for kind in ('json', 'png', 'md'):
            result = bridge.collection_export(identifier, kind, str(target) + '.' + kind)
            assert result['status'] == 'exported' and Path(result['path']).is_file(), result
        assert bridge.collection_export(identifier, 'json', str(config.project_root / 'outside.json'))['status'] == 'faulty'
        printing = bridge.collection_export(identifier, 'pdf', str(target) + '.pdf')
        assert printing['status'] == 'print' and '<article>' in printing['html']
        assert bridge.collection_print('unknown')['status'] == 'faulty'
        assert bridge.collection_action('delete', identifier)['status'] == 'deleted'
        assert bridge.collection(identifier)['status'] == 'faulty'
    finally:
        bridge._close()


def _png():
    stream = BytesIO()
    Image.new('RGB', (40, 30), 'blue').save(stream, format='PNG')
    return stream.getvalue()
