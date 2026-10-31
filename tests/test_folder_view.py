"""Folder views: the Asset sources and processing tabs read bounded rows, never whole records (decision 0023)."""
import asyncio
from contextlib import closing
import json
import sqlite3
import threading
import time
import tracemalloc

import pytest

from test_sources import managed, ready_source  # noqa: F401 -- fixtures
from local_asset_library import folder_view, library_view, processing_queue, sources
from local_asset_library.desktop import DesktopBridge
from local_asset_library.incremental import update_record, working


def work_of(config, source):
    return working(sources.bound(config, source))


def inflate(config, source, copies, padding):
    """Clone the folder's first record ``copies`` times with ``padding`` bytes of unused variants each."""
    catalog = work_of(config, source).output_path('data', 'catalog.sqlite')
    with closing(sqlite3.connect(catalog)) as db, db:
        row = db.execute('SELECT asset_id, source_id, pack_id, identity, name, availability, record FROM assets').fetchone()
        record = json.loads(row[6])
        record['variants'] = [{'asset_id': 'x' * 40, 'evidence': 'y' * 60, 'relationship': 'filename_variant_candidate'}] * (padding // 120)
        first = db.execute('SELECT COUNT(*) FROM assets').fetchone()[0]
        for n in range(first, first + copies):
            clone = dict(record, asset_id=f'asset_clone{n:05d}', display_name=f'clone {n}')
            db.execute('INSERT INTO assets VALUES (?,?,?,?,?,?,?)',
                       (clone['asset_id'], row[1], row[2], f'clone-{n}', clone['display_name'], row[5], json.dumps(clone)))


def peak(call):
    tracemalloc.start()
    try:
        call()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_view_states_and_counts_match_the_records(managed, monkeypatch):
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    blocked = {'previews': {'reason': 'Blender is not set up', 'fix': 'Set up Blender', 'stages': ['inspection', 'previews'], 'types': ['model_3d']}}
    monkeypatch.setattr(library_view, 'blockers', lambda config: blocked)
    (sources.Path(one['path']) / 'extra.obj').write_text('v 0 0 0\n')
    sources.scan_source(config, one)
    work = work_of(config, one)
    records = sources.read_records(work)
    faults = sources.embedding_failures(work)
    expected = {r['asset_id']: library_view.state_of(r, blocked, faults) for r in records}
    items = library_view.folder_items(config, one['key'], show_files=False, page_size=200)
    assert {i['asset_id']: (i['state'], i['reason']) for i in items['items']} == expected
    assert items['counts']['blocked'] == 1 and items['counts']['ready'] == len(records) - 1
    root = next(n for f in library_view.tree(config)['folders'] if f['key'] == one['key'] for n in f['nodes'] if n['path'] == '')
    assert root['assets'] == len(records) and root['blocked'] == 1
    page = library_view.folder_items(config, one['key'], offset=1, page_size=2)
    assert [i['asset_id'] for i in page['items']] == [i['asset_id'] for i in items['items']][1:3]


def test_pages_and_builds_stay_bounded_as_records_grow(managed, monkeypatch):
    config, _, one, _ = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    sources.scan_source(config, one)
    library_view.folder_items(config, one['key'])  # Module imports and the first build, outside the measurements.
    library_view.tree(config)
    small = peak(lambda: library_view.folder_items(config, one['key'], page_size=80)), peak(lambda: library_view.tree(config))
    inflate(config, one, 1500, 40_000)  # About 60 MB of record JSON; loading it whole costs several times that.
    work = work_of(config, one)
    target = work.metadata_root / 'library/views/probe.sqlite'
    built = peak(lambda: folder_view.build(work, target))
    target.unlink()
    library_view.folder_items(config, one['key'])
    large = peak(lambda: library_view.folder_items(config, one['key'], page_size=80)), peak(lambda: library_view.tree(config))
    # A page and the tree cost the same with 1,500 more large records; a build streams them.
    assert built < 8 * 2**20 and all(b - a < 2**20 for a, b in zip(small, large)), (built, small, large)
    assert library_view.folder_items(config, one['key'])['assets'] >= 1500


def test_a_changed_catalog_gets_a_new_view_and_a_stale_one_answers_meanwhile(managed, monkeypatch):
    config, _, one, _ = managed
    sources.scan_source(config, one)
    work = work_of(config, one)
    with closing(folder_view.connect(work)) as view:
        first = view.path
        count = view.execute('SELECT COUNT(*) FROM assets').fetchone()[0]
    inflate(config, one, 2, 100)
    with closing(folder_view.connect(work)) as view:  # Built within the wait: the new rows are there.
        assert view.path != first and view.execute('SELECT COUNT(*) FROM assets').fetchone()[0] == count + 2
        second = view.path
    assert not first.exists()  # The older view of this generation is pruned.
    monkeypatch.setitem(folder_view._jobs, second.parent / 'work', {'done': threading.Event(), 'ended': time.monotonic(), 'took': 3600})
    folder_view._jobs[second.parent / 'work']['done'].set()
    inflate(config, one, 1, 100)
    with closing(folder_view.connect(work)) as view:  # A large view rebuilt moments ago is not rebuilt again yet.
        assert view.path == second
    with closing(folder_view.connect(work, fresh=True)) as view:  # Resolving work to process always waits for it.
        assert view.path != second and view.execute('SELECT COUNT(*) FROM assets').fetchone()[0] == count + 3


def test_a_first_build_answers_reading_and_runs_once(managed, monkeypatch):
    config, _, one, _ = managed
    sources.scan_source(config, one)
    release, runs, original = threading.Event(), [], folder_view.build
    monkeypatch.setattr(folder_view, 'WAIT', 0.05)

    def slow(current, target):
        runs.append(target)
        release.wait(10)
        original(current, target)
    monkeypatch.setattr(folder_view, 'build', slow)
    assert library_view.folder_items(config, one['key'])['status'] == 'reading'
    folder = next(f for f in library_view.tree(config)['folders'] if f['key'] == one['key'])
    assert folder['reading'] and folder['nodes'] == [] and not folder['scan_fault'] and folder['attention'] == []
    assert sources.source_status(config, one)['reading']
    release.set()
    deadline = time.monotonic() + 10
    while library_view.folder_items(config, one['key'])['status'] == 'reading' and time.monotonic() < deadline:
        time.sleep(.05)
    assert library_view.folder_items(config, one['key'])['status'] == 'ready' and len(runs) == 1


def test_queue_resolves_and_lists_failures_from_the_view(managed, monkeypatch):
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    (sources.Path(one['path']) / 'extra.obj').write_text('v 0 0 0\n')
    sources.scan_source(config, one)
    found = processing_queue.resolve(config, 'previews', {'key': one['key'], 'path': ''})
    assert len(found['ids']) == 1 and found['kinds'] == {'model_3d': 1}
    work = work_of(config, one)
    record = next(r for r in sources.read_records(work) if r['asset_id'] == found['ids'][0])
    record['processing']['inspection'] = 'failed'
    record['stage_faults'] = {'inspection': {'error': 'Broken mesh'}}
    update_record(work, record)
    assert processing_queue.resolve(config, 'previews', {'key': one['key'], 'path': ''})['ids'] == []
    groups = processing_queue.failures(config)
    assert [(g['stage'], g['reason'], len(g['assets'])) for g in groups] == [('inspection', 'Broken mesh', 1)]
    assert sources.importing_failures(config)['assets'] == 1


def test_bridge_shares_identical_calls_and_closes_with_a_read_still_running(managed):
    config, _, _, _ = managed
    bridge = DesktopBridge(config, prestart_worker=False)
    release, runs = threading.Event(), []

    def slow(value):
        runs.append(value)
        release.wait(30)
        return {'status': 'ready', 'value': value}
    try:
        calls = [asyncio.run_coroutine_threadsafe(bridge._present(slow, 1, guarded=False, shared=True), bridge._loop) for _ in range(3)]
        time.sleep(.2)
        release.set()
        assert [c.result(5)['value'] for c in calls] == [1, 1, 1] and runs == [1]
        release.clear()
        stuck = asyncio.run_coroutine_threadsafe(bridge._present(slow, 2, guarded=False, shared=True), bridge._loop)
        time.sleep(.2)
        started = time.perf_counter()
        bridge._close()
        assert time.perf_counter() - started < 10 and not bridge._thread.is_alive() and stuck.done()
    finally:
        release.set()
        bridge._close()


@pytest.mark.parametrize('path, rows', [('', 3), ('a', 2), ('a_b', 1)])
def test_inside_sql_matches_folders_exactly(path, rows):
    with closing(sqlite3.connect(':memory:')) as db:
        db.execute('CREATE TABLE t (folder TEXT)')
        db.executemany('INSERT INTO t VALUES (?)', [('a',), ('a/b',), ('a_b',)])
        where, params = folder_view.inside_sql(path)
        assert db.execute(f'SELECT COUNT(*) FROM t WHERE {where}', params).fetchone()[0] == rows
