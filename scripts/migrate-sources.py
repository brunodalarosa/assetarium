"""One-time owner-approved conversion to source-owned metadata."""
from pathlib import Path
import json
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'src'))
from local_asset_library.config import load_config
from local_asset_library.source_migration import migrate
config=load_config(root/'config.example.toml',root)
_,report=migrate(config,root/'config.example.toml')
print(json.dumps(report,indent=2))
sys.exit(report['status']!='passed')
