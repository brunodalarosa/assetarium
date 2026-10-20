"""Versioned asset semantics; source bytes and existing inference inputs stay unchanged.

This is a small concrete dispatch contract, not a plugin registry. Recognizing a
type does not imply an installed decoder, description model or embedding modality.
"""
from collections import deque
from copy import deepcopy
import hashlib
import json
from pathlib import PurePosixPath
import re

from .config import ConfigError

CATALOG_VERSION = 2
STRUCTURE_VERSION = 1
ASSET_TYPES = ('model_3d', 'image', 'audio')
STAGES = ('inventory', 'inspection', 'previews', 'caption', 'embeddings')
RELATIONSHIPS = ('alternate_export', 'contains', 'depends_on', 'variant')
FILE_ROLES = ('primary', 'alternate_export', 'dependency', 'supplied_preview')
ID_PATTERN = r'asset_[0-9a-f]{32}'


def asset_type(record):
    # All v1 records were logical models, including unsupported model formats.
    return record.get('asset_type', 'model_3d')


def applicable_stages(record):
    return tuple(stage for stage in STAGES if not (asset_type(record) == 'image' and stage == 'caption'))


def supported_stage(record, stage):
    kind = asset_type(record)
    unsupported = kind == 'audio' or record.get('identity_version') == 'subasset-v1'
    return stage in applicable_stages(record) and (not unsupported or stage == 'inventory')


def description_supported(record):
    return asset_type(record) == 'model_3d' and supported_stage(record, 'caption')


def file_roles(record):
    if 'file_roles' in record:
        return dict(record['file_roles'])
    files = record.get('files', [])
    primary = record.get('primary_inspection_path') or (files[0]['path'] if files else None)
    return {f['path']: 'primary' if f['path'] == primary else 'alternate_export' for f in files}


def structure(record):
    """A fresh, bounded presentation view; never mutate shared cached records."""
    kind = asset_type(record)
    return {'version': STRUCTURE_VERSION, 'asset_type': kind,
            'identity_version': record.get('identity_version', 'asset-v1'),
            'parent_asset_id': record.get('parent_asset_id'),
            'applicable_stages': list(applicable_stages(record)),
            'preview_capabilities': {'still_image': kind in ('model_3d', 'image') and supported_stage(record, 'previews'),
                                     'playback': False, 'interactive_model': kind == 'model_3d' and supported_stage(record, 'previews')},
            'description_supported': description_supported(record),
            'direct_media_channel': 'image' if kind in ('model_3d', 'image') and supported_stage(record, 'embeddings') else None,
            'file_roles': file_roles(record)}


def child_id(parent, kind, key):
    if kind not in ('frame', 'clip', 'region') or not isinstance(key, str) or not key.strip() or len(key) > 256:
        raise ConfigError('Sub-assets need an explicit frame/clip/region kind and stable key (1-256 characters)')
    value = ['subasset-v1', parent['source_id'], parent['pack_id'], parent['asset_id'], kind, key]
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'asset_' + hashlib.sha256(raw).hexdigest()[:32]


def upgrade_record(record):
    """Explicit JSON migration. Keep file/dependency lists and generated evidence identical."""
    value = deepcopy(record)
    value.update(schema_version=CATALOG_VERSION)
    value.setdefault('structure_version', STRUCTURE_VERSION)
    value.setdefault('asset_type', 'model_3d')
    value.setdefault('identity_version', 'asset-v1')
    value.setdefault('type_metadata', {'version': 1})
    value.setdefault('file_roles', file_roles(record))
    value.setdefault('relationships', [])
    validate_record(value)
    return value


def new_record(pack, path, format, sha256, kind):
    """For explicit adapters/fixtures only. Inventory does not enroll new media yet."""
    from .catalog import SOURCE_ID, asset_id
    if kind not in ASSET_TYPES:
        raise ConfigError('Unsupported asset type')
    relative = PurePosixPath(path)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != pack:
        raise ConfigError('Asset file must belong to its source pack')
    identity = relative.relative_to(pack).as_posix()
    value = {'schema_version': 2, 'asset_id': asset_id(pack, identity), 'source_id': SOURCE_ID,
             'pack_id': pack, 'source_relative_identity': identity, 'display_name': relative.stem,
             'availability': 'available', 'files': [{'path': path, 'format': format, 'sha256': sha256, 'availability': 'available'}],
             'dependencies': [], 'previews': [], 'variants': [], 'grouping': {}, 'license_evidence': [],
             'technical': None, 'description': None, 'caption_provenance': None, 'embeddings': [],
             'owner_overlay': {}, 'provenance': {}, 'processing': {s: 'pending' for s in STAGES},
             'asset_type': kind, 'file_roles': {path: 'primary'}}
    value = upgrade_record(value)
    for stage in STAGES:
        if stage not in applicable_stages(value):
            value['processing'][stage] = 'not_applicable'
        elif not supported_stage(value, stage):
            value['processing'][stage] = 'unsupported'
            value.setdefault('stage_faults', {})[stage] = {
                'status': 'unsupported', 'kind': 'unsupported_media',
                'reason': 'Audio adapters are not implemented; no decode, playback or inference was attempted.'}
    value['processing']['inventory'] = 'complete'
    return value


