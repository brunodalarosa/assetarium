"""Explicit, source-hash-bound texture overrides; original files stay read only."""
from pathlib import PurePosixPath

from .captions import file_hash
from .config import ConfigError


def subpack(path):
    parts = PurePosixPath(path).parts
    return '/'.join(parts[:2] if parts[0] in {'synty-part1', 'craftpix-free-packs'} else parts[:1])


def validate_recipe(config, record):
    recipe = record.get('texture_repair')
    if not recipe:
        return None
    if (recipe.get('schema_version') != 1 or recipe.get('asset_id') != record['asset_id']
            or recipe.get('originals_modified') is not False or not recipe.get('bindings')):
        raise ConfigError('Invalid texture repair override')
    source = next((f for f in record['files'] if f['path'] == recipe['source_path']), None)
    if not source or source['sha256'] != recipe['source_sha256']:
        raise ConfigError('Texture repair does not match the original source')
    for b in recipe['bindings']:
        shared = recipe.get('kind') == 'shared_dependency_paths' and bool(b.get('dependency_resolution'))
        if shared and (b.get('from') != source['path'] or
                       (b.get('dependency_resolution') or {}).get('consumer_sha256') != source['sha256']):
            raise ConfigError('Shared texture binding does not match its referring model')
        if not shared and subpack(b['path']) != subpack(source['path']):
            raise ConfigError('Texture repair crosses a subpack boundary')
        from .dependency_resolution import dependency_file
        if file_hash(dependency_file(config, b) if shared else config.source_file(b['path'])) != b['sha256']:
            raise ConfigError('Texture repair dependency changed')
        for table in b['evidence'].get('tables', []):
            if file_hash(config.source_file(table['path'])) != table['sha256']:
                raise ConfigError('Publisher material table changed')
    return recipe
