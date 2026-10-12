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
from local_asset_library.config import load_config
from local_asset_library.gpu_queue import lease
from local_asset_library.incremental import refresh, publish, coverage, working, process, policy
from local_asset_library.catalog import save_json
from local_asset_library.publication import atomic_json

parser = argparse.ArgumentParser()
parser.add_argument('operation', choices=['scan', 'process', 'refresh', 'status'])
parser.add_argument('--dry-run', action='store_true')
parser.add_argument('--batch-size', type=int, default=50)
args = parser.parse_args()
config = load_config(root / 'config.example.toml', root)
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
        result = {s: process(config, s, args.batch_size, dry_run=True) for s in ('inspection', 'caption', 'embeddings')}
    else:
        before, base = storage('before-bulk')
        budgets = policy(config)['budget']
        save_json(run / 'before.json', {'receipt': before, 'allocated_bytes': base, 'budget': budgets})
        if base + 2 * 1024**3 > budgets['total_allocated_bytes']:
            raise RuntimeError('Conservative projected peak exceeds approved budget; work preserved')
        for stage, executable in [('inspection', '.venv-mcp'), ('caption', '.venv-caption'), ('embeddings', '.venv-embedding')]:
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
                if allocated > budgets['total_allocated_bytes'] or allocated - base > budgets['peak_additional_allocated_bytes']:
                    raise RuntimeError('Approved storage budget exceeded; resumable work preserved')
        result = publish(config)
        after, allocated = storage('after-bulk')
        result['storage'] = {'before': before, 'after': after, 'before_allocated': base, 'after_allocated': allocated}
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
