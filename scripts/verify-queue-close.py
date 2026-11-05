"""Real WebView2 check of closing and reopening while assets are processing (decision 0023).

Phase close: a running item (a synthetic operation record, no worker) makes the real window close ask first:
Keep open keeps the app, Stop & close closes it and leaves every item waiting for Continue. Phase reopen (a
second process, as a real restart): the banner says what stopped, Asset processing offers Continue, and
Continue empties the queue (the synthetic folders have nothing left to do, so nothing is rendered). Small
isolated synthetic sources; no model or Blender run. Writes data/gui/<run-name>/verification.json.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source
from local_asset_library import processing_queue
from local_asset_library.config import Config
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.publication import atomic_json
from local_asset_library.sources import bound, registry
from gui_harness import Harness, isolate_hash_cache
isolate_hash_cache(__file__)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
parser.add_argument('--phase', choices=['close', 'reopen'], default='close')
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
fixture = ROOT / 'scratch' / args.run_name
if args.phase == 'close':
    OUT.mkdir(parents=True, exist_ok=False)
    fixture.mkdir(exist_ok=False)
    config, backend, one, two = managed.__wrapped__(fixture)
    ready_source(config, backend, one)
    ready_source(config, backend, two)
    (OUT / 'fixture.json').write_text(json.dumps({'project': str(config.project_root), 'source_root': str(config.source_root),
                                                  'registry': str(config.sources_registry)}) + '\n')
else:
    saved = json.loads((OUT / 'fixture.json').read_text())
    config = Config(Path(saved['project']), Path(saved['source_root']), None, sources_registry=Path(saved['registry']))
    one, two = registry(config)['sources'][:2]
    # What the stopped worker leaves behind (watch_owner): its operation record says it stopped with the app.
    atomic_json(bound(config, one).output_path('data', 'library/source-operation.json'),
                {'status': 'cancelled', 'token': 'synthetic', 'operation': 'process', 'phase': 'Stopped',
                 'reason': 'Stopped when you closed Assetarium', 'completed': 1, 'total': 3})


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False  # Never trigger startup scans or processing.
        return result


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview
bridge = FixtureBridge(config)
if args.phase == 'close':
    # One item "running" on folder one (its operation record names this live process) and one waiting.
    queue = processing_queue.load(config)
    for source, status in ((one, 'running'), (two, 'waiting')):
        queue['items'].append({'id': source['key'] + '-item', 'action': 'previews', 'scope': {'key': source['key']},
                               'label': source['name'], 'added_utc': processing_queue.now(), 'status': status,
                               'estimate': {'seconds': None}, **({'token': 'synthetic'} if status == 'running' else {})})
    processing_queue.save(config, queue)
    atomic_json(bound(config, one).output_path('data', 'library/source-operation.json'),
                {'status': 'processing', 'token': 'synthetic', 'pid': os.getpid(), 'operation': 'process', 'completed': 1, 'total': 3})
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'phase': args.phase, 'checks': {}, 'synthetic_only': True, 'owner_visual_approval': 'pending'}
ui = Harness(window, OUT, report)
js = ui.js


def close_window():
    threading.Thread(target=window.destroy, daemon=True).start()


def verify_close():
    ui.wait_ready()
    close_window()
    ui.check('close_asks_first', """until(()=>document.getElementById('confirm-dialog')?.open).then(()=>({
      title: $('confirm-title').textContent==='Asset processing ongoing',
      body: $('confirm-body').textContent.startsWith('Make previews · one is running (1 / 3), and 1 more waits.'),
      keep: $('confirm-cancel').textContent==='Keep open', stop: $('confirm-accept').textContent.includes('Stop & close')}))""")
    ui.capture('01-close-asks-first.png')
    js("$('confirm-cancel').click();true")
    ui.check('keep_open_keeps_the_app', "until(()=>!document.getElementById('confirm-dialog').open).then(()=>lal.state.ready)")
    assert processing_queue.load(config)['items'][0]['status'] == 'running'
    close_window()
    ui.check('asks_again', "until(()=>document.getElementById('confirm-dialog')?.open)")
    js("$('confirm-accept').click();true")  # Stop & close: the window closes and webview.start returns.


def verify_reopen():
    ui.wait_ready()
    ui.check('banner_says_what_stopped', """until(()=>$('stopped-banner')).then(()=>({
      text: $('stopped-banner').textContent.includes('2 items stopped when you closed Assetarium'),
      continue: $('continue-stopped').textContent==='Continue'}))""")
    ui.capture('02-reopen-banner.png')
    js("lal.navigate({page:'processing'});true")
    ui.check('processing_offers_continue', """until(()=>$('queue-paused')&&!$('stopped-banner')).then(()=>({
      paused: $('queue-paused').textContent.startsWith('Stopped when you closed Assetarium'),
      button: $('resume-queue').textContent==='Continue'}))""")
    ui.capture('03-processing-continue.png')
    js("$('resume-queue').click();true")
    ui.check('continue_runs_the_line', "until(()=>lal.state.queue&&!lal.state.queue.paused&&!lal.state.queue.up_next.length&&!lal.state.queue.stopped_on_close)")
    recent = processing_queue.load(config)['recent']
    report['checks']['nothing_left_to_do'] = [r['status'] for r in recent[:2]]
    assert [r['status'] for r in recent[:2]] == ['nothing_to_do', 'nothing_to_do'], recent[:2]
    close_window()  # Nothing processing now: the window closes without asking.


def verify():
    try:
        (verify_close if args.phase == 'close' else verify_reopen)()
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture(f'failure-{args.phase}.png')
        except Exception:
            pass
        bridge._allow_close = True
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
started = time.monotonic()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
bridge._close()
record_profile_outcome(bridge, profile)
if report['status'] == 'running':
    value = processing_queue.load(config)
    if args.phase == 'close':
        report['checks']['stopped_items_wait'] = [(i['status'], i.get('stopped_on_close')) for i in value['items']]
        assert [(i['status'], i.get('stopped_on_close')) for i in value['items']] == [('waiting', True), ('waiting', True)]
        assert value['paused'] and value['owner']['closing'] and 'token' not in value['items'][0]
        assert bound(config, one).output_path('data', 'library/source-cancel.json').exists()
    report['status'] = 'passed'
(OUT / f'verification-{args.phase}.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if args.phase == 'close' and report['status'] == 'passed':
    reopened = subprocess.run([sys.executable, __file__, '--run-name', args.run_name, '--phase', 'reopen'], cwd=ROOT)
    summary = {'status': 'passed' if reopened.returncode == 0 else 'faulty',
               'phases': ['verification-close.json', 'verification-reopen.json']}
    (OUT / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n')
    raise SystemExit(reopened.returncode)
raise SystemExit(0 if report['status'] == 'passed' else 1)
