"""Owner-chosen texture folder for models missing textures (decision 0021), with synthetic unrelated names."""
from argparse import Namespace

import pytest

from local_asset_library import sources
from local_asset_library.config import ConfigError
from local_asset_library.incremental import inspection_input, update_record, working
from local_asset_library.sources import read_records
from local_asset_library.texture_folders import KIND
from local_asset_library.texture_repair import validate_recipe
from test_blender_integration import small_fixture  # noqa: F401 (fixture)
from test_sources import managed  # noqa: F401 (fixture)

# Model -> textures its file names. "a" differs per pipeline folder, "b" exists once, "c" twice with identical
# bytes, "d" nowhere.
NEEDS = {'rock': ['a'], 'bush': ['b'], 'tree': ['a', 'd'], 'cactus': ['c']}


def pack(root):
    for name in list(NEEDS) + ['fence']:
        path = root / 'Models' / (name + '.fbx')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fbx ' + name.encode())
    for relative, data in (('Tex/PBR/Rocks/a.png', b'pbr a'), ('Tex/URP/Rocks/a.png', b'urp a'),
                           ('Tex/Other/b.png', b'only b'), ('Tex/PBR/c.png', b'same c'), ('Tex/URP/c.png', b'same c')):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def inspected(work):
    """What a Blender inspection records for models whose FBX names textures without a usable path."""
    for record in read_records(work):
        names = NEEDS.get(record['display_name'], [])
        record['technical'] = {'inspected_path': record['files'][0]['path'], 'inspected_sha256': record['files'][0]['sha256'],
                               'inspected_format': 'fbx', 'textures': [
                                   {'name': n, 'original_path': f'C:\\author\\textures\\{n}.png', 'required_for_render': True,
                                    'status': 'missing', 'render_users': ['material:m']} for n in names]}
        record['processing'].update(inspection='complete', previews='failed' if names else 'complete')
        update_record(work, record)


@pytest.fixture
def source(managed, tmp_path):
    config = managed[0]
    added = sources.add(config, str(pack(tmp_path / 'pack')))
    sources.scan_source(config, added)
    work = working(sources.bound(config, added))
    inspected(work)
    sources.scan_source(config, added)
    return config, added, work


def by_name(work):
    return {r['display_name']: r for r in read_records(work)}


def test_suggestion_offers_pipeline_folders_with_counts(source):
    config, added, _ = source
    found = sources.source_status(config, added)['texture_suggestion']
    assert found['assets'] == 4
    options = {o['folder']: o for o in found['folders']}
    assert set(options) == {'Tex/PBR', 'Tex/URP'}  # Shallowest folders; Tex/PBR/Rocks is covered by Tex/PBR.
    assert options['Tex/PBR']['fixes_without_single_copies'] == 2  # rock, and cactus whose "c" is in the folder
    assert options['Tex/PBR']['fixes'] == 3  # rock, bush (single copy), cactus (identical copies)
    assert options['Tex/PBR']['unresolved'] == 1 and 'd.png: No file with this name' in options['Tex/PBR']['unresolved_examples'][0]['reason']
    assert found['single_copies_only']['fixes'] == 2  # bush and cactus; rock needs a folder choice


def test_applying_writes_recipes_only_for_fully_resolved_models(source):
    config, added, work = source
    healthy = by_name(work)['fence']
    sources.set_texture_folder(config, added['key'], 'Tex/PBR', True)
    sources.scan_source(config, added)
    records = by_name(work)
    rock, bush, tree = records['rock'], records['bush'], records['tree']
    assert rock['texture_repair']['kind'] == KIND and rock['texture_repair']['bindings'][0]['path'].endswith('Tex/PBR/Rocks/a.png')
    assert bush['texture_repair']['bindings'][0]['evidence']['resolution'] == 'single_copy'
    assert 'Tex/PBR' in rock['texture_repair']['authorization'] and rock['texture_repair']['originals_modified'] is False
    assert rock['processing']['previews'] == 'pending' and validate_recipe(work, rock) == rock['texture_repair']
    assert 'texture_repair' not in tree and tree['processing']['previews'] == 'failed'  # "d" is missing: all or nothing.
    assert records['fence'] == healthy
    assert sources.source_status(config, added)['texture_suggestion']['assets'] == 1  # Only tree still waits.
    # The recipe is part of the inspection input, so the next Process assets renders these models once.
    assert inspection_input(work, rock, content_only=True)[3] != inspection_input(
        work, {**rock, 'texture_repair': None}, content_only=True)[3]


def test_without_single_copies_only_folder_matches_are_used(source):
    config, added, work = source
    sources.set_texture_folder(config, added['key'], 'Tex/URP', False)
    sources.scan_source(config, added)
    records = by_name(work)
    assert records['rock']['texture_repair']['bindings'][0]['path'].endswith('Tex/URP/Rocks/a.png')
    assert records['cactus']['texture_repair']['bindings'][0]['path'].endswith('Tex/URP/c.png')  # In the folder.
    assert 'texture_repair' not in records['bush']  # Only elsewhere, and single copies are off.


