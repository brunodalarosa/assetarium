"""Packs and bundles detected from folder structure, never from publisher names (decisions 0019, 0023).

A pack is the folder closest to the assets that carries pack markers (a license, a readme, a preview image,
internet shortcuts, a versioned name). A folder whose children hold packs is a bundle. Without markers, the
first folder under the library folder that contains assets is the pack. The owner's "Make this a pack" and
"Merge into parent pack" answers are saved per folder and survive rescans. A pack is a light object: a name,
a cover and license evidence; no tags and no collection membership.
"""
from collections import defaultdict
from functools import lru_cache
import json
from pathlib import PurePosixPath
import re

from .catalog import digest

VERSIONED = re.compile(r'(?:^|[ _-])v?\d+(?:\.\d+)+(?:[ _-]|$)|_FREE$', re.I)
README = re.compile(r'^(?:readme|read me|read_me|about|overview)\b.*\.(?:txt|md|html?|pdf)$', re.I)
LICENSE = re.compile(r'^(?:licen[cs]e|copying|eula|terms)\b.*', re.I)
PREVIEW = re.compile(r'^(?:preview|cover|thumbnail|contents|overview|sample)\b.*\.(?:png|jpe?g|webp|gif)$', re.I)


def markers(folder, files):
    """Pack evidence found in one folder: its name and the files directly inside it."""
    found = []
    name = PurePosixPath(folder).name
    if name and VERSIONED.search(name):
        found.append({'kind': 'versioned_name', 'evidence': name})
    for file in files:
        if LICENSE.match(file):
            found.append({'kind': 'license', 'evidence': file})
        elif README.match(file):
            found.append({'kind': 'readme', 'evidence': file})
        elif PREVIEW.match(file):
            found.append({'kind': 'preview', 'evidence': file})
        elif file.lower().endswith('.url'):
            found.append({'kind': 'shortcut', 'evidence': file})
    return found


def folders_of(paths):
    """{folder: [file names directly inside]} for folder-relative POSIX paths ('' is the library folder)."""
    tree = defaultdict(list)
    for path in paths:
        parent = PurePosixPath(path).parent.as_posix()
        tree['' if parent == '.' else parent].append(PurePosixPath(path).name)
        parts = PurePosixPath(path).parts[:-1]
        for depth in range(len(parts)):
            tree.setdefault('/'.join(parts[:depth]), [])
    return tree


def detect(paths, asset_paths, answers=()):
    """Packs and bundles of one library folder.

    ``paths``: every file (folder-relative); ``asset_paths``: the files of selectable assets; ``answers``: saved
    owner overrides ``{'path', 'value': 'make_pack' | 'merge'}``. Returns {'packs': {folder: pack}, 'bundles': [...],
    'pack_of': {asset file folder: pack folder}}.
    """
    tree = folders_of(paths)
    made = {a['path'] for a in answers if a['value'] == 'make_pack'}
    merged = {a['path'] for a in answers if a['value'] == 'merge'}
    marked = {folder: markers(folder, files) for folder, files in tree.items()}
    holders = {PurePosixPath(p).parent.as_posix() for p in asset_paths}
    holders = {'' if h == '.' else h for h in holders}

    def ancestors(folder):
        parts = PurePosixPath(folder).parts if folder else ()
        return ['/'.join(parts[:depth]) for depth in range(len(parts), -1, -1)]

    def pack_for(folder):
        chain = ancestors(folder)
        for candidate in chain:  # The nearest folder with markers or an owner answer (the library folder itself counts).
            if candidate not in merged and (candidate in made or marked.get(candidate)):
                return candidate
        top = chain[-2] if len(chain) > 1 else ''
        # No markers: the first folder under the library folder (the library folder for loose files or when merged).
        return '' if top in merged else top

    pack_of = {holder: pack_for(holder) for holder in holders}
    packs = {}
    for holder, pack in pack_of.items():
        entry = packs.setdefault(pack, {'path': pack, 'name': PurePosixPath(pack).name if pack else '', 'markers': marked.get(pack, []),
                                         'basis': 'owner' if pack in made else 'markers' if marked.get(pack) else 'first-folder'})
        entry.setdefault('folders', []).append(holder)
    bundles = sorted({a for pack in packs for a in ancestors(pack)[1:] if a and sum(
        1 for other in packs if other.startswith(a + '/')) >= 2 and a not in packs})
    for pack in packs.values():
        preview = next((m['evidence'] for m in pack['markers'] if m['kind'] == 'preview'), None)
        pack['cover'] = (pack['path'] + '/' + preview).lstrip('/') if preview else None
        pack['id'] = 'pack_' + digest(pack['path'])[:16]
        pack['folders'].sort()
    return {'packs': packs, 'bundles': bundles, 'pack_of': pack_of}


