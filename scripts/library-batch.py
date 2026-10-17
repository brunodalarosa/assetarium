"""Manual bounded coordinator. Uses prepared runtimes; never syncs or downloads."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from contextlib import nullcontext

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from local_asset_library.config import load_project_config
from local_asset_library.gpu_queue import lease
from local_asset_library.incremental import refresh, publish, coverage, working, process, policy
from local_asset_library.catalog import save_json
from local_asset_library.publication import atomic_json

parser = argparse.ArgumentParser()
parser.add_argument('operation', choices=['scan', 'process', 'refresh', 'status'])
parser.add_argument('--dry-run', action='store_true')
parser.add_argument('--source', help='Registered asset source key')
parser.add_argument('--batch-size', type=int, default=50)
parser.add_argument('--skip-captions', action='store_true', help='Leave descriptions pending; inspect and index available images only')
parser.add_argument('--peak-reserve-mib', type=int, default=2048, help='Estimated and enforced additional storage ceiling for this run')
args = parser.parse_args()
if not 1 <= args.batch_size <= 1000 or args.peak_reserve_mib <= 0:
    parser.error('Batch size must be 1–1000 and peak reserve must be positive')
stages = [('inspection', '.venv-mcp'), ('caption', '.venv-caption'), ('embeddings', '.venv-embedding')]
if args.skip_captions:
    stages = [item for item in stages if item[0] != 'caption']
config = load_project_config(root)
if config.sources_registry:
    from local_asset_library.sources import registry,source_status
    from local_asset_library.source_operations import start
    if args.dry_run or args.operation=='status':
        print(json.dumps({'sources':[source_status(config,s) for s in registry(config)['sources']]}))
    elif args.operation in {'scan','process'}:
        if args.operation=='process' and not args.source:
            parser.error('Choose --source or use the source card in LAL')
        print(json.dumps(start(config,args.operation,args.source)))
    else:
        parser.error('Process assets publishes automatically; use the source card in LAL')
    raise SystemExit(0)
run = root / 'data/library/operations' / uuid.uuid4().hex
run.mkdir(parents=True, exist_ok=False)
def storage(name):
    receipt = 'step8-' + name + '-' + uuid.uuid4().hex + '.json'
    subprocess.run([str(root / '.venv/Scripts/python.exe'), str(root / 'scripts/storage-report.py'), '--output', receipt], cwd=root, check=True, stdout=subprocess.DEVNULL)
    value = json.loads((root / 'data/storage' / receipt).read_text(encoding='utf-8'))
    if value['status'] != 'passed':
        raise RuntimeError('Storage receipt has faults; see ' + receipt)
    return receipt, value['totals']['allocated_bytes']

operation_lease = nullcontext() if args.dry_run or args.operation=='status' else lease(config, 'manual-operation', timeout=0, resource='operations')
lease_acquired = False
try:
    operation_lease.__enter__()
    lease_acquired = True
    if args.operation == 'scan':
        result = refresh(config, args.dry_run)
    elif args.operation == 'status':
        result = coverage(working(config))
    elif args.operation == 'refresh':
        result = {'dry_run': True, 'coverage': coverage(working(config))} if args.dry_run else publish(config)
    elif args.dry_run:
        result = {s: {k: v for k, v in process(config, s, args.batch_size, dry_run=True).items()
                      if k != 'outcomes'} for s, _ in stages}
        result['skipped_stages'] = ['caption'] if args.skip_captions else []
    else:
        before, base = storage('before-bulk')
        budgets = policy(config)['budget']
        reserve = args.peak_reserve_mib * 1024**2
        if reserve > budgets['peak_additional_allocated_bytes']:
            raise RuntimeError('Requested peak reserve exceeds approved additional storage budget')
        save_json(run / 'before.json', {'receipt': before, 'allocated_bytes': base, 'budget': budgets, 'run_peak_reserve_bytes': reserve, 'skipped_stages': ['caption'] if args.skip_captions else []})
        if base + reserve > budgets['total_allocated_bytes']:
            raise RuntimeError('Conservative projected peak exceeds approved budget; work preserved')
        for stage, executable in stages:
            for batch in range(1000):
                preview = process(config, stage, args.batch_size if stage != 'embeddings' else 1000, dry_run=True)
                pending = preview.get('pending', 0)
                save_json(run / f'{stage}-{batch:03}-dry.json', {k:v for k,v in preview.items() if k != 'outcomes'})
                if not pending:
                    break
                log = run / f'{stage}-{batch:03}.log'
                env = os.environ.copy()
                env.update(PYTHONPATH=str(root / 'src'), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
                with log.open('w', encoding='utf-8') as stream:
                    completed = subprocess.run([str(root / executable / 'Scripts/python.exe'), '-m', 'local_asset_library.cli',
                        'process', '--stage', stage, '--limit', str(args.batch_size if stage != 'embeddings' else 1000)], cwd=root, env=env,
                        stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                if completed.returncode:
                    raise RuntimeError(f'Batch application/runtime failure; resume after explicit repair: {log}')
                receipt, allocated = storage(stage + '-batch')
                save_json(run / f'{stage}-{batch:03}-storage.json', {'receipt': receipt, 'allocated_bytes': allocated})
                if allocated > budgets['total_allocated_bytes'] or allocated - base > reserve:
                    raise RuntimeError('Approved storage budget exceeded; resumable work preserved')
        result = publish(config)
        after, allocated = storage('after-bulk')
        result['storage'] = {'before': before, 'after': after, 'before_allocated': base, 'after_allocated': allocated}
        result['skipped_stages'] = ['caption'] if args.skip_captions else []
        if allocated > budgets['total_allocated_bytes'] or allocated - base > reserve:
            raise RuntimeError('Approved storage budget exceeded after publication; results preserved')
    save_json(run / 'result.json', result)
    print(json.dumps({k:v for k,v in result.items() if k != 'outcomes'}, ensure_ascii=False))
except BaseException as exc:
    save_json(run / 'interruption-or-failure.json', {'type': type(exc).__name__, 'reason': str(exc), 'utc': datetime.now(timezone.utc).isoformat(), 'resume': 'Repeat the explicit manual operation; finished stages and unchanged faults remain retained.'})
    if lease_acquired and not args.dry_run and args.operation != 'status':
        atomic_json(root / 'data/library/processing-status.json', {'status':'faulty',
            'stage':args.operation, 'reason':str(exc), 'evidence':str(run / 'interruption-or-failure.json')})
    raise
finally:
    if lease_acquired:
        operation_lease.__exit__(None, None, None)
