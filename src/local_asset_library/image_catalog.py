"""Scanner-side enrollment of static 2D images; no decoding and no inference.

Every image is enrolled (decision 0023) and classified by ``image_kinds``: model textures stay dependencies,
material textures and 2D images are assets. Kept apart from image_media.py so changing enrollment rules never
changes the pixel-adapter fingerprint (and so never re-queues image inspections or descriptions).
"""
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ElementTree

from .image_media import FORMATS, PREFERENCE, image_format

SHEET_SIDECARS = ('.xml', '.json', '.atlas', '.plist', '.tsx', '.tmx')
MAX_SIDECAR_BYTES = 1024 * 1024
PURPOSES = (('icon', {'icon', 'icons'}), ('tile', {'tile', 'tiles', 'tileset', 'tilesets'}),
            ('sprite', {'sprite', 'sprites', 'character', 'characters'}),
            ('ui', {'ui', 'gui', 'hud', 'interface', 'button', 'buttons', 'cursor', 'cursors'}),
            ('background', {'background', 'backgrounds', 'backdrop', 'backdrops', 'bg', 'parallax', 'sky', 'skies'}))


def suggested_purpose(folders):
    """Nearest folder-name keyword as a suggestion with evidence, never a fact."""
    for name in reversed(list(folders)):
        words = set(re.findall(r'[a-z]+', re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name).lower()))
        for purpose, keys in PURPOSES:
            if words & keys:
                return {'value': purpose, 'basis': 'folder-name-v1', 'evidence': f'Folder name {name!r}'}
    return None


def sheet_paths(config, rows):
    """Images described by an atlas/tileset sidecar belong to sprite-sheet support (step 3)."""
    available = {r['path'] for r in rows if r.get('status') == 'available'}
    found = {}
    for row in rows:
        path = PurePosixPath(row['path'])
        if row.get('status') != 'available' or path.suffix.lower() not in SHEET_SIDECARS:
            continue
        for fmt in FORMATS:
            sibling = path.with_suffix('.' + fmt).as_posix()
            if sibling in available and fmt != 'svg':
                found[sibling] = f'Same-name {path.suffix} sidecar {path.name}'
        if path.suffix.lower() in {'.tsx', '.tmx'} and (row.get('size') or 0) <= MAX_SIDECAR_BYTES:
            try:
                with config.open_source(row['path']) as stream:
                    root = ElementTree.fromstring(stream.read(MAX_SIDECAR_BYTES + 1))
            except (OSError, ValueError, ElementTree.ParseError):
                continue  # An unreadable sidecar does not establish a sheet.
            for image in root.iter('image'):
                parts = []
                for part in (path.parent / str(image.get('source', ''))).as_posix().split('/'):
                    if part == '..' and parts:
                        parts.pop()
                    elif part not in {'', '.'}:
                        parts.append(part)
                target = '/'.join(parts)
                if target in available:
                    found[target] = f'Tileset image referenced by {path.name}'
    return found


def excluded_role(row, sheets):
    path = PurePosixPath(row['path'])
    if row['path'] in sheets:
        return 'deferred_sprite_sheet', sheets[row['path']]
    stem = path.stem.lower()
    if stem.startswith(('preview', 'contents', 'cover')):
        return 'pack_contact_sheet', None  # Supplied pack overviews stay evidence (and pack covers), not selectable assets.
    if stem.startswith('sample'):
        return 'pack_sample', None
    return None, None


def _shared(a, b):
    common = 0
    for x, y in zip(a.parts, b.parts):
        if x != y:
            break
        common += 1
    return common


def model_references(config, rows, models, previous=()):
    """Image path -> evidence for every image a model uses: parsed references, FBX names, Blender's texture list."""
    from .image_kinds import fbx_references
    referenced = {d['path']: f"{d.get('evidence', 'Referenced')} in {PurePosixPath(d['from']).name}"
                  for a in models for d in a.get('dependencies', []) if d.get('path') and d.get('from')}
    referenced.update({p['source_path']: 'Supplied preview of a model' for a in models for p in a.get('previews', []) if p.get('source_path')})
    referenced.update({d['path']: 'Blender texture of ' + PurePosixPath(d['from']).name for r in previous
                       for d in r.get('dependencies', []) if d.get('inspection_version') and d.get('path') and d.get('from')})
    images, sizes = {}, {r['path']: r.get('size') for r in rows}
    for row in rows:
        if image_format(row['path']) and row.get('status') == 'available':
            images.setdefault(PurePosixPath(row['path']).name.casefold(), []).append(row['path'])
    for model in models:
        for file in model['files']:
            if file['format'] != 'fbx' or file['availability'] != 'available':
                continue
            folder = PurePosixPath(file['path']).parent
            for name in fbx_references(config, file['path'], sizes.get(file['path'])):
                # The nearest image with that name inside the same top folders as the model.
                found = sorted(images.get(name, []), key=lambda p: -_shared(PurePosixPath(p).parent, folder))
                if found and _shared(PurePosixPath(found[0]).parent, folder) >= 2:
                    referenced.setdefault(found[0], f'Named in {PurePosixPath(file["path"]).name}')
    return referenced


