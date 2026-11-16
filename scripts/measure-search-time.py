"""Warm search time on a real library, plus the result IDs of a fixed keyword query set.

Normal search use only: no processing, no asset writes. On this checkout, searches go through the
desktop bridge as the window's do (keyword and combined; combined needs the verified embedding
runtime). ``--project-root`` measures another checkout's library read-only: keyword searches run
in this process through the service the app and MCP share, since the bridge would write that
checkout's launch audits and start its embedding runtime. Writes data/gui/<run-name>/report.json.
"""
import argparse
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
parser = argparse.ArgumentParser()
parser.add_argument('--run-name', required=True)
parser.add_argument('--project-root', default=str(ROOT), help='Checkout whose library is searched (read only)')
parser.add_argument('--query', default='Coin')
parser.add_argument('--runs', type=int, default=3)
args = parser.parse_args()
if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', args.run_name):
    raise SystemExit('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
# The verify-search-agreement queries in keyword mode, so result IDs can be compared across commits.
AGREEMENT = ['Coin', 'red car', 'wooden house', 'green tree', 'barrel', 'small round table', 'street lamp',
             'blue potion icon', 'trophy', 'six-sided die', 'tile', 'treasure chest']

from local_asset_library.config import load_project_config
from local_asset_library.mcp_assets import AssetService
from local_asset_library.publication import snapshot
from local_asset_library.retrieval import library_records
from local_asset_library.source_operations import operation_status

project = Path(args.project_root).resolve()
config = load_project_config(project)
own = project == ROOT.resolve()
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def processing():
    value = operation_status(config)
    return {k: value.get(k) for k in ('status', 'operation', 'phase', 'stage') if k in value}


report = {'status': 'running', 'commit': commit, 'project': 'this checkout' if own else 'another checkout (read only)',
          'query': args.query, 'runs_per_mode': args.runs, 'processing_before': processing(), 'modes': {},
          'agreement': [], 'boundary': 'In-process service timing (no window, no STDIO); warm = after one search in this process'}
bridge = None
try:
    with snapshot(config):
        report['library_assets'] = len(library_records(config))
    if own:
        from local_asset_library.desktop import DesktopBridge
        bridge = DesktopBridge(config)
        report['measured_through'] = 'desktop bridge'
        modes = ['keyword', 'combined']
    else:
        service = AssetService(config)
        report['measured_through'] = 'in-process search service'
        modes = ['keyword']

    def search(mode, query, limit=20):
        arguments = {'query': query, 'mode': mode, 'filters': {}, 'limit': limit}
        clock = time.perf_counter()
        if bridge:
            result = bridge.search(arguments)
            if result.get('status') == 'faulty' or result.get('is_error'):
                raise RuntimeError((result.get('payload') or {}).get('reason') or result.get('reason'))
            payload = result['payload']
        else:
            with snapshot(config):
                payload = service.search(arguments)[0]
        return payload, time.perf_counter() - clock

    for mode in modes:
        try:
            _, first = search(mode, args.query)
            times, payload = [], None
            for _ in range(args.runs):
                payload, seconds = search(mode, args.query)
                times.append(seconds)
            report['modes'][mode] = {'first_seconds': round(first, 3), 'warm_seconds': [round(t, 3) for t in times],
                                     'warm_median_seconds': round(statistics.median(times), 3),
                                     'results': len(payload['results']), 'fault_count': payload['fault_count'],
                                     'top_ids': [r['asset_id'] for r in payload['results']]}
        except Exception as exc:
            report['modes'][mode] = {'status': 'faulty', 'reason': str(exc) or type(exc).__name__}
    for query in AGREEMENT:
        payload, seconds = search('keyword', query)
        report['agreement'].append({'query': query, 'mode': 'keyword', 'seconds': round(seconds, 3),
                                    'ids': [r['asset_id'] for r in payload['results']],
                                    'fault_count': payload['fault_count'], 'faults': payload['faults']})
    report['status'] = 'passed'
except BaseException as exc:
    report.update(status='faulty', reason=str(exc) or type(exc).__name__)
finally:
    if bridge:
        bridge._close()
    report['processing_after'] = processing()
    report['processing_running'] = any(r.get('status') in {'queued', 'processing'}
                                       for r in (report['processing_before'], report['processing_after']))
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': report['status'], 'reason': report.get('reason'), 'library_assets': report.get('library_assets'),
                  'processing_running': report['processing_running'],
                  'modes': {m: v.get('warm_median_seconds', v.get('reason')) for m, v in report['modes'].items()}}, indent=1))
sys.exit(report['status'] != 'passed')
