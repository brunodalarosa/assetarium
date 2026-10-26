"""Owner-chosen texture folder for models whose textures were not found (decision 0021).

Packs often ship textures once per render pipeline (``Textures/PBR``, ``URP``, ``HDRP``…) while their
FBX files name a texture without a usable path. After inspection records which textures a model
could not find, a scan suggests folders by exact file name: a name with several different copies
needs a folder choice; a name with one copy (or byte-identical copies) is unambiguous but is still
only used when the owner allows single copies. Nothing is repaired until the owner applies a choice;
then each model whose every missing texture resolves gets a source-hash-bound texture repair recipe
(the existing Blender repair worker loads the mapped files in its temporary scene). Originals never
change, and a model with any unresolved texture keeps its recorded failure.
"""
from collections import defaultdict
from pathlib import PurePosixPath
import re

KIND = 'texture_folder_paths'
IMAGES = {'.png', '.jpg', '.jpeg', '.tga', '.bmp', '.tif', '.tiff', '.webp', '.exr', '.hdr', '.dds'}
FOUND = {'available', 'embedded', 'generated_in_source'}
MAX_FOLDERS = 8


def relative(path):
    return path.split('/', 1)[1] if '/' in path else path


def needed(record):
    """Textures the inspected model uses but could not find."""
    technical = record.get('technical') or {}
    return [t for t in technical.get('textures', []) if t.get('required_for_render') and t.get('status') not in FOUND]


def copies(rows):
    """{file name (case-folded): {sha256: [paths]}} for available images in the source."""
    index = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get('status') == 'available' and row.get('sha256') and PurePosixPath(row['path']).suffix.lower() in IMAGES:
            index[PurePosixPath(row['path']).name.casefold()][row['sha256']].append(row['path'])
    return index


def texture_name(texture):
    return PurePosixPath(str(texture.get('original_path') or texture.get('name') or '').replace('\\', '/')).name.casefold()


def resolve(texture, index, folder, single):
    """(path, sha256, how) or (None, None, reason) for one missing texture under a choice."""
    found = index.get(texture_name(texture), {})
    if not found:
        return None, None, 'No file with this name in the source'
    if folder:
        prefix = folder.casefold().rstrip('/') + '/'
        inside = {sha: sorted(p for p in paths if relative(p).casefold().startswith(prefix)) for sha, paths in found.items()}
        inside = {sha: paths for sha, paths in inside.items() if paths}
        if len(inside) == 1:
            sha, paths = next(iter(inside.items()))
            return paths[0], sha, 'chosen_folder'
    if len(found) == 1:
        if single:
            sha, paths = next(iter(found.items()))
            return sorted(paths)[0], sha, 'single_copy'
        return None, None, 'Only one copy exists, and single copies are not allowed'
    return None, None, 'Several different copies exist and none is in the chosen folder'


def plan(records, index, folder, single):
    """{asset_id: bindings} for models whose every missing texture resolves, plus unresolved examples."""
    fixed, unresolved = {}, []
    for record in records:
        missing = needed(record)
        if not missing:
            continue
        bindings, problem = [], None
        for texture in missing:
            path, sha, how = resolve(texture, index, folder, single)
            if path is None:
                problem = f"{PurePosixPath(texture_name(texture)).name}: {how}"
                break
            name = PurePosixPath(path).name
            role = ('Emission' if re.search(r'emiss', name, re.I) else
                    'Normal' if re.search(r'normal|bump', name, re.I) else 'Albedo')
            bindings.append({'image': texture['name'], 'original_path': texture['original_path'], 'path': path,
                             'sha256': sha, 'role': role, 'preserve_supplied_alpha': True,
                             'evidence': {'kind': 'owner_texture_folder', 'resolution': how, 'folder': folder,
                                          'original_path': texture['original_path']}})
        if problem:
            unresolved.append({'asset_id': record['asset_id'], 'name': record['display_name'], 'reason': problem})
        else:
            fixed[record['asset_id']] = bindings
    return fixed, unresolved