def _folder(path):
    parent = PurePosixPath(path).parent.as_posix()
    return '' if parent == '.' else parent


def _ancestors(folder):
    parts = PurePosixPath(folder).parts if folder else ()
    return ['/'.join(parts[:depth]) for depth in range(len(parts), -1, -1)]


def _pack(detected, folder):
    if folder in detected['pack_of']:
        return detected['pack_of'][folder]
    chain = _ancestors(folder)
    return next((f for f in chain if f in detected['packs']), chain[-2] if len(chain) > 1 else '')


def image_assets(config, rows, models, license_for, previous=(), answers=()):
    """Logical image records; model textures and other excluded candidates keep a visible role.

    ``previous``: the folder's last records (Blender's texture lists, recorded pixel evidence). ``answers``: saved
    owner answers per folder (``image_kind`` and ``pack``).
    """
    from .asset_structure import image_record
    from .catalog import digest
    from .image_kinds import classify
    from .packs import detect
    referenced = model_references(config, rows, models, previous)
    sheets = sheet_paths(config, rows)
    prefix = (config.source_key + '/') if config.source_key else ''
    inside = lambda path: path[len(prefix):] if prefix and path.startswith(prefix) else path.split('/', 1)[-1]
    model_files = [f['path'] for a in models for f in a['files']]
    detected = detect([inside(r['path']) for r in rows if r.get('status') == 'available'],
                      [inside(p) for p in model_files], [a for a in answers if a['kind'] == 'pack'])
    with_models = {_pack(detected, _folder(inside(p))) for p in model_files}
    stems = {PurePosixPath(p).stem.casefold() for p in model_files}
    model_folders = {PurePosixPath(p).parent.as_posix() for p in model_files}
    kinds = {a['path']: a['value'] for a in answers if a['kind'] == 'image_kind'}
    pixels = {r['files'][0]['path']: (r.get('type_metadata') or {}).get('pixel_kind') for r in previous
              if r.get('asset_type') == 'image' and r.get('files')}
    groups = {}
    for row in rows:
        if image_format(row['path']) is None or row.get('role') == 'boundary_exclusion':
            continue
        role, reason = excluded_role(row, sheets)
        if not role:
            folder = _folder(inside(row['path']))
            answer = next((kinds[f] for f in _ancestors(folder) if f in kinds), None)
            kind = classify(row['path'], referenced, stems, model_folders, _pack(detected, folder) in with_models,
                            answer, pixels.get(row['path']))
            row['image_kind'] = kind
            if kind['value'] == 'model_texture':
                role, reason = 'model_dependency_image', kind['evidence']
        if role:
            row['role'] = role
            if reason:
                row['deferred_reason'] = reason
            continue
        path = PurePosixPath(row['path'])
        row['role'] = 'image_asset'
        groups.setdefault((path.parent.as_posix(), path.stem), []).append(row)
    source_folders = list(Path(config.source_root).parts[-3:]) if config.source_root else []
    assets = []
    for (parent, stem), files in sorted(groups.items()):
        files.sort(key=lambda r: (PREFERENCE.index(image_format(r['path'])), r['path']))
        pack = files[0]['path'].split('/')[0]
        relative = PurePosixPath(parent).parts[1:]
        evidence = ({'method': 'single-image-file', 'anchor': parent} if len(files) == 1 else
                    {'method': 'same-folder-and-stem', 'anchor': parent, 'visual_equivalence': 'unverified'})
        record = image_record(pack, 'image:' + '/'.join((*relative, stem)), stem, files, evidence,
                              suggested_purpose([*source_folders, *relative]), license_for(pack))
        record['type_metadata']['image_kind'] = files[0]['image_kind']
        assets.append(record)
    by_hash = {}
    for record in assets:
        for f in record['files']:
            by_hash.setdefault(f['sha256'], set()).add(record['asset_id'])
    for record in assets:
        same = sorted({other for f in record['files'] for other in by_hash.get(f['sha256'], ())} - {record['asset_id']})
        if same:
            record['type_metadata']['identical_content'] = {
                'asset_ids': same[:16], 'total': len(same), 'evidence': 'Byte-identical source file (SHA-256); not merged'}
        record['provenance']['inventory_fingerprint'] = digest(record['files'])
    return assets
