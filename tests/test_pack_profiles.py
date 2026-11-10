"""Pack profiles: a pack's answers as one versioned rule set, its effect, its signals and its file (decision 0035)."""
from contextlib import closing
import json
from pathlib import Path

import pytest

from test_sources import managed, ready_source  # noqa: F401 -- fixtures
from local_asset_library import folder_view, library_view, pack_profiles, sources
from local_asset_library.config import ConfigError
from local_asset_library.incremental import working

OBJ = 'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n'


def pack(config, source, *names, root='Kit_1.0'):
    folder = Path(source['path']) / root
    folder.mkdir(parents=True, exist_ok=True)
    if root == 'Kit_1.0':
        (folder / 'License.txt').write_text('CC0')
    for name in names:
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(OBJ)
    sources.scan_source(config, source)


@pytest.fixture
def kit(managed, monkeypatch):
    config, backend, one, _ = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    ready_source(config, backend, one)
    pack(config, one, 'Cars/Car_A.obj', 'Cars/Car_B.obj', 'Rocks/Rock_01.obj', 'Rocks/Rock_02.obj', 'Rocks/Rock_03.obj',
         'Unity FBX/Cars/Car_A.obj')
    return config, one


def test_rules_are_a_closed_vocabulary():
    assert pack_profiles.validate([{'kind': 'variant_axis', 'folder': 'Rocks', 'values': ['numbers'], 'note': 'numbered rocks are recolors'}])
    for bad, message in [({'kind': 'regex', 'pattern': '.*'}, 'kind must be one of'),
                         ({'kind': 'variant_axis', 'folder': 'Rocks', 'values': ['anything']}, 'Variant values'),
                         ({'kind': 'exclude', 'folder': 'Unity*'}, 'folder path inside the pack'),
                         ({'kind': 'exclude', 'folder': ''}, 'never the pack itself'),
                         ({'kind': 'pack', 'folder': 'A', 'value': 'make_pack', 'extra': 1}, 'pack takes')]:
        with pytest.raises(ConfigError, match=message):
            pack_profiles.validate([bad])
    with pytest.raises(ConfigError, match='Rule 2: another rule already sets this'):
        pack_profiles.validate([{'kind': 'exclude', 'folder': 'A'}, {'kind': 'engine_copy', 'folder': 'A', 'of': ''}])


def test_effect_then_apply_then_revert_keeps_every_version(kit):
    config, one = kit
    rules = [{'kind': 'variant_axis', 'folder': 'Rocks', 'values': ['numbers']}, {'kind': 'pack_name', 'value': 'Starter Kit'}]
    seen = pack_profiles.effect(config, one['key'], 'Kit_1.0', rules)
    assert seen['cards'] == {'before': 5, 'after': 3} and seen['instant'] and not seen['excluded_files']
    assert pack_profiles.current(config, one, 'Kit_1.0') == []  # Nothing was saved by looking.
    saved = pack_profiles.apply(config, one['key'], 'Kit_1.0', rules, {'by': 'owner'})
    assert saved == {'status': 'saved', 'version': 2, 'rescan': False, 'changed': ['pack_name', 'variant_axis']}
    page = library_view.folder_items(config, one['key'], 'Kit_1.0/Rocks', show_files=False)
    assert page['cards'] == 1 and [v['variant'] for v in page['items'][0]['variants']] == ['01', '02', '03']
    assert pack_profiles.apply(config, one['key'], 'Kit_1.0', rules, {'by': 'owner'})['status'] == 'unchanged'
    reverted = pack_profiles.revert(config, one['key'], 'Kit_1.0', 1)
    assert reverted['version'] == 3 and pack_profiles.current(config, one, 'Kit_1.0') == []
    assert [h['origin']['by'] for h in pack_profiles.history(config, one['key'], 'Kit_1.0')] == ['owner', 'owner', 'earlier']


def test_engine_copy_excludes_on_the_next_scan_and_says_how_many_files(kit):
    config, one = kit
    rules = [{'kind': 'engine_copy', 'folder': 'Unity FBX', 'of': ''}]
    assert pack_profiles.effect(config, one['key'], 'Kit_1.0', rules)['excluded_files'] == 1
    saved = pack_profiles.apply(config, one['key'], 'Kit_1.0', rules, {'by': 'agent', 'agent': 'test'})
    assert saved['rescan'] and sources.excluded_folders(sources.bound(config, one)) == ['Kit_1.0/Unity FBX']
    assert pack_profiles.current(config, one, 'Kit_1.0') == [{'kind': 'engine_copy', 'folder': 'Unity FBX', 'of': ''}]
    sources.scan_source(config, one)
    page = library_view.folder_items(config, one['key'], 'Kit_1.0', show_files=False)
    assert [(i['folder'], i['state']) for i in page['items'] if 'Unity FBX' in i['folder']] == []


def test_export_matches_the_same_pack_elsewhere_and_partial_copies(kit):
    config, one = kit
    pack_profiles.apply(config, one['key'], 'Kit_1.0', [{'kind': 'variant_axis', 'folder': 'Rocks', 'values': ['numbers']}], {'by': 'owner'})
    body = pack_profiles.export(config, one['key'], 'Kit_1.0')
    assert body['pack']['files'] == 7 and body['rules'][0]['kind'] == 'variant_axis'
    assert pack_profiles.match(config, one['key'], 'Kit_1.0', json.loads(json.dumps(body))) == 1.0
    body['pack'].update(sha256='other', names=body['pack']['names'][:-1])
    assert pack_profiles.match(config, one['key'], 'Kit_1.0', body) == round(6 / 7, 3)
    with pytest.raises(ConfigError, match='not an Assetarium pack profile'):
        pack_profiles.read_file({'rules': []})


def test_signals_flag_repeated_names_and_a_review_quiets_them_until_they_change(kit):
    config, one = kit
    pack(config, one, 'A/Barrel.obj', 'A/Crate.obj', 'A/Door.obj', 'B/Barrel.obj', 'B/Crate.obj', 'B/Door.obj', root='Kit_1.0/Props')
    found = pack_profiles.signals(config, one['key'])['Kit_1.0']
    assert found['status'] == 'needs_structure' and 'names repeat in several folders' in found['needs'][0]
    pack_profiles.review(config, one['key'], 'Kit_1.0', found['evidence'])
    assert pack_profiles.signals(config, one['key'])['Kit_1.0']['status'] == 'fine'
    pack(config, one, 'A/Lamp.obj', 'B/Lamp.obj', root='Kit_1.0/Props')
    assert pack_profiles.signals(config, one['key'])['Kit_1.0']['status'] == 'needs_structure'
