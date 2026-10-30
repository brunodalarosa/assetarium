"""Proof that re-keying keeps every finished result and re-queues nothing (decision 0023, ASSETRM-0002 phase 1).

Read only for asset folders and their generated folders: each folder's stage ledger is copied into scratch and
re-keyed there, with a scratch library store. For every folder it compares the dry-run pending assets under the
old fingerprints with those under the new keys. Passing means nothing new became pending; assets that stop being
pending reuse a finished result with the same inputs (a duplicate). Writes data/evidence/rekey/<run>.json.
"""
import argparse
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from local_asset_library.config import load_project_config  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--search', action='append', default=[], help='also look for old generated folders here')
    args = parser.parse_args()
    config = load_project_config(ROOT)
    report_path = config.output_path('data', f'evidence/rekey/{args.run_name}.json')
    if report_path.exists():
        raise SystemExit(f'{report_path} exists; choose a new --run-name (existing outputs are evidence)')
    from local_asset_library import incremental, library_migration
    from local_asset_library.sources import bound
    scratch = config.output_path('scratch', f'rekey/{args.run_name}')
    shutil.rmtree(scratch, ignore_errors=True)
    store = replace(config, library_root=scratch / 'store')
    folders, started = [], time.monotonic()
    for found in library_migration.discover(config, [Path(p) for p in args.search]):
        if found.get('fault'):
            folders.append(found)
            continue
        source = {'id': found['id'], 'key': found['key'], 'name': found['key'], 'path': found['path'], 'enabled': True}
        work = incremental.working(bound(store, source))
        copy = scratch / found['id'] / 'jobs.sqlite'
        copy.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(work.output_path('data', 'library/jobs.sqlite'))) as src, closing(sqlite3.connect(copy)) as dst:
            src.backup(dst)
        incremental.ledger = lambda _config, copy=copy: sqlite3.connect(copy)
        entry = {'path': found['path'], 'key': found['key'], 'stages': {}}
        try:
            before = {stage: library_migration.pending(work, stage, legacy=True) for stage in ('inspection', 'caption')}
            with closing(sqlite3.connect(copy)) as db:
                entry['rekeyed'] = library_migration.rekey(work, db)
            for stage in ('inspection', 'caption'):
                after = library_migration.pending(work, stage)
                reused = sorted(before[stage] - after)
                entry['stages'][stage] = {'pending_before': len(before[stage]), 'pending_after': len(after),
                                          'newly_pending': sorted(after - before[stage]), 'reuse_a_shared_result': len(reused)}
        except Exception as exc:  # A fault stops only this folder; it is reported, the others continue.
            entry['fault'] = f'{type(exc).__name__}: {exc}'
        folders.append(entry)
    with closing(sqlite3.connect(scratch / 'store/results/index.sqlite')) as db:
        shared = db.execute('SELECT stage, count(*) FROM results GROUP BY stage').fetchall() if (scratch / 'store/results/index.sqlite').exists() else []
    shutil.rmtree(scratch, ignore_errors=True)
    passed = bool(folders) and all(not f.get('fault') and not any(s['newly_pending'] for s in f['stages'].values()) for f in folders)
    report = {'run_name': args.run_name, 'folders': folders, 'indexed_results': dict(shared), 'passed': passed,
              'elapsed_seconds': round(time.monotonic() - started, 1)}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for folder in folders:
        stages = ', '.join(f"{stage} {s['pending_before']} -> {s['pending_after']} pending ({len(s['newly_pending'])} new, "
                           f"{s['reuse_a_shared_result']} reuse a shared result)" for stage, s in folder.get('stages', {}).items())
        print(f"{folder['path']}: {folder.get('fault') or stages}")
    print(('PASSED' if passed else 'FAILED') + f': {report_path.relative_to(ROOT)}')
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
