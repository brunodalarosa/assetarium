from copy import deepcopy
from pathlib import Path

import pytest

from test_incremental import library, ready
from test_overnight import overnight
from local_asset_library.captions import file_hash
from local_asset_library.incremental import inspection_input, working
from local_asset_library.membership import records
from local_asset_library.texture_repair import build_recipe, material_table, validate_recipe, unique_texture
from local_asset_library.overnight import plan
from local_asset_library.config import ConfigError
from local_asset_library.incremental import update_record
from local_asset_library.mcp_assets import AssetService


def test_publisher_slots_and_repeated_prefab_meshes(tmp_path):
    path = tmp_path / 'MaterialList.txt'
    path.write_text('Prefab Name: A\n Mesh Name: mesh\n Slot: Wood\n Albedo: Wood.png (_Albedo_Map)\n'
                    ' Slot: Atlas (PolygonStarter_Texture_01)\n'
                    'Prefab Name: B\n Mesh Name: mesh\n Slot: Wood\n Albedo: Wood.png (_Albedo_Map)\n'
                    ' Slot: Atlas (PolygonStarter_Texture_01)\n')
    result = material_table(path)
    assert [s['maps']['Albedo'] for s in result['mesh']] == ['Wood.png', 'PolygonStarter_Texture_01.png']


def test_differing_duplicate_texture_names_are_ambiguous(tmp_path):
    for folder, data in [('a', b'a'), ('b', b'b')]:
        (tmp_path / folder).mkdir()
        (tmp_path / folder / 'map.png').write_bytes(data)
    paths = ['a/map.png', 'b/map.png']
    assert unique_texture(paths, tmp_path) is None
    (tmp_path / paths[1]).write_bytes(b'a')
    assert unique_texture(paths, tmp_path)[0] == paths[0]


def synthetic_recipe(config, record, path):
    source = record['files'][0]
    return {'schema_version': 1, 'asset_id': record['asset_id'], 'source_path': source['path'],
            'source_sha256': source['sha256'], 'originals_modified': False,
            'bindings': [{'image': 'map', 'original_path': 'X:/map.png', 'path': path,
                          'sha256': file_hash(config.source_file(path)), 'evidence': {}}]}


def test_repair_changes_only_opted_in_fingerprints_and_rejects_stale_map(library):
    config, _ = library
    rows = records(working(config))
    record, healthy = deepcopy(rows[0]), rows[1]
    source = config.source_file(record['files'][0]['path'])
    texture = source.parent / 'map.png'
    texture.write_bytes(b'synthetic image')
    relative = texture.relative_to(config.source_root).as_posix()
    worker = config.project_root / 'src/local_asset_library/blender_repair_worker.py'
    worker.write_text('synthetic repair worker')
    old = inspection_input(config, record)[3]
    stable = inspection_input(config, healthy)[3]
    record['texture_repair'] = synthetic_recipe(config, record, relative)
    assert inspection_input(config, record)[3] != old
    assert inspection_input(config, healthy)[3] == stable
    content = inspection_input(config, record, content_only=True)[3]
    worker.write_text('changed settings only')
    assert inspection_input(config, record, content_only=True)[3] == content
    texture.write_bytes(b'changed texture')
    with pytest.raises(ConfigError, match='dependency changed'):
        validate_recipe(config, record)


def test_override_cannot_cross_pack_or_escape_root(library):
    config, _ = library
    row = deepcopy(records(working(config))[0])
    other = config.source_root / 'other'
    other.mkdir()
    (other / 'map.png').write_bytes(b'x')
    row['texture_repair'] = synthetic_recipe(config, row, 'other/map.png')
    with pytest.raises(ConfigError, match='subpack boundary'):
        validate_recipe(config, row)
    row['texture_repair']['bindings'][0]['path'] = '../escape.png'
    with pytest.raises(ConfigError):
        validate_recipe(config, row)


def test_exact_maps_are_subpack_scoped_and_unmatched_input_stays_faulty(library):
    config, _ = library
    row = deepcopy(records(working(config))[0])
    source = row['files'][0]
    row['primary_inspection_path'] = source['path']
    row['technical'] = {'textures': [{'name': 'map', 'original_path': 'X:\\map.png',
                                     'required_for_render': True, 'status': 'rejected',
                                     'render_users': ['material:mat']}], 'meshes': []}
    path = config.source_file(source['path']).parent / 'map.png'
    path.write_bytes(b'synthetic image')
    relative = path.relative_to(config.source_root).as_posix()
    recipe, faults = build_recipe(config, row, [relative], [])
    assert recipe['bindings'][0]['path'] == relative and not faults
    recipe, faults = build_recipe(config, row, ['other/map.png'], [])
    assert recipe is None and faults[0]['image'] == 'map'


def test_caption_allowlist_excludes_unrelated_failures(overnight):
    config, work, _ = overnight
    pending = plan(config)
    target = pending['targets'][1]['asset_id']
    result = plan(config, asset_ids=[target])
    assert result['selected'] == 1 and result['targets'][0]['asset_id'] == target
    assert plan(config, asset_ids=[])['selected'] == 0
    with pytest.raises(ConfigError, match='unknown asset'):
        plan(config, asset_ids=['asset_unknown'])


def test_repaired_source_handoff_contains_verified_bindings_and_import_limit(library):
    config, _ = library
    work = ready(config)
    row = deepcopy(records(work)[0])
    source = row['files'][0]
    texture = config.source_file(source['path']).parent / 'map.png'
    texture.write_bytes(b'synthetic image')
    path = texture.relative_to(config.source_root).as_posix()
    row['texture_repair'] = synthetic_recipe(config, row, path)
    row['technical']['textures'] = [{'name': 'map', 'render_users': ['material:mat']}]
    row['dependencies'].append({'path': path, 'sha256': file_hash(texture), 'status': 'available',
                                'from': source['path'], 'role': 'texture', 'required_for_render': True})
    update_record(work, row)
    payload, _, _ = AssetService(work).execute('get_asset', {'asset_id': row['asset_id']})
    assert payload['usable'] is True
    binding = payload['texture_overrides'][0]
    assert binding['resolved_path'] == str(texture)
    assert binding['material_users'] == ['material:mat']
    assert any('unchanged original' in s for s in payload['limitations'])
