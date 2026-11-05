"""The library store's own database: library folders, recognized assets and their history (decision 0023).

A library folder is a watched root. An asset ID is assigned once, at first sight, and kept by recognizing the
asset again: the same place, or the same content where a vanished asset was (a move). The same content beside a
present asset is a duplicate with its own ID; new content at a known place is the same asset, edited. Every
recognition other than "same place, same content" is recorded with its evidence.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3
import uuid

from .catalog import asset_id as formula_id, digest, encoded
from .config import ConfigError
from .store_versions import checked

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS folders(id TEXT PRIMARY KEY, key TEXT UNIQUE, name TEXT, path TEXT, enabled INTEGER,
  state TEXT, added_utc TEXT, replaced_by TEXT);
CREATE TABLE IF NOT EXISTS assets(asset_id TEXT PRIMARY KEY, folder_id TEXT, locator TEXT, content TEXT,
  state TEXT, first_seen TEXT, last_seen TEXT, record TEXT);
CREATE INDEX IF NOT EXISTS assets_place ON assets(folder_id, locator);
CREATE INDEX IF NOT EXISTS assets_content ON assets(content);
CREATE TABLE IF NOT EXISTS recognition(sequence INTEGER PRIMARY KEY, utc TEXT, asset_id TEXT, kind TEXT,
  folder_id TEXT, locator TEXT, evidence TEXT);
CREATE TABLE IF NOT EXISTS answers(folder_id TEXT, path TEXT, kind TEXT, value TEXT, utc TEXT,
  PRIMARY KEY(folder_id, path, kind));
CREATE TABLE IF NOT EXISTS profiles(folder_id TEXT, pack TEXT, version INTEGER, rules TEXT, origin TEXT, utc TEXT,
  PRIMARY KEY(folder_id, pack, version));
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def database_path(config):
    return config.library_store() / 'library.sqlite'


def connect(config):
    path = database_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = checked(sqlite3.connect(path, timeout=30), 'The library database', 1)
    db.executescript(SCHEMA)
    return db


def revision(config):
    path = database_path(config)
    if not path.exists():
        return 'empty'
    with closing(connect(config)) as db:
        row = db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
    return row[0] if row else 'empty'


def touch(db):
    db.execute("INSERT OR REPLACE INTO meta VALUES ('revision', ?)", (uuid.uuid4().hex,))


def _folder(row):
    return {'id': row[0], 'key': row[1], 'name': row[2], 'path': row[3], 'enabled': bool(row[4])}


def folders(config):
    """``{'sources': active folders, 'detached': removed ones}``, the shape the source registry always had."""
    path = database_path(config)
    if not path.exists():
        return {'schema_version': 1, 'revision': 'empty', 'sources': [], 'detached': []}
    with closing(connect(config)) as db:
        rows = db.execute('SELECT id, key, name, path, enabled, state FROM folders ORDER BY added_utc, key').fetchall()
        value = db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
    return {'schema_version': 1, 'revision': value[0] if value else 'empty',
            'sources': [_folder(r) for r in rows if r[5] == 'active'],
            'detached': [_folder(r) for r in rows if r[5] != 'active']}


def save_folder(db, folder, state='active', replaced_by=None):
    old = db.execute('SELECT added_utc FROM folders WHERE id=?', (folder['id'],)).fetchone()
    db.execute('INSERT OR REPLACE INTO folders VALUES (?,?,?,?,?,?,?,?)',
               (folder['id'], folder['key'], folder['name'], folder['path'], int(folder['enabled']), state,
                old[0] if old else now(), replaced_by))
    touch(db)


def replaced(config, folder_id):
    """Folders the folder ``folder_id`` replaced when it was added around them."""
    with closing(connect(config)) as db:
        return [dict(_folder(r), replaced_by=folder_id) for r in db.execute(
            "SELECT id, key, name, path, enabled FROM folders WHERE state='replaced' AND replaced_by=?", (folder_id,))]


def content_of(record):
    """Recognition evidence: the bytes of the asset's files, wherever they are."""
    return digest(sorted(f.get('sha256') or f['path'] for f in record['files']))


