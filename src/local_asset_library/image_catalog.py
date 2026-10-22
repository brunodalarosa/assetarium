"""Scanner-side enrollment of static 2D images; no decoding and no inference.

Kept apart from image_media.py so changing enrollment rules never changes the
pixel-adapter fingerprint (and so never re-queues image inspections or descriptions).
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


def excluded_role(row, referenced, sheets):
    path = PurePosixPath(row['path'])
    folders = {part.lower() for part in path.parts[:-1]}
    if row['path'] in referenced:
        return 'model_dependency_image', None
    if row['path'] in sheets:
        return 'deferred_sprite_sheet', sheets[row['path']]
    stem = path.stem.lower()
    if stem.startswith('preview'):
        return 'pack_contact_sheet', None  # Supplied pack overviews stay evidence, not selectable assets.
    if stem.startswith('sample'):
        return 'pack_sample', None
    if folders & {'texture', 'textures'}:
        return 'deferred_texture', None
    return None, None


def image_assets(config, rows, models, license_for):
    """Logical image records for an image-enabled source; excluded candidates keep a visible role."""
    from .asset_structure import image_record
    from .catalog import digest
    referenced = {d.get('path') for a in models for d in a.get('dependencies', [])}
    referenced |= {p.get('source_path') for a in models for p in a.get('previews', [])}
    sheets = sheet_paths(config, rows)
    groups = {}
    for row in rows:
        if image_format(row['path']) is None or row.get('role') == 'boundary_exclusion':
            continue
        role, reason = excluded_role(row, referenced, sheets)
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
        assets.append(image_record(pack, 'image:' + '/'.join((*relative, stem)), stem, files, evidence,
                                   suggested_purpose([*source_folders, *relative]), license_for(pack)))
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
