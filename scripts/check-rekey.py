"""Proof that keying 3D inspections by Blender's major version re-queues nothing (decision 0028).

Read only for the library store it checks (default: this checkout's) and for asset folders: the ledger, the folder
registry and each folder's working catalog are copied into scratch, and every 3D inspection the ledger recorded
(finished or faulty) is compared under the old definition (``library_migration.legacy_inspection_input``) and the
new code. Passing means nothing the old code saw as current is pending now, and the same holds with the configured
Blender moved to another path of the same version. Controls (reported, expected near zero: only faults whose inputs
cannot be read keep their key): with old-key recognition off, and with another major version. Writes data/evidence/rekey/<run>.json.
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


def snapshot(source, target):
    """A consistent copy of a SQLite file opened read only."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(f'file:{source.as_posix()}?mode=ro', uri=True)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def copy_store(library, store):
    """Ledger, folder registry and each folder's working catalog; results, previews and indexes stay behind."""
    for name in ('ledger.sqlite', 'library.sqlite'):
        snapshot(library / name, store / name)
    for folder in sorted((library / 'folders').iterdir()):
        target = store / 'folders' / folder.name
        target.mkdir(parents=True)
        for path in folder.glob('*.json'):
            shutil.copy2(path, target / path.name)
        work = folder / 'library/generations/work'
        for path in work.rglob('*') if work.is_dir() else ():
            relative = path.relative_to(folder)
            if path.is_file() and relative.parts[3:4] != ('embeddings',):
                (target / relative).parent.mkdir(parents=True, exist_ok=True)
                if path.suffix == '.sqlite':
                    snapshot(path, target / relative)
                else:
                    shutil.copy2(path, target / relative)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--library', help="library store to check (read only); default: this checkout's")
    args = parser.parse_args()
    config = load_project_config(ROOT)
    report_path = config.output_path('data', f'evidence/rekey/{args.run_name}.json')
    if report_path.exists():
        raise SystemExit(f'{report_path} exists; choose a new --run-name (existing outputs are evidence)')
    from local_asset_library import incremental, inspection, library_migration
    from local_asset_library.asset_structure import asset_type
    from local_asset_library.catalog import digest
    from local_asset_library.membership import records
    from local_asset_library.sources import bound, registry
    library = Path(args.library).resolve() if args.library else config.library_store()
    scratch = config.output_path('scratch', f'rekey/{args.run_name}')
    shutil.rmtree(scratch, ignore_errors=True)
    started = time.monotonic()
    copy_store(library, scratch / 'store')
    store = replace(config, library_root=scratch / 'store')
    # Remembered Blenders live in scratch too: the proof never adds entries to this checkout's list.
    versions = scratch / 'blender-versions.json'
    inspection.blender_versions_path = lambda _config: versions
    version = inspection.blender_version(store)
    if version is None:
        raise SystemExit('No configured Blender: [tools].blender must name the Blender the library was processed with')
    moved, other = scratch / 'moved/blender.exe', scratch / 'other/blender.exe'
    for path, reported in ((moved, version), (other, f'{int(version.split(".")[0]) + 1}.0.0')):
        path.parent.mkdir(parents=True)
        path.write_bytes(path.parent.name.encode())  # Never run: its version is recorded as seen.
        inspection.remember_blender(store, path, reported)
    recognized = library_migration.recognized
    def current(work, record, fp, how):
        try:
            return key(work, record, fp, how) == fp
        except (OSError, ValueError) as exc:  # As the pending pass keys an asset whose inputs cannot be read.
            return digest({'asset': record['asset_id'], 'stage': 'inspection', 'precondition': str(exc),
                           'files': record['files']}) == fp
    def key(work, record, fp, how):
        if how == 'old':
            return library_migration.legacy_inspection_input(work, record, recorded=fp)[3]
        scoped = {'moved': replace(work, blender=moved), 'other': replace(work, blender=other)}.get(how, work)
        library_migration.recognized = (lambda *a: False) if how == 'no_recognition' else recognized
        try:
            return incremental.inspection_input(scoped, record, recorded=fp)[3]
        finally:
            library_migration.recognized = recognized
    cases = ('old', 'new', 'moved', 'no_recognition', 'other')
    folders, faults = [], []
    for source in registry(store)['sources']:
        scoped = bound(store, source)
        work = incremental.working(scoped)
        entry = {'key': source['key'], 'checked': 0, **{c: 0 for c in cases}, 'newly_pending': [], 'newly_pending_moved': []}
        with closing(incremental.ledger(scoped)) as db:
            rows = {r[0]: r[1:] for r in db.execute(
                "SELECT asset_id, fingerprint, status FROM jobs WHERE stage='inspection' AND status IN ('complete','failed','unsupported')")}
        try:
            catalog = records(work)
        except Exception as exc:  # A folder whose catalog cannot be read is reported; the others continue.
            faults.append({'key': source['key'], 'fault': f'{type(exc).__name__}: {exc}'})
            continue
        for record in catalog:
            row = rows.get(record['asset_id'])
            if not row or asset_type(record) != 'model_3d':
                continue
            entry['checked'] += 1
            try:
                result = {c: current(work, record, row[0], c) for c in cases}
            except Exception as exc:
                faults.append({'asset_id': record['asset_id'], 'fault': f'{type(exc).__name__}: {exc}'})
                continue
            for c in cases:
                entry[c] += result[c]
            if result['old'] and not result['new']:
                entry['newly_pending'].append(record['asset_id'])
            if result['old'] and not result['moved']:
                entry['newly_pending_moved'].append(record['asset_id'])
        folders.append(entry)
    total = {c: sum(f[c] for f in folders) for c in ('checked',) + cases}
    newly = sum(len(f['newly_pending']) + len(f['newly_pending_moved']) for f in folders)
    report = {'run': args.run_name, 'library': str(library), 'blender': str(config.blender), 'blender_version': version,
              'meaning': {'old': 'current under the old path+mtime key', 'new': 'current under the major-version key',
                          'moved': 'current with Blender moved to another path, same version',
                          'no_recognition': 'control: current without old-key recognition',
                          'other': f'control: current with Blender {int(version.split(".")[0]) + 1}.0.0'},
              'totals': total, 'folders': folders, 'faults': faults,
              'passed': newly == 0 and total['old'] > 0 and not faults,
              'seconds': round(time.monotonic() - started, 1)}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    shutil.rmtree(scratch, ignore_errors=True)
    print(json.dumps({k: report[k] for k in ('totals', 'passed', 'seconds')}, indent=2))
    print(report_path)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
