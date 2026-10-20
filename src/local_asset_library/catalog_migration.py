"""Explicit, bounded migration of working data only; active generations stay immutable."""
from contextlib import closing
import json
import os
import shutil
import sqlite3
import uuid

from .asset_structure import upgrade_record, validate_collection
from .catalog import encoded
from .config import ConfigError
from .publication import atomic_json, verified_hash


def migrate_working_catalog(config, max_additional_bytes):
    """Call under the coordinator's writer lease, after approving copy costs.

Not called by startup, reads, scans or initialize. A failed candidate and receipt
are retained; no active manifest, index, original, overlay or job is changed.
"""
    if config.catalog_generation != 'work':
        raise ConfigError('Only an explicit working catalog can be migrated')
    if type(max_additional_bytes) is not int or max_additional_bytes < 1:
        raise ConfigError('An explicit migration copy budget is required')
    path = config.output_path('data', 'catalog.sqlite')
    stamp = path.stat()
    signature = (stamp.st_size, stamp.st_mtime_ns, stamp.st_ctime_ns)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
    if version == 2:
        return {'status': 'unchanged', 'schema_version': 2, 'copied_bytes': 0}
    if version != 1:
        raise ConfigError('Unknown catalog version; no migration attempted')
    # Candidate plus rollback journal and metadata expansion. This is a reserve,
    # not a folder-size estimate of unique installed dependency allocation.
    reserve = stamp.st_size * 3 + 65536
    if reserve > max_additional_bytes or reserve > shutil.disk_usage(path.parent).free:
        raise ConfigError(f'Migration needs a {reserve}-byte peak copy reserve; prior working data retained')
    token = uuid.uuid4().hex
    candidate = path.with_name('migration-' + token + '.sqlite')
    receipt_path = config.output_path('data', 'library/migrations/' + token + '.json')
    report = {'from_version': 1, 'to_version': 2, 'source': str(path), 'candidate': str(candidate),
              'reserved_peak_bytes': reserve, 'before_sha256': verified_hash(path, fresh=True)}
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(candidate)) as db:
            source.backup(db)
            records = [upgrade_record(json.loads(r[0])) for r in db.execute('SELECT record FROM assets')]
            validate_collection(records)
            with db:
                db.execute('CREATE TABLE files_v2 (path TEXT NOT NULL, asset_id TEXT NOT NULL REFERENCES assets(asset_id), '
                           'format TEXT NOT NULL, sha256 TEXT, availability TEXT NOT NULL, PRIMARY KEY(asset_id,path))')
                db.execute('INSERT INTO files_v2 SELECT * FROM files')
                db.execute('DROP TABLE files')
                db.execute('ALTER TABLE files_v2 RENAME TO files')
                db.executemany('UPDATE assets SET record=? WHERE asset_id=?', [(encoded(r), r['asset_id']) for r in records])
                db.execute("INSERT OR REPLACE INTO metadata VALUES ('schema_version','2')")
                db.execute('PRAGMA user_version=2')
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
                raise ConfigError('Migrated candidate failed integrity checks')
        now = path.stat()
        if (now.st_size, now.st_mtime_ns, now.st_ctime_ns) != signature or verified_hash(path, fresh=True) != report['before_sha256']:
            raise ConfigError('Working catalog changed during migration; candidate retained without replacement')
        report.update(status='ready', assets=len(records), copied_bytes=candidate.stat().st_size,
                      after_sha256=verified_hash(candidate, fresh=True))
        atomic_json(receipt_path, report)
        os.replace(candidate, path)
        report['status'] = 'complete'
        atomic_json(receipt_path, report)
    except (OSError, ValueError, sqlite3.Error) as exc:
        atomic_json(receipt_path, dict(report, status='failed', error=str(exc)))
        raise
    return report