@lru_cache(maxsize=32)
def _cached(key, paths, asset_paths, answers):
    return detect(paths, asset_paths, json.loads(answers))


def structure(config, source, records=None):
    """Packs of a scanned library folder, from its saved inventory (cheap; cached by the catalog's identity)."""
    from contextlib import closing
    from .catalog import read_database
    from .incremental import working
    from .library_store import answers
    from .sources import bound, read_records
    work = working(bound(config, source))
    path = work.output_path('data', 'catalog.sqlite')
    if not path.exists():
        return {'packs': {}, 'bundles': [], 'pack_of': {}}
    prefix = source['key'] + '/'
    with closing(read_database(work)) as db:
        paths = tuple(sorted(json.loads(r[0])['path'][len(prefix):] for r in db.execute('SELECT record FROM inventory')
                             if json.loads(r[0]).get('path', '').startswith(prefix)))
    records = read_records(work) if records is None else records
    asset_paths = tuple(sorted(f['path'][len(prefix):] for r in records for f in r['files'][:1] if f['path'].startswith(prefix)))
    saved = json.dumps(sorted(({'path': a['path'], 'value': a['value']} for a in answers(config, source['id'], 'pack')),
                              key=lambda a: a['path']))
    stat = path.stat()
    return _cached((str(path), stat.st_mtime_ns, stat.st_size), paths, asset_paths, saved)


def pack_of(config, source, record, detected=None):
    """The pack (path and display name) an asset belongs to."""
    detected = detected or structure(config, source)
    folder = PurePosixPath(record['files'][0]['path'].split('/', 1)[1]).parent.as_posix()
    path = detected['pack_of'].get('' if folder == '.' else folder, '')
    pack = detected['packs'].get(path) or {'path': path, 'name': PurePosixPath(path).name, 'id': 'pack_' + digest(path)[:16]}
    names = names_of(config, source)
    return {'id': pack['id'], 'path': path, 'name': names.get(path) or pack['name'] or source['name']}


def fields(config, record):
    """``pack_name`` and ``pack_path`` for agents (the detected pack); empty when it cannot be told."""
    from .sources import registry
    if not config.sources_registry or not record.get('files'):
        return {}
    try:
        source = next((s for s in registry(config)['sources'] + registry(config)['detached'] if s['key'] == record['pack_id']), None)
        if source is None:
            return {}
        pack = pack_of(config, source, record)
        return {'pack_name': pack['name'], 'pack_path': pack['path']}
    except Exception:  # Pack detection never breaks search or detail; the folder key is still there.
        return {}


def names_of(config, source):
    from .library_store import answers
    return {a['path']: a['value'] for a in answers(config, source['id'], 'pack_name')}


def answer(config, key, folder, value):
    """Save "Make this a pack" (``make_pack``), "Merge into parent pack" (``merge``) or clear (None) for a folder."""
    from .config import ConfigError
    from .library_store import save_answer
    from .sources import get_source, validate_exclusion
    if value not in {'make_pack', 'merge', None}:
        raise ConfigError('Choose Make this a pack or Merge into parent pack')
    source = get_source(config, key)
    save_answer(config, source['id'], validate_exclusion(folder) if folder else '', 'pack', value)
    _cached.cache_clear()
    return source


def rename(config, key, folder, name):
    """A pack's display name (defaults to its folder name); an empty name restores the default."""
    from .config import ConfigError
    from .library_store import save_answer
    from .sources import get_source
    source = get_source(config, key)
    if not isinstance(name, str) or len(name.strip()) > 120:
        raise ConfigError('Give a pack name of up to 120 characters')
    save_answer(config, source['id'], folder, 'pack_name', name.strip() or None)
    return source