def new_subasset(parent, kind, key, media_type):
    """Explicit identities only. Frame slicing/clip decoding belong to later steps."""
    value = new_record(parent['pack_id'], parent['files'][0]['path'], parent['files'][0]['format'],
                       parent['files'][0]['sha256'], media_type)
    identifier = child_id(parent, kind, key)
    value.update(asset_id=identifier, source_id=parent['source_id'], identity_version='subasset-v1',
                 parent_asset_id=parent['asset_id'], subasset={'kind': kind, 'key': key},
                 source_relative_identity='@subasset/' + identifier, display_name=key,
                 files=deepcopy(parent['files']), file_roles=deepcopy(parent.get('file_roles', {
                     f['path']: 'primary' for f in parent['files']})), license_evidence=deepcopy(parent.get('license_evidence', [])))
    for stage in STAGES:
        if stage in applicable_stages(value) and stage != 'inventory':
            value['processing'][stage] = 'unsupported'
            value.setdefault('stage_faults', {})[stage] = {
                'status': 'unsupported', 'kind': 'unsupported_subasset',
                'reason': 'Sub-asset media adapters are deferred; the parent file is not a sliced frame or played clip.'}
    validate_record(value)
    return value


def validate_record(record):
    version = record.get('schema_version', 1)
    if type(version) is not int or version not in (1, 2):
        raise ConfigError('Unknown asset record schema version')
    if version == 1:
        return
    if record.get('structure_version') != STRUCTURE_VERSION or asset_type(record) not in ASSET_TYPES:
        raise ConfigError('Unknown asset structure version or type')
    if any(not isinstance(record.get(k), str) or not record[k] for k in ('asset_id', 'source_id', 'pack_id', 'source_relative_identity')):
        raise ConfigError('Asset requires stable source and identity strings')
    metadata = record.get('type_metadata')
    if not isinstance(metadata, dict) or metadata.get('version') != 1 or len(json.dumps(metadata)) > 32768:
        raise ConfigError('Invalid or oversized type-specific metadata')
    roles = record.get('file_roles')
    paths = {f['path'] for f in record['files']}
    if not isinstance(roles, dict) or set(roles) != paths or any(r not in FILE_ROLES for r in roles.values()):
        raise ConfigError('File roles must name each recorded source file')
    relationships = record.get('relationships')
    if not isinstance(relationships, list) or len(relationships) > 64:
        raise ConfigError('At most 64 explicit relationships are allowed per asset')
    for relation in relationships:
        if (not isinstance(relation, dict) or relation.get('kind') not in RELATIONSHIPS
                or not isinstance(relation.get('asset_id'), str) or not re.fullmatch(ID_PATTERN, relation['asset_id'])
                or not isinstance(relation.get('evidence'), str) or not relation['evidence'].strip()
                or len(relation['evidence']) > 2048 or relation['asset_id'] == record['asset_id']):
            raise ConfigError('Invalid relationship identity, kind or evidence')
    for stage in STAGES:
        if stage not in record['processing']:
            raise ConfigError('Asset is missing a processing stage state')
        if record['processing'][stage] == 'not_applicable' and stage in applicable_stages(record):
            raise ConfigError('An applicable stage cannot be marked not_applicable')
        if record['processing'][stage] not in ('pending', 'running', 'complete', 'failed', 'unsupported', 'partial', 'unknown', 'not_applicable'):
            raise ConfigError('Unknown processing stage state')
    if record.get('identity_version') not in ('asset-v1', 'subasset-v1'):
        raise ConfigError('Unknown asset identity algorithm')
    if record['identity_version'] == 'subasset-v1':
        selector = record.get('subasset')
        if (not isinstance(record.get('parent_asset_id'), str) or not re.fullmatch(ID_PATTERN, record['parent_asset_id'])
                or not isinstance(selector, dict)):
            raise ConfigError('Sub-asset requires its parent and explicit selector')
    elif record.get('parent_asset_id') is not None:
        raise ConfigError('Parent linkage requires subasset-v1 identity')
    else:
        from .catalog import asset_id
        if record['asset_id'] != asset_id(record['pack_id'], record['source_relative_identity']):
            raise ConfigError('Asset identity does not match the preserved asset-v1 algorithm')


def validate_collection(records):
    """Validate a complete candidate before changing membership/publication."""
    by_id = {r['asset_id']: r for r in records}
    if len(by_id) != len(records):
        raise ConfigError('Duplicate asset identity')
    edges, incoming = {key: set() for key in by_id}, dict.fromkeys(by_id, 0)
    for record in records:
        validate_record(record)
        for relation in record.get('relationships', []):
            target = by_id.get(relation['asset_id'])
            if target is None:
                raise ConfigError('Relationship target is outside the candidate catalog')
            if relation['kind'] == 'contains':
                if target.get('parent_asset_id') != record['asset_id']:
                    raise ConfigError('Containment must agree with the child parent identity')
                edges[record['asset_id']].add(target['asset_id'])
        if record.get('identity_version') == 'subasset-v1':
            parent = by_id.get(record['parent_asset_id'])
            if parent is None or any(parent[k] != record[k] for k in ('source_id', 'pack_id')):
                raise ConfigError('Sub-asset parent is missing or belongs to another source')
            selector = record['subasset']
            if record['asset_id'] != child_id(parent, selector.get('kind'), selector.get('key')):
                raise ConfigError('Sub-asset identity does not match its parent and selector')
            if not any(r['kind'] == 'contains' and r['asset_id'] == record['asset_id'] for r in parent.get('relationships', [])):
                raise ConfigError('Parent must retain explicit containment evidence')
            if not {f['path'] for f in record['files']}.issubset({f['path'] for f in parent['files']}):
                raise ConfigError('Sub-assets must reference their parent source files')
    for children in edges.values():
        for child in children:
            incoming[child] += 1
    ready = deque(key for key, degree in incoming.items() if not degree)
    visited = 0
    while ready:
        key = ready.popleft()
        visited += 1
        for child in edges[key]:
            incoming[child] -= 1
            if not incoming[child]:
                ready.append(child)
    if visited != len(by_id):
        raise ConfigError('Containment relationships contain a cycle')
