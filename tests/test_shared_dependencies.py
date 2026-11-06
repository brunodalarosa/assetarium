"""Arbitrarily named split sources exercise shared paths and revoked dependencies."""
from copy import deepcopy
import json
import os

from PIL import Image
import pytest

from test_sources import managed
from local_asset_library import sources
from local_asset_library.catalog import build_inventory, detail
from local_asset_library.captions import file_hash
from local_asset_library.config import ConfigError
from local_asset_library.dependency_resolution import dependency_file, worker_files
from local_asset_library.incremental import working, update_record
from local_asset_library.retrieval import source_check, resolved_detail
from local_asset_library.texture_repair import validate_recipe
from local_asset_library.publication import generation, snapshot


def split(managed):
    config, _, consumer, _ = managed
    folder = config.project_root.parent / 'shared-art'
    (folder / 'ExampleProject/Textures').mkdir(parents=True)
    texture = folder / 'ExampleProject/Textures/map.png'
    Image.new('RGBA', (4, 4), '#f07030').save(texture)
    provider = sources.add(config, str(folder))
    scoped = sources.bound(config, consumer)
    model = scoped.source_root / 'ExampleProject/Models/mesh.gltf'
    model.parent.mkdir(parents=True)
    model.write_text(json.dumps({'asset': {'version': '2.0'}, 'images': [
        {'uri': '../Textures/map.png', 'name': 'palette'}]}))
    return config, scoped, consumer, provider, model, texture


def mesh(scoped):
    return next(r for r in build_inventory(scoped)[1] if r['display_name'] == 'mesh')


def test_texture_only_provider_resolves_without_scan_or_source_specific_rules(managed):
    config, scoped, consumer, provider, model, texture = split(managed)
    before = model.read_bytes(), texture.read_bytes()
    record = mesh(scoped)
    dep = record['dependencies'][0]
    assert dep['status'] == 'available'
    assert dep['path'] == provider['key'] + '/ExampleProject/Textures/map.png'
    assert dep['dependency_resolution']['original_status'] == 'missing'
    assert dependency_file(scoped, dep) == texture
    with pytest.raises(ConfigError, match='different asset source'):
        scoped.source_file(dep['path'])
    assert source_check(scoped, record)
    assert validate_recipe(scoped, record)['kind'] == 'shared_dependency_paths'
    assert worker_files(scoped, record['texture_repair'])[0]['resolved_path'] == str(texture)
    assert before == (model.read_bytes(), texture.read_bytes())
    sources.scan_source(config, consumer)
    work = working(scoped)
    fresh = detail(work, record['asset_id'])
    fresh['processing']['inspection'] = 'complete'
    update_record(work, fresh)
    sources.scan_source(config, consumer)
    assert detail(work, record['asset_id'])['processing']['inspection'] == 'complete'
    assert detail(work, record['asset_id'])['texture_repair'] == record['texture_repair']


def test_combined_inventory_and_original_byte_audit_share_the_same_resolution(managed):
    from local_asset_library.inspection import source_evidence
    config, scoped, _, _, _, _ = split(managed)
    record = next(r for r in build_inventory(config)[1] if r['display_name'] == 'mesh')
    assert record['texture_repair']['kind'] == 'shared_dependency_paths'
    evidence = source_evidence(scoped, [record])
    assert len(evidence) == 2 and all(item['matches_catalog'] for item in evidence)


def test_disabled_consumer_remains_manually_browsable_with_an_enabled_provider(managed):
    config, scoped, consumer, _, _, texture = split(managed)
    record = mesh(scoped)
    value = deepcopy(sources.registry(config))
    next(s for s in value['sources'] if s['id'] == consumer['id'])['enabled'] = False
    sources.save_registry(config, value)
    assert dependency_file(scoped, record['dependencies'][0]) == texture
    assert source_check(scoped, record)


def test_exact_local_file_wins_and_basename_only_match_is_not_used(managed):
    _, scoped, _, _, model, texture = split(managed)
    local = model.parent.parent / 'Textures/map.png'
    local.parent.mkdir()
    local.write_bytes(b'local exact file')
    record = mesh(scoped)
    assert record['dependencies'][0]['path'].startswith(scoped.source_key + '/')
    assert 'texture_repair' not in record
    local.unlink()
    texture.rename(texture.with_name('different.png'))
    same_name = texture.parent.parent / 'Elsewhere/map.png'
    same_name.parent.mkdir()
    same_name.write_bytes(b'an unrelated basename')
    record = mesh(scoped)
    assert record['dependencies'][0]['status'] == 'missing'
    assert 'texture_repair' not in record


