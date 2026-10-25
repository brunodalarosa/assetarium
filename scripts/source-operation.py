"""App-owned source scanner/coordinator, using existing offline runtimes."""
import argparse
import os
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from local_asset_library.config import load_project_config
from local_asset_library.sources import get_source, bound
from local_asset_library.source_operations import scan_all, process_source, describe_source, worker_stage, state, operation_lease
from local_asset_library.gpu_queue import lease

parser = argparse.ArgumentParser()
parser.add_argument('operation', choices=['scan', 'process', 'describe', 'stage'])
parser.add_argument('--source')
parser.add_argument('--token', required=True)
parser.add_argument('--stage', choices=['inspection', 'caption', 'embeddings'])
args = parser.parse_args()
config = load_project_config(root)
source = get_source(config, args.source) if args.source else None
scoped = bound(config, source) if source else config
if args.operation == 'stage':
    worker_stage(config, source, args.stage, args.token)
else:
    # Wait for the parent to finish its short, atomic process handoff.
    with lease(config, 'source-operation-handoff', resource='sources'):
        state(scoped, pid=os.getpid())
    try:
        with operation_lease(config, scoped, args.token) as ready:
            if not ready:
                pass
            elif args.operation == 'scan':
                scan_all(config, args.token, args.source)
            elif args.operation == 'describe':
                describe_source(config, source, args.token)
            else:
                process_source(config, source, args.token)
    except BaseException as exc:
        state(scoped, status='faulty', phase='Operation stopped', reason=str(exc))
        raise
