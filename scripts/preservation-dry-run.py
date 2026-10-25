"""Read-only stage dry runs for every registered source, for before/after code comparison.

Run once with the original code on PYTHONPATH and once with the current code, both
against the same live project data; compare the two JSON outputs. Nothing is
processed or written except the output file.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default=str(ROOT))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    from local_asset_library import sources
    from local_asset_library.config import load_project_config
    from local_asset_library.incremental import process, working
    from local_asset_library.library_index import index_library
    config = load_project_config(Path(args.project))
    result = {'code': str(Path(sources.__file__).parent), 'sources': {}}
    for source in sources.registry(config)['sources']:
        scoped = sources.bound(config, source)
        row = {}
        for stage in ('inspection', 'caption'):
            try:
                report = process(scoped, stage, limit=1000, dry_run=True)
                row[stage] = {'pending': report['pending'], 'retained': report['retained'], 'pending_ids': sorted(report['pending_ids'])}
            except Exception as exc:
                row[stage] = {'error': f'{type(exc).__name__}: {exc}'}
        try:
            report = index_library(working(scoped), None, 1000, dry_run=True)
            row['embeddings'] = {'pending': report['pending'], 'deferred': report['deferred_descriptions'],
                                 'outcomes': sorted((o['asset_id'], o['channel'], o['status'], bool(o.get('reused'))) for o in report['outcomes'])}
        except Exception as exc:
            row['embeddings'] = {'error': f'{type(exc).__name__}: {exc}'}
        result['sources'][source['key']] = row
    Path(args.output).write_text(json.dumps(result, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: {s: v.get('pending') for s, v in row.items()} for k, row in result['sources'].items()}))


if __name__ == '__main__':
    main()