@pytest.mark.parametrize('identical', [True, False])
def test_duplicate_layouts_require_identical_bytes_and_keep_candidate_evidence(managed, identical):
    config, scoped, _, _, _, texture = split(managed)
    folder = config.project_root.parent / 'another-provider'
    target = folder / 'ExampleProject/Textures/map.png'
    target.parent.mkdir(parents=True)
    target.write_bytes(texture.read_bytes() if identical else b'a different image')
    sources.add(config, str(folder))
    record = mesh(scoped)
    dep = record['dependencies'][0]
    assert dep['status'] == ('available' if identical else 'ambiguous')
    candidates = dep['dependency_resolution']['equivalent_candidates'] if identical else dep['resolution_candidates']
    assert len(candidates) == 2
    if not identical:
        assert 'texture_repair' not in record
        with pytest.raises(ConfigError, match='conflicting'):
            source_check(scoped, record)


@pytest.mark.parametrize('change', ['disable', 'remove', 'identity', 'texture', 'consumer', 'local', 'conflict'])
def test_recorded_shared_resolution_revalidates_after_changes(managed, change):
    config, scoped, _, provider, model, texture = split(managed)
    record = mesh(scoped)
    value = deepcopy(sources.registry(config))
    if change == 'disable':
        next(s for s in value['sources'] if s['id'] == provider['id'])['enabled'] = False
    elif change == 'remove':
        value['sources'] = [s for s in value['sources'] if s['id'] != provider['id']]
    elif change == 'identity':
        next(s for s in value['sources'] if s['id'] == provider['id'])['id'] = 'f' * 32
    elif change == 'texture':
        texture.write_bytes(b'changed texture')
    elif change == 'consumer':
        model.write_text(model.read_text() + ' ')
    elif change == 'local':
        local = model.parent.parent / 'Textures/map.png'
        local.parent.mkdir()
        local.write_bytes(texture.read_bytes())
    else:
        folder = config.project_root.parent / 'conflicting-provider'
        target = folder / 'ExampleProject/Textures/map.png'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'a conflicting image')
        sources.add(config, str(folder))
    if change in {'disable', 'remove', 'identity'}:
        sources.save_registry(config, value)
    with pytest.raises(ConfigError):
        source_check(scoped, record)
    assert not any((scoped.metadata_root / 'inspection').glob('**/result.json'))


def test_provider_link_escape_and_parent_traversal_remain_rejected(managed):
    _, scoped, _, _, model, texture = split(managed)
    outside = texture.parents[3] / 'outside.png'
    outside.write_bytes(texture.read_bytes())
    texture.unlink()
    try:
        texture.symlink_to(outside)
    except OSError:
        pytest.skip('File symlinks unavailable')
    record = mesh(scoped)
    assert record['dependencies'][0]['status'] == 'rejected'
    assert 'texture_repair' not in record
    texture.unlink()
    model.write_text(json.dumps({'images': [{'uri': '../../../../outside.png'}]}))
    assert mesh(scoped)['dependencies'][0]['status'] == 'rejected'


@pytest.mark.skipif(os.name != 'nt', reason='Windows junction boundary')
def test_provider_directory_junction_cannot_grant_an_external_texture(managed):
    import subprocess
    _, scoped, _, _, _, texture = split(managed)
    outside = texture.parents[3] / 'external-textures'
    outside.mkdir()
    (outside / texture.name).write_bytes(texture.read_bytes())
    texture.unlink()
    texture.parent.rmdir()
    result = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(texture.parent), str(outside)],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stdout + result.stderr
    record = mesh(scoped)
    assert record['dependencies'][0]['status'] == 'rejected'
    assert 'texture_repair' not in record


def test_shared_dependencies_reach_scoped_detail_and_preview_and_revoke_tickets(managed, monkeypatch):
    from types import SimpleNamespace
    from local_asset_library.interactive_preview import InteractivePreviewService
    config, scoped, consumer, provider, _, texture = split(managed)
    sources.scan_source(config, consumer)
    work = working(scoped)
    record = mesh(scoped)
    service = SimpleNamespace(config=work, record=lambda identifier: record)
    preview = InteractivePreviewService(service)
    resolved = resolved_detail(work, record['asset_id'])
    assert resolved['dependencies'][0]['resolved_path'] == str(texture)
    package = preview.prepare(record['asset_id'], 'gltf', generation(work))
    assert package['status'] == 'ready'
    assert len(package['files']) == 2
    for index in range(2):
        assert preview.file(package['ticket'], index)['status'] == 'ready'
    value = deepcopy(sources.registry(config))
    next(s for s in value['sources'] if s['id'] == provider['id'])['enabled'] = False
    sources.save_registry(config, value)
    assert preview.file(package['ticket'], 1)['status'] == 'faulty'
    value = deepcopy(sources.registry(config))
    next(s for s in value['sources'] if s['id'] == provider['id'])['enabled'] = True
    sources.save_registry(config, value)
    reopened = preview.prepare(record['asset_id'], 'gltf', generation(work))
    assert reopened['status'] == 'ready'
    assert reopened['ticket'] != package['ticket']


