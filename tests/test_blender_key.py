"""3D inspection keys hold Blender's major version, not its path (decision 0028, E7).

A fake ``blender --version`` answers by executable; old path+mtime keys stay current for every remembered
Blender of the same major version, and setup asks to re-render only across major versions.
"""
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest

from local_asset_library import incremental, inspection, render_devices, setup_core
from local_asset_library.incremental import inspection_input, ledger, process, working
from local_asset_library.library_migration import legacy_inspection_input
from local_asset_library.membership import records
from test_incremental import library  # noqa: F401  (fixture)

REAL_RUN_PROCESS = inspection.run_process
VERSIONS = {'a': 'Blender 5.1.0', 'b': 'Blender 5.5.2\nbuild hash: synthetic', 'c': 'Blender 6.0.0', 'bad': 'Python 3.13.0'}


@pytest.fixture
def blenders(tmp_path, monkeypatch):
    """Executables a, b, c (5.1, 5.5, 6.0) and bad (not Blender); records each --version run."""
    runs, paths = [], {}
    for name in VERSIONS:
        path = tmp_path / 'installs' / name / 'blender.exe'
        path.parent.mkdir(parents=True)
        path.write_bytes(name.encode() * 3)
        paths[name] = path
    def run(command, cwd, env, timeout):
        runs.append(command)
        name = next(n for n, p in paths.items() if command[0] == str(p))
        return {'returncode': 0, 'timed_out': False, 'output': VERSIONS[name], 'elapsed_seconds': 0.1}
    monkeypatch.setattr(inspection, 'run_process', run)
    monkeypatch.setattr(inspection, '_versions', {})
    paths['runs'] = runs
    return paths


def keys(config, blender, recorded=None):
    work = working(replace(config, blender=blender))
    return {r['asset_id']: inspection_input(work, r, recorded=(recorded or {}).get(r['asset_id']))[3] for r in records(work)}


def test_key_holds_the_major_version_and_reads_it_once_per_executable(library, blenders):
    config, _ = library
    first = keys(config, blenders['a'])
    assert keys(config, blenders['b']) == first  # Another path, size and mtime, same major: same keys.
    assert set(keys(config, blenders['c']).values()).isdisjoint(first.values())  # 6.x renders anew.
    assert len(blenders['runs']) == 3  # One --version per executable, not per asset.
    inspection._versions.clear()
    keys(config, blenders['a'])
    assert len(blenders['runs']) == 3  # Remembered on disk across processes.
    saved = json.loads(inspection.blender_versions_path(config).read_text(encoding='utf-8'))['executables']
    assert [e['version'] for e in saved] == ['5.1.0', '5.5.2', '6.0.0']
    blenders['a'].write_bytes(b'patched in place')  # A changed executable is asked again.
    keys(config, blenders['a'])
    assert len(blenders['runs']) == 4


def test_old_keys_stay_current_after_a_move_within_the_major_version(library, blenders):
    config, _ = library
    work = working(replace(config, blender=blenders['a']))
    old = {r['asset_id']: legacy_inspection_input(work, r)[3] for r in records(work)}
    assert set(old.values()).isdisjoint(keys(config, blenders['a']).values())  # The definition did change.
    assert keys(config, blenders['a'], old) == old  # Today's Blender, old definition: current.
    assert keys(config, blenders['b'], old) == old  # Moved or minor-updated after being seen once: current.
    assert set(keys(config, blenders['c'], old).values()).isdisjoint(old.values())  # Another major: pending.


def test_an_old_key_from_a_blender_never_seen_is_not_guessed(library, blenders):
    config, _ = library
    work = working(replace(config, blender=blenders['a']))
    old = {r['asset_id']: legacy_inspection_input(work, r)[3] for r in records(work)}
    assert set(keys(config, blenders['b'], old).values()).isdisjoint(old.values())


def test_processing_keeps_old_keyed_results_and_faults_after_a_move(library, blenders, monkeypatch):
    config, _ = library
    attempted = []
    monkeypatch.setattr(incremental, 'run_inspection', lambda c, r, fp, resolution=640, formats=None:
                        attempted.append(r['asset_id']) or {'status': 'complete'})
    monkeypatch.setattr(render_devices, 'ensure', lambda *a, **k: None)  # No speed test with fake executables.
    moved, before = replace(config, blender=blenders['b']), replace(config, blender=blenders['a'])
    process(before, 'inspection', 6)
    work = working(before)
    with closing(ledger(before)) as db, db:  # Rewrite the ledger as the previous release left it.
        for i, record in enumerate(records(work)):
            db.execute("UPDATE jobs SET fingerprint=?, status=? WHERE asset_id=? AND stage='inspection'",
                       (legacy_inspection_input(work, record)[3], 'failed' if i == 0 else 'complete', record['asset_id']))
    count = len(attempted)
    dry = process(moved, 'inspection', 6, dry_run=True)
    assert dry['pending'] == 0 and len(attempted) == count
    assert process(moved, 'inspection', 6)['selected'] == 0 and len(attempted) == count  # The fault is not retried.
    assert process(replace(config, blender=blenders['c']), 'inspection', 6, dry_run=True)['pending'] == 5


