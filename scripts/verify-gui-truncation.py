"""A small synthetic catalog verifies deterministic truncation over both real transports."""
import asyncio
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_retrieval import indexed
from test_mcp_assets import update
from local_asset_library.desktop import DesktopBridge, profile_path, record_profile_outcome

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', default='synthetic-truncation')
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
fixture = ROOT / 'scratch' / ('gui-' + args.run_name)
fixture.mkdir(parents=True, exist_ok=False)
config, _, records = indexed.__wrapped__(fixture)
for record in records:
    record['display_name'] = ('Synthetic truncation fixture ' + record['display_name'] + ' ') * 65
    update(config, record)
report = {'status': 'running', 'synthetic_only': True, 'real_assets_modified': False}
os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
bridge = DesktopBridge(config)
import webview
window = webview.create_window('Synthetic GUI / MCP transport check', html='<html><body><p>Checking synthetic shortlist truncation. No original assets are processed.</p></body></html>', js_api=bridge)
profile = profile_path(config, bridge, window)


def verify():
    process = None
    try:
        settings = {'query': 'obj', 'mode': 'keyword', 'filters': {}, 'limit': 5}
        event, returned = threading.Event(), []
        def callback(value):
            returned.append(value)
            event.set()
        window.evaluate_js('window.pywebview.api.search(' + json.dumps(settings) + ')', callback)
        assert event.wait(20)
        gui = returned[0]
        assert not gui['is_error'], gui
        code = 'from pathlib import Path; import sys,asyncio; from local_asset_library.config import Config; from local_asset_library.mcp_server import serve; asyncio.run(serve(Config(Path(sys.argv[1]),Path(sys.argv[2]),None)))'
        env = os.environ.copy()
        env['PYTHONPATH'] = str(ROOT / 'src')
        stderr = (OUT / 'mcp-stderr.log').open('w', encoding='utf-8')
        process = subprocess.Popen([sys.executable, '-c', code, str(config.project_root), str(config.source_root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, env=env,
            text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
        messages, sequence, wire = queue.Queue(), 0, []
        def reader():
            for line in process.stdout:
                messages.put(line)
        threading.Thread(target=reader, daemon=True).start()
        def send(method, params=None, notification=False):
            nonlocal sequence
            message = {'jsonrpc': '2.0', 'method': method}
            if params is not None:
                message['params'] = params
            if not notification:
                sequence += 1
                message['id'] = sequence
            process.stdin.write(json.dumps(message) + '\n')
            process.stdin.flush()
            if notification:
                return
            while True:
                response = json.loads(messages.get(timeout=20))
                wire.append(response)
                if response.get('id') == sequence:
                    return response
        send('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'synthetic-cap-check', 'version': '1'}})
        send('notifications/initialized', notification=True)
        result = send('tools/call', {'name': 'search_assets', 'arguments': settings})['result']
        assert not result.get('isError'), result
        mcp = json.loads(result['content'][0]['text'])
        report['partial_payload'] = mcp
        (OUT / 'wire.json').write_text(json.dumps(wire, indent=2) + '\n', encoding='utf-8')
        assert gui['payload'] == mcp
        assert mcp['truncated'] and len(mcp['results']) < settings['limit']
        assert len(result['content'][0]['text']) <= 6000
        report.update(status='passed', settings=settings, candidates=len(mcp['results']), truncated=True,
            identical_payloads=True, returned_asset_ids=[r['asset_id'] for r in mcp['results']],
            serialized_characters=mcp['serialized_characters'], gui_worker_started=bridge._gateway.worker is not None)
        (OUT / 'wire.json').write_text(json.dumps(wire, indent=2) + '\n', encoding='utf-8')
        process.stdin.close()
        assert process.wait(timeout=10) == 0
        stderr.close()
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
    finally:
        if process and process.poll() is None:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        window.destroy()


try:
    webview.start(verify, gui='edgechromium', private_mode=True, storage_path=str(profile))
finally:
    bridge._close()
    record_profile_outcome(bridge, profile)
    report['gui_lifecycle'] = json.loads((bridge._gateway.audit_root / 'lifecycle.json').read_text())
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
sys.exit(report['status'] != 'passed')
