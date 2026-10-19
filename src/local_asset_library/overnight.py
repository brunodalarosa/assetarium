"""Owner-started caption retries, durable per-asset attempts and morning reports.

No inference imports occur during planning. Completed attempts, including faults,
are never repeated when resuming the same run. Each fresh run is an explicit
owner request to retry its selected caption faults.
"""
from contextlib import closing, contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

from .catalog import detail, digest, encoded, save_json
from .caption_quality import caption_quality
from .captions import file_hash, image_inputs, infer_captions, publish as publish_caption
from .config import ConfigError
from .incremental import (CAPTION_PROMPT_VERSION, caption_input, checkpoint, ledger,
                          policy, stage_content, update_record, working)
from .membership import membership, records
from .publication import atomic_json, read_json
from .retrieval import source_check
from .settings import processing_formats, processing_eligible

RUN_ROOT = 'overnight-descriptions'
TERMINAL = {'complete', 'failed', 'skipped'}


def utc():
    return datetime.now(timezone.utc).isoformat()


def run_path(config, identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{32}', identifier):
        raise ConfigError('Invalid overnight run ID')
    return config.output_path('data', f'{RUN_ROOT}/{identifier}')


def usable(record, config):
    description = record.get('description')
    return (isinstance(description, dict) and isinstance(description.get('description'), str)
            and bool(description['description'].strip()) and not caption_quality(config, record)['caption_faulty'])


def contract(config):
    files = [f'prompts/caption-{CAPTION_PROMPT_VERSION}.txt', 'docs/caption-model.json',
             'src/local_asset_library/caption_backend.py', 'src/local_asset_library/captions.py',
             'src/local_asset_library/overnight.py', 'src/local_asset_library/incremental.py',
             'scripts/overnight-descriptions.py', 'config.example.toml', 'src/local_asset_library/embedding_backend.py',
             'src/local_asset_library/library_index.py', 'runtime/caption/uv.lock', 'runtime/embedding/uv.lock',
             'docs/embedding-model.json', 'docs/library-membership.json']
    return {name: file_hash(config.project_root / name) for name in files}


def plan(config, packs=None, pending_only=False, peak_reserve_mib=500, asset_ids=None):
    work = working(config)
    all_records = records(work)
    formats = processing_formats(config)
    if packs and set(packs) - {r['pack_id'] for r in all_records}:
        raise ConfigError('Description selection contains an unknown pack')
    if asset_ids is not None and set(asset_ids) - {r['asset_id'] for r in all_records}:
        raise ConfigError('Description selection contains an unknown asset ID')
    selected = [r for r in all_records if not usable(r, work)
                and processing_eligible(r, formats)
                and (not packs or r['pack_id'] in packs)
                and (not pending_only or r['processing']['caption'] == 'pending')
                and (asset_ids is None or r['asset_id'] in asset_ids)]
    faults = []
    for r in selected:
        try:
            source_check(work, r)
            image_inputs(work, r)
        except (OSError, ValueError, KeyError) as exc:
            faults.append({'asset_id': r['asset_id'], 'reason': str(exc)})
    return {'selected': len(selected), 'skipped_usable': sum(usable(r, work) for r in all_records),
            'skipped_out_of_scope': len(all_records) - len(selected) - sum(usable(r, work) for r in all_records),
            'packs': sorted(set(packs or [])), 'pending_only': pending_only,
            'asset_ids': sorted(set(asset_ids)) if asset_ids is not None else None,
            'prompt_version': CAPTION_PROMPT_VERSION, 'description_words': [10, 170],
            'targets': [{'asset_id': r['asset_id'], 'name': r['display_name'], 'pack': r['pack_id'],
                         'previous_state': r['processing']['caption']} for r in selected],
            'input_faults': faults, 'model_inference_performed': False,
            'estimated_hours': [round(len(selected) * 12 / 3600, 2), round(len(selected) * 24 / 3600, 2)],
            'peak_additional_bytes': peak_reserve_mib * 1024**2}


def image_rows(config):
    path = working(config).output_path('data', 'embeddings/index.sqlite')
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        return {r[0]: digest([hashlib.sha256(v).hexdigest() if isinstance(v, bytes) else v for v in r])
                for r in db.execute("SELECT * FROM vectors WHERE channel='image'")}


def protected(config, targets):
    work = working(config)
    return {'usable_records': {r['asset_id']: digest(r) for r in records(work) if r['asset_id'] not in targets},
            'corrections': {str(p.relative_to(config.project_root)): file_hash(p)
                            for p in config.output_path('data', 'captions/corrections').glob('*.json')},
            'image_vectors': image_rows(config)}


def create_run(config, packs=None, pending_only=False, peak_reserve_mib=500, asset_ids=None):
    description = plan(config, packs, pending_only, peak_reserve_mib, asset_ids)
    identifier = uuid.uuid4().hex
    path = run_path(config, identifier)
    path.mkdir(parents=True, exist_ok=False)
    ids = {r['asset_id'] for r in description['targets']}
    value = {'schema_version': 1, 'run_id': identifier, 'created_utc': utc(),
             'membership_fingerprint': membership(working(config))['fingerprint'],
             'contracts': contract(config), 'plan': description,
             'authorization': ('Owner requested pending descriptions only; existing caption faults are retained.' if pending_only
                               else 'Owner manually started a run to generate missing descriptions and retry actual caption faults once.')}
    save_json(path / 'plan.json', value)
    save_json(path / 'protected-before.json', protected(config, ids))
    for r in records(working(config)):
        if r['asset_id'] in ids:
            save_json(path / 'original-records' / (r['asset_id'] + '.json'), r)
    atomic_json(path / 'state.json', {'status': 'ready', 'phase': 'caption', 'created_utc': utc()})
    latest(config, identifier)
    return identifier


def check_run(config, identifier):
    path = run_path(config, identifier)
    value = read_json(path / 'plan.json')
    if value['contracts'] != contract(config):
        raise ConfigError('Run code/prompt/model contracts changed; retain this run and explicitly start a new run.')
    if value['membership_fingerprint'] != membership(working(config))['fingerprint']:
        raise ConfigError('Catalog membership changed; retain this run and explicitly start a new run.')
    return value


def outcomes(config, identifier):
    path = run_path(config, identifier)
    return {p.stem: read_json(p) for p in (path / 'outcomes').glob('*.json')}


def remaining(config, identifier):
    value = check_run(config, identifier)
    done = outcomes(config, identifier)
    return [r for r in value['plan']['targets'] if r['asset_id'] not in done]


def progress(config, identifier, phase, current=None, status='running', **extra):
    value = {'status': status, 'phase': phase, 'pid': os.getpid(), 'utc': utc(),
             'worker_token': os.environ.get('OVERNIGHT_WORKER_TOKEN'),
             'current': current, **extra}
    atomic_json(run_path(config, identifier) / 'worker-progress.json', value)
    atomic_json(config.output_path('data', 'library/processing-status.json'),
                {**value, 'stage': phase, 'run_id': identifier})


def latest(config, identifier):
    state = read_json(run_path(config, identifier) / 'state.json')
    atomic_json(config.output_path('data', f'{RUN_ROOT}/latest.json'),
                {'run_id': identifier, 'status': state['status'], 'phase': state['phase'],
                 'report': f'data/{RUN_ROOT}/{identifier}/summary.md', 'updated_utc': utc()})


def set_state(config, identifier, **changes):
    path = run_path(config, identifier) / 'state.json'
    value = read_json(path)
    value.update(changes, updated_utc=utc())
    atomic_json(path, value)
    latest(config, identifier)


def persist(config, identifier, record, outcome, provenance):
    """Save new evidence before changing working metadata; never replace old logs."""
    path = run_path(config, identifier)
    asset_id = record['asset_id']
    raw_path = path / 'attempts' / (asset_id + '.json')
    if raw_path.exists():
        raise ConfigError('Attempt evidence already exists; recovery must not generate again')
    save_json(raw_path, {'asset_id': asset_id, **outcome, 'provenance': provenance})
    return apply_saved(config, identifier, asset_id)


def apply_saved(config, identifier, asset_id):
    """Recover a completed saved response/publication without model inference."""
    work = working(config)
    path = run_path(config, identifier)
    result_path = path / 'outcomes' / (asset_id + '.json')
    if result_path.exists():
        return read_json(result_path)
    raw_path = path / 'attempts' / (asset_id + '.json')
    saved = read_json(raw_path)
    record = detail(work, asset_id)
    provenance = saved['provenance']
    relative = ('data/' + raw_path.relative_to(config.metadata_root).as_posix() if config.metadata_root
                else raw_path.relative_to(config.project_root).as_posix())
    provenance = {**provenance, 'result_path': relative}
    status = saved['status']
    errors = [a.get('error') for a in saved.get('attempts', []) if a.get('error')]
    try:
        # A killed worker may have saved a valid response before committing it.
        # Recheck the exact input contract instead of silently adopting stale text.
        current = caption_input(work, record, prompt_version=CAPTION_PROMPT_VERSION, recorded=provenance.get('fingerprint'))
        if provenance.get('fingerprint') != current:
            raise ConfigError('Saved response input changed before publication')
        if status == 'complete':
            source_check(work, record)
            image_inputs(work, record)
        updated = publish_caption(work, asset_id, saved, provenance)
        if status == 'complete' and 'caption' in updated.get('stage_faults', {}):
            updated['stage_faults'].pop('caption')
            update_record(work, updated)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        status = 'failed'
        errors.append(f'Publication/input error: {exc}')
        record['processing']['caption'] = 'failed'
        record.setdefault('stage_faults', {})['caption'] = {'error': str(exc), 'result_path': relative,
                                                          'run_id': identifier, 'raw_response_retained': True}
        update_record(work, record)
    receipt = {'asset_id': asset_id, 'status': status, 'result_path': relative,
               'errors': errors, 'finished_utc': utc(), 'model_attempts': len(saved.get('attempts', []))}
    with closing(ledger(config)) as db:
        checkpoint(db, asset_id, 'caption', provenance['fingerprint'], status,
                   {**receipt, 'explicit_caption_retry': True, 'fault_content': stage_content(work, detail(work, asset_id), 'caption')})
    atomic_json(result_path, receipt)
    return receipt


def record_fault(config, identifier, asset_id, reason, kind):
    path = run_path(config, identifier)
    if (path / 'outcomes' / (asset_id + '.json')).exists():
        return read_json(path / 'outcomes' / (asset_id + '.json'))
    if (path / 'attempts' / (asset_id + '.json')).exists():
        return apply_saved(config, identifier, asset_id)
    record = detail(working(config), asset_id)
    fp = caption_input(working(config), record, prompt_version=CAPTION_PROMPT_VERSION)
    provenance = {'fingerprint': fp, 'run_id': identifier, 'prompt_version': CAPTION_PROMPT_VERSION,
                  'ai_review': 'pending', 'owner_caption_review': 'pending', 'owner_artistic_suitability': 'pending'}
    return persist(config, identifier, record,
                   {'status': 'failed', 'description': None, 'suggested_uses': [],
                    'attempts': [{'status': kind, 'error': reason}]}, provenance)


def caption_batch(config, identifier, backend_factory, limit=25):
    from .caption_batching import GpuMemoryError, MODE
    from .settings import caption_batch_size
    path = run_path(config, identifier)
    work = working(config)
    tasks = remaining(config, identifier)[:limit]
    backend = None
    size = caption_batch_size(config)
    prompt_path = config.project_root / f'prompts/caption-{CAPTION_PROMPT_VERSION}.txt'
    prompt = prompt_path.read_text(encoding='utf-8')
    progress(config, identifier, 'caption', status='starting')

    def generate(ready):
        nonlocal backend
        if backend is None:
            progress(config, identifier, 'caption', status='loading_model', current=None)
            backend = backend_factory(work)
        progress(config, identifier, 'caption', current=ready[0][0], completed=len(outcomes(config, identifier)))
        # This intent precedes generation, so an interrupted batch is not
        # automatically repeated when the owner resumes the same run.
        atomic_json(path / 'inflight.json', {'asset_ids': [t['asset_id'] for t, _, _, _ in ready], 'started_utc': utc(),
                                             'fingerprints': {t['asset_id']: fp for t, _, _, fp in ready}})
        try:
            results = infer_captions(backend, [inputs for _, _, inputs, _ in ready], prompt, batch_size=size)
        except GpuMemoryError:
            # Out of GPU memory generated nothing: these assets stay pending in this run.
            (path / 'inflight.json').unlink()
            raise
        for position, ((_, record, inputs, fp), outcome) in enumerate(zip(ready, results)):
            provenance = {'fingerprint': fp, 'run_id': identifier, 'model': backend.contract,
                          'settings': backend.settings, 'prompt_version': CAPTION_PROMPT_VERSION,
                          'prompt_sha256': file_hash(prompt_path), 'input_views': inputs,
                          'generation_mode': MODE, 'batch': {'size': size, 'assets': len(ready), 'position': position},
                          'attempts': outcome['attempts'], 'ai_review': 'pending',
                          'owner_caption_review': 'pending', 'owner_artistic_suitability': 'pending'}
            persist(config, identifier, record, outcome, provenance)
        (path / 'inflight.json').unlink()
        return any(a.get('status') == 'inference_failed' for o in results for a in o['attempts'])

    try:
        ready = []
        for task in tasks:
            asset_id = task['asset_id']
            progress(config, identifier, 'caption', current=task, completed=len(outcomes(config, identifier)))
            if (path / 'attempts' / (asset_id + '.json')).exists():
                apply_saved(config, identifier, asset_id)
                continue
            record = detail(work, asset_id)
            if not processing_eligible(record, processing_formats(config)):
                atomic_json(path / 'outcomes' / (asset_id + '.json'),
                            {'asset_id': asset_id, 'status': 'skipped', 'reason': 'Source format is disabled in Settings → General', 'finished_utc': utc()})
                continue
            if usable(record, work):
                atomic_json(path / 'outcomes' / (asset_id + '.json'),
                            {'asset_id': asset_id, 'status': 'skipped', 'reason': 'Usable caption appeared after selection', 'finished_utc': utc()})
                continue
            try:
                source_check(work, record)
                inputs = image_inputs(work, record)
                fp = caption_input(work, record, prompt_version=CAPTION_PROMPT_VERSION)
            except (OSError, ValueError, KeyError) as exc:
                record_fault(config, identifier, asset_id, str(exc), 'input_failed')
                continue
            ready.append((task, record, inputs, fp))
            if len(ready) == size:
                failed, ready = generate(ready), []
                if failed:
                    break  # Fresh owned worker for the NEXT batch, never a retry.
        else:
            if ready:
                generate(ready)
        progress(config, identifier, 'caption', status='batch_complete', completed=len(outcomes(config, identifier)))
    finally:
        if backend is not None:
            backend.close()


def recover_inflight(config, identifier):
    path = run_path(config, identifier) / 'inflight.json'
    if path.exists():
        value = read_json(path)
        for asset_id in value.get('asset_ids') or [value['asset_id']]:
            record_fault(config, identifier, asset_id,
                         'Generation was interrupted; this run will not repeat the attempt.', 'interrupted')
        path.unlink()


def verify_protected(config, identifier):
    original = read_json(run_path(config, identifier) / 'protected-before.json')
    target_ids = {r['asset_id'] for r in check_run(config, identifier)['plan']['targets']}
    now = protected(config, target_ids)
    changed = {}
    for category, values in original.items():
        changed[category] = [key for key, value in values.items() if now[category].get(key) != value]
        if category == 'image_vectors':
            changed[category] += sorted(set(now[category]) - set(values))
    receipt = {'status': 'passed' if not any(changed.values()) else 'faulty', 'changes': changed, 'utc': utc()}
    atomic_json(run_path(config, identifier) / 'preservation.json', receipt)
    if receipt['status'] != 'passed':
        raise ConfigError('Protected caption/correction/image data changed; publication blocked. See preservation.json.')
    return receipt


def summary(config, identifier):
    path = run_path(config, identifier)
    value = read_json(path / 'plan.json')
    state = read_json(path / 'state.json')
    done = outcomes(config, identifier)
    counts = {s: sum(r['status'] == s for r in done.values()) for s in TERMINAL}
    new_vectors, vector_failures, retained_failures = set(), {}, set()
    for receipt in sorted(path.glob('index-*.json'), key=lambda p: p.stat().st_mtime_ns):
        for item in read_json(receipt).get('outcomes', []):
            if item.get('channel') != 'description':
                continue
            if item.get('status') == 'failed':
                if not item.get('reused') or item.get('corrupt_output'):
                    vector_failures[item['asset_id']] = item
                else:
                    retained_failures.add(item['asset_id'])
            elif item.get('status') == 'complete' and not item.get('reused'):
                new_vectors.add(item['asset_id'])
    report = {'run_id': identifier, 'status': state['status'], 'phase': state['phase'],
              'selected': value['plan']['selected'], 'results': counts,
              'not_attempted': value['plan']['selected'] - len(done), 'state': state,
              'failures': [r for r in done.values() if r['status'] == 'failed'],
              'description_index': {'new_vectors': len(new_vectors - set(vector_failures)),
                                    'new_failed': len(vector_failures), 'failures': list(vector_failures.values()),
                                    'retained_failed': len(retained_failures - set(vector_failures))},
              'worker_faults': [read_json(p) for p in path.glob('worker-fault-*.json')],
              'owner_accuracy_review': 'pending', 'updated_utc': utc()}
    atomic_json(path / 'summary.json', report)
    lines = ['# Overnight description results', '', f"Run: `{identifier}`", '',
             f"Status: **{state['status']}**; stage: **{state['phase']}**.", '',
             f"Selected: {report['selected']}; completed: {counts['complete']}; failed: {counts['failed']}; skipped: {counts['skipped']}; not attempted: {report['not_attempted']}.", '',
             f"New description-search vectors: {report['description_index']['new_vectors']}; new indexing faults: {len(vector_failures)}; retained index faults: {report['description_index']['retained_failed']}.", '',
             f"Worker interruptions/timeouts: {len(report['worker_faults'])}. See `worker-fault-*.json` and corresponding logs.", '',
             'New captions used the local model and 10–170-word prompt. Accuracy review remains pending.', '',
             'Original attempts, rendered images and owner corrections are retained. Detailed results are in `summary.json`, `attempts/`, `outcomes/` and worker logs.', '']
    if state.get('error'):
        lines += [f"Run error: {state['error']}", '']
    if state.get('generation'):
        lines += [f"Published catalog: `{state['generation']}`.", '']
    if report['failures']:
        lines += ['## Caption failures', '']
        for receipt in report['failures']:
            task = next(r for r in value['plan']['targets'] if r['asset_id'] == receipt['asset_id'])
            lines.append(f"- {task['pack']} / {task['name']}: {'; '.join(receipt.get('errors', []))}. Log: `{receipt.get('result_path')}`")
    if vector_failures:
        lines += ['', '## Description-search faults', '']
        lines.extend(f"- `{item['asset_id']}`: {item.get('error', 'Indexing failure')}. See `index-*.json` for full evidence."
                     for item in vector_failures.values())
    atomic_text(path / 'summary.md', '\n'.join(lines) + '\n')
    latest(config, identifier)
    return report


def atomic_text(path, text):
    temp = path.with_suffix('.md.pending')
    temp.write_text(text, encoding='utf-8')
    os.replace(temp, path)


@contextmanager
def keep_awake():
    if os.name != 'nt':
        yield
        return
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.SetThreadExecutionState.argtypes = [ctypes.c_uint]
    kernel.SetThreadExecutionState.restype = ctypes.c_uint
    if not kernel.SetThreadExecutionState(0x80000001):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        kernel.SetThreadExecutionState(0x80000000)
