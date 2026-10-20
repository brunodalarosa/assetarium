"""Explicit source-owned glTF texture paths; originals and healthy imports stay unchanged."""
from functools import lru_cache
from pathlib import PurePosixPath

from .config import ConfigError, _relative
from .publication import read_json


@lru_cache(maxsize=16)
def _manifest(path, stamp, size):
    value = read_json(path)
    if (value.get('schema_version') != 1 or not isinstance(value.get('authorization'), str)
            or not value['authorization'].strip()
            or not isinstance(value.get('sources'), dict) or not isinstance(value.get('paths'), dict)):
        raise ConfigError('Invalid dependency path override manifest')
    return value


def apply_override(config, source, dependency, inventory, image_name=None):
    if (not config.source_key or dependency['status'] != 'missing'
            or dependency['role'] != 'texture' or dependency['evidence'] != 'glTF images.uri'):
        return
    path = config.output_path('data', 'library/dependency-overrides.json')
    if not path.exists():
        return
    stat = path.stat()
    manifest = _manifest(path, stat.st_mtime_ns, stat.st_size)
    binding = manifest['paths'].get(dependency['path'])
    if binding is None or source['path'] not in manifest['sources']:
        return
    if (not isinstance(binding, dict) or not isinstance(binding.get('path'), str)
            or not isinstance(binding.get('sha256'), str)):
        raise ConfigError('Invalid dependency texture path binding')
    if manifest['sources'][source['path']] != source['sha256']:
        raise ConfigError('Dependency path override source changed')
    target = binding['path']
    _relative(target)
    if target.split('/', 1)[0] != config.source_key:
        raise ConfigError('Dependency path override crosses an asset source')
    config.source_file(target)
    measured = inventory.get(target)
    if not measured or measured['status'] != 'available' or measured['sha256'] != binding['sha256']:
        raise ConfigError('Dependency path override texture changed or unavailable')
    dependency['dependency_override'] = {
        'kind': 'explicit_source_texture_path', 'original_path': dependency['path'],
        'original_status': dependency['status'], 'image': image_name or PurePosixPath(dependency['reference']).name,
        'authorization': manifest['authorization']}
    dependency.update(path=target, sha256=binding['sha256'], status='available')


def repair_recipe(config, record):
    mapped = [d for d in record['dependencies'] if d.get('dependency_override')]
    if not mapped:
        return None
    sources = {d['from'] for d in mapped}
    if len(sources) != 1:
        raise ConfigError('Texture path overrides require one selected glTF source')
    source = next(f for f in record['files'] if f['path'] in sources)
    bindings = []
    for dep in mapped:
        original = str((config.source_file(source['path']).parent / dep['reference']).resolve())
        bindings.append({'image': dep['dependency_override']['image'], 'original_path': original,
                         'path': dep['path'], 'sha256': dep['sha256'], 'role': 'Albedo',
                         'preserve_supplied_alpha': False, 'evidence': dep['dependency_override']})
    return {'schema_version': 1, 'kind': 'gltf_dependency_paths', 'asset_id': record['asset_id'],
            'source_path': source['path'], 'source_sha256': source['sha256'],
            'authorization': mapped[0]['dependency_override']['authorization'],
            'originals_modified': False, 'bindings': bindings}


def synchronize_recipe(kept, fresh):
    recipe = fresh.get('texture_repair') or {}
    if recipe.get('kind') in {'gltf_dependency_paths', 'shared_dependency_paths'}:
        kept['texture_repair'] = recipe
    elif (kept.get('texture_repair') or {}).get('kind') in {'gltf_dependency_paths', 'shared_dependency_paths'}:
        kept.pop('texture_repair')
