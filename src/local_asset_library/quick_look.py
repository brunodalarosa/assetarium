"""Quick look: a names-only walk of a folder for the Add library folder wizard (decisions 0032, 0035).

It reads folder and file names only (no hashing, no file contents, nothing written into the folder), so the wizard
can show the tree filling in within seconds and say which packs look fine and which need a structure. Once the folder
is added, ``save`` keeps the names as a small snapshot in the library store, so pack tools and agents can work before
the first full scan (hashing) has finished; the real folder view replaces it as soon as one exists.
"""
from contextlib import closing
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import threading
import time
import uuid

from .config import ConfigError

TOP = 80  # Folders listed live while the walk runs.
_jobs = {}
_lock = threading.Lock()


def start(config, directory):
    """Start a names-only walk; ``{'status': 'started', 'job'}`` or ``covered`` when a library folder holds it already."""
    from .sources import Covered, registry, validate_directory
    root = validate_directory(config, directory)
    for source in registry(config)['sources']:
        if root.is_relative_to(Path(source['path'])):
            raise Covered(source)
    job = {'id': uuid.uuid4().hex[:12], 'path': str(root), 'name': root.name, 'files': 0, 'folders': 0, 'started': time.monotonic(),
           'top': {}, 'done': False, 'error': None, 'result': None, 'paths': None}
    with _lock:
        for stale in [k for k, v in _jobs.items() if v['done'] and time.monotonic() - v['started'] > 3600]:
            del _jobs[stale]
        _jobs[job['id']] = job
    threading.Thread(target=_run, args=(job, root), name='quick-look', daemon=True).start()
    return {'status': 'started', 'job': job['id'], 'path': str(root), 'name': root.name}


def _run(job, root):
    from .config import LEGACY_METADATA_DIR
    from .packs import markers
    paths = []
    try:
        for directory, dirs, files in os.walk(root, followlinks=False):
            here = Path(directory)
            dirs[:] = sorted(d for d in dirs if d.casefold() != LEGACY_METADATA_DIR and not (here / d).is_symlink()
                             and not (here / d).is_junction())
            relative = here.relative_to(root).as_posix()
            relative = '' if relative == '.' else relative
            job['folders'] += 1
            for name in sorted(files):
                paths.append(f'{relative}/{name}' if relative else name)
            job['files'] = len(paths)
            top = relative.split('/', 1)[0] if relative else ''
            if top:
                entry = job['top'].setdefault(top, {'name': top, 'files': 0, 'markers': []})
                entry['files'] += len(files)
                if relative == top or relative.count('/') == 1:
                    found = sorted((m['kind'] for m in markers(relative, files)), key=lambda k: k == 'versioned_name')
                    entry['markers'] = list(dict.fromkeys(entry['markers'] + found))[:4]
        job['paths'] = paths
        job['result'] = summarize(paths, job['name'])
    except OSError as exc:
        job['error'] = f'This folder could not be read: {exc}'
    finally:
        job['done'] = True


