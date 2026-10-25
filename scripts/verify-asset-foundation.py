"""Read-only live-library preservation check. Never scans, publishes or loads models."""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from local_asset_library.config import load_project_config
from local_asset_library.incremental import inspection_input, caption_input
from local_asset_library.publication import snapshot
from local_asset_library.retrieval import source_check, description_input
from local_asset_library.sources import bound, registry


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def capture(root):
    config = load_project_config(root)
    files, samples, counts = {}, {}, {}
    for scoped in [config] + [bound(config, source) for source in registry(config)['sources']]:
        key = scoped.source_key or 'combined'
        with snapshot(scoped):
            catalog = scoped.output_path('data', 'catalog.sqlite')
            if not catalog.exists():
                # A newly registered source has no publication yet. Report the
                # changed scope; do not create a catalog or fail the whole audit.
                counts[key] = None
                samples[key] = {'publication': 'missing'}
                continue
            for relative in ('catalog.sqlite', 'embeddings/index.sqlite', 'library/membership.json',
                             'library/active.json', 'library/jobs.sqlite'):
                path = scoped.output_path('data', relative)
                if path.is_file():
                    files[str(path)] = sha(path)
            with closing(sqlite3.connect(catalog.as_uri() + '?mode=ro', uri=True)) as db:
                counts[key] = db.execute('SELECT count(*) FROM assets').fetchone()[0]
                raw = db.execute('SELECT record FROM assets ORDER BY asset_id LIMIT 1').fetchone()
            if not raw:
                continue
            record = json.loads(raw[0])
            sample = {'asset_id': record['asset_id']}
            for name, call in (
                ('source', lambda: source_check(scoped, record)),
                ('inspection', lambda: inspection_input(scoped, record)[3]),
                ('caption', lambda: caption_input(scoped, record)),
                ('description', lambda: description_input(scoped, record)[1]),
            ):
                try:
                    sample[name] = {'fingerprint': call()}
                except (OSError, ValueError, KeyError) as exc:
                    sample[name] = {'retained_unavailable': str(exc)}
            samples[key] = sample
            corrections = scoped.output_path('data', 'captions/corrections')
            if corrections.is_dir():
                for path in corrections.glob('*.json'):
                    files[str(path)] = sha(path)
    for relative in ('data/library/sources.json', 'data/library/settings.json',
                     'data/library/asset-sources.json', 'data/library/notifications.json'):
        path = root / relative
        if path.is_file():
            files[str(path)] = sha(path)
    return {'files': files, 'samples': samples, 'counts': counts}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.environ['LAL_HASH_CACHE'] = str(root / 'scratch/asset-foundation/file-hashes.sqlite')
    current = capture(root)
    if args.verify:
        before = json.loads(args.baseline.read_text(encoding='utf-8'))
        differences = [key for key in current if current[key] != before[key]]
        report = {'status': 'failed' if differences else 'passed', 'differences': differences,
                  'checked_files': len(current['files']), 'samples': current['samples'], 'counts': current['counts']}
        report['baseline_samples_preserved'] = all(current['samples'].get(k) == v for k, v in before['samples'].items())
        report['baseline_counts_preserved'] = all(current['counts'].get(k) == v for k, v in before['counts'].items())
        report['changed_baseline_files'] = [
            {'path': path, 'before': digest, 'after': sha(Path(path)) if Path(path).is_file() else None}
            for path, digest in before['files'].items()
            if not Path(path).is_file() or sha(Path(path)) != digest]
        report['added_scopes'] = sorted(set(current['counts']) - set(before['counts']))
        if args.output:
            if args.output.exists():
                raise SystemExit('Refuse to replace existing evidence')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        raise SystemExit(bool(differences))
    if args.baseline.exists():
        raise SystemExit('Refuse to replace existing baseline')
    args.baseline.parent.mkdir(parents=True, exist_ok=True)
    args.baseline.write_text(json.dumps(current, indent=2), encoding='utf-8')
    print(json.dumps({'baseline': str(args.baseline), 'checked_files': len(current['files']), 'counts': current['counts']}))