def test_new_dependency_fingerprint_requeues_only_changed_failures(managed, monkeypatch):
    from local_asset_library import incremental
    config, scoped, consumer, provider, _, _ = split(managed)
    value = deepcopy(sources.registry(config))
    next(s for s in value['sources'] if s['id'] == provider['id'])['enabled'] = False
    sources.save_registry(config, value)
    sources.scan_source(config, consumer)
    work = working(scoped)
    record = next(r for r in sources.read_records(work) if r['display_name'] == 'mesh')
    fp = incremental.stage_content(work, record, 'inspection')
    with incremental.ledger(scoped) as db:
        incremental.checkpoint(db, record['asset_id'], 'inspection', 'failed-fingerprint', 'failed',
                               {'error': 'missing texture', 'fault_content': fp})
    value = deepcopy(sources.registry(config))
    next(s for s in value['sources'] if s['id'] == provider['id'])['enabled'] = True
    sources.save_registry(config, value)
    sources.scan_source(config, consumer)
    fresh = detail(work, record['asset_id'])
    assert incremental.stage_content(work, fresh, 'inspection') != fp
    with incremental.ledger(scoped) as db:
        assert db.execute("select count(*) from history where status='failed'").fetchone()[0] == 1


@pytest.mark.parametrize('tamper', ['kind', 'path', 'provider', 'model_hash', 'shape'])
def test_malformed_or_forged_resolution_is_a_visible_fault(managed, tamper):
    _, scoped, _, _, _, _ = split(managed)
    item = deepcopy(mesh(scoped)['dependencies'][0])
    if tamper == 'kind':
        item['dependency_resolution']['kind'] = 'unknown'
    elif tamper == 'path':
        item['dependency_resolution']['original_path'] = '../escaped/map.png'
    elif tamper == 'provider':
        item['dependency_resolution']['provider_id'] = 'a' * 32
    elif tamper == 'model_hash':
        item['dependency_resolution']['consumer_sha256'] = '0' * 64
    else:
        item['dependency_resolution'] = 'invalid evidence'
    with pytest.raises(ConfigError):
        dependency_file(scoped, item)


def test_split_projects_joined_under_one_folder_keep_their_texture_and_render_key(managed):
    """Sibling sub-packs that borrowed a core pack's texture as separate folders still do once a folder is added
    around them, with the same inspection key, so a finished render is reused instead of rendered again."""
    from pathlib import Path
    from local_asset_library.result_store import first_sight_key
    from local_asset_library.incremental import inspection_input
    config, _, consumer, _ = managed
    worker = config.project_root / 'src/local_asset_library/blender_shared_dependency_worker.py'
    worker.write_text('synthetic worker')  # Its hash joins the inspection key.
    parent = Path(consumer['path']).parent
    texture = parent / 'art/ExampleProject/Textures/map.png'
    texture.parent.mkdir(parents=True)
    Image.new('RGBA', (4, 4), '#f07030').save(texture)
    provider = sources.add(config, str(parent / 'art'))
    model = Path(consumer['path']) / 'ExampleProject/Models/mesh.gltf'
    model.parent.mkdir(parents=True)
    model.write_text(json.dumps({'asset': {'version': '2.0'}, 'images': [{'uri': '../Textures/map.png', 'name': 'palette'}]}))
    scoped = sources.bound(config, consumer)
    apart = mesh(scoped)
    assert apart['dependencies'][0]['path'] == provider['key'] + '/ExampleProject/Textures/map.png'
    keys = inspection_input(scoped, apart)[3], first_sight_key(scoped, apart)
    joined = sources.add(config, str(parent))
    assert set(joined['replaced']) == {consumer['key'], provider['key'], 'two'}
    folder = sources.bound(config, sources.get_source(config, joined['key']))
    record = mesh(folder)
    dep = record['dependencies'][0]
    assert dep['status'] == 'available' and dep['path'] == joined['key'] + '/art/ExampleProject/Textures/map.png'
    assert dependency_file(folder, dep) == texture and validate_recipe(folder, record)['kind'] == 'shared_dependency_paths'
    assert worker_files(folder, record['texture_repair']) == []  # Inside its own folder: read like any source file.
    assert (inspection_input(folder, record)[3], first_sight_key(folder, record)) == keys
    # A path that differs in more than one folder, or only in the file's own folder, is not a sibling layout.
    from local_asset_library.dependency_resolution import sibling_path
    assert sibling_path('k/a/P/T/x.png', 'k/b/P/T/x.png') and not sibling_path('k/a/P/T/x.png', 'k/b/Q/T/x.png')
    assert not sibling_path('k/a/P/T/x.png', 'k/a/P/U/x.png')