def summarize(paths, name):
    """Packs and their first verdicts from names alone: variant groups, repeated names, duplicate export folders."""
    from .catalog import IMAGES, MODELS, export_candidates
    from .packs import detect
    from .variant_groups import CAP, assign
    suffix = lambda p: PurePosixPath(p).suffix.casefold()
    models = [p for p in paths if suffix(p) in MODELS]
    images = [p for p in paths if suffix(p) in IMAGES or suffix(p) == '.svg']
    detected = detect(paths, models + images)
    holder = lambda path: detected['pack_of'].get(_parent(path), '')
    # File evidence (a license, a readme) explains a pack better than a version in its name, so it comes first.
    packs = {path: {'pack': path, 'name': pack['name'] or name,
                    'evidence': [m['evidence'] for m in sorted(pack['markers'], key=lambda m: m['kind'] == 'versioned_name')][:3],
                    'basis': pack['basis'], 'models': 0, 'images': 0, 'groups': 0, 'grouped': 0, 'oversized': [],
                    'clashes': 0, 'exports': 0} for path, pack in detected['packs'].items()}
    blank = lambda: {'pack': '', 'name': name, 'evidence': [], 'basis': 'first-folder', 'models': 0, 'images': 0, 'groups': 0,
                     'grouped': 0, 'oversized': [], 'clashes': 0, 'exports': 0}
    by_folder, stems = {}, {}
    for path in models:
        pack = packs.setdefault(holder(path), blank())
        pack['models'] += 1
        by_folder.setdefault(_parent(path), []).append(path)
        stems.setdefault((holder(path), PurePosixPath(path).stem.casefold()), set()).add(_parent(path))
    for path in images:
        packs.setdefault(holder(path), blank())['images'] += 1
    examples = {'group': None, 'series': None}
    for folder, files in by_folder.items():
        rows = [(f, folder, PurePosixPath(f).stem, 'model_3d') for f in files]
        found, big = assign(rows)
        pack = packs[holder(files[0])]
        pack['groups'] += len({k for k, _, _ in found.values()})
        pack['grouped'] += len(found)
        pack['oversized'] += big
        if found and not examples['group']:
            key = next(iter(found.values()))[0]
            examples['group'] = (PurePosixPath(key).name, sorted(v for k, v, _ in found.values() if k == key))
        if not examples['series']:
            series, _ = assign(rows, {folder: ['numbers']})
            numbered = [(k, v) for k, v, _ in series.values() if v.isdigit()]
            if len(numbered) >= 3:
                examples['series'] = (PurePosixPath(numbered[0][0]).name, len([n for n in numbered if n[0] == numbered[0][0]]))
    for (pack, _), folders in stems.items():
        if len(folders) > 1:
            packs[pack]['clashes'] += 1
    candidates = export_candidates([{'path': 'q/' + p} for p in models])
    pair = None
    for candidate in candidates.values():
        anchor = candidate['anchor']
        owner = max((p for p in packs if not p or anchor == p or anchor.startswith(p + '/')), key=len, default='')
        packs.setdefault(owner, blank())['exports'] += 1
        pair = pair or (candidate['folders'], anchor)
    result = []
    for pack in sorted(packs.values(), key=lambda p: p['pack']):
        cards = pack['models'] - pack['grouped'] + pack['groups'] + pack['images']
        needs = []
        if pack['oversized']:
            needs.append(f"{len(pack['oversized'])} name sets too big for one card (over {CAP})")
        if pack['clashes'] >= 3:
            needs.append(f"{pack['clashes']} names repeat in several folders")
        sets = pack['exports']
        suggestions = [f"{sets} {'folder set looks' if sets == 1 else 'folder sets look'} like other exports of the same models"] if sets else []
        result.append({**{k: pack[k] for k in ('pack', 'name', 'evidence', 'basis', 'models', 'images', 'groups')},
                       'cards': cards, 'needs': needs, 'suggestions': suggestions,
                       'status': 'needs_structure' if needs else 'suggestions' if suggestions else 'fine'})
    why = []
    marked = next((p for p in result if p['evidence']), None)
    if marked:
        reason = marked['evidence'][0]
        why.append(f"“{marked['name']}” is a pack because of {reason}" if reason != PurePosixPath(marked['pack']).name
                   else f"“{marked['name']}” is a pack because its name carries a version")
    if examples['group']:
        base, values = examples['group']
        why.append(f"{base}_{{{','.join(values)}}} became one card with {len(values)} variants")
    if examples['series']:
        base, count = examples['series']
        why.append(f"{base}_01…{count:02} stay {count} separate assets (a numbered series)")
    if pair:
        why.append(f"{' and '.join(pair[0][:2])} look like exports of the same models; you choose whether to group them")
    counts = {status: sum(p['status'] == status for p in result) for status in ('fine', 'suggestions', 'needs_structure')}
    return {'packs': result, 'counts': counts, 'files': len(paths), 'models': len(models), 'images': len(images), 'why': why}


def _parent(path):
    parent = PurePosixPath(path).parent.as_posix()
    return '' if parent == '.' else parent