def candidate_folders(records, index):
    """Shallowest folders that hold exactly one version of each ambiguous name they contain."""
    names = {texture_name(t) for r in records for t in needed(r)}
    ambiguous = {n for n in names if len(index.get(n, {})) > 1}
    covers = defaultdict(set)
    for name in ambiguous:
        by_folder = defaultdict(set)
        for sha, paths in index[name].items():
            for path in paths:
                parts = PurePosixPath(relative(path)).parts[:-1]
                for depth in range(1, len(parts) + 1):
                    by_folder['/'.join(parts[:depth])].add(sha)
        for folder, shas in by_folder.items():
            if len(shas) == 1:
                covers[folder].add(name)
    keep = [f for f, covered in covers.items()
            if not ('/' in f and covers.get(f.rsplit('/', 1)[0], set()) >= covered)]
    return sorted(keep, key=lambda f: (-len(covers[f]), f.casefold()))[:MAX_FOLDERS]


def suggestion(records, index):
    """What the owner can choose for this source's models with missing textures; None when none apply."""
    waiting = [r for r in records if needed(r) and not r.get('texture_repair')]
    if not waiting:
        return None
    options = []
    for folder in candidate_folders(waiting, index):
        with_single, unresolved = plan(waiting, index, folder, True)
        without_single, _ = plan(waiting, index, folder, False)
        options.append({'folder': folder, 'fixes': len(with_single), 'fixes_without_single_copies': len(without_single),
                        'unresolved': len(unresolved), 'unresolved_examples': unresolved[:5]})
    # Most models fixed by the folder alone first, so the preselected option is the most complete set.
    options.sort(key=lambda o: (-o['fixes_without_single_copies'], -o['fixes'], o['folder'].casefold()))
    single_only, unresolved = plan(waiting, index, None, True)
    return {'assets': len(waiting), 'folders': options, 'single_copies_only': {
                'fixes': len(single_only), 'unresolved': len(unresolved), 'unresolved_examples': unresolved[:5]},
            'examples': [r['display_name'] for r in waiting[:5]]}


def apply(records, rows, choice):
    """Add, keep or drop owner texture-folder recipes on scanned records; return the open suggestion."""
    index = copies(rows)
    if choice:
        fixed, _ = plan([r for r in records if not r.get('texture_repair') or r['texture_repair'].get('kind') == KIND],
                        index, choice.get('folder'), bool(choice.get('single_copies')))
    else:
        fixed = {}
    authorization = (f"Owner chose texture folder {choice.get('folder') or '(none)'}"
                     f"{' and single copies' if choice.get('single_copies') else ''} on {choice.get('utc')}") if choice else None
    for record in records:
        current = record.get('texture_repair') or {}
        if current and current.get('kind') != KIND:
            continue  # Other repairs keep their own rules.
        technical = record.get('technical') or {}
        source = technical.get('inspected_path')
        if record['asset_id'] in fixed and source:
            sha = next((f['sha256'] for f in record['files'] if f['path'] == source), None)
            recipe = {'schema_version': 1, 'kind': KIND, 'asset_id': record['asset_id'], 'source_path': source,
                      'source_sha256': sha, 'authorization': authorization, 'originals_modified': False,
                      'choice': {'folder': choice.get('folder'), 'single_copies': bool(choice.get('single_copies'))},
                      'bindings': fixed[record['asset_id']]}
            if current.get('bindings') != recipe['bindings'] or current.get('choice') != recipe['choice']:
                record['texture_repair'] = recipe
                # Applied by the owner: the model waits for Process assets; its earlier evidence stays.
                for stage in ('inspection', 'previews'):
                    if record['processing'].get(stage) == 'failed':
                        record['processing'][stage] = 'pending'
        elif current and (not choice or current.get('choice') != {'folder': choice.get('folder'),
                                                                   'single_copies': bool(choice.get('single_copies'))}):
            record.pop('texture_repair')  # Choice removed or changed: back to the recorded inputs.
    return suggestion(records, index)