def _remap(records, mapping):
    if not mapping:
        return records
    text = encoded(records)
    for old, new in mapping.items():
        text = text.replace('"' + old + '"', '"' + new + '"')
    return json.loads(text)


def recognize(config, folder, fresh, previous=(), excluded=()):
    """Give each freshly scanned record its kept ID; record moves, duplicates, edits and vanished assets.

    ``fresh`` carries formula IDs from the scan. Returns (records with kept IDs, summary). ``previous`` holds
    this folder's last records, kept as snapshots of assets that went Missing. An asset that vanished because its
    folder is now excluded (``excluded``: folder paths the scan skipped) is ``excluded``, not Missing: it is not listed,
    and including the folder again brings it back with its ID.
    """
    stamp = now()
    summary = {'new': 0, 'moved': 0, 'duplicate': 0, 'edited': 0, 'missing': 0, 'returned': 0, 'excluded': 0}
    skipped = lambda locator: any(locator.removeprefix('image:').startswith(f + '/') for f in excluded)
    with closing(connect(config)) as db, db:
        known = {r[1]: r for r in db.execute(
            "SELECT asset_id, locator, content, state FROM assets WHERE folder_id=?", (folder['id'],))}
        locators = {r['source_relative_identity'] for r in fresh}
        vanished = {row[0]: row for locator, row in known.items() if locator not in locators and row[3] == 'present'}
        missing = {r[0]: r for r in db.execute("SELECT asset_id, locator, content, state, folder_id FROM assets WHERE state='missing'")}
        # A missing asset whose own locator is back in this scan returns as itself; a copy elsewhere can't claim it.
        missing = {i: r for i, r in missing.items() if not (r[4] == folder['id'] and r[1] in locators)}
        missing.update(vanished)
        by_content = {}
        for row in missing.values():
            by_content.setdefault(row[2], []).append(row[0])
        taken = {r[0] for r in db.execute('SELECT asset_id FROM assets')}
        mapping, kept, history = {}, set(), []
        for record in fresh:
            locator, content = record['source_relative_identity'], content_of(record)
            row = known.get(locator)
            if row:
                identifier = row[0]
                if row[2] != content:
                    summary['edited'] += 1
                    history.append((identifier, 'edited', locator, {'before': row[2], 'after': content}))
                elif row[3] in {'missing', 'excluded'}:
                    summary['returned'] += 1
                    history.append((identifier, 'returned', locator, {'content': content}))
            elif candidates := [i for i in by_content.get(content, []) if i not in kept]:
                identifier = candidates[0]
                summary['moved'] += 1
                history.append((identifier, 'moved', locator, {'from': missing[identifier][1], 'content': content,
                                                               'from_folder': missing[identifier][4] if len(missing[identifier]) > 4 else folder['id']}))
            else:
                identifier = record['asset_id']
                suffix = 0
                while identifier in taken:  # Formula IDs stay deterministic; a clash with a kept ID takes the next one.
                    suffix += 1
                    identifier = formula_id(record['pack_id'], f"{locator}#{suffix}")
                duplicate = db.execute("SELECT asset_id FROM assets WHERE content=? AND state='present' LIMIT 1", (content,)).fetchone()
                summary['duplicate' if duplicate else 'new'] += 1
                if duplicate:
                    history.append((identifier, 'duplicate', locator, {'of': duplicate[0], 'content': content}))
            kept.add(identifier)
            taken.add(identifier)
            if identifier != record['asset_id']:
                mapping[record['asset_id']] = identifier
            if row and row[0] == identifier and row[2] == content and row[3] == 'present':
                continue  # Unchanged: an unchanged scan leaves the database untouched.
            db.execute('INSERT INTO assets VALUES (?,?,?,?,?,?,?,NULL) ON CONFLICT(asset_id) DO UPDATE SET '
                       "folder_id=excluded.folder_id, locator=excluded.locator, content=excluded.content, state='present', "
                       'last_seen=excluded.last_seen, record=NULL',
                       (identifier, folder['id'], locator, content, 'present', stamp, stamp))
        snapshots = {r['asset_id']: r for r in previous}
        for identifier, row in vanished.items():
            if identifier in kept:
                continue
            state = 'excluded' if skipped(row[1]) else 'missing'
            summary[state] += 1
            history.append((identifier, state, row[1], {'content': row[2]}))
            snapshot = snapshots.get(identifier)
            db.execute('UPDATE assets SET state=?, record=? WHERE asset_id=?', (state, encoded(snapshot) if snapshot else None, identifier))
        db.executemany('INSERT INTO recognition(utc, asset_id, kind, folder_id, locator, evidence) VALUES (?,?,?,?,?,?)',
                       [(stamp, i, kind, folder['id'], locator, encoded(evidence)) for i, kind, locator, evidence in history])
        if history:
            touch(db)
    return _remap(fresh, mapping), summary


