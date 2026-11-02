"""One small view per catalog generation, so the Asset sources and processing tabs never load whole records.

A view holds what those tabs show and count: each asset's folder, kind, work-state inputs, description state and a
record digest, plus the folder's other files. It is derived data in the library store (``library/views``), rebuilt
when its catalog, embedding index or processing formats change. A build streams the catalog row by row in its own
thread, one per catalog at a time and at most two at once, so memory does not grow with the library. Readers wait
briefly for a build and otherwise use the last view (counts may lag processing by seconds); without any view yet they
get ``Reading`` instead of blocking the window. Nothing in a library folder is read or written.

Variant groups (``variant_groups``) are assigned here, one folder at a time, from names and the folder's
``variant_axis`` answers; a variant that shares its group's description shows the description state ``shared``.
"""
from contextlib import closing
import hashlib
from itertools import groupby
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import threading
import time
import uuid

from .config import ConfigError

VERSION = 2
VIEW_ANSWERS = ('variant_axis', 'separate_descriptions')  # Answers a view applies; they are part of its stamp.
WAIT = 1.5
# Heavy record fields no view column needs; SQLite drops them before Python parses a row.
HEAVY = ('technical', 'dependencies', 'texture_repair', 'texture_repair_history', 'dependency_inspection',
         'provenance', 'grouping', 'license_evidence', 'effective_caption', 'inspection_run', 'description')
_lock = threading.Lock()
_jobs = {}
_slots = threading.BoundedSemaphore(2)


class Reading(ConfigError):
    """The first view of this catalog is still being built."""


class View(sqlite3.Connection):
    path = None


def _stat(path):
    try:
        value = path.stat()
        return value.st_size, value.st_mtime_ns
    except FileNotFoundError:
        return None


def _place(current):
    catalog = current.output_path('data', 'catalog.sqlite')
    if current.metadata_root is None:
        raise ConfigError('Folder views need a library folder')
    return catalog, current.metadata_root / 'library/views', catalog.parent.name


def stamp(current):
    from .catalog import digest
    from .settings import processing_formats
    catalog = current.output_path('data', 'catalog.sqlite')
    index = current.output_path('data', 'embeddings/index.sqlite')
    return digest([VERSION, _stat(catalog), _stat(index), sorted(processing_formats(current)), view_answers(current)])[:16]


def view_answers(current):
    """This folder's answers that change its view, as sorted ``[kind, path, value]`` lists."""
    from .library_store import answers
    if current.metadata_root is None:
        return []
    return sorted([a['kind'], a['path'], a['value']] for kind in VIEW_ANSWERS for a in answers(current, current.metadata_root.name, kind))


def _open(path):
    db = sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True, factory=View, check_same_thread=False)
    db.path = Path(path)
    return db


def _latest(folder, name):
    found = [p for p in folder.glob(name + '-*.sqlite') if p.name.rsplit('-', 1)[0] == name]
    return max(found, key=lambda p: p.stat().st_mtime_ns, default=None)


def connect(current, wait=None, fresh=False):
    """A read-only connection to this catalog's view, rebuilt first when that takes under ``wait`` seconds.

    ``wait`` defaults to ``WAIT``. ``fresh`` waits for an up-to-date view however long it takes (resolving work to process). Otherwise a stale view
    answers while a rebuild runs, and a view that takes a second or more is rebuilt at most every three build durations.
    """
    catalog, folder, name = _place(current)
    if not catalog.exists():
        raise ConfigError('Catalog missing; run scan first')
    wait = WAIT if wait is None else wait
    target = folder / f'{name}-{stamp(current)}.sqlite'
    if not target.exists():
        job = _start(current, target, fresh or _latest(folder, name) is None)
        if job:
            job['done'].wait(None if fresh else wait)
            if job['done'].is_set() and job.get('error') and not target.exists():
                raise ConfigError('This library folder could not be read: ' + job['error'])
    path = target if target.exists() else None if fresh else _latest(folder, name)
    if path is None:
        raise Reading('Reading this library folder…')
    return _open(path)


