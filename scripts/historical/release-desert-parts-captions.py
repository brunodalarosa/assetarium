"""One-time, owner-authorized release of four Desert Pack description failures (October 27, 2026).

Desert Pack failed Grass_L_1, Grass_S_1, Pebble_3 and Rock_8 with "Core visual attributes must not
be empty": one-piece objects listing no parts, which validate_caption now accepts. The owner asked for
one new attempt each. This saves every failure's caption result, ledger row and stage fault under
data/evidence/<run-name>/before/, then checkpoints only those assets' description stage as pending
(the failure rows stay in the ledger history), so the next Generate descriptions makes the attempt
through the normal pipeline. Refuses reruns, a running operation, and any asset whose recorded
failure is not that error.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.catalog import detail
from local_asset_library.config import ConfigError, load_project_config
from local_asset_library.gpu_queue import lease
from local_asset_library.incremental import checkpoint, ledger, update_record, working
from local_asset_library.publication import atomic_json
from local_asset_library.source_operations import active_operation
from local_asset_library.sources import bound, get_source, now

SOURCE = 'Desert Pack'
ASSETS = ('asset_0f40bd571b63d3cb09086aab708d440c', 'asset_71787a292031ad88cf4d67bec42af342',
          'asset_d956b3a7be6e99dfd965e926506e16a7', 'asset_f39f4edafeed65bf75d4145f304f5e01')
ERROR = 'Core visual attributes must not be empty'
AUTHORIZATION = ('Owner approved one new attempt for each Desert Pack description that failed only because a '
                 'one-piece object listed no parts (October 27, 2026); previous evidence retained.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run-name', required=True)
    args = parser.parse_args()
    config = load_project_config(ROOT)
    scoped = bound(config, get_source(config, SOURCE))
    work = working(scoped)
    out = config.output_path('data', 'evidence/' + args.run_name)
    if out.exists():
        raise SystemExit(f'Run already exists; this release never reruns: {out}')
    if active_operation(config):
        raise SystemExit('An operation is running; release the failures when it finishes')
    released = []
    with lease(config, 'batch-source-caption', timeout=5), closing(ledger(scoped)) as db:
        rows = {}
        for identifier in ASSETS:
            record = detail(work, identifier)
            row = db.execute("SELECT fingerprint,status,evidence,updated FROM jobs WHERE asset_id=? AND stage='caption'",
                             (identifier,)).fetchone()
            evidence = json.loads(row[2]) if row else {}
            errors = {a.get('error') for a in evidence.get('attempts', [])}
            if record['processing'].get('caption') != 'failed' or not row or row[1] != 'failed' or errors != {ERROR}:
                raise ConfigError(f'{identifier} is not a recorded "{ERROR}" failure; nothing was released')
            rows[identifier] = (record, row)
        for identifier, (record, row) in rows.items():
            before = out / 'before' / identifier
            before.mkdir(parents=True)
            for path in sorted(work.output_path('data', f'captions/library/{identifier}').glob('*.json')):
                shutil.copy2(path, before / path.name)
            atomic_json(before / 'ledger.json', {'fingerprint': row[0], 'status': row[1], 'evidence': json.loads(row[2]),
                                                 'updated': row[3], 'stage_fault': record.get('stage_faults', {}).get('caption')})
            checkpoint(db, identifier, 'caption', row[0], 'pending',
                       {'released': True, 'authorization': AUTHORIZATION, 'previous_evidence': str(before), 'utc': now()})
            record['processing']['caption'] = 'pending'
            record.get('stage_faults', {}).pop('caption', None)
            update_record(work, record)
            released.append({'asset_id': identifier, 'name': record['display_name'], 'fingerprint': row[0]})
            print('Released', record['display_name'], flush=True)
    atomic_json(out / 'receipt.json', {'source': SOURCE, 'authorization': AUTHORIZATION, 'error': ERROR,
                                       'released': released, 'utc': now(),
                                       'next': f'local-assets describe --asset-source "{SOURCE}"'})
    print(f'Released {len(released)}; run Generate descriptions for {SOURCE}. Receipt: {out / "receipt.json"}')


if __name__ == '__main__':
    main()
