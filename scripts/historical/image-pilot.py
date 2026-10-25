"""Register the owner-approved step 2 image pilot sources and run Process assets on each.

Uses the application's own registration and background operation path; originals
are only read. Re-running skips sources that are already registered.
"""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library import sources
from local_asset_library.config import load_project_config
from local_asset_library.source_operations import operation_status, start

KENNEY = Path(r'C:/Users/backup pc/Documents/General game assets/Kenney Game Assets All-in-1 3.7.0')
PILOT = [KENNEY / 'Icons/Game Icons/PNG', KENNEY / '2D assets/Tiny Dungeon/Tiles', KENNEY / 'Icons/Board Game Icons/Vector/Icons']
ACTIVE = {'queued', 'scanning', 'processing', 'publishing', 'cancelling', 'verifying'}


def main():
    config = load_project_config(ROOT)
    report = []
    for folder in PILOT:
        known = next((s for s in sources.registry(config)['sources'] if Path(s['path']) == folder), None)
        source = known or sources.add(config, str(folder))
        if 'image' not in sources.import_types(sources.bound(config, source)):
            sources.set_import_types(config, source['key'], True)
        started = time.monotonic()
        result = start(config, 'process', source['key'])
        print(json.dumps({'source': source['key'], 'path': str(folder), 'start': result}), flush=True)
        scoped = sources.bound(config, source)
        while operation_status(scoped).get('status') in ACTIVE:
            time.sleep(5)
        final = operation_status(scoped)
        status = sources.source_status(config, source)
        entry = {'source': source['key'], 'id': source['id'], 'path': str(folder), 'seconds': round(time.monotonic() - started, 1),
                 'operation': {k: final.get(k) for k in ('status', 'phase', 'reason', 'faults')},
                 'assets': status.get('assets'), 'failed': status.get('failed'), 'pending': status.get('pending'),
                 'descriptions': status.get('descriptions'), 'format_counts': status.get('format_counts')}
        print(json.dumps(entry), flush=True)
        report.append(entry)
    out = ROOT / 'data/verification/image-pilot-20261020'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'processing.json').write_text(json.dumps(report, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
