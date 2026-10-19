"""Exercise optional descriptions and notifications in real WebView2 with isolated synthetic assets.

The description run is a stand-in that writes synthetic descriptions; no caption
model, GPU or real asset source is used. Evidence: data/gui/<run-name>/.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source, failed_caption
from local_asset_library import notifications, sources
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.incremental import working, update_record
from local_asset_library.library_index import index_library
from local_asset_library.membership import records
from local_asset_library.source_operations import publish_source, state, cancelled
from ui_text import assert_ui_text

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True, exist_ok=False)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir(exist_ok=False)
config, backend, one, two = managed.__wrapped__(fixture)
work = ready_source(config, backend, one)
ready_source(config, backend, two)
# Source one: two assets imported without descriptions and one recorded description failure.
missing, failed = records(work)[:2], records(work)[2]
originals = {r['asset_id']: deepcopy(r) for r in missing}
for record in missing:
    record.update(description=None, caption_provenance=None)
    record['processing']['caption'] = 'pending'
    update_record(work, record)
failed_caption(work, failed)
index_library(work, backend)
publish_source(sources.bound(config, one))
sources.aggregate(config)
for source in (one, two):
    sources.scan_source(config, source)
# Original synthetic asset files; generated metadata and publications may change.
saved = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in (fixture / 'sources').rglob('*') if p.is_file() and 'metadata-lal' not in p.parts}
assert saved


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False  # Never trigger startup scans or processing.
        return result

    def _start_source_operation(self, operation, key):
        if operation != 'describe':
            raise RuntimeError('Only the synthetic description run is allowed here')
        source = sources.get_source(self._config, key)
        scoped, token = sources.bound(self._config, source), uuid.uuid4().hex
        state(scoped, token=token, pid=os.getpid(), status='processing', operation='describe', key=key,
              stage='caption', phase='Writing descriptions', progress=.05, reason=None, completed=0, total=len(missing))
        notifications.clear_ready(self._config, source['id'])
        threading.Thread(target=self._describe, args=(source, scoped, token), daemon=True).start()
        return {'status': 'started', 'token': token}

    def _describe(self, source, scoped, token):
        # Same publication path as describe_source, with synthetic descriptions instead of the model.
        started = time.monotonic()
        for i, record in enumerate(missing):
            time.sleep(2)
            if cancelled(scoped, token):
                break
            current = next(r for r in records(work) if r['asset_id'] == record['asset_id'])
            current.update(description=originals[record['asset_id']]['description'],
                           caption_provenance=originals[record['asset_id']]['caption_provenance'])
            current['processing']['caption'] = 'complete'
            update_record(work, current)
            state(scoped, status='processing', phase='Writing descriptions', completed=i + 1, total=len(missing),
                  progress=.05 + .4 * (i + 1) / len(missing), current_asset=record['asset_id'])
        state(scoped, status='processing', stage='embeddings', phase='Preparing search data', progress=.6)
        index_library(work, backend)
        state(scoped, status='publishing', phase='Publishing descriptions', progress=.9)
        publish_source(scoped)
        sources.aggregate(self._config)
        sources.scan_source(self._config, source)
        written = sum(r['processing']['caption'] == 'complete' and r['asset_id'] in originals for r in records(work))
        notifications.notify_report(self._config, source, token, 'complete', written=written, failed=0,
                                    remaining=len(missing) - written, elapsed_seconds=round(time.monotonic() - started))
        state(scoped, status='complete', phase='Descriptions generated and published', progress=1, current_asset=None)


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True, 'owner_usability_approval': 'pending'}


def wait(expression, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if window.evaluate_js(expression):
            return
        time.sleep(.1)
    raise RuntimeError('UI condition timed out: ' + expression + ' ' + str(window.evaluate_js(
        "({main:$('error').textContent,sources:$('sources-message').textContent})")))


def js(script):
    if '(async' not in script:
        return window.evaluate_js(script)
    done, result = threading.Event(), []
    window.evaluate_js(script, lambda value: (result.append(value), done.set()))
    if not done.wait(40):
        raise RuntimeError('UI action timed out: ' + script[:150])
    return result[0]


def capture(name):
    assert_ui_text(window, name, report)
    from System import Action
    from System.IO import MemoryStream
    from System.Threading.Tasks import Task
    from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
    form = window.gui.BrowserView.instances[window.uid]
    stream, done, faults = MemoryStream(), threading.Event(), []
    def start():
        task = form.browser.webview.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream)
        def finish(task):
            if task.IsFaulted:
                faults.append(str(task.Exception))
            done.set()
        task.ContinueWith(Action[Task](finish), form.browser.syncContextTaskScheduler)
    form.Invoke(Action(start))
    assert done.wait(15) and not faults
    (OUT / name).write_bytes(bytes(stream.ToArray()))
    stream.Dispose()


def text(selector):
    return window.evaluate_js(f"document.querySelector({json.dumps(selector)})?.textContent||''")


def verify():
    try:
        wait('state.context&&state.items.length===6&&state.sources.length===2&&state.notificationKeys!==null')
        assert window.evaluate_js("document.querySelectorAll('.source-warning').length===0&&$('source-warnings').hidden")
        cards = window.evaluate_js("[...$('grid').querySelectorAll('.card')].map(c=>c.textContent).join('|')")
        assert 'Caption fault' not in cards and cards.count('Review pending') == 3, cards
        report['checks'].append('Missing and failed descriptions raise no source card and no card badges; described assets keep review badges')
        # First launch seeds one notice for the source with missing descriptions; no toast for earlier notices.
        wait("$('notifications-count').textContent==='1'&&!$('notifications-count').hidden")
        assert window.evaluate_js("$('toasts').children.length===0&&$('open-notifications').getAttribute('aria-label')==='Notifications, 1 unread'")
        js("$('open-notifications').click();true")
        wait("!$('notifications-panel').hidden&&document.activeElement===$('notifications-title')")
        body = text('#notifications-list .notification')
        assert 'Descriptions ready to generate' in body and '2 assets have no description yet' in body and 'one' in body, body
        assert window.evaluate_js("[...document.querySelectorAll('#notifications-list button')].map(b=>b.textContent).join()==='Generate descriptions,Not now'")
        assert window.evaluate_js("$('open-notifications').getAttribute('aria-expanded')==='true'")
        assert window.evaluate_js("$('open-settings').getAttribute('aria-label')==='Settings'&&Boolean($('open-settings').querySelector('svg'))")
        capture('01-ready-notice.png')
        js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));true")
        wait("$('notifications-panel').hidden&&document.activeElement===$('open-notifications')&&$('notifications-count').hidden")
        assert notifications.load(config)['items'][0]['read']
        report['checks'].append('Bell shows the seeded ready notice; Escape closes the panel, returns focus and marks it read')
        # A notice that arrives while the app is open also shows a toast.
        notifications.notify_report(config, two, 'synthetic-stop', 'stopped', written=1, failed=0, remaining=2,
                                    reason='Not enough GPU memory for description batch size 8. Lower it in Settings → General.')
        wait("$('toasts').children.length===1&&$('notifications-count').textContent==='1'")
        toast = text('#toasts .toast')
        assert 'Description run stopped' in toast and 'still missing' in toast and 'Continue' in toast, toast
        capture('02-toast.png')
        js("document.querySelector('#toasts .toast > .notification-dismiss').click();true")
        wait("$('toasts').children.length===0")
        report['checks'].append('A new report pops a dismissible toast with its action while the bell counts it')
        js("$('open-settings').click();$('asset-sources-tab').click();true")
        wait("!$('settings-view').hidden&&document.querySelectorAll('.source-descriptions').length===2")
        summary = window.evaluate_js("[...document.querySelectorAll('.source-descriptions-summary')].map(x=>x.textContent)")
        assert summary == ['Descriptions 2 missing · 1 failed', 'Descriptions 3 descriptions written'], summary
        assert window.evaluate_js("[...document.querySelectorAll('[data-action=describe]')].map(b=>b.disabled).join()==='false,true'")
        capture('03-settings-descriptions.png')
        report['checks'].append('Each source shows written/missing/failed counts; Generate is enabled only where descriptions are missing')
        js("$('close-settings').click();true")
        wait("!$('library-view').hidden")
        js("$('open-notifications').click();true")
        wait("!$('notifications-panel').hidden")
        js("[...document.querySelectorAll('#notifications-list button')].find(b=>b.textContent==='Generate descriptions').click();true")
        wait("document.querySelector('#notifications-running .notification.running progress')!==null")
        running = text('#notifications-running')
        assert 'Generating descriptions' in running and 'Cancel' in running, running
        assert window.evaluate_js("!document.querySelector('[data-notification=\"ready-" + one['id'] + "\"]')")
        assert window.evaluate_js("document.querySelectorAll('.source-warning').length===0")
        capture('04-running.png')
        report['checks'].append('Generate starts the background run; the panel shows live progress with Cancel and the main view gets no warning card')
        wait("[...document.querySelectorAll('#notifications-list h3')].some(h=>h.textContent.includes('Descriptions finished'))", 60)
        wait("!document.querySelector('#notifications-running .notification')")
        finished = text('#notifications-list .notification')
        assert '2 descriptions written' in finished and 'View source' in finished, finished
        assert window.evaluate_js("$('toasts').children.length===0")  # The open panel already shows it.
        capture('05-report.png')
        report['checks'].append('Finished run reports written count in the open panel without a duplicate toast')
        js("[...document.querySelectorAll('#notifications-list button')].find(b=>b.textContent==='View source').click();true")
        # Generate is disabled now, so focus lands on the source name in its settings row.
        wait("!$('settings-view').hidden&&!$('asset-sources-panel').hidden&&document.activeElement?.dataset.action==='browse'&&document.activeElement?.dataset.source===" + json.dumps(one['key']))
        wait("document.querySelector('.source-descriptions-summary').textContent==='Descriptions 2 descriptions written · 1 failed'")
        assert window.evaluate_js("document.querySelector('[data-action=describe]').disabled&&document.querySelector('.source-descriptions .hint').textContent.includes('Failed descriptions are recorded and not retried')")
        assert window.evaluate_js("document.querySelector('.source-descriptions').textContent.includes('Last run finished.')")
        capture('06-settings-after-run.png')
        report['checks'].append('View source opens the source settings; nothing left to generate and failures are not retried')
        js("$('close-settings').click();true")
        wait("!$('library-view').hidden")
        window.resize(680, 800)
        wait('innerWidth<761')
        js("$('open-notifications').click();true")
        wait("!$('notifications-panel').hidden")
        assert window.evaluate_js("document.documentElement.scrollWidth<=innerWidth&&$('notifications-panel').getBoundingClientRect().right<=innerWidth")
        capture('07-narrow-panel.png')
        js("document.querySelector('#notifications-list .notification-dismiss').click();true")
        wait("document.querySelectorAll('#notifications-list .notification').length===1")
        report['checks'].append('Narrow layout keeps the panel in view without horizontal overflow; dismiss removes a report')
        js("document.body.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));true")
        wait("$('notifications-panel').hidden")
        assert not bridge._gateway.model_requested
        changed = [p for p, digest in saved.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
        assert not changed, changed
        report['checks'].append('Clicking outside closes the panel; original fixture files unchanged; no model worker loaded')
        report.update(status='passed', protected_files=len(saved))
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            capture('failure.png')
        except Exception:
            pass
    finally:
        (OUT / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(report, indent=2, ensure_ascii=False))
raise SystemExit(0 if report['status'] == 'passed' else 1)
