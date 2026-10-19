"""Split publisher packs use authorized texture paths without moving originals."""
from copy import deepcopy
import json

import pytest

from test_sources import managed
from test_incremental import library
from local_asset_library import sources
from local_asset_library.catalog import build_inventory, detail, save_json
from local_asset_library.captions import file_hash
from local_asset_library.dependency_overrides import synchronize_recipe
from local_asset_library.incremental import working, update_record


def split_pack(managed):
    config, _, source, other = managed
    scoped = sources.bound(config, source)
    model = scoped.source_root / 'addon/Models/mesh.gltf'
    model.parent.mkdir(parents=True)
    model.write_text(json.dumps({'asset': {'version': '2.0'},
                                'images': [{'uri': '../Textures/map.png', 'name': 'atlas'}]}))
    texture = scoped.source_root / 'core/Textures/map.png'
    texture.parent.mkdir(parents=True)
    texture.write_bytes(b'synthetic texture')
    model_path = source['key'] + '/addon/Models/mesh.gltf'
    original = source['key'] + '/addon/Textures/map.png'
    target = source['key'] + '/core/Textures/map.png'
    manifest = {'schema_version': 1, 'authorization': 'Synthetic explicit owner approval',
                'sources': {model_path: file_hash(model)},
                'paths': {original: {'path': target, 'sha256': file_hash(texture)}}}
    return scoped, model, texture, manifest


def asset(scoped):
    return next(a for a in build_inventory(scoped)[1] if a['display_name'] == 'mesh')


def test_split_texture_mapping_preserves_original_and_survives_rescan(managed):
    scoped, model, texture, manifest = split_pack(managed)
    before = model.read_bytes(), texture.read_bytes()
    assert asset(scoped)['dependencies'][0]['status'] == 'missing'
    save_json(scoped.output_path('data', 'library/dependency-overrides.json'), manifest)
    mapped = asset(scoped)
    dep = mapped['dependencies'][0]
    assert dep['status'] == 'available' and '/core/' in dep['path']
    assert dep['dependency_override']['original_status'] == 'missing'
    binding = mapped['texture_repair']['bindings'][0]
    assert binding['image'] == 'atlas' and binding['preserve_supplied_alpha'] is False
    assert binding['original_path'] == str((model.parent / '../Textures/map.png').resolve())
    config, _, source, _ = managed
    sources.scan_source(config, source)
    current = detail(working(scoped), mapped['asset_id'])
    current['processing']['inspection'] = 'complete'
    update_record(working(scoped), current)
    sources.scan_source(config, source)
    again = detail(working(scoped), mapped['asset_id'])
    assert again['texture_repair'] == mapped['texture_repair']
    assert again['processing']['inspection'] == 'complete'
    assert (model.read_bytes(), texture.read_bytes()) == before


@pytest.mark.parametrize('fault', ['source_changed', 'texture_changed', 'cross_source', 'escape', 'malformed'])
def test_invalid_mapping_remains_faulty_instead_of_substituting(managed, fault):
    scoped, model, texture, manifest = split_pack(managed)
    binding = next(iter(manifest['paths'].values()))
    if fault == 'source_changed':
        next_key = next(iter(manifest['sources']))
        manifest['sources'][next_key] = '0' * 64
    elif fault == 'texture_changed':
        binding['sha256'] = '0' * 64
    elif fault == 'cross_source':
        binding['path'] = managed[3]['key'] + '/map.png'
    elif fault == 'escape':
        binding['path'] = '../map.png'
    else:
        manifest['paths'][next(iter(manifest['paths']))] = 'invalid binding'
    save_json(scoped.output_path('data', 'library/dependency-overrides.json'), manifest)
    result = asset(scoped)
    assert result['dependencies'][0]['status'] == 'rejected'
    assert 'texture_repair' not in result


def test_mapping_removal_and_unrelated_repair_preservation():
    kept = {'texture_repair': {'kind': 'gltf_dependency_paths'}}
    synchronize_recipe(kept, {})
    assert 'texture_repair' not in kept
    unrelated = {'texture_repair': {'schema_version': 1, 'bindings': ['existing']}}
    before = deepcopy(unrelated)
    synchronize_recipe(unrelated, {})
    assert unrelated == before


def test_successful_missing_stage_drops_current_fault_but_retains_history(library, monkeypatch):
    from local_asset_library import incremental
    from local_asset_library.membership import records
    config, _ = library
    work = working(config)
    record = records(work)[0]
    record['stage_faults'] = {'inspection': {'error': 'old missing dependency'},
                              'caption': {'error': 'caption still missing'}}
    update_record(work, record)
    with incremental.ledger(config) as db:
        incremental.checkpoint(db, record['asset_id'], 'inspection', 'old', 'failed',
                               {'error': 'old missing dependency', 'fault_content': 'old input'})
    def completed(config, record, fingerprint, *args, **kwargs):
        return {'status': 'complete'}
    monkeypatch.setattr(incremental, 'run_inspection', completed)
    incremental.process(config, 'inspection', limit=1000)
    current = detail(work, record['asset_id'])
    assert 'inspection' not in current['stage_faults']
    assert 'caption' in current['stage_faults']
    with incremental.ledger(config) as db:
        assert db.execute("SELECT count(*) FROM history WHERE asset_id=? AND status='failed'",
                          (record['asset_id'],)).fetchone()[0] == 1


def test_source_owned_caption_retry_keeps_its_evidence_reference(managed):
    from local_asset_library.incremental import caption_input
    from local_asset_library.overnight import run_path, apply_saved
    from local_asset_library.membership import records
    config, _, source, _ = managed
    sources.scan_source(config, source)
    scoped = sources.bound(config, source)
    work = working(scoped)
    record = records(work)[0]
    identifier = '1' * 32
    raw = run_path(scoped, identifier) / 'attempts' / (record['asset_id'] + '.json')
    save_json(raw, {'status': 'failed', 'description': None, 'suggested_uses': [],
                   'attempts': [{'error': 'Synthetic retained generation failure'}],
                   'provenance': {'fingerprint': caption_input(work, record, prompt_version='v4')}})
    result = apply_saved(scoped, identifier, record['asset_id'])
    assert result['status'] == 'failed'
    assert work.output_path('data', result['result_path'].removeprefix('data/')) == raw
    assert raw.is_file()
