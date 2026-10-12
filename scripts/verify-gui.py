"""Actual WebView2 bridge + actual STDIO agreement, UI behavior, rendering and lifecycle."""
import argparse
import base64
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.config import load_config
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', default='actual-window')
parser.add_argument('--render-only', action='store_true', help='Focused UI presentation check; no embedding worker or duplicate semantic benchmark')
parser.add_argument('--caption-classification', action='store_true', help='Check caption severity badges, detail separation and actual MCP transport')
args = parser.parse_args()
if args.caption_classification and not args.render_only:
    parser.error('--caption-classification requires --render-only')
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
report = {'status': 'running', 'checks': [], 'searches': [], 'faults': [],
          'evidence_boundary': 'Actual app and protocol verification, separate from owner usability/accessibility approval'}


def save():
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


class Wire:
    def __init__(self):
        self.stderr = (OUT / 'mcp-stderr.log').open('w', encoding='utf-8')
        self.before = {p.name for p in (ROOT / 'data/mcp/runs').glob('*')}
        self.process = subprocess.Popen([str(ROOT / '.venv-mcp/Scripts/python.exe'), str(ROOT / 'scripts/asset-mcp.py')],
            cwd=ROOT.parent, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
        self.messages = queue.Queue()
        self.seq = 0
        self.wire = []
        def read():
            for line in self.process.stdout:
                self.messages.put(line)
            self.messages.put(None)
        threading.Thread(target=read, daemon=True).start()
        self.send('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                'clientInfo': {'name': 'desktop-agreement-check', 'version': '1'}})
        self.send('notifications/initialized', notification=True)
        assert {t['name'] for t in self.send('tools/list')['result']['tools']} == {'search_assets', 'get_asset'}

    def send(self, method, params=None, notification=False):
        message = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            message['params'] = params
        if not notification:
            self.seq += 1
            message['id'] = self.seq
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()
        if notification:
            return
        while True:
            line = self.messages.get(timeout=110)
            if line is None:
                raise RuntimeError('MCP exited without response')
            response = json.loads(line)
            self.wire.append(response)
            if response.get('id') == self.seq:
                return response

    def search(self, arguments):
        started = time.perf_counter()
        response = self.send('tools/call', {'name': 'search_assets', 'arguments': arguments})['result']
        assert not response.get('isError'), response
        return json.loads(response['content'][0]['text']), time.perf_counter() - started

    def close(self):
        self.process.stdin.close()
        report['mcp_exit_code'] = self.process.wait(timeout=20)
        self.stderr.close()
        (OUT / 'mcp-wire.json').write_text(json.dumps(self.wire, indent=2) + '\n', encoding='utf-8')
        lives = [json.loads((p / 'lifecycle.json').read_text()) for p in (ROOT / 'data/mcp/runs').glob('*')
                 if p.name not in self.before and (p / 'lifecycle.json').is_file()]
        report['mcp_lifecycle'] = lives
        assert report['mcp_exit_code'] == 0 and len(lives) == 1 and lives[0]['closed']
        assert lives[0]['worker_pid'] is None or lives[0]['worker_returncode'] == 0


def js(script, timeout=110):
    done, result = threading.Event(), []
    def callback(value):
        result.append(value)
        done.set()
    window.evaluate_js(script, callback)
    if not done.wait(timeout):
        raise RuntimeError('GUI JavaScript bridge completion timed out')
    return result[0]


def wait_js(expression, timeout=25):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if window.evaluate_js(expression):
            return
        time.sleep(.15)
    raise RuntimeError('GUI condition timed out: ' + expression)


def screenshot(name):
    # Capture the actual running WebView2 control, using its supported renderer API.
    from System import Action
    from System.IO import MemoryStream
    from System.Threading.Tasks import Task
    from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
    form = window.gui.BrowserView.instances[window.uid]
    stream, done, faults = MemoryStream(), threading.Event(), []
    def capture():
        task = form.browser.webview.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream)
        def finished(task):
            if task.IsFaulted:
                faults.append(str(task.Exception))
            done.set()
        task.ContinueWith(Action[Task](finished), form.browser.syncContextTaskScheduler)
    form.Invoke(Action(capture))
    assert done.wait(15), 'CapturePreview did not complete'
    assert not faults, faults
    (OUT / name).write_bytes(bytes(stream.ToArray()))
    stream.Dispose()


def search_script(arguments):
    values = {'query': arguments.get('query', ''), 'mode': arguments['mode'], 'limit': str(arguments['limit']),
              'pack': '', 'format': '', 'triangles': '', 'rigged': ''}
    for key, value in arguments['filters'].items():
        values[{'max_triangles': 'triangles'}.get(key, key)] = str(value).lower() if isinstance(value, bool) else str(value)
    if arguments['mode'] == 'reference':
        values.update({'reference-asset': arguments['reference_asset_id'], 'reference-view': arguments['reference_view']})
    # Invoke the packaged form search path; capture the result from its real Python bridge call.
    return """(async()=>{const original=state.api;let captured;
      state.api={...original,search:async args=>{captured=await original.search(args);return captured;}};
      try { for(const [key,value] of Object.entries(VALUES))$(key).value=value;
        $('mode').onchange();await search();
        return {captured,settings:state.lastSettings,ids:state.items.map(x=>x.asset_id),error:$('error').hidden?null:$('error').textContent};
      } finally {state.api=original;}})()""".replace('VALUES', json.dumps(values))


def verify():
    wire = None
    try:
        wait_js("Boolean(state.context && state.items.length===state.context.pilot_count)")
        assert bridge._gateway.worker is None, 'Browsing must not load a model'
        wait_js("document.querySelectorAll('.thumb img').length===state.context.pilot_count")
        report['browse'] = {'context': bridge.context(), 'cards': window.evaluate_js('state.items.length'),
                            'thumbnails': window.evaluate_js("document.querySelectorAll('.thumb img').length"),
                            'worker_started': False}
        assert window.gui.renderer == 'edgechromium'
        report['checks'].append('Pilot membership/counts, all existing three-quarter thumbnails, WebView2, no browse model load')
        screenshot('browse.png')
        if args.render_only:
            if args.caption_classification:
                records = bridge.browse()['items']
                expected = {level: sum(r['caption_status'] == level for r in records)
                            for level in ('warning', 'fault', 'review_note', 'clear')}
                actual_badges = window.evaluate_js("({warning:document.querySelectorAll('.card .caption-quality-badge.warning').length,fault:document.querySelectorAll('.card .caption-quality-badge.fault').length})")
                assert actual_badges == {k: expected[k] for k in ('warning', 'fault')}, actual_badges
                report['caption_counts'] = expected
                wire = Wire()
                for level in ('review_note', 'warning', 'fault'):
                    item = next(r for r in records if r['caption_status'] == level)
                    identifier = item['asset_id']
                    js('selectAsset(' + json.dumps(identifier) + ')')
                    arguments = {'asset_id': identifier, 'include_metadata': True}
                    mcp = wire.send('tools/call', {'name': 'get_asset', 'arguments': arguments})['result']
                    assert not mcp.get('isError'), mcp
                    mcp_payload = json.loads(mcp['content'][0]['text'])
                    detail = bridge.asset(identifier)['payload']
                    quality = detail['presentation']['caption_quality']
                    assert quality == mcp_payload['metadata']['caption_quality']
                    assert detail['caption_status'] == mcp_payload['caption_status'] == level
                    rendered = window.evaluate_js("(()=>{const sections=[...$('detail').querySelectorAll('.evidence')];const find=name=>sections.find(s=>s.querySelector('h3').textContent===name);const notes=find('Caption warnings and notes'),faults=find('Recorded faults');return {notes:[...notes.querySelectorAll(':scope > ul > li')].map(li=>li.textContent),faults:[...faults.querySelectorAll('.fault-list li')].map(li=>li.textContent),evidence:notes.querySelector('pre').textContent};})()")
                    assert rendered['notes'] == [('Warning: ' if i['severity'] == 'warning' else 'Note: ') + i['reason']
                                                 for i in quality['issues'] if i['severity'] != 'fault']
                    for issue in quality['issues']:
                        if issue['severity'] == 'fault': assert issue['evidence'] in rendered['faults']
                        else: assert issue['evidence'] not in rendered['faults']
                        assert issue['evidence'] in rendered['evidence']
                    window.evaluate_js("(()=>{const section=[...$('detail').querySelectorAll('.evidence')].find(s=>s.querySelector('h3').textContent==='Caption warnings and notes');$('detail').scrollTop=section.offsetTop-$('detail').offsetTop-20;})()")
                    screenshot('caption-' + level + '.png')
                    search_args = {'query': item['name'], 'mode': 'keyword', 'filters': {}, 'limit': 5}
                    gui = js(search_script(search_args))
                    mcp_search, _ = wire.search(search_args)
                    assert not gui['error'] and gui['captured']['payload'] == mcp_search
                    report['searches'].append({'arguments': search_args, 'asset_ids': gui['ids'], 'caption_level': level})
                    js('browse()')
                    wait_js("document.querySelectorAll('.thumb img').length===state.context.pilot_count")
                wire.close()
                wire = None
                report['checks'].append('Actual severity badges and rendered note/warning/fault separation; three real STDIO detail/search payloads agree; original evidence retained')
            gui = js(search_script({'query': 'apple', 'mode': 'keyword', 'filters': {}, 'limit': 5}))
            assert not gui['error'] and gui['ids']
            wait_js("document.querySelectorAll('.thumb img').length===state.items.length")
            js('selectAsset(' + json.dumps(gui['ids'][0]) + ')')
            screenshot('detail.png')
            window.resize(680, 760)
            wait_js('innerWidth<761')
            assert window.evaluate_js('document.documentElement.scrollWidth<=innerWidth')
            screenshot('narrow.png')
            report['checks'].append('Final concise cards and evidence detail rendered in the actual shell; narrow layout; keyword only; no model load')
            report['status'] = 'passed'
            return
        records = bridge.browse()['items']
        apple = next(r for r in records if r['name'].casefold() == 'apple')
        wire = Wire()
        cases = [
            {'query': 'a small round red apple fruit with a leaf'},
            {'query': 'a boxy orange-red car with wheels'},
            {'query': 'a chair with a curved back and flat seat'},
            {'query': 'sedan sports', 'mode': 'keyword'},
            {'query': 'a car with wheels', 'filters': {'pack': 'kenney_car-kit', 'format': 'glb', 'max_triangles': 3000, 'rigged': False}},
            {'query': 'spaceship laser submarine'},
            {'query': 'a red apple with a green leaf', 'mode': 'image'},
            {'query': 'a red apple with a green leaf', 'mode': 'combined'},
            {'query': 'a red apple with a green leaf', 'mode': 'description'},
            {'mode': 'reference', 'reference_asset_id': apple['asset_id'], 'reference_view': 'three_quarter'}]
        worker_pids = []
        for case in cases:
            arguments = {'mode': 'keyword_description', 'filters': {}, 'limit': 5, **case}
            gui = js(search_script(arguments))
            assert not gui['error'], gui
            actual = gui['captured']
            assert actual['arguments'] == arguments == gui['settings']
            mcp, mcp_seconds = wire.search(arguments)
            assert actual['payload'] == mcp, 'GUI/MCP payload disagreement'
            assert gui['ids'] == [x['asset_id'] for x in mcp['results']]
            report['searches'].append({'arguments': arguments, 'asset_ids': gui['ids'], 'truncated': mcp['truncated'],
                'gui_seconds': actual['elapsed_seconds'], 'mcp_seconds': mcp_seconds,
                'match_status': [x['match_status'] for x in mcp['results']]})
            worker_pids.append(bridge._gateway.worker.pid)
            save()
        assert len(set(worker_pids)) == 1
        report['checks'].append('Ten packaged-form → pywebview-bridge searches exactly match actual STDIO MCP payloads/order/truncation; one retained GUI worker')
        # Packaged keyboard handlers and actual native resizing, without OS-input claims.
        key_result = window.evaluate_js("(()=>{const cards=[...$('grid').querySelectorAll('.card')];cards[0].focus();cards[0].dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));return document.activeElement===cards[1];})()")
        assert key_result
        assert js("selectAsset(state.items[0].asset_id).then(()=>({title:$('detail').querySelector('h2').textContent,images:$('detail').querySelectorAll('img').length}))")['images'] == 1
        screenshot('detail.png')
        window.resize(680, 760)
        wait_js('innerWidth<761')
        assert window.evaluate_js('document.documentElement.scrollWidth<=innerWidth')
        screenshot('narrow.png')
        window.resize(1280, 860)
        report['checks'].append('Actual native resize, narrow layout without horizontal overflow, arrow-navigation handler, detail/source/view controls and real PNG rendering')
        # Bounded synthetic UI transport faults/races. No real source or backend fault is introduced.
        synthetic = js("""(async()=>{const real=state.api;const item=name=>({asset_id:name,name,pack:'synthetic_fixture',caption_owner_review:'pending'});
          state.api={...real,asset:async()=>({payload:{preview:{status:'faulty',reason:'Synthetic missing preview fixture'}}}),
            search:args=>new Promise(resolve=>setTimeout(()=>resolve({arguments:args,elapsed_seconds:0.01,payload:{results:[item(args.query)],fault_count:0,truncated:true}}),args.query==='old'?60:10))};
          try {$('mode').value='keyword';$('query').value='old';const first=search();$('query').value='new';const second=search();await Promise.all([first,second]);
            const latest=state.items[0].asset_id==='new';const truncated=$('status').textContent.includes('truncated');
            state.api.search=async()=>({is_error:true,payload:{status:'faulty',reason:'Synthetic embedding runtime failure; no fallback'}});
            await search();const visible=$('error').textContent.includes('Synthetic embedding runtime failure');const partial=state.items[0].asset_id==='new';
            return {latest,truncated,visible,partial};}finally{state.api=real;}})()""")
        assert all(synthetic.values()), synthetic
        report['synthetic_ui_checks'] = synthetic
        report['checks'].append('Synthetic older-result suppression, explicit truncation, runtime-error visibility and preservation of earlier cards without fallback')
        copied = bridge.copy_text(json.dumps(report['searches'][0]['arguments'], indent=2))
        assert copied['status'] == 'copied'
        report['checks'].append('Native clipboard accepted exact reproducible MCP argument JSON')
        js("(async()=>{$('clear').click();await new Promise(resolve=>setTimeout(resolve,400));return true;})()")
        wait_js('state.items.length===state.context.pilot_count')
        assert state_free_resources(window)
        report['checks'].append('Clear restores full pilot; all app-loaded resource URLs are local/data')
        wire.close()
        wire = None
        report['status'] = 'passed'
    except Exception as exc:
        report['status'] = 'faulty'
        report['faults'].append({'item': 'GUI/protocol verification', 'reason': str(exc), 'traceback': traceback.format_exc()})
    finally:
        if wire:
            try:
                wire.close()
            except Exception as exc:
                report['faults'].append({'item': 'verification-owned MCP shutdown', 'reason': str(exc)})
        save()
        window.destroy()


def state_free_resources(window):
    return window.evaluate_js("performance.getEntriesByType('resource').every(r=>!/^https?:/.test(r.name))")


os.environ.update(PYTHONNET_RUNTIME='netfx', WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--force-renderer-accessibility',
    TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
config = load_config(ROOT / 'config.example.toml', ROOT)
bridge = DesktopBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
import webview
save()
try:
    webview.start(verify, gui='edgechromium', private_mode=True,
                  storage_path=str(profile))
finally:
    bridge._close()
    record_profile_outcome(bridge, profile)
    report['gui_lifecycle'] = json.loads((bridge._gateway.audit_root / 'lifecycle.json').read_text())
    report['gui_thread_alive_after_close'] = bridge._thread.is_alive()
    if report['status'] == 'passed' and (report['gui_thread_alive_after_close'] or
            (report['gui_lifecycle']['worker_pid'] is not None and report['gui_lifecycle']['worker_returncode'] != 0)):
        report['status'] = 'faulty'
        report['faults'].append({'item': 'GUI-owned lifecycle', 'reason': 'GUI worker/thread did not close cleanly'})
    save()
print(json.dumps({'status': report['status'], 'checks': report['checks'], 'faults': report['faults']}, indent=2))
sys.exit(report['status'] != 'passed')
