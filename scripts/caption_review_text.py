"""Compact text companion to the real input mosaics."""
from pathlib import Path
import json
import sys
from local_asset_library.catalog import detail
from local_asset_library.config import load_config

root = Path(__file__).resolve().parents[1]
config = load_config(root / "config.example.toml", root)
report = json.loads((root / "data/captions/pilot-v2-report.json").read_text(encoding="utf-8"))
start = int(sys.argv[1]) if len(sys.argv)>1 else 0
for index, outcome in enumerate(report["outcomes"][start:start+10], start+1):
    record = detail(config, outcome["asset_id"])
    print(json.dumps({"index": index, "name": outcome["name"], "asset_id": outcome["asset_id"],
          "status": outcome["status"], "description": record["description"],
          "errors": [a.get("error") for a in outcome["attempts"] if a.get("error")]}))