def _start(current, target, needed):
    with _lock:
        job = _jobs.get(target.parent / target.name.rsplit('-', 1)[0])
        if job and not job['done'].is_set():
            return job
        if job and not needed and job['took'] >= 1 and time.monotonic() - job['ended'] < 3 * job['took']:
            return None  # Processing writes the catalog often; a large view is not rebuilt after every write.
        job = {'done': threading.Event(), 'ended': 0.0, 'took': 0.0}
        _jobs[target.parent / target.name.rsplit('-', 1)[0]] = job
    threading.Thread(target=_run, args=(current, target, job), name='folder-view', daemon=True).start()
    return job


def _run(current, target, job):
    started = time.monotonic()
    try:
        with _slots:
            build(current, target)
    except Exception as exc:  # Shown by the next reader; the catalog and the previous view stay as they are.
        job['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        job.update(ended=time.monotonic(), took=time.monotonic() - started)
        job['done'].set()


def lean(row):
    """The record fields the view's helpers read, from one ``_ROWS`` row."""
    record = json.loads(row[2])
    record['technical'] = {'inspected_path': row[3]} if row[4] else None
    record['description'] = row[5]
    return record


_ROWS = ("SELECT asset_id, record, json_remove(record, " + ', '.join(f"'$.{k}'" for k in HEAVY) + "), "
         "json_extract(record, '$.technical.inspected_path'), "
         "(SELECT count(*) FROM json_each(record, '$.technical')) * (json_type(record, '$.technical') = 'object'), "
         "json_extract(record, '$.description') FROM assets")
SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE assets (asset_id TEXT PRIMARY KEY, name TEXT NOT NULL, folder TEXT NOT NULL, folder_key TEXT NOT NULL,
    name_key TEXT NOT NULL, kind TEXT NOT NULL, asset_type TEXT, path TEXT, formats TEXT NOT NULL, groups TEXT NOT NULL,
    has_preview INTEGER NOT NULL, failed TEXT, failed_stages TEXT, pending_next TEXT, outcome TEXT NOT NULL,
    eligible INTEGER NOT NULL, description TEXT NOT NULL, warning INTEGER NOT NULL, inspection TEXT, digest TEXT NOT NULL,
    group_key TEXT, variant TEXT, representative INTEGER NOT NULL DEFAULT 1, card TEXT, kind_basis TEXT);
CREATE INDEX assets_order ON assets (folder_key, name_key, asset_id);
CREATE INDEX assets_card ON assets (card);
CREATE TABLE folders (path TEXT PRIMARY KEY);
CREATE TABLE inventory (path TEXT PRIMARY KEY);
CREATE TABLE files (path TEXT PRIMARY KEY, name TEXT NOT NULL, folder TEXT NOT NULL, folder_key TEXT NOT NULL,
    name_key TEXT NOT NULL, role TEXT, excluded INTEGER NOT NULL);
CREATE INDEX files_order ON files (folder_key, name_key, path);
"""


_INSERT = ('INSERT INTO assets (asset_id, name, folder, folder_key, name_key, kind, asset_type, path, formats, groups, has_preview, '
           'failed, failed_stages, pending_next, outcome, eligible, description, warning, inspection, digest, kind_basis) VALUES (' + ','.join('?' * 21) + ')')


def group(db, saved):
    """Assign variant groups folder by folder; returns the oversized sets. ``saved`` comes from ``view_answers``."""
    from .variant_groups import assign
    rules = {path: value for kind, path, value in saved if kind == 'variant_axis'}
    separate = {path for kind, path, value in saved if kind == 'separate_descriptions' and value}
    oversized, updates = [], []
    rows = db.execute('SELECT asset_id, folder, name, kind FROM assets ORDER BY folder, asset_id')
    for _, chunk in groupby(rows, key=lambda r: r[1]):
        found, big = assign(list(chunk), rules)
        oversized += big
        updates += [(key, value, int(first), asset_id) for asset_id, (key, value, first) in found.items()]
    db.executemany('UPDATE assets SET group_key=?, variant=?, representative=? WHERE asset_id=?', updates)
    db.execute('UPDATE assets SET card = COALESCE(group_key, asset_id)')
    # A variant shares its group's description unless the owner asked for separate ones; its own finished one stays.
    db.execute("UPDATE assets SET description='shared' WHERE representative=0 AND description IN ('missing', 'unavailable') "
               "AND group_key NOT IN (SELECT value FROM json_each(?))", (json.dumps(sorted(separate)),))
    return oversized


def build(current, target):
    """Stream one catalog into a new view file and swap it in; older views of this generation are removed."""
    from .library_view import _folder, kind_of, state_of
    from .publication import read_only
    from .settings import format_group, processing_eligible, processing_formats
    from .sources import description_state, embedding_failures, import_outcome
    catalog, folder, name = _place(current)
    key, formats, faults = current.source_key, processing_formats(current), embedding_failures(current)
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / f'.{target.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp'
    try:
        with closing(read_only(catalog)) as source, closing(sqlite3.connect(temporary)) as db:
            db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;' + SCHEMA)
            db.execute('CREATE TEMP TABLE owned (path TEXT PRIMARY KEY)')
            batch = []
            for row in source.execute(_ROWS):
                record = lean(row)
                outcome = import_outcome(record, None if faults is None else record['asset_id'] in faults)
                failed, stages = None, None
                if outcome['failed_stages']:
                    failed = state_of(record, {}, faults)[1]
                    recorded = record.get('stage_faults') or {}
                    stages = {}
                    for stage in outcome['failed_stages']:
                        fault = recorded.get(stage) or recorded.get('previews') or {}
                        stages[stage] = str(fault.get('error') or fault.get('reason') or 'Recorded failure')[:300]
                following = next((s for s in ('inspection', 'previews', 'embeddings') if s in outcome['pending_stages']), None)
                review = (record.get('caption_provenance') or {}).get('findings') or []
                files = record.get('files') or []
                where = _folder(record, key)
                batch.append((record['asset_id'], record['display_name'], where, where.casefold(), record['display_name'].casefold(),
                              kind_of(record), record.get('asset_type'), files[0]['path'] if files else None,
                              json.dumps(sorted({f['format'] for f in files})), json.dumps(sorted({format_group(f['format']) for f in files})),
                              int(bool(record.get('previews'))), failed, stages and json.dumps(stages),
                              following if outcome['state'] == 'pending' else None, outcome['state'],
                              int(processing_eligible(record, formats)), description_state(record),
                              int(any(f.get('severity') == 'warning' for f in review if isinstance(f, dict))),
                              record['processing'].get('inspection'), hashlib.sha256(row[1].encode()).hexdigest(),
                              ((record.get('type_metadata') or {}).get('image_kind') or {}).get('basis')))
                db.executemany('INSERT OR IGNORE INTO temp.owned VALUES (?)', [(f['path'],) for f in files])
                if len(batch) >= 500:
                    db.executemany(_INSERT, batch)
                    batch = []
            db.executemany(_INSERT, batch)
            oversized = group(db, view_answers(current))
            prefix, parents, batch = key + '/', set(), []
            for path, role, payload in source.execute('SELECT path, role, record FROM inventory'):
                row = json.loads(payload)
                path = row.get('path', path)
                relative = path.removeprefix(prefix)
                parent = PurePosixPath(relative).parent.as_posix()
                parents.add('' if parent == '.' else parent)
                if path.startswith(prefix):
                    db.execute('INSERT OR IGNORE INTO inventory VALUES (?)', (relative,))
                if row.get('status') == 'excluded_folder' or db.execute('SELECT 1 FROM temp.owned WHERE path=?', (path,)).fetchone():
                    continue
                file_name = PurePosixPath(path).name
                batch.append((path, file_name, '' if parent == '.' else parent, ('' if parent == '.' else parent).casefold(),
                              file_name.casefold(), row.get('role', role), int(row.get('status') == 'excluded_directory_link')))
            db.executemany('INSERT OR IGNORE INTO files VALUES (?,?,?,?,?,?,?)', batch)
            db.executemany('INSERT INTO folders VALUES (?)', [(p,) for p in sorted(parents)])
            db.executemany('INSERT INTO meta VALUES (?,?)', [('version', str(VERSION)), ('catalog', str(catalog)),
                                                             ('oversized', json.dumps(oversized[:200])), ('oversized_count', str(len(oversized)))])
            db.commit()
        os.replace(temporary, target)
    except PermissionError:
        if not target.exists():
            raise  # Another process may have just placed the same view; otherwise the fault is shown.
    finally:
        temporary.unlink(missing_ok=True)
    _prune(folder, name, target, catalog.parent.parent)


def _prune(folder, name, keep, generations):
    """Remove older views of this generation and views of generations that are gone; a view in use stays."""
    for path in folder.iterdir():
        if path == keep or path.is_dir() or path.is_symlink():
            continue
        if path.suffix == '.tmp':
            stale = time.time() - path.stat().st_mtime > 3600  # A crashed build's leftover; a live one is newer.
        elif path.suffix == '.sqlite':
            generation = path.name.rsplit('-', 1)[0]
            stale = generation == name or not (generations / generation).is_dir()
        else:
            continue
        if stale:
            try:
                path.unlink()
            except OSError:
                pass  # Open in a reader (Windows); removed after a later build.


SKIPPED = 'Not processed: Assetarium does not process this file type'


def state_sql(blocked):
    """SQL for each asset's work state and reason under the current blockers, with its parameters."""
    cases, params = [], []
    for blocker in blocked.values():
        cases.append(f"pending_next IN ({','.join('?' * len(blocker['stages']))}) AND kind IN ({','.join('?' * len(blocker['types']))})")
        params.append((*blocker['stages'], *blocker['types'], blocker['reason']))
    blocks = ''.join(f' WHEN {case} THEN ?' for case in cases)
    # Skipped: waiting work Assetarium will not do (not eligible), so no action can offer it (queue and counts agree).
    state = f"CASE WHEN failed IS NOT NULL THEN 'failed' WHEN pending_next IS NULL THEN 'ready' WHEN NOT eligible THEN 'skipped'{blocks} ELSE 'no_previews' END"
    reason = (f"CASE WHEN failed IS NOT NULL THEN failed WHEN pending_next IS NULL THEN NULL WHEN NOT eligible THEN ?{blocks}"
              " WHEN pending_next = 'embeddings' THEN 'Search data pending' ELSE NULL END")
    state_params = [v for p in params for v in (*p[:-1], 'blocked')]
    reason_params = [SKIPPED] + [v for p in params for v in p]
    return state, state_params, reason, reason_params


def inside_sql(path, column='folder'):
    """SQL keeping rows in ``path`` or below it ('' is the whole library folder)."""
    if not path:
        return '1', []
    prefix = path.rstrip('/') + '/'
    return f'({column} = ? OR substr({column}, 1, ?) = ?)', [path, len(prefix), prefix]


def summary(current, published, formats):
    """Format counts, pending and failed work for the source status, from views (``sources.processing_summary``)."""
    from .settings import PROCESSING_FORMATS
    catalog = published.output_path('data', 'catalog.sqlite')
    with closing(connect(current)) as db:
        # A record differs from its published copy when their digests do; without a publication every one is pending.
        changed = 'OR 1'
        if catalog == current.output_path('data', 'catalog.sqlite'):
            changed = ''
        elif catalog.exists():
            with closing(connect(published)) as other:
                db.execute('ATTACH DATABASE ? AS pub', (other.path.as_uri() + '?mode=ro',))
            changed = 'OR NOT EXISTS (SELECT 1 FROM pub.assets p WHERE p.asset_id = a.asset_id AND p.digest = a.digest)'
        counts = dict.fromkeys(PROCESSING_FORMATS, 0)
        counts.update(db.execute('SELECT j.value, COUNT(*) FROM assets, json_each(assets.groups) j GROUP BY j.value').fetchall())
        total, failed, skipped = db.execute('SELECT COUNT(*), COUNT(failed), COALESCE(SUM(eligible = 0), 0) FROM assets').fetchone()
        descriptions = dict.fromkeys(('complete', 'missing', 'failed', 'unavailable', 'shared'), 0)
        descriptions.update(db.execute('SELECT description, COUNT(*) FROM assets WHERE eligible GROUP BY description').fetchall())
        pending = [r[0] for r in db.execute(f"SELECT asset_id FROM assets a WHERE eligible AND (outcome = 'pending' {changed}) ORDER BY asset_id")]
    from .sources import summary_result
    return summary_result(counts, pending, failed, skipped, total, descriptions, formats)
