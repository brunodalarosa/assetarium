"""Shared project-layout dependencies; exact paths, verified bytes, no basename guessing."""
from copy import deepcopy
from pathlib import Path, PurePosixPath

from .config import ConfigError, _relative
from .publication import request_memo

KIND = 'shared_project_layout_v1'


def dependency_file(config, item):
    """Read a recorded dependency, without widening ordinary source-file access."""
    evidence = item.get('dependency_resolution')
    if not evidence:
        return config.source_file(item['path'])
    from .sources import get_source, bound
    from .captions import file_hash
    if not isinstance(evidence, dict) or not config.sources_registry or evidence.get('kind') != KIND:
        raise ConfigError('Unknown shared dependency resolution')
    original, target = evidence.get('original_path', ''), item.get('path', '')
    consumer = evidence.get('consumer_path', '')
    if any(not isinstance(value, str) for value in (original, target, consumer)):
        raise ConfigError('Invalid shared dependency path')
    _relative(original)
    _relative(target)
    _relative(consumer)
    consumer_key = consumer.split('/', 1)[0]
    if (original.split('/', 1)[0] != consumer_key or item.get('from', consumer) != consumer
            or config.source_key and config.source_key != consumer_key
            or original.split('/', 1)[-1].casefold() != target.split('/', 1)[-1].casefold()
            or len(PurePosixPath(original).parts) < 3):
        raise ConfigError('Shared dependency does not match its recorded project layout')
    source = get_source(config, consumer_key)
    provider = get_source(config, target.split('/', 1)[0])
    if not provider['enabled']:
        raise ConfigError('Shared dependency source is disabled; enable it in Asset sources')
    if (provider['id'] != evidence.get('provider_id') or provider['key'] == consumer_key
            or item.get('sha256') != evidence.get('sha256')):
        raise ConfigError('Shared dependency provider identity or hash changed')
    owner = bound(config, source)
    if file_hash(owner.source_file(consumer)) != evidence.get('consumer_sha256'):
        raise ConfigError('Shared dependency referring model changed; scan its source again')
    # An exact, healthy original reference always has precedence over a resolution.
    original_file = Path(source['path']) / original.split('/', 1)[1]
    if original_file.exists():
        raise ConfigError('Original dependency is now present; scan its source again')
    path = bound(config, provider).source_file(target)
    if file_hash(path) != item['sha256']:
        raise ConfigError('Shared dependency content changed; scan its source again')
    candidates = request_memo(('shared-dependency-candidates', config, original),
                              lambda: SharedDependencies(config).candidates(original))
    if not candidates or {entry['sha256'] for entry in candidates} != {item['sha256']}:
        raise ConfigError('Shared dependency candidates changed or conflict; scan its source again')
    return path


class SharedDependencies:
    """One scan's candidate set. A provider need not contain catalogued models."""
    def __init__(self, config):
        self.config, self.matches = config, {}
        from .sources import registry
        self.sources = [s for s in registry(config)['sources'] if s['enabled']]

    def candidates(self, original):
        from .sources import bound
        from .captions import file_hash
        key, relative = original.split('/', 1)
        if original not in self.matches:
            found = []
            for source in self.sources:
                if source['key'] == key:
                    continue
                scoped = bound(self.config, source)
                target = source['key'] + '/' + relative
                # Probe only the complete project-relative path, never search disk.
                if not (scoped.source_root / relative).is_file():
                    continue
                path = scoped.source_file(target)  # Reject escaping links and metadata.
                found.append({'path': target, 'sha256': file_hash(path), 'provider_id': source['id']})
            self.matches[original] = sorted(found, key=lambda item: item['path'])
        return self.matches[original]

    def resolve(self, source, dependency, image_name=None):
        # Additional format adapters can consume the same resolver. Only the
        # glTF image adapter currently supports scene-only path rebinding.
        if (not self.config.sources_registry or dependency['status'] != 'missing'
                or dependency['role'] != 'texture' or dependency['evidence'] != 'glTF images.uri'
                or not dependency.get('path') or len(PurePosixPath(dependency['path']).parts) < 3):
            return
        original = dependency['path']
        candidates = self.candidates(original)
        if not candidates:
            dependency['error'] = 'Referenced texture is missing; no matching project-relative path in enabled asset sources'
            return
        if len({item['sha256'] for item in candidates}) != 1:
            dependency.update(status='ambiguous', error='Shared dependency has conflicting files at the same project-relative path',
                              resolution_candidates=deepcopy(candidates))
            return
        chosen = candidates[0]
        evidence = {'kind': KIND, 'original_path': original, 'original_status': dependency['status'],
                    'consumer_path': source['path'], 'consumer_sha256': source['sha256'],
                    'provider_id': chosen['provider_id'], 'sha256': chosen['sha256'],
                    'image': image_name or PurePosixPath(dependency['reference']).name,
                    'equivalent_candidates': deepcopy(candidates)}
        dependency.update(path=chosen['path'], sha256=chosen['sha256'], status='available',
                          dependency_resolution=evidence)


def repair_recipe(config, record):
    mapped = [d for d in record['dependencies'] if d.get('dependency_resolution')]
    if not mapped:
        return None
    source = next(f for f in record['files'] if f['path'] == record['primary_inspection_path'])
    mapped = [d for d in mapped if d['from'] == source['path']]
    if not mapped:
        return None
    bindings = []
    for dep in mapped:
        original = str((config.source_file(source['path']).parent / dep['reference']).resolve())
        bindings.append({'image': dep['dependency_resolution']['image'], 'original_path': original,
                         'path': dep['path'], 'sha256': dep['sha256'], 'role': 'Albedo',
                         'from': dep['from'], 'dependency_resolution': deepcopy(dep['dependency_resolution']),
                         'preserve_supplied_alpha': False, 'evidence': {'kind': KIND}})
    from .dependency_overrides import repair_recipe as explicit_recipe
    local = explicit_recipe(config, record)
    if local:
        bindings.extend(local['bindings'])
    return {'schema_version': 1, 'kind': 'shared_dependency_paths', 'asset_id': record['asset_id'],
            'source_path': source['path'], 'source_sha256': source['sha256'], 'originals_modified': False,
            'authorization': 'Shared project-layout dependency resolution; owner-approved system feature',
            'bindings': bindings}


def worker_files(config, recipe):
    """Exact per-file grants for a trusted background worker; no directory grants."""
    from .sources import get_source
    files = []
    for binding in recipe['bindings']:
        if not binding.get('dependency_resolution'):
            continue
        path = dependency_file(config, binding)
        provider = get_source(config, binding['path'].split('/', 1)[0])
        files.append({**binding, 'resolved_path': str(path), 'provider_root': provider['path']})
    return files
