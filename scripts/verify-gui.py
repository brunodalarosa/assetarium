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
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from local_asset_library.config import load_project_config
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
        assert {t['name'] for t in self.send('tools/list')['result']['tools']} == {'search_assets', 'get_asset', 'list_collections', 'get_collection', 'edit_collection', 'tag_assets'}

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
    return ui.js(script, timeout)


def wait_js(expression, timeout=25):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def screenshot(name):
    # Capture the actual running WebView2 control, using its supported renderer API.
    ui.capture(name)


# Home browses (Enter on an empty search) 40-card pages; thumbnails load only near the viewport.
PAGE = 'Math.min(40,lal.state.context.pilot_count)'
THUMBNAILS_SETTLED = "document.querySelectorAll('#grid .thumb img').length>0&&lal.thumbnailWorkers()===0"


def select(identifier):
    js("(async()=>{await lal.selectAsset('library'," + json.dumps(identifier) + ");await until(()=>!lal.state.library.detail.loading&&$('detail').querySelector('h2'));return true})()")

def all_items(filters=None):
    """Every library member across browse pages (the first page alone is not representative)."""
    items, offset = [], 0
    while True:
        page = bridge.browse(filters or {}, offset, 100)
        items.extend(page['items'])
        offset += len(page['items'])
        if not page['items'] or offset >= page['total_count']:
            return items


def search_script(arguments):
    filters = {'asset_type': '', 'pack': '', 'format': '', 'triangles': '', 'rigged': '', 'transparent': '', 'size_class': '',
               'mode': arguments['mode'], 'limit': str(arguments['limit'])}
    for key, value in arguments['filters'].items():
        filters[{'max_triangles': 'triangles'}.get(key, key)] = str(value).lower() if isinstance(value, bool) else str(value)
    if arguments['mode'] == 'reference':
        filters.update({'reference_asset': arguments['reference_asset_id'], 'reference_view': arguments['reference_view']})
    # Run the app's own search action; capture the result from its real Python bridge call.
    return """(async()=>{const original=lal.state.api;let captured;
      lal.setState({api:Object.assign(Object.create(original),{search:async args=>{captured=await original.search(args);return captured;}})});
      try { lal.setState({filters:{...lal.state.filters,...FILTERS}});lal.setQuery(QUERY);await lal.search();
        return {captured,settings:lal.state.search.lastSettings,ids:lal.state.library.items.map(x=>x.asset_id),error:lal.state.search.error};
      } finally {lal.setState({api:original});}})()""".replace('FILTERS', json.dumps(filters)).replace('QUERY', json.dumps(arguments.get('query', '')))