def test_an_unreadable_version_is_a_visible_fault_not_a_precondition(library, blenders):
    config, _ = library
    with pytest.raises(inspection.BlenderVersionError, match='did not report a Blender version'):
        process(replace(config, blender=blenders['bad']), 'inspection', 6, dry_run=True)
    keys(config, blenders['a'])
    inspection.blender_versions_path(config).write_text('{"executables": [{"path": 3}]}', encoding='utf-8')
    inspection._versions.clear()  # Another process, reading the damaged file.
    with pytest.raises(inspection.BlenderVersionError, match='restore it'):
        keys(config, blenders['a'])


def test_a_blender_that_cannot_start_stops_processing_and_keeps_finished_work(library, blenders, monkeypatch):
    config, _ = library
    monkeypatch.setattr(incremental, 'run_inspection', lambda c, r, fp, resolution=640, formats=None: {'status': 'complete'})
    monkeypatch.setattr(render_devices, 'ensure', lambda *a, **k: None)
    before = replace(config, blender=blenders['a'])
    process(before, 'inspection', 6)
    work = working(before)
    with closing(ledger(before)) as db, db:
        for record in records(work):
            db.execute("UPDATE jobs SET fingerprint=? WHERE asset_id=? AND stage='inspection'",
                       (legacy_inspection_input(work, record)[3], record['asset_id']))
        finished = db.execute("SELECT asset_id, fingerprint, status FROM jobs WHERE stage='inspection' ORDER BY 1").fetchall()
    damaged = blenders['a'].parent.parent / 'damaged' / 'blender.exe'
    damaged.parent.mkdir()
    damaged.write_bytes(b'not a program')  # Real launch: WinError 193 on Windows, PermissionError elsewhere.
    monkeypatch.setattr(inspection, 'run_process', REAL_RUN_PROCESS)
    for dry_run in (True, False):
        with pytest.raises(inspection.BlenderVersionError, match='could not be started'):
            process(replace(config, blender=damaged), 'inspection', 6, dry_run=dry_run)
    with closing(ledger(before)) as db:
        assert db.execute("SELECT asset_id, fingerprint, status FROM jobs WHERE stage='inspection' ORDER BY 1").fetchall() == finished


WRITER = r'''
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from local_asset_library import inspection
class Config:
    project_root = Path(sys.argv[2])
    def output_path(self, area, relative):
        return self.project_root / area / relative
read = inspection.remembered_blenders
def slow(config):
    entries = read(config)
    time.sleep(1.5)  # Long enough for the other writer to read the same old list without a lease.
    return entries
inspection.remembered_blenders = slow
inspection.remember_blender(Config(), sys.argv[3], '5.2.2')
'''


def test_concurrent_processes_keep_every_remembered_blender(tmp_path, blenders):
    root = tmp_path / 'checkout'
    root.mkdir()
    src = str(Path(inspection.__file__).parents[1])
    writers = [subprocess.Popen([sys.executable, '-c', WRITER, src, str(root), str(blenders[name])])
               for name in ('a', 'b')]
    assert [w.wait(timeout=60) for w in writers] == [0, 0]
    saved = json.loads((root / 'data/inspection/blender-versions.json').read_text(encoding='utf-8'))['executables']
    assert sorted(e['path'] for e in saved) == sorted([str(blenders['a']), str(blenders['b'])])


def test_no_blender_configured_keeps_a_key(library, blenders):
    config, _ = library
    assert all(keys(config, None).values()) and not blenders['runs']


def test_setup_asks_to_rerender_only_across_major_versions(library, blenders, monkeypatch):
    config, _ = library
    saved = {'path': blenders['a']}
    monkeypatch.setattr(setup_core, 'configured_blender', lambda c: (replace(c, blender=saved['path']),
                                                                     str(saved['path']) if saved['path'] else None, 'config.local.toml'))
    monkeypatch.setattr(setup_core, 'processed_models', lambda c: 7)
    def validate(c, path):
        version = inspection.blender_version(c, path)
        setup_core._validated[setup_core._identity(path)] = {'status': 'passed', 'version': version}
        return {'status': 'passed', 'path': str(path), 'checks': [], 'version': version}
    monkeypatch.setattr(setup_core, 'validate_blender', validate)
    assert setup_core.check_blender(config, str(blenders['b']))['rerender'] == 0
    assert setup_core.blender_plan(config, str(blenders['b'])) == 'write'  # Saves without the confirmation.
    assert setup_core.check_blender(config, str(blenders['c']))['rerender'] == 7
    with pytest.raises(Exception, match='Confirm that finished previews'):
        setup_core.blender_plan(config, str(blenders['c']))
    assert setup_core.blender_plan(config, str(blenders['c']), confirm_rerender=True) == 'write'
    blenders['a'].unlink()  # The saved Blender was uninstalled: its remembered version still counts.
    inspection._versions.clear()
    assert setup_core.keeps_inspections(config, '5.5.2') and not setup_core.keeps_inspections(config, '6.0.0')
    saved['path'] = None  # Nothing saved yet: a first Blender may re-render.
    assert not setup_core.keeps_inspections(config, '5.5.2')
