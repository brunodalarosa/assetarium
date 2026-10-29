"""One-time, owner-authorized revalidation of 35 saved description outputs (October 28, 2026).

The October 27 description run rejected 35 complete, accurate descriptions on wording alone: 15 Viking
boats in Medieval Megapack for the ship's "rigging" (read as a character rig), and 20 assets for use
wording such as "designed for use in games". validate_caption now accepts both; use wording becomes a
review note. The owner approved accepting the saved model outputs without running the model again.

For each recorded failure with only those errors, this saves the result file, ledger row and stage fault
under data/evidence/<run-name>/before/, checks the saved output with the current validator and, if it
passes with an unchanged fingerprint, records it as complete with a `revalidation` provenance entry. The
original failed attempt stays in the result and in the ledger history; an output that still fails stays
failed and is listed. Refuses reruns, a running operation, and unexpected failure counts. Process assets
afterwards adds the search data and publishes.
"""
import argparse
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.captions import file_hash, parse_caption, publish, use_notes
from local_asset_library.catalog import detail, save_json
from local_asset_library.config import ConfigError, load_project_config
from local_asset_library.gpu_queue import lease
from local_asset_library.incremental import caption_input, checkpoint, ledger, stage_content, update_record, working
from local_asset_library.publication import atomic_json
from local_asset_library.source_operations import active_operation
from local_asset_library.sources import bound, get_source, now

EXPECTED = {'Low Poly Nature - Extended': 10, 'Medieval Megapack - Low Poly': 22,
            'Medieval Props - Small Pack Low Poly': 3}
ERRORS = {'Measured technical claim in visual observations', 'Suggested use in visual observations'}
AUTHORIZATION = ('Owner approved accepting the saved description outputs rejected only for ship rigging or use '
                 'wording, without running the model again (October 28, 2026); previous evidence retained.')


def failures(work, db):
    found = []
    for identifier, fingerprint, status, evidence, updated in db.execute(
            "SELECT asset_id,fingerprint,status,evidence,updated FROM jobs WHERE stage='caption' AND status='failed'"):
        evidence = json.loads(evidence)
        errors = {a.get('error') for a in evidence.get('attempts', [])}
        if errors and errors <= ERRORS:
            record = detail(work, identifier)
            if record['processing'].get('caption') != 'failed':
                raise ConfigError(f'{identifier} is failed in the ledger but not in the catalog; nothing was changed')
            found.append((record, (fingerprint, status, evidence, updated)))
    return found


def revalidate(work, record, row):
    """The accepted outcome and provenance, or the reason it stays failed. Writes nothing."""
    fingerprint, _, evidence, _ = row
    path = work.output_path('data', f"captions/library/{record['asset_id']}/{fingerprint}.json")
    saved = json.loads(path.read_text(encoding='utf-8'))
    if saved.get('status') != 'failed' or saved['attempts'] != evidence['attempts']:
        return path, None, None, 'Saved result does not match the ledger failure'
    try:
        caption = parse_caption(saved['attempts'][-1]['raw'])
    except (ValueError, TypeError) as exc:
        return path, None, None, f'Still rejected: {exc}'
    uses = caption.pop('suggested_uses')
    outcome = {'status': 'complete', 'description': caption, 'suggested_uses': uses, 'attempts': saved['attempts']}
    notes = use_notes(caption)
    provenance = {**({'validation_notes': notes} if notes else {}), **saved['provenance'],
                  'revalidation': {'utc': now(), 'authorization': AUTHORIZATION,
                                   'previous_error': saved['attempts'][-1]['error'],
                                   'validator_sha256': file_hash(ROOT / 'src/local_asset_library/captions.py')}}
    candidate = deepcopy(record)
    candidate['processing']['caption'] = 'complete'
    candidate['caption_provenance'] = provenance
    if caption_input(work, candidate) != fingerprint:
        return path, None, None, 'Fingerprint changed since the run (model, prompt or images); a new run is needed'
    return path, outcome, provenance, None


def run(config, out, dry_run=False):
    if out.exists():
        raise SystemExit(f'Run already exists; this revalidation never reruns: {out}')
    if active_operation(config):
        raise SystemExit('An operation is running; revalidate when it finishes')
    receipt = {'authorization': AUTHORIZATION, 'errors': sorted(ERRORS), 'dry_run': dry_run, 'sources': {}}
    with lease(config, 'batch-source-caption', timeout=5):
        scoped = {key: bound(config, get_source(config, key)) for key in EXPECTED}
        for key, expected in EXPECTED.items():  # Every count is checked before anything is written.
            with closing(ledger(scoped[key])) as db:
                if len(found := failures(working(scoped[key]), db)) != expected:
                    raise ConfigError(f'{key}: expected {expected} recorded wording failures, found {len(found)}; nothing was changed')
        for key in EXPECTED:
            work = working(scoped[key])
            with closing(ledger(scoped[key])) as db:
                accepted, kept = [], []
                for record, row in failures(work, db):
                    identifier, name = record['asset_id'], record['display_name']
                    path, outcome, provenance, reason = revalidate(work, record, row)
                    if reason:
                        kept.append({'asset_id': identifier, 'name': name, 'reason': reason})
                        print(f'Kept failed: {key} / {name}: {reason}', flush=True)
                        continue
                    accepted.append({'asset_id': identifier, 'name': name, 'fingerprint': row[0],
                                     'previous_error': provenance['revalidation']['previous_error'],
                                     'review_notes': len(provenance.get('validation_notes', []))})
                    print(f"{'Would accept' if dry_run else 'Accepted'}: {key} / {name}", flush=True)
                    if dry_run:
                        continue
                    before = out / 'before' / key / identifier
                    before.mkdir(parents=True)
                    shutil.copy2(path, before / path.name)
                    atomic_json(before / 'ledger.json', {'fingerprint': row[0], 'status': row[1], 'evidence': row[2],
                                                         'updated': row[3], 'stage_fault': record.get('stage_faults', {}).get('caption')})
                    save_json(path, {'asset_id': identifier, **outcome, 'provenance': provenance})
                    publish(work, identifier, outcome, provenance)
                    updated = detail(work, identifier)
                    updated.get('stage_faults', {}).pop('caption', None)
                    update_record(work, updated)  # Prior failures remain in the append-only stage history.
                    checkpoint(db, identifier, 'caption', row[0], 'complete',
                               {'status': 'complete', 'result_path': f'data/captions/library/{identifier}/{row[0]}.json',
                                'attempts': outcome['attempts'], 'revalidation': provenance['revalidation'],
                                'previous_evidence': str(before), 'fault_content': stage_content(work, updated, 'caption')})
                receipt['sources'][key] = {'accepted': accepted, 'kept_failed': kept}
    if not dry_run:
        receipt.update(utc=now(), next='local-assets process --asset-source KEY for each source (search data, then publish)')
        atomic_json(out / 'receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--dry-run', action='store_true', help='Report what would be accepted; write nothing')
    args = parser.parse_args()
    config = load_project_config(ROOT)
    out = config.output_path('data', 'evidence/' + args.run_name)
    receipt = run(config, out, args.dry_run)
    print(json.dumps({k: {'accepted': len(v['accepted']), 'kept_failed': v['kept_failed']}
                      for k, v in receipt['sources'].items()}, indent=2))
    if not args.dry_run:
        print(f'Run Process assets for each source. Receipt: {out / "receipt.json"}')


if __name__ == '__main__':
    main()