def status(job_id):
    """Progress for the live tree (bounded), and the summary once the walk is done."""
    job = _jobs.get(job_id)
    if job is None:
        raise ConfigError('This quick look is no longer running; choose the folder again')
    top = sorted(job['top'].values(), key=lambda e: e['name'].casefold())[:TOP]
    return {'status': 'faulty' if job['error'] else 'done' if job['done'] else 'running', 'reason': job['error'],
            'name': job['name'], 'path': job['path'], 'files': job['files'], 'folders': job['folders'],
            'seconds': round(time.monotonic() - job['started'], 1), 'top': top, 'more_top': max(0, len(job['top']) - TOP),
            'result': job['result']}


def snapshot_path(current):
    return current.metadata_root / 'library/quicklook.sqlite'


def save(config, source, job_id):
    """Keep a finished quick look as the folder's names snapshot, until its first folder view exists.

    Excluded folders are left out and images are classified by name (``image_kinds.classify`` without model
    references), with the folder's image-kind answers, so saving again after an answer shows its effect.
    """
    from .catalog import IMAGES, MODELS, asset_id, excluded_folder
    from .folder_view import SCHEMA, group, view_answers
    from .image_kinds import classify
    from .library_store import answers
    from .packs import detect
    from .sources import bound, excluded_folders
    job = _jobs.get(job_id)
    if job is None or not job['done'] or job['paths'] is None or Path(job['path']) != Path(source['path']):
        return None
    current = bound(config, source)
    target = snapshot_path(current)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.unlink(missing_ok=True)
    excluded = excluded_folders(current)
    paths = [p for p in job['paths'] if not any(excluded_folder('/'.join(PurePosixPath(p).parts[:i]), x)
                                                 for i in range(1, len(PurePosixPath(p).parts)) for x in excluded)]
    suffix = lambda p: PurePosixPath(p).suffix.casefold()
    models = [p for p in paths if suffix(p) in MODELS]
    saved = answers(config, source['id'])
    images = [p for p in paths if suffix(p) in IMAGES or suffix(p) == '.svg']
    detected = detect(paths, models + images, [{'path': a['path'], 'value': a['value']} for a in saved if a['kind'] == 'pack'])
    with_models = {detected['pack_of'].get(_parent(p), '') for p in models}
    stems, folders = {PurePosixPath(p).stem.casefold() for p in models}, {_parent(p) for p in models}
    kinds = {a['path']: a['value'] for a in saved if a['kind'] == 'image_kind'}
    rows = []
    for path in paths:
        kind, basis = ('model_3d', None) if suffix(path) in MODELS else (None, None)
        if suffix(path) in IMAGES or suffix(path) == '.svg':
            folder = _parent(path)
            answer = next((kinds[f] for f in [folder] + [str(a) for a in PurePosixPath(folder).parents][:-1] + [''] if f in kinds), None)
            found = classify(source['key'] + '/' + path, {}, stems, {source['key'] + '/' + f for f in folders},
                             detected['pack_of'].get(folder, '') in with_models, answer)
            kind, basis = ('image' if found['value'] == 'image' else 'material_texture'), found['basis']
        if kind:
            folder, name = _parent(path), PurePosixPath(path).stem
            rows.append((asset_id(source['key'], path), name, folder, folder.casefold(), name.casefold(), kind, kind,
                         source['key'] + '/' + path, json.dumps([suffix(path)[1:]]), '[]', 0, None, None, 'inspection', 'pending', 1,
                         'unavailable', 0, None, '', basis))
    with closing(sqlite3.connect(temporary)) as db:
        db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;' + SCHEMA)
        db.executemany('INSERT OR IGNORE INTO assets (asset_id, name, folder, folder_key, name_key, kind, asset_type, path, formats, '
                       'groups, has_preview, failed, failed_stages, pending_next, outcome, eligible, description, warning, '
                       'inspection, digest, kind_basis) VALUES (' + ','.join('?' * 21) + ')', rows)
        db.executemany('INSERT OR IGNORE INTO inventory VALUES (?)', [(p,) for p in paths])
        oversized = group(db, view_answers(current))
        db.executemany('INSERT INTO meta VALUES (?,?)', [('version', 'quicklook'), ('snapshot', '1'),
                                                         ('oversized', json.dumps(oversized[:200]))])
        db.commit()
    os.replace(temporary, target)
    return str(target)
