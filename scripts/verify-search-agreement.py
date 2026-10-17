"""Real STDIO MCP and desktop bridge agreement with the actual worker and model.

Normal search use only: no processing, no asset writes. Writes
data/gui/<run-name>/report.json with candidate IDs, timings and worker phases.
"""
import argparse
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
parser = argparse.ArgumentParser()
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', args.run_name):
    raise SystemExit('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
QUERIES = [{'query': 'red car'}, {'query': 'wooden house', 'limit': 10}, {'query': 'green tree'},
           {'query': 'barrel', 'mode': 'keyword'}, {'query': 'small round table', 'mode': 'description'},
           {'query': 'street lamp', 'mode': 'image'}]


class Wire:
    def __init__(self):
        self.stderr = (OUT / 'mcp-stderr.log').open('w', encoding='utf-8')
        self.process = subprocess.Popen([str(ROOT / '.venv-mcp/Scripts/python.exe'), str(ROOT / 'scripts/asset-mcp.py')],
            cwd=ROOT.parent, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
        self.messages, self.seq = queue.Queue(), 0
        def read():
            for line in self.process.stdout:
                self.messages.put(line)
            self.messages.put(None)
        threading.Thread(target=read, daemon=True).start()
        self.send('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                'clientInfo': {'name': 'search-agreement-check', 'version': '1'}})
        self.send('notifications/initialized', notification=True)

    def send(self, method, params=None, notification=False):
        message = {'jsonrpc': '2.0', 'method': method, **({'params': params} if params is not None else {})}
        if not notification:
            self.seq += 1
            message['id'] = self.seq
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()
        while not notification:
            line = self.messages.get(timeout=180)
            if line is None:
                raise RuntimeError('MCP exited without response')
            response = json.loads(line)
            if response.get('id') == self.seq:
                return response

    def search(self, arguments):
        response = self.send('tools/call', {'name': 'search_assets', 'arguments': arguments})['result']
        return json.loads(response['content'][0]['text']), bool(response.get('isError'))

    def close(self):
        self.process.stdin.close()
        code = self.process.wait(timeout=30)
        self.stderr.close()
        return code


report = {'status': 'running', 'searches': [], 'evidence_boundary': 'Technical agreement only; owner relevance approval is separate'}
from local_asset_library.config import load_project_config
from local_asset_library.desktop import DesktopBridge
config = load_project_config(ROOT)
started = time.perf_counter()
bridge = DesktopBridge(config)
wire = None
try:
    while bridge._gateway.worker_phase in {'not_started', 'loading_libraries'} and time.perf_counter() - started < 180:
        time.sleep(0.1)
    report['gui_prestart'] = {'phase': bridge._gateway.worker_phase, 'seconds': round(time.perf_counter() - started, 2),
                              'model_requested': bridge._gateway.model_requested}
    assert report['gui_prestart']['phase'] == 'ready' and not report['gui_prestart']['model_requested']
    wire = Wire()
    for query in QUERIES:
        arguments = {'mode': 'combined', 'filters': {}, 'limit': 20, **query}
        clock = time.perf_counter(); gui = bridge.search(arguments); gui_seconds = time.perf_counter() - clock
        clock = time.perf_counter(); mcp, mcp_error = wire.search(arguments); mcp_seconds = time.perf_counter() - clock
        gui_ids = [r['asset_id'] for r in gui['payload'].get('results', [])]
        mcp_ids = [r['asset_id'] for r in mcp.get('results', [])]
        report['searches'].append({'arguments': arguments, 'gui_seconds': round(gui_seconds, 2), 'mcp_seconds': round(mcp_seconds, 2),
            'agree': gui_ids == mcp_ids and gui['payload'].get('truncated') == mcp.get('truncated'),
            'count': len(gui_ids), 'gui_error': gui['is_error'], 'mcp_error': mcp_error,
            'top': [r['name'] for r in gui['payload'].get('results', [])[:3]], 'worker_phase': bridge._gateway.worker_phase})
        assert not gui['is_error'] and not mcp_error and gui_ids == mcp_ids and gui_ids, report['searches'][-1]
    report['mcp_exit_code'] = wire.close(); wire = None
    assert report['mcp_exit_code'] == 0
    report['status'] = 'passed'
except BaseException as exc:
    report.update(status='faulty', reason=str(exc) or type(exc).__name__)
finally:
    if wire:
        wire.close()
    bridge._close()
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: report[k] for k in ('status', 'gui_prestart') if k in report} | {'reason': report.get('reason'),
      'searches': [(s['arguments']['query'], s['arguments']['mode'], s['gui_seconds'], s['mcp_seconds'], s['agree']) for s in report['searches']]}, indent=1))
sys.exit(report['status'] != 'passed')
