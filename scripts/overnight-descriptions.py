"""Manual overnight coordinator and private prepared-runtime workers."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.config import load_config, ConfigError
from local_asset_library.gpu_queue import lease, process_alive
from local_asset_library.incremental import working, publish, policy
from local_asset_library.library_index import index_library
from local_asset_library.overnight import (RUN_ROOT, plan, run_path, create_run, check_run,
    caption_batch, record_fault, recover_inflight, remaining, outcomes, progress,
    set_state, summary, verify_protected, keep_awake, utc)
from local_asset_library.publication import atomic_json, read_json


def stop_owned(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        # The root PID is from our live Popen handle, not a user-supplied PID.
        # Include only descendants of that owned wrapper/runtime process.
        result = subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode and process.poll() is None:
            raise RuntimeError('Could not stop the owned worker; no further worker will be started')
    else:
        process.kill()
    process.wait(timeout=20)


def assert_worker_stopped(config, identifier):
    path = run_path(config, identifier)
    owner = path / 'worker-owner.json'
    if not owner.exists():
        return
    value = read_json(owner)
    live = process_alive(value.get('pid'))
    heartbeat = path / 'worker-progress.json'
    if heartbeat.exists():
        child = read_json(heartbeat)
        if child.get('worker_token') == value.get('token'):
            live = live or process_alive(child.get('pid'))
    if live:
        raise ConfigError('An earlier owned worker is still running. Let its current batch finish before resuming; no process was stopped.')


def supervise(config, identifier, command, phase, timeout=180):
    path = run_path(config, identifier)
    token = uuid.uuid4().hex
    log = path / f'worker-{phase}-{token}.log'
    env = os.environ.copy()
    env.update(OVERNIGHT_WORKER_TOKEN=token, PYTHONUNBUFFERED='1', PYTHONUTF8='1',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    last_key, last_change, active, last_completed = None, time.monotonic(), None, -1
    fault_path = path / ('worker-fault-' + token[:12] + '.json')
    with log.open('x', encoding='utf-8') as stream:
        process = subprocess.Popen(command, cwd=config.project_root, env=env, stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        owner_path = path / 'worker-owner.json'
        atomic_json(owner_path, {'pid': process.pid, 'token': token, 'phase': phase, 'started_utc': utc()})
        try:
            while process.poll() is None:
                heartbeat = path / 'worker-progress.json'
                if heartbeat.exists():
                    value = read_json(heartbeat)
                    if value.get('worker_token') == token:
                        active = value.get('current')
                        key = (value.get('pid'), value.get('status'), (active or {}).get('asset_id'))
                        if key != last_key:
                            last_key, last_change = key, time.monotonic()
                            if active:
                                print(f"Generating: {active.get('pack', '')} / {active.get('name', '')}", flush=True)
                        if phase == 'embeddings':
                            global_path = config.output_path('data', 'library/processing-status.json')
                            if global_path.exists():
                                item = read_json(global_path)
                                count = item.get('completed', 0)
                                if item.get('pid') == value.get('pid') and count != last_completed:
                                    last_completed, last_change = count, time.monotonic()
                                    print(f'Text-search entries processed in this batch: {count}', flush=True)
                if time.monotonic() - last_change > timeout:
                    stop_owned(process)
                    atomic_json(fault_path, {'status':'faulty','phase':phase,'reason':f'Progress deadline exceeded ({timeout} seconds)',
                        'asset_id':(active or {}).get('asset_id'),'worker_root_pid':process.pid,'log':log.name,'utc':utc()})
                    if phase == 'caption' and active and active.get('asset_id'):
                        record_fault(config, identifier, active['asset_id'],
                            f'Owned caption worker exceeded the {timeout}-second progress deadline; log: {log.name}', 'watchdog_timeout')
                        recover_inflight(config, identifier)
                        return {'status': 'asset_timeout', 'log': log.name}
                    raise RuntimeError(f'Owned {phase} worker stalled during startup/indexing; resume is available. Log: {log.name}')
                time.sleep(0.25)
            if process.returncode:
                recover_inflight(config, identifier)
                raise RuntimeError(f'{phase} worker exited with code {process.returncode}; see {log.name}')
            return {'status': 'passed', 'log': log.name}
        except BaseException as exc:
            stop_owned(process)
            if not fault_path.exists():
                atomic_json(fault_path, {'status':'faulty','phase':phase,'reason':f'{type(exc).__name__}: {exc}',
                    'asset_id':(active or {}).get('asset_id'),'worker_root_pid':process.pid,'log':log.name,'utc':utc()})
            raise
        finally:
            if process.poll() is not None:
                owner_path.unlink(missing_ok=True)


def worker_command(config, identifier, stage):
    runtime = 'caption' if stage == 'caption' else 'embedding'
    return ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            str(config.project_root / 'scripts' / (runtime + '-runtime.ps1')),
            'run', '--locked', '--no-sync', '--offline', '--project', str(config.project_root / 'runtime' / runtime),
            'python', str(config.project_root / 'scripts/overnight-descriptions.py'),
            '--worker', stage, '--run-id', identifier]


def storage(config, identifier, label):
    name = f'overnight-{identifier}-{label}-{uuid.uuid4().hex}.json'
    subprocess.run([str(config.project_root / '.venv/Scripts/python.exe'),
        str(config.project_root / 'scripts/storage-report.py'), '--output', name],
        cwd=config.project_root, check=True, stdout=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    receipt = read_json(config.output_path('data', 'storage/' + name))
    if receipt['status'] != 'passed':
        raise ConfigError('Storage measurement has faults; see data/storage/' + name)
    return {'receipt': 'data/storage/' + name, 'allocated_bytes': receipt['totals']['allocated_bytes']}


def budget_check(config, identifier, label):
    measured = storage(config, identifier, label)
    state = read_json(run_path(config, identifier) / 'state.json')
    budget = policy(config)['budget']
    limit = min(check_run(config, identifier)['plan']['peak_additional_bytes'], budget['peak_additional_allocated_bytes'])
    target = run_path(config, identifier) / ('storage-' + uuid.uuid4().hex[:12] + '.json')
    while target.exists():
        target = run_path(config, identifier) / ('storage-' + uuid.uuid4().hex[:12] + '.json')
    atomic_json(target, {**measured, 'stage': label})
    if measured['allocated_bytes'] > budget['total_allocated_bytes'] or measured['allocated_bytes'] - state['baseline_allocated_bytes'] > limit:
        raise ConfigError('Approved storage ceiling exceeded; all work is retained. Resume after reviewing storage.')
    return measured


def worker(config, identifier, stage):
    check_run(config, identifier)
    progress(config, identifier, stage, status='starting')
    with lease(config, 'batch-overnight-' + stage):
        if stage == 'caption':
            from local_asset_library.caption_backend import QwenBackend
            model = json.loads((config.project_root / 'docs/caption-model.json').read_text(encoding='utf-8'))
            caption_batch(config, identifier, lambda work: QwenBackend(work, model))
        else:
            from local_asset_library.embedding_backend import EmbeddingBackend
            progress(config, identifier, stage, status='loading_model')
            backend = EmbeddingBackend(working(config))
            try:
                progress(config, identifier, stage)
                result = index_library(working(config), backend, limit=250, description_only=True)
                atomic_json(run_path(config, identifier) / ('index-' + uuid.uuid4().hex[:12] + '.json'), result)
                progress(config, identifier, stage, status='batch_complete', completed=result['processed'])
            finally:
                backend.model.to('cpu')
                backend.model = None
                import gc
                gc.collect()
                backend.torch.cuda.empty_cache()


def choose_run(config, explicit=None, new=False, packs=None, pending_only=False, peak_reserve_mib=500, asset_ids=None):
    if explicit:
        check_run(config, explicit)
        return explicit
    pointer = config.output_path('data', f'{RUN_ROOT}/latest.json')
    if pointer.exists() and not new:
        value = read_json(pointer)
        if value['status'] not in {'complete', 'complete_with_caption_faults', 'complete_with_faults', 'no_work'}:
            check_run(config, value['run_id'])
            return value['run_id']
    return create_run(config, packs, pending_only, peak_reserve_mib, asset_ids)


def main():
    parser = argparse.ArgumentParser(description='Generate missing/faulty asset descriptions overnight; existing usable captions are skipped.')
    parser.add_argument('--dry-run', action='store_true', help='Save selection and input-check report; no inference or catalog changes')
    parser.add_argument('--new-run', action='store_true', help='Explicitly start a fresh run, including another attempt on current caption faults')
    parser.add_argument('--resume', help='Resume a specific run without repeating completed/failed attempts')
    parser.add_argument('--pack', action='append', help='Limit a fresh run to this pack; repeat for multiple packs')
    parser.add_argument('--pending-only', action='store_true', help='Generate pending descriptions and retain existing caption faults')
    parser.add_argument('--asset-ids-file', help='JSON array limiting a fresh run to explicitly selected asset IDs')
    parser.add_argument('--peak-reserve-mib', type=int, default=500, help='Additional storage allowance within the approved project budget')
    parser.add_argument('--worker', choices=['caption', 'embeddings'], help=argparse.SUPPRESS)
    parser.add_argument('--run-id', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.new_run and args.resume:
        parser.error('--new-run and --resume are mutually exclusive')
    if args.peak_reserve_mib <= 0:
        parser.error('--peak-reserve-mib must be positive')
    if args.resume and (args.pack or args.pending_only or args.asset_ids_file or args.peak_reserve_mib != 500):
        parser.error('Resume uses its saved selection and storage allowance; do not pass new selection/budget options')
    config = load_config(ROOT / 'config.example.toml', ROOT)
    asset_ids = None
    if args.asset_ids_file:
        asset_ids = read_json(Path(args.asset_ids_file))
        if (not isinstance(asset_ids, list) or len(asset_ids) > 1901
                or any(not isinstance(v, str) for v in asset_ids)):
            raise ConfigError('Asset selection must be a bounded JSON array of IDs')
    if args.worker:
        worker(config, args.run_id, args.worker)
        return 0
    if args.dry_run:
        result = plan(config, args.pack, args.pending_only, args.peak_reserve_mib, asset_ids)
        result['contracts'] = check_prerequisites(config)
        target = config.output_path('data', f'{RUN_ROOT}/dry-run-{uuid.uuid4().hex}.json')
        atomic_json(target, result)
        print(json.dumps({k:v for k,v in result.items() if k not in {'targets', 'contracts'}}, indent=2))
        print('Dry-run report: ' + str(target))
        return 0
    identifier = None
    try:
        with lease(config, 'overnight-descriptions', timeout=0, resource='operations'), keep_awake():
            check_prerequisites(config)
            previous = config.output_path('data', f'{RUN_ROOT}/latest.json')
            if previous.exists():
                assert_worker_stopped(config, read_json(previous)['run_id'])
            # A fresh receipt precedes bulk work and original-record snapshots.
            if args.resume:
                identifier = args.resume
                check_run(config, identifier)
                assert_worker_stopped(config, identifier)
            else:
                pointer = config.output_path('data', f'{RUN_ROOT}/latest.json')
                if pointer.exists() and not args.new_run and read_json(pointer)['status'] not in {'complete', 'complete_with_caption_faults', 'complete_with_faults', 'no_work'}:
                    identifier = choose_run(config)
                else:
                    base = storage(config, 'preflight', 'before')
                    allowed = policy(config)['budget']
                    reserve = args.peak_reserve_mib * 1024**2
                    if reserve > allowed['peak_additional_allocated_bytes']:
                        raise ConfigError('Requested growth allowance exceeds the approved additional storage budget')
                    if base['allocated_bytes'] + reserve > allowed['total_allocated_bytes']:
                        raise ConfigError('Projected peak exceeds the approved total storage ceiling')
                    identifier = choose_run(config, new=True, packs=args.pack, pending_only=args.pending_only,
                                            peak_reserve_mib=args.peak_reserve_mib, asset_ids=asset_ids)
                    set_state(config, identifier, baseline_allocated_bytes=base['allocated_bytes'], storage_before=base)
            state = read_json(run_path(config, identifier) / 'state.json')
            if 'baseline_allocated_bytes' not in state:
                base = storage(config, identifier, 'before')
                set_state(config, identifier, baseline_allocated_bytes=base['allocated_bytes'], storage_before=base)
            budget_check(config, identifier, 'start-or-resume')
            recover_inflight(config, identifier)
            value = check_run(config, identifier)
            print(f"Run {identifier}: {value['plan']['selected']} selected assets. Morning report: {run_path(config, identifier) / 'summary.md'}", flush=True)
            if not value['plan']['selected']:
                set_state(config, identifier, status='no_work', phase='complete')
                summary(config, identifier)
                return 0
            state = read_json(run_path(config, identifier) / 'state.json')
            if state['phase'] == 'caption':
                set_state(config, identifier, status='running', phase='caption', error=None)
                summary(config, identifier)
                while remaining(config, identifier):
                    previous = len(outcomes(config, identifier))
                    supervise(config, identifier, worker_command(config, identifier, 'caption'), 'caption')
                    recover_inflight(config, identifier)
                    if len(outcomes(config, identifier)) <= previous:
                        raise ConfigError('Caption worker made no progress; stopped with all evidence retained')
                    budget_check(config, identifier, 'caption-batch')
                    summary(config, identifier)
                set_state(config, identifier, phase='embeddings')
            state = read_json(run_path(config, identifier) / 'state.json')
            if state['phase'] == 'embeddings':
                set_state(config, identifier, status='running', error=None)
                while index_library(working(config), dry_run=True, description_only=True)['pending']:
                    supervise(config, identifier, worker_command(config, identifier, 'embeddings'), 'embeddings')
                    budget_check(config, identifier, 'index-batch')
                    summary(config, identifier)
                set_state(config, identifier, phase='publish')
            verify_protected(config, identifier)
            budget_check(config, identifier, 'before-publication')
            # Reserve for the new immutable snapshot before creating it.
            state = read_json(run_path(config, identifier) / 'state.json')
            reserve = sum(working(config).output_path('data', name).stat().st_size for name in ('catalog.sqlite', 'embeddings/index.sqlite'))
            before = storage(config, identifier, 'publication-projection')
            budget = policy(config)['budget']
            if before['allocated_bytes'] + reserve > min(budget['total_allocated_bytes'], state['baseline_allocated_bytes'] + value['plan']['peak_additional_bytes']):
                raise ConfigError('Projected publication snapshot exceeds the storage limit; ready work preserved')
            result = publish(config)
            after = budget_check(config, identifier, 'after-publication')
            failed = any(r['status'] == 'failed' for r in outcomes(config, identifier).values())
            indexing = summary(config, identifier)['description_index']
            worker_faults = len(list(run_path(config, identifier).glob('worker-fault-*.json')))
            set_state(config, identifier, status='complete_with_faults' if failed or indexing['new_failed'] or worker_faults else 'complete', phase='complete',
                      generation=result['generation'], storage_after=after, error=None)
            report = summary(config, identifier)
            print(f"Finished. Completed: {report['results']['complete']}; caption faults: {report['results']['failed']}; new indexing faults: {indexing['new_failed']}; worker faults: {worker_faults}. See {run_path(config, identifier) / 'summary.md'}", flush=True)
            return 0
    except BaseException as exc:
        if identifier and (run_path(config, identifier) / 'state.json').exists():
            set_state(config, identifier, status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'blocked', error=f'{type(exc).__name__}: {exc}')
            summary(config, identifier)
        else:
            fault = config.output_path('data', f'{RUN_ROOT}/startup-fault-{uuid.uuid4().hex}.json')
            atomic_json(fault, {'status': 'blocked', 'error': f'{type(exc).__name__}: {exc}', 'utc': utc()})
            print('Startup fault: ' + str(fault), flush=True)
        print(f'Stopped: {exc}. Saved work and evidence are retained.', file=sys.stderr)
        return 1


def check_prerequisites(config):
    # Filesystem checks only. Runtime/model loading occurs in owned workers.
    from local_asset_library.overnight import contract
    for name in ('.venv/Scripts/python.exe', '.venv-caption/Scripts/python.exe', '.venv-embedding/Scripts/python.exe',
                 'scripts/caption-runtime.ps1', 'scripts/embedding-runtime.ps1', 'data/captions/model-download.json',
                 'data/embeddings/model-download.json', 'data/embeddings/capability.json'):
        if not (config.project_root / name).is_file():
            raise ConfigError('Prepared runtime/model receipt missing: ' + name)
    return contract(config)


if __name__ == '__main__':
    raise SystemExit(main())