def missing_assets(config, folder_id=None, prefix=None):
    """Missing assets with their last saved record, results and collection entries kept until forgotten."""
    if not database_path(config).exists():
        return []
    query = "SELECT asset_id, folder_id, locator, last_seen, record FROM assets WHERE state='missing'"
    with closing(connect(config)) as db:
        rows = db.execute(query + (' AND folder_id=?' if folder_id else ''), (folder_id,) if folder_id else ()).fetchall()
    found = [{'asset_id': r[0], 'folder_id': r[1], 'locator': r[2], 'last_seen': r[3], 'record': json.loads(r[4]) if r[4] else None}
             for r in rows]
    def within(asset):
        places = [asset['locator'].removeprefix('image:')]
        places += [f['path'].split('/', 1)[-1] for f in (asset.get('record') or {}).get('files', [])]
        return not prefix or any(p == prefix or p.startswith(prefix.rstrip('/') + '/') for p in places)
    return [a for a in found if within(a)]


def missing_count(config, folder_id):
    if not database_path(config).exists():
        return 0
    with closing(connect(config)) as db:
        return db.execute("SELECT COUNT(*) FROM assets WHERE state='missing' AND folder_id=?", (folder_id,)).fetchone()[0]


def missing_list(config, folder_id):
    """Missing assets with the few saved fields a list shows; the saved records stay in the database."""
    if not database_path(config).exists():
        return []
    with closing(connect(config)) as db:
        rows = db.execute("SELECT asset_id, locator, last_seen, json_extract(record, '$.display_name'), "
                          "json_extract(record, '$.files'), json_extract(record, '$.asset_type'), "
                          "json_extract(record, '$.type_metadata.image_kind') FROM assets WHERE state='missing' AND folder_id=?",
                          (folder_id,)).fetchall()
    return [{'asset_id': r[0], 'locator': r[1], 'last_seen': r[2], 'record': {
        'display_name': r[3], 'files': [{'path': f['path'], 'format': f.get('format')} for f in json.loads(r[4] or '[]')], 'asset_type': r[5],
        'type_metadata': {'image_kind': json.loads(r[6])} if r[6] else {}} if r[3] or r[4] else None} for r in rows]


