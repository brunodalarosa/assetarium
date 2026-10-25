"""Explicit, source-hash-bound texture overrides; original files stay read only."""
from collections import defaultdict
from pathlib import Path, PurePosixPath
import re

from .captions import file_hash
from .catalog import digest
from .config import ConfigError


def subpack(path):
    parts = PurePosixPath(path).parts
    return '/'.join(parts[:2] if parts[0] in {'synty-part1', 'craftpix-free-packs'} else parts[:1])


def material_table(path):
    """Read publisher slot order and explicit map filenames, including atlas slots."""
    rows, mesh, slots, slot = {}, None, None, None
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        text = line.strip()
        if text.startswith('Mesh Name:'):
            mesh = text.split(':', 1)[1].strip()
            slots = rows.setdefault(mesh, [])
        elif text.startswith('Slot:') and slots is not None:
            name = text.split(':', 1)[1].strip()
            slot = {'name': name, 'maps': {}}
            # Repeated prefab references describe the same mesh; collapse later.
            slots.append(slot)
            atlas = re.search(r'\(([^()]+Texture[^()]*)\)', name, re.I)
            if atlas:
                slot['maps']['Albedo'] = atlas.group(1) + '.png'
        elif slot is not None:
            match = re.match(r'(Albedo|Emission|Normal):\s*(\S+\.(?:png|tga|jpg))\b', text, re.I)
            if match:
                slot['maps'][match.group(1).capitalize()] = match.group(2)
    for mesh, slots in rows.items():
        unique = []
        for slot in slots:
            if slot not in unique:
                unique.append(slot)
        rows[mesh] = unique
    return rows


def unique_texture(candidates, source_root):
    """Identical duplicate exports are safe; differing candidates are ambiguous."""
    if not candidates:
        return None
    hashed = [(p, file_hash(source_root / p)) for p in sorted(candidates)]
    if len({h for _, h in hashed}) != 1:
        return None
    return hashed[0]


def build_recipe(config, record, textures, tables):
    technical = record.get('technical') or {}
    source = record['primary_inspection_path']
    prefix = subpack(source)
    local = [p for p in textures if p.startswith(prefix + '/')]
    by_name = defaultdict(list)
    for p in local:
        by_name[PurePosixPath(p).name.casefold()].append(p)
    author_slots = defaultdict(list)
    for table_path, entries in tables:
        if not table_path.startswith(prefix + '/'):
            continue
        for mesh in technical.get('meshes', []):
            names = [mesh['object'], mesh['mesh']]
            if len(technical.get('meshes', [])) == 1:
                names.append(record['display_name'])
            matches = [entries[n] for n in names if n in entries]
            if not matches or any(m != matches[0] for m in matches):
                continue
            slots = matches[0]
            if len(slots) != len(mesh['material_slots']):
                continue
            for name, slot in zip(mesh['material_slots'], slots):
                author_slots[name].append((table_path, slot))
    bindings, faults = [], []
    for image in technical.get('textures', []):
        if not image.get('required_for_render') or image['status'] in {'available', 'embedded', 'generated_in_source'}:
            continue
        old_name = PurePosixPath(image['original_path'].replace('\\', '/')).name
        role = ('Emission' if re.search(r'emiss', old_name, re.I) else
                'Normal' if re.search(r'normal|bump', old_name, re.I) else 'Albedo')
        exact = unique_texture(by_name.get(old_name.casefold(), []), config.source_root)
        evidence = {'kind': 'exact_filename_in_same_subpack', 'original_path': image['original_path']}
        chosen = exact
        users = [u.removeprefix('material:') for u in image['render_users'] if u.startswith('material:')]
        authored = [v for user in users for v in author_slots.get(user, [])]
        maps = {slot['maps'].get(role) for _, slot in authored}
        if not chosen and users and all(author_slots.get(u) for u in users) and len(maps) == 1 and None not in maps:
            filename = next(iter(maps))
            chosen = unique_texture(by_name.get(filename.casefold(), []), config.source_root)
            evidence = {'kind': 'publisher_mesh_slot_map', 'role': role,
                        'tables': [{'path': p, 'sha256': file_hash(config.source_file(p)), 'slot': s}
                                   for p, s in authored], 'original_path': image['original_path']}
        if chosen:
            path, sha256 = chosen
            bindings.append({'image': image['name'], 'original_path': image['original_path'],
                             'path': path, 'sha256': sha256, 'role': role, 'evidence': evidence,
                             'preserve_supplied_alpha': True})
        else:
            faults.append({'image': image['name'], 'original_path': image['original_path'],
                           'reason': 'No unambiguous supplied texture with exact filename or publisher mesh-slot mapping'})
    if faults or not bindings:
        return None, faults
    return {'schema_version': 1, 'asset_id': record['asset_id'], 'source_path': source,
            'source_sha256': next(f['sha256'] for f in record['files'] if f['path'] == source),
            'authorization': 'Owner approved texture/material repairs for the 648 blocked imported models on 2026-10-14.',
            'originals_modified': False, 'bindings': bindings}, []


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
