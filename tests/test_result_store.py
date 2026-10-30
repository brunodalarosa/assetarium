"""Results keyed by inputs (decision 0023): duplicates share them, moves keep them, nothing re-renders."""
import json
from pathlib import Path

from PIL import Image
import pytest

from test_sources import managed  # noqa: F401 -- fixture
from local_asset_library import incremental, result_store, sources
from local_asset_library.captions import file_hash
from local_asset_library.incremental import inspection_input, process, working
from local_asset_library.membership import records

OBJ = '# shared\nmtllib crate.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n'


def write_pack(root, folder, texture='tex/crate.png'):
    target = root / folder
    (target / Path(texture).parent).mkdir(parents=True, exist_ok=True)
    (target / 'crate.obj').write_text(OBJ)
    (target / 'crate.mtl').write_text(f'newmtl crate\nmap_Kd {texture}\n')
    Image.new('RGB', (4, 4), 'brown').save(target / texture)


def crate(config, source):
    sources.scan_source(config, source)
    work = working(sources.bound(config, source))
    return work, next(r for r in records(work) if r['display_name'] == 'crate')


def finished_result(work, record, key):
    """What a finished Blender run leaves in the store for ``key``."""
    _, source, _, _ = inspection_input(work, record)
    relative = result_store.result_path('inspection', key)
    folder = work.output_path('data', relative)
    folder.mkdir(parents=True, exist_ok=True)
    previews = []
    for view in ('front', 'side', 'three_quarter'):
        Image.new('RGB', (8, 8), 'gray').save(folder / f'{view}.png')
        previews.append({'filename': f'{view}.png', 'view_label': view, 'sha256': file_hash(folder / f'{view}.png'),
                         'quality': {'empty': False, 'off_frame': False}})
    texture = next(d['path'] for d in record['dependencies'] if d['role'] == 'texture')
    technical = {'autoexec_enabled': False, 'object_count': 1, 'mesh_object_count': 1, 'evaluated_instance_totals': {'triangles': 1},
                 'world_bounds': {}, 'units': {}, 'materials': [], 'armatures': [], 'animation_clips': [], 'meshes': [],
                 'textures': [{'name': 'crate.png', 'path': texture, 'sha256': 'x', 'status': 'available', 'required_for_render': True}]}
    result = {'schema_version': 1, 'asset_id': record['asset_id'], 'source_path': source['path'], 'format': 'obj',
              'status': 'complete', 'technical': technical, 'previews': previews, 'blender_version': 'synthetic',
              'render_settings': {'coordinate_convention': 'synthetic'}, 'errors': [], 'sources': []}
    (folder / 'result.json').write_text(json.dumps(result), encoding='utf-8')
    result_store.remember(work, 'inspection', key, 'data/' + relative, record['asset_id'])
    return relative


def test_keys_hold_content_and_relative_paths_never_locations(managed):
    config, _, one, two = managed
    write_pack(Path(one['path']), 'Crates')
    write_pack(Path(two['path']), 'Elsewhere/Deeper')
    work_one, first = crate(config, one)
    work_two, second = crate(config, two)
    assert first['asset_id'] != second['asset_id']
    key = inspection_input(work_one, first)[3]
    assert inspection_input(work_two, second)[3] == key  # Same bytes, same relative texture path: one result.
    write_pack(Path(two['path']), 'Other', texture='maps/crate.png')
    other = next(r for r in records(working(sources.bound(config, two))) if r['source_relative_identity'].startswith('Other')
                 ) if sources.scan_source(config, two) else None
    # The texture is found at another relative path, which changes what Blender resolves.
    assert inspection_input(working(sources.bound(config, two)), other)[3] != key


def test_a_duplicate_reuses_the_finished_result_without_rendering(managed, monkeypatch):
    config, _, one, two = managed
    write_pack(Path(one['path']), 'Crates')
    write_pack(Path(two['path']), 'Copy')
    work_one, first = crate(config, one)
    key = inspection_input(work_one, first)[3]
    relative = finished_result(work_one, first, key)
    monkeypatch.setattr(incremental, 'run_inspection', lambda *a, **k: pytest.fail('a duplicate must not render'))
    scoped = sources.bound(config, two)
    work_two, second = crate(config, two)
    assert second['asset_id'] not in process(scoped, 'inspection', 10, dry_run=True)['pending_ids']
    process(scoped, 'inspection', 10, asset_ids={second['asset_id']})
    second = next(r for r in records(work_two) if r['asset_id'] == second['asset_id'])
    assert second['processing']['inspection'] == 'complete' and second['inspection_run']['result_path'] == f'data/{relative}/result.json'
    assert {p['path'] for p in second['previews'] if p['origin'] == 'rendered'} == {f'data/{relative}/{v}.png' for v in ('front', 'side', 'three_quarter')}
    # Blender's texture paths follow this file, not the one that rendered first.
    texture = next(d for d in second['dependencies'] if d.get('evidence') == 'Blender inspected image datablock')
    assert texture['path'] == two['key'] + '/Copy/tex/crate.png'
    # No result was written into either asset folder.
    for source in (one, two):
        assert not [p for p in Path(source['path']).rglob('*') if p.suffix == '.png' and p.parent.name != 'tex']


def test_unusable_shared_result_is_forgotten_and_the_stage_runs(managed, monkeypatch):
    config, _, one, two = managed
    write_pack(Path(one['path']), 'Crates')
    write_pack(Path(two['path']), 'Copy')
    work_one, first = crate(config, one)
    key = inspection_input(work_one, first)[3]
    relative = finished_result(work_one, first, key)
    (work_one.output_path('data', relative) / 'front.png').write_bytes(b'changed')
    ran = []
    monkeypatch.setattr(incremental, 'run_inspection', lambda config, record, *a, **k: ran.append(record['asset_id']) or {'status': 'complete'})
    scoped = sources.bound(config, two)
    second = crate(config, two)[1]
    process(scoped, 'inspection', 10, asset_ids={second['asset_id']})
    assert ran and result_store.lookup(config, 'inspection', key) is None
