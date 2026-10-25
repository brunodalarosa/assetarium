"""Read-only proof that refactors keep finished work valid: pending counts and fingerprints per source.

Runs dry-run stage previews (no processing, no models) on every registered source and
records pending counts, pending-ID digests and the caption fingerprint of every
completed description. Compare two outputs with --compare; any difference is a fault.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.catalog import digest, encoded
from local_asset_library.config import load_project_config


def snapshot(config):
    from local_asset_library.incremental import caption_input, process, records, working
    from local_asset_library.sources import bound, registry
    result = {}
    for source in registry(config)['sources']:
        scoped = bound(config, source)
        entry = {'enabled': source['enabled']}
        for stage in ('inspection', 'caption', 'embeddings'):
            try:
                report = process(scoped, stage, limit=1000, dry_run=True)
                entry[stage] = {'pending': report.get('pending'), 'ids': digest(sorted(report.get('pending_ids') or []))}
            except Exception as exc:
                entry[stage] = {'fault': f'{type(exc).__name__}: {exc}'}
        fingerprints = {}
        for record in records(working(scoped)):
            if record['processing'].get('caption') == 'complete':
                recorded = (record.get('caption_provenance') or {}).get('fingerprint')
                try:
                    fingerprints[record['asset_id']] = [recorded, caption_input(working(scoped), record, recorded=recorded)]
                except Exception as exc:
                    fingerprints[record['asset_id']] = [recorded, f'{type(exc).__name__}: {exc}']
        entry['captions'] = {'complete': len(fingerprints), 'digest': digest(fingerprints),
                             'unchanged': sum(a == b for a, b in fingerprints.values())}
        result[source['key']] = entry
    return result


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True, help='New file name under data/engines/')
parser.add_argument('--compare', help='Earlier output under data/engines/ to compare with')
args = parser.parse_args()
target = ROOT / 'data/engines' / args.output
if target.exists():
    sys.exit('Output exists; choose a new name (existing outputs are evidence)')
config = load_project_config(ROOT)
value = {'snapshot': snapshot(config)}
if args.compare:
    before = json.loads((ROOT / 'data/engines' / args.compare).read_text(encoding='utf-8'))['snapshot']
    value['compared_with'] = args.compare
    value['differences'] = [key for key in sorted(set(before) | set(value['snapshot']))
                            if before.get(key) != value['snapshot'].get(key)]
    value['status'] = 'faulty' if value['differences'] else 'passed'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(encoded(value) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in value.items() if k != 'snapshot'} or {'written': str(target)}))
for key, entry in value['snapshot'].items():
    print(key, {s: entry[s].get('pending', entry[s].get('fault')) for s in ('inspection', 'caption', 'embeddings')}, entry['captions'])