def test_undo_drops_the_recipes_and_refuses_unoffered_folders(source):
    config, added, work = source
    with pytest.raises(ConfigError, match='not one of the current suggestions'):
        sources.set_texture_folder(config, added['key'], 'Tex/Other', True)
    with pytest.raises(ConfigError, match='single copies, or both'):
        sources.set_texture_folder(config, added['key'], None, False)
    sources.set_texture_folder(config, added['key'], 'Tex/PBR', True)
    sources.scan_source(config, added)
    sources.forget_texture_folder(config, added['key'])
    sources.scan_source(config, added)
    assert not any(r.get('texture_repair') for r in read_records(work))
    assert sources.source_status(config, added)['texture_folder'] is None
    with pytest.raises(ConfigError, match='No texture folder'):
        sources.forget_texture_folder(config, added['key'])


def test_real_blender_renders_a_missing_texture_from_the_chosen_folder(small_fixture):
    """Inspection reports the texture missing; the repair worker renders it from the folder recipe."""
    import hashlib, json
    from PIL import Image
    from test_blender_integration import BLENDER, invoke
    from local_asset_library.inspection import blender_command, environment, run_process
    from local_asset_library.texture_folders import copies, plan
    config = small_fixture
    corners = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    faces = ((1, 2, 4, 3), (5, 7, 8, 6), (1, 5, 6, 2), (3, 4, 8, 7), (1, 3, 7, 5), (2, 6, 8, 4))
    (config.source_root / 'model.obj').write_text(
        'mtllib model.mtl\n' + ''.join(f'v {x} {y} {z}\n' for x, y, z in corners) + 'vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\n'
        'usemtl paint\n' + ''.join('f ' + ' '.join(f'{v}/{i + 1}' for i, v in enumerate(face)) + '\n' for face in faces))
    (config.source_root / 'model.mtl').write_text('newmtl paint\nKd 1 1 1\nmap_Kd C:/author/textures/paint.png\n')
    rows = []
    for folder, colour in (('Tex/PBR', 'red'), ('Tex/URP', 'blue')):
        path = config.source_root / folder / 'paint.png'
        path.parent.mkdir(parents=True)
        Image.new('RGB', (8, 8), colour).save(path)
        rows.append({'path': 'pack/' + folder + '/paint.png', 'status': 'available', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    process, result = invoke(config, 'model.obj', 'obj')
    assert result['status'] == 'failed' and 'texture' in result['errors'][0]
    record = {'asset_id': 'fixture', 'display_name': 'model', 'technical': result['technical']}
    fixed, unresolved = plan([record], copies(rows), 'Tex/PBR', False)
    assert not unresolved and fixed['fixture'][0]['path'] == 'pack/Tex/PBR/paint.png'
    bindings = [{**b, 'path': b['path'].removeprefix('pack/')} for b in fixed['fixture']]  # This fixture has no source key.
    source_sha = hashlib.sha256((config.source_root / 'model.obj').read_bytes()).hexdigest()
    output = config.output_path('data', 'repaired')
    job = {'asset_id': 'fixture', 'project_root': str(config.project_root), 'source_root': str(config.source_root),
           'source_path': 'model.obj', 'source_sha256': source_sha, 'format': 'obj', 'output': str(output), 'resolution': 320,
           'texture_repair': {'schema_version': 1, 'kind': KIND, 'asset_id': 'fixture', 'source_path': 'model.obj',
                              'source_sha256': source_sha, 'originals_modified': False, 'bindings': bindings}}
    task = config.output_path('data', 'repair-job.json')
    task.write_text(json.dumps(job), encoding='utf-8')
    from pathlib import Path
    worker = Path(__file__).resolve().parents[1] / 'src/local_asset_library/blender_repair_worker.py'
    repaired = run_process(blender_command(BLENDER, '--python-exit-code', '5', '--python', str(worker), '--', str(task)),
                           config.project_root, environment(config), 120)
    outcome = json.loads((output / 'result.json').read_text())
    assert repaired['returncode'] == 0 and outcome['status'] == 'complete', (outcome.get('errors'), repaired['output'][-800:])
    assert outcome['technical']['texture_repair']['bindings'][0]['path'] == 'Tex/PBR/paint.png'


def test_the_owner_cli_lists_the_choices(source, capsys):
    from local_asset_library.owner_commands import sources_command
    config, added, _ = source
    args = Namespace(action='textures', key=added['key'], use=None, single_copies=False, undo=False, json=False, quiet=False)
    sources_command(args, config)
    out = capsys.readouterr().out
    assert "4 models can't find their textures" in out and '--use "Tex/PBR"  fixes 2; with --single-copies 3' in out