def verify():
    wire = None
    try:
        ui.wait_ready()
        js("(async()=>{await lal.submitSearch();return true})()")
        wait_js(f"lal.state.library.items.length==={PAGE}")
        assert not bridge._gateway.model_requested, 'Browsing must not load a model'
        wait_js(THUMBNAILS_SETTLED)
        report['browse'] = {'context': bridge.context(), 'cards': js('lal.state.library.items.length'),
                            'thumbnails': js("document.querySelectorAll('#grid .thumb img').length"),
                            'model_requested': False}
        assert window.gui.renderer == 'edgechromium'
        report['checks'].append('Library counts, first browse page, visible three-quarter thumbnails, WebView2, no browse model load')
        screenshot('browse.png')
        if args.render_only:
            if args.caption_classification:
                records = all_items()
                expected = {level: sum(r['caption_status'] == level for r in records)
                            for level in ('warning', 'fault', 'review_note', 'clear')}
                # Badges are compared on the cards actually shown: the first browse page.
                shown = bridge.browse({}, 0, 40)['items']
                page_expected = {level: sum(r['caption_status'] == level for r in shown) for level in ('warning', 'fault')}
                actual_badges = js("({warning:document.querySelectorAll('.card .caption-quality-badge.warning').length,fault:document.querySelectorAll('.card .caption-quality-badge.fault').length})")
                assert actual_badges == {'warning': page_expected['warning'], 'fault': 0}, (actual_badges, page_expected)
                report['caption_counts'] = expected
                wire = Wire()
                for level in ('review_note', 'warning', 'fault'):
                    item = next(r for r in records if r['caption_status'] == level)
                    identifier = item['asset_id']
                    select(identifier)
                    arguments = {'asset_id': identifier, 'include_metadata': True}
                    mcp = wire.send('tools/call', {'name': 'get_asset', 'arguments': arguments})['result']
                    assert not mcp.get('isError'), mcp
                    mcp_payload = json.loads(mcp['content'][0]['text'])
                    detail = bridge.asset(identifier)['payload']
                    quality = detail['presentation']['caption_quality']
                    assert quality == mcp_payload['metadata']['caption_quality']
                    assert detail['caption_status'] == mcp_payload['caption_status'] == level
                    # Evidence tab: open the original-evidence disclosure, then read notes, faults and raw evidence.
                    rendered = js("""(async()=>{$('inspector-tab-evidence').click();await frame();
                      const sections=[...$('detail').querySelectorAll('.evidence')];const find=name=>sections.find(s=>s.querySelector('h3').textContent===name);
                      const notes=find('Caption warnings & notes'),faults=find('Recorded faults');
                      [...notes.querySelectorAll('button[aria-expanded=false]')].find(b=>b.textContent.includes('Original caption review evidence'))?.click();
                      await until(()=>notes.querySelector('pre'));
                      return {notes:[...notes.querySelectorAll('ul > li')].map(li=>li.querySelector('span').textContent+': '+li.querySelector('p').textContent),
                        faults:[...faults.querySelectorAll('.fault-list li')].map(li=>li.textContent),evidence:notes.querySelector('pre').textContent};})()""")
                    assert rendered['notes'] == [('Warning: ' if i['severity'] == 'warning' else 'Review note: ') + i['reason']
                                                 for i in quality['issues'] if i['severity'] != 'fault']
                    for issue in quality['issues']:
                        if issue['severity'] == 'fault': assert issue['evidence'] in rendered['faults']
                        else: assert issue['evidence'] not in rendered['faults']
                        assert issue['evidence'] in rendered['evidence']
                    js("(()=>{const section=[...$('detail').querySelectorAll('.evidence')].find(s=>s.querySelector('h3').textContent==='Caption warnings & notes');$('detail').scrollTop=section.offsetTop-$('detail').offsetTop-20;return true})()")
                    screenshot('caption-' + level + '.png')
                    search_args = {'query': item['name'], 'mode': 'keyword', 'filters': {}, 'limit': 5}
                    gui = js(search_script(search_args))
                    mcp_search, _ = wire.search(search_args)
                    assert not gui['error'] and gui['captured']['payload'] == mcp_search
                    report['searches'].append({'arguments': search_args, 'asset_ids': gui['ids'], 'caption_level': level})
                    js('lal.browse()')
                    wait_js(THUMBNAILS_SETTLED)
                wire.close()
                wire = None
                report['checks'].append('Actual severity badges and rendered note/warning/fault separation; three real STDIO detail/search payloads agree; original evidence retained')
            gui = js(search_script({'query': 'apple', 'mode': 'keyword', 'filters': {}, 'limit': 5}))
            assert not gui['error'] and gui['ids']
            wait_js(THUMBNAILS_SETTLED)
            select(gui['ids'][0])
            screenshot('detail.png')
            window.resize(680, 760)
            wait_js('innerWidth<761')
            assert js("$('library-view').scrollWidth<=$('library-view').clientWidth+1")
            screenshot('narrow.png')
            report['checks'].append('Final concise cards and evidence detail rendered in the actual shell; narrow layout; keyword only; no model load')
            report['status'] = 'passed'
            return
        records = all_items()
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
        key_result = js("(async()=>{await frame();const cards=[...$('grid').querySelectorAll('.card')];cards[0].focus();cards[0].dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));return document.activeElement===cards[1];})()")
        assert key_result
        select(js('lal.state.library.items[0].asset_id'))
        assert js("$('detail').querySelectorAll('img').length") == 1
        screenshot('detail.png')
        window.resize(680, 760)
        wait_js('innerWidth<761')
        assert js("$('library-view').scrollWidth<=$('library-view').clientWidth+1")
        screenshot('narrow.png')
        window.resize(1280, 860)
        report['checks'].append('Actual native resize, narrow layout without horizontal overflow, arrow-navigation handler, detail/source/view controls and real PNG rendering')
        # Bounded synthetic UI transport faults/races. No real source or backend fault is introduced.
        synthetic = js("""(async()=>{const real=lal.state.api;const item=name=>({asset_id:name,name,pack:'synthetic_fixture',caption_owner_review:'pending'});
          const stub=Object.assign(Object.create(real),{asset:async()=>({payload:{preview:{status:'faulty',reason:'Synthetic missing preview fixture'}}}),
            search:args=>new Promise(resolve=>setTimeout(()=>resolve({arguments:args,elapsed_seconds:0.01,payload:{generation:lal.state.context.generation,results:[item(args.query)],fault_count:0,truncated:true}}),args.query==='old'?60:10))});
          lal.setState({api:stub});
          try {lal.setState({filters:{...lal.state.filters,mode:'keyword'}});lal.setQuery('old');const first=lal.search();lal.setQuery('new');const second=lal.search();await Promise.all([first,second]);await frame();
            const latest=lal.state.library.items[0].asset_id==='new';const truncated=$('status').textContent.includes('truncated');
            stub.search=async()=>({is_error:true,payload:{status:'faulty',reason:'Synthetic embedding runtime failure; no fallback'}});
            await lal.search();await frame();const visible=$('error').textContent.includes('Synthetic embedding runtime failure');const partial=lal.state.library.items[0].asset_id==='new';
            return {latest,truncated,visible,partial};}finally{lal.setState({api:real});}})()""")
        assert all(synthetic.values()), synthetic
        report['synthetic_ui_checks'] = synthetic
        report['checks'].append('Synthetic older-result suppression, explicit truncation, runtime-error visibility and preservation of earlier cards without fallback')
        copied = bridge.copy_text(json.dumps(report['searches'][0]['arguments'], indent=2))
        assert copied['status'] == 'copied'
        report['checks'].append('Native clipboard accepted exact reproducible MCP argument JSON')
        js("(async()=>{$('clear').click();await until(()=>lal.state.search.phase==='idle'&&!$('grid'));await lal.submitSearch();return true;})()")
        wait_js(f'lal.state.library.items.length==={PAGE}')
        assert state_free_resources(window)
        report['checks'].append('Clear returns Home to its idle search; browsing again restores the first page; all app-loaded resource URLs are local/data')
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
config = load_project_config(ROOT)
bridge = DesktopBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
from gui_harness import Harness
ui = Harness(window, OUT, report)
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
