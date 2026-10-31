"""Variant groups (change C): one group per name base and last token, derived in folder views, never pair lists."""
from contextlib import closing
from pathlib import Path

from test_sources import managed, ready_source  # noqa: F401 -- fixtures
from local_asset_library import folder_view, library_view, sources, variant_groups
from local_asset_library.incremental import working
from local_asset_library.library_store import save_answer


def rows(*names, folder='Cars', kind='model_3d'):
    return [(f'asset_{n}', folder, n, kind) for n in names]


def test_last_token_from_a_known_set_groups_and_numbered_series_stay_separate():
    groups, oversized = variant_groups.assign(rows('Car_11_R', 'Car_11_G', 'Car_11_B', 'Car_12_R', 'Rock_01', 'Rock_02',
                                                   'Tree_LOD1', 'Tree_LOD0', 'Chair-Wood', 'Chair-Metal', 'Lamp'))
    assert {k for k, _, _ in groups.values()} == {'Cars/Car_11', 'Cars/Tree', 'Cars/Chair'}
    assert groups['asset_Car_11_B'] == ('Cars/Car_11', 'B', True)  # Natural order picks the representative.
    assert groups['asset_Tree_LOD0'][2] and not groups['asset_Tree_LOD1'][2]
    assert 'asset_Car_12_R' not in groups and 'asset_Rock_01' not in groups and not oversized
    # Owner or agent rule: this folder's numbered series are variants; another folder's rule turns them off.
    numbered, _ = variant_groups.assign(rows('Rock_01', 'Rock_02'), {'Cars': ['numbers']})
    assert numbered['asset_Rock_01'] == ('Cars/Rock', '01', True)
    off, _ = variant_groups.assign(rows('Car_11_R', 'Car_11_G'), {'': ['letters'], 'Cars': []})
    assert not off


def test_images_never_group_and_big_sets_are_flagged_not_grouped():
    groups, _ = variant_groups.assign(rows('Icon_A', 'Icon_B', kind='image'))
    assert not groups
    letters = [f'Car_{chr(65 + n)}' for n in range(variant_groups.CAP + 1)]
    groups, oversized = variant_groups.assign(rows(*letters))
    assert not groups and oversized == [{'folder': 'Cars', 'base': 'Car', 'members': variant_groups.CAP + 1}]


def scanned(config, source, *names):
    folder = Path(source['path']) / 'Cars'
    folder.mkdir(exist_ok=True)
    for name in names:
        (folder / f'{name}.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
    sources.scan_source(config, source)


def test_a_group_is_one_card_with_a_picker_and_shares_one_description(managed, monkeypatch):
    config, backend, one, _ = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    ready_source(config, backend, one)
    scanned(config, one, 'Car_11_R', 'Car_11_G', 'Car_11_B', 'Rock_01', 'Rock_02')
    page = library_view.folder_items(config, one['key'], 'Cars', show_files=False)
    assert page['assets'] == 5 and page['cards'] == 3 and page['total'] == 3
    car = next(i for i in page['items'] if i.get('group'))
    assert car['name'] == 'Car_11_B' and car['group'] == 'Cars/Car_11'
    assert [(v['variant'], v['representative']) for v in car['variants']] == [('B', True), ('G', False), ('R', False)]
    work = working(sources.bound(config, one))
    with closing(folder_view.connect(work, fresh=True)) as view:
        states = dict(view.execute("SELECT name, description FROM assets WHERE folder='Cars'"))
    assert states['Car_11_G'] == states['Car_11_R'] == 'shared' and states['Car_11_B'] != 'shared'
    # "Generate separate descriptions for each variant" on this group: its variants need their own again.
    save_answer(config, one['id'], 'Cars/Car_11', 'separate_descriptions', True)
    with closing(folder_view.connect(work, fresh=True)) as view:
        assert 'shared' not in dict(view.execute("SELECT name, description FROM assets WHERE folder='Cars'")).values()


def test_a_state_filter_shows_the_matching_member_as_the_card(managed, monkeypatch):
    config, backend, one, _ = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    ready_source(config, backend, one)
    scanned(config, one, 'Car_A', 'Car_B')
    every = library_view.folder_items(config, one['key'], 'Cars', show_files=False)
    assert [len(i['variants']) for i in every['items']] == [2]
    filtered = library_view.folder_items(config, one['key'], 'Cars', filters={'states': ['no_previews']}, show_files=False)
    assert filtered['cards'] == 1 and filtered['counts']['no_previews'] == 2


def test_variants_point_search_and_detail_at_the_shared_description(managed, monkeypatch):
    config, backend, one, _ = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    ready_source(config, backend, one)
    scanned(config, one, 'Car_A', 'Car_B')
    work = working(sources.bound(config, one))
    with closing(folder_view.connect(work, fresh=True)) as view:
        ids = dict(view.execute("SELECT name, asset_id FROM assets WHERE folder='Cars'"))
    assert variant_groups.shared_map(work) == {ids['Car_B']: (ids['Car_A'], 'B')}
    record = next(r for r in sources.read_records(work) if r['asset_id'] == ids['Car_B'])
    found = variant_groups.membership(config, record)
    assert found['shared'] and found['representative'] == {'asset_id': ids['Car_A'], 'name': 'Car_A'}
    assert [v['value'] for v in found['variants']] == ['A', 'B']
