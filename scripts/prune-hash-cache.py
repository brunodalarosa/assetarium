"""Owner maintenance: drop hash records for paths that no longer exist (decision 0004).

The record is an accelerator, never evidence; pruning costs at most one re-hash per file.
Stop the app, the MCP server and processing first. Writes a receipt under data/storage/.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library import hash_cache

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True, help='New receipt name under data/storage/')
args = parser.parse_args()
receipt = ROOT / 'data/storage' / Path(args.output).name
if receipt.exists():
    raise SystemExit('Receipt exists; choose a new name')
path = hash_cache.location()
before = path.stat().st_size if path and path.is_file() else 0
kept, removed = hash_cache.prune()
hash_cache.reset()
after = path.stat().st_size if path and path.is_file() else 0
result = {'created': datetime.now(timezone.utc).isoformat(), 'record': str(path), 'kept': kept, 'removed': removed,
          'bytes_before': before, 'bytes_after': after}
receipt.parent.mkdir(parents=True, exist_ok=True)
receipt.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
