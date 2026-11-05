"""After a crash: read-only reads recover a killed writer's journal, and one unreadable source never hides the others."""
from contextlib import closing
import sqlite3
import subprocess
import sys

import pytest

from test_sources import managed, ready_source  # noqa: F401  (fixture and helper)
from local_asset_library import sources
from local_asset_library.publication import read_only

WRITER = """
import sqlite3, sys, time
db = sqlite3.connect(sys.argv[1], isolation_level=None)
db.execute('PRAGMA cache_size=1')  # Spill dirty pages into the file mid-transaction, as a large batch does.
db.execute('BEGIN')
db.executemany('INSERT INTO vectors VALUES (?, ?)', [(i, b'x' * 512) for i in range(1000, 4000)])
print('writing', flush=True)
if sys.argv[2] == 'commit':
    sys.stdin.readline()
    db.execute('COMMIT')
    print('committed', flush=True)
else:
    time.sleep(60)
"""


@pytest.fixture
def index(tmp_path):
    path = tmp_path / 'index.sqlite'
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE vectors (id INTEGER PRIMARY KEY, value BLOB)')
        db.executemany('INSERT INTO vectors VALUES (?, ?)', [(i, b'v') for i in range(100)])
    (tmp_path / 'writer.py').write_text(WRITER)
    return path


def writer(index, mode):
    process = subprocess.Popen([sys.executable, str(index.parent / 'writer.py'), str(index), mode],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert process.stdout.readline().strip() == 'writing'
    return process


def test_read_only_recovers_the_journal_of_a_killed_writer(index):
    process = writer(index, 'kill')
    process.kill()  # A crash or forced close mid-batch.
    process.wait()
    journal = index.with_name('index.sqlite-journal')
    assert journal.exists()
    with closing(sqlite3.connect(index.as_uri() + '?mode=ro', uri=True)) as plain, \
            pytest.raises(sqlite3.OperationalError, match='readonly'):
        plain.execute('SELECT count(*) FROM vectors').fetchone()  # What the source list hit after the real crash.
    with closing(read_only(index)) as db:
        assert db.execute('SELECT count(*) FROM vectors').fetchone()[0] == 100  # Committed rows; the batch is undone.
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert not journal.exists() or journal.stat().st_size == 0


def test_read_only_never_touches_a_live_writers_journal(index):
    process = writer(index, 'commit')
    try:
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            read_only(index)  # Busy, not recovered: the writer still owns its journal.
        process.stdin.write('\n')
        process.stdin.flush()
        assert process.stdout.readline().strip() == 'committed'
    finally:
        process.wait(30)
    with closing(read_only(index)) as db:
        assert db.execute('SELECT count(*) FROM vectors').fetchone()[0] == 3100


def test_one_unreadable_source_never_hides_the_others(managed, monkeypatch):
    config, backend, one, two = managed
    for source in (one, two):
        ready_source(config, backend, source)
    original = sources._format_status

    def unreadable(scoped, *args):
        if scoped.source_key == one['key']:
            raise sqlite3.OperationalError('attempt to write a readonly database')
        return original(scoped, *args)
    monkeypatch.setattr(sources, '_format_status', unreadable)
    statuses = {s['key']: s for s in sources.source_statuses(config)}
    assert 'could not be read (attempt to write a readonly database)' in statuses[one['key']]['scan_fault']
    assert not statuses[two['key']].get('scan_fault') and statuses[two['key']]['name'] == two['name']
    original_status = sources.source_status
    monkeypatch.setattr(sources, 'source_status', lambda c, s: (_ for _ in ()).throw(RuntimeError('broken record'))
                        if s['key'] == two['key'] else original_status(c, s))
    statuses = {s['key']: s for s in sources.source_statuses(config)}
    assert set(statuses) == {one['key'], two['key']}
    broken = statuses[two['key']]
    assert 'RuntimeError: broken record' in broken['scan_fault'] and broken['exclusions'] == [] and broken['operation']


def test_the_desktop_source_list_shows_every_source_with_its_fault(managed, monkeypatch):
    from local_asset_library.desktop import DesktopBridge
    config, backend, one, two = managed
    original = sources.source_status
    monkeypatch.setattr(sources, 'source_status', lambda c, s: (_ for _ in ()).throw(sqlite3.OperationalError('disk I/O error'))
                        if s['key'] == one['key'] else original(c, s))
    bridge = DesktopBridge(config, prestart_worker=False)
    try:
        listed = bridge.sources()
        assert listed['status'] == 'ready' and {s['key'] for s in listed['sources']} == {one['key'], two['key']}
        assert 'disk I/O error' in next(s for s in listed['sources'] if s['key'] == one['key'])['scan_fault']
    finally:
        bridge._close()