def forget_missing(config, folder_id, prefix=None, expected_revision=None):
    """Forget Missing assets (all of a folder, or those under ``prefix``); the history keeps the evidence."""
    stamp = now()
    with closing(connect(config)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute("SELECT value FROM meta WHERE key='revision'").fetchone()
        if expected_revision is not None and expected_revision != (current[0] if current else 'empty'):
            raise ConfigError('The library changed. Review the missing entries again before deleting.')
        chosen = missing_assets(config, folder_id, prefix)
        if not chosen:
            raise ConfigError('Nothing is missing here')
        for asset in chosen:
            db.execute('DELETE FROM assets WHERE asset_id=?', (asset['asset_id'],))
            db.execute('INSERT INTO recognition(utc, asset_id, kind, folder_id, locator, evidence) VALUES (?,?,?,?,?,?)',
                       (stamp, asset['asset_id'], 'forgotten', folder_id, asset['locator'], encoded({'last_seen': asset['last_seen']})))
        touch(db)
    return len(chosen)


def history(config, asset_id):
    """Why an asset has its ID: every recognition recorded for it, oldest first."""
    if not database_path(config).exists():
        return []
    with closing(connect(config)) as db:
        return [{'utc': r[0], 'kind': r[1], 'folder_id': r[2], 'locator': r[3], 'evidence': json.loads(r[4])}
                for r in db.execute('SELECT utc, kind, folder_id, locator, evidence FROM recognition WHERE asset_id=? ORDER BY sequence',
                                    (asset_id,))]


def relocate(db, child, parent_id, prefix):
    """A folder added around ``child`` takes over its assets: same IDs, locators now one level down."""
    db.execute("UPDATE assets SET folder_id=:parent, locator=CASE WHEN locator LIKE 'image:%' "
               "THEN 'image:' || :prefix || '/' || substr(locator, 7) ELSE :prefix || '/' || locator END WHERE folder_id=:child",
               {'parent': parent_id, 'prefix': prefix, 'child': child['id']})


def carry_answers(db, child, parent_id, prefix):
    """A replaced folder's answers (packs, image kinds, variant axes…) under the folder added around it, paths prefixed.

    The new folder's own answer for the same path wins; each such conflict is returned as a note. The child keeps its
    rows, so adding it on its own again still finds them."""
    notes = []
    for path, kind, value, utc in db.execute('SELECT path, kind, value, utc FROM answers WHERE folder_id=?', (child['id'],)).fetchall():
        moved = f'{prefix}/{path}' if path else prefix
        if db.execute('SELECT 1 FROM answers WHERE folder_id=? AND path=? AND kind=?', (parent_id, moved, kind)).fetchone():
            notes.append(f'{kind} answer for “{moved}”: the new library folder’s own answer was kept')
            continue
        db.execute('INSERT INTO answers VALUES (?,?,?,?,?)', (parent_id, moved, kind, value, utc))
    return notes


def carried(record, child, folder, prefix):
    """A record from a replaced folder as the folder around it sees it: paths gain the folder's prefix."""
    text = encoded(record).replace('"' + child['key'] + '/', '"' + folder['key'] + '/' + prefix + '/')
    value = json.loads(text)
    value['pack_id'] = folder['key']
    return value


def answers(config, folder_id, kind=None):
    """Owner answers saved on a folder or pack path (exclusions, export groups, texture folders, image kinds, packs)."""
    if not database_path(config).exists():
        return []
    with closing(connect(config)) as db:
        rows = db.execute('SELECT path, kind, value, utc FROM answers WHERE folder_id=?' + (' AND kind=?' if kind else ''),
                          (folder_id, kind) if kind else (folder_id,)).fetchall()
    return [{'path': r[0], 'kind': r[1], 'value': json.loads(r[2]), 'utc': r[3]} for r in rows]


def save_answer(config, folder_id, path, kind, value):
    with closing(connect(config)) as db, db:
        if value is None:
            db.execute('DELETE FROM answers WHERE folder_id=? AND path=? AND kind=?', (folder_id, path, kind))
        else:
            db.execute('INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?)', (folder_id, path, kind, encoded(value), now()))
        touch(db)


def replace_answers(config, folder_id, kinds, inside, rows):
    """Replace this folder's answers of ``kinds`` at or below path ``inside`` ('' is everything) with ``rows``.

    ``rows`` are ``(path, kind, value)``; one transaction, so a pack profile never applies half.
    """
    prefix = inside.rstrip('/') + '/'
    with closing(connect(config)) as db, db:
        for kind in kinds:
            db.execute('DELETE FROM answers WHERE folder_id=? AND kind=? AND (?=\'\' OR path=? OR substr(path, 1, ?)=?)',
                       (folder_id, kind, inside, inside, len(prefix), prefix))
        db.executemany('INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?)',
                       [(folder_id, path, kind, encoded(value), now()) for path, kind, value in rows])
        touch(db)
