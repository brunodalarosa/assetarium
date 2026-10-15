"""Exercise source browsing in real WebView2 using small isolated synthetic assets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source
from local_asset_library import sources
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
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
# More than one page exercises scrolling, batch boundaries and retained cards.
for i in range(48):
    (Path(one['path']) / f'extra{i:02}.obj').write_text(
        'v -1 0 -1\nv 1 0 -1\nv 0 2 0\nv 0 0 1\nf 1 3 2\nf 1 2 4\nf 2 3 4\nf 3 1 4\n')
ready_source(config, backend, one)
ready_source(config, backend, two)
sources.set_enabled(config, one['key'], False)
empty_dir = fixture / 'empty-source'
empty_dir.mkdir()
empty = sources.add(config, str(empty_dir))
saved = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in fixture.rglob('*') if p.is_file()}


class FixtureBridge(DesktopBridge):
    delay = False
    entered = threading.Event()
    unblock = threading.Event()

    def context(self):
        result = super().context()
        result['managed_sources'] = False  # Never trigger startup scans or processing.
        return result

    def source_asset(self, *args):
        if self.delay:
            self.entered.set()
            self.unblock.wait(20)
        return super().source_asset(*args)


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
        "({main:$('error').textContent,source:$('source-browser-error').textContent})")))


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
    path = OUT / name
    path.write_bytes(bytes(stream.ToArray()))
    stream.Dispose()
    return path


def verify():
    try:
        wait('state.context&&state.items.length===3&&state.sources.length===3')
        js("(async()=>{$('query').value='item0';$('mode').value='keyword';await search();window.savedLibraryCards=[...$('grid').children];return true;})()")
        js("$('open-settings').click();true")
        js("$('asset-sources-tab').click();true")
        wait("!$('settings-view').hidden&&document.querySelectorAll('.source-browse-link').length===3")
        capture('01-source-links.png')
        assert window.evaluate_js("document.querySelector('.source-browse-link').getAttribute('aria-label').includes('Browse assets')")
        # Clicking the label and icon follows the same button action.
        js("document.querySelector('.source-browse-link span:first-child').click();true")
        wait("!$('source-browser-view').hidden&&state.sourceBrowse.items.length===40&&!state.sourceBrowse.loading")
        wait("document.querySelectorAll('#source-grid .thumb img').length>=4")
        assert window.evaluate_js("$('source-browser-status').textContent.includes('51 saved assets')&&$('source-browser-status').textContent.includes('Disabled')")
        assert window.evaluate_js("$('search-form').closest('[hidden]')!==null")
        assert window.evaluate_js("$('source-collection').scrollHeight>$('source-collection').clientHeight")
        capture('02-disabled-source-grid.png')
        report['checks'].append('Name opens disabled source with 51 saved assets, independent scroll area and no search form')
        js("$('source-collection').scrollTop=$('source-collection').scrollHeight;true")
        wait('state.sourceBrowse.items.length===51&&!state.sourceBrowse.loading')
        assert window.evaluate_js("new Set([...$('source-grid').children].map(x=>x.dataset.id)).size===51&&$('source-load-more').hidden")
        report['checks'].append('Scrolling loads the final batch without duplicates or losing earlier cards')
        js("$('source-collection').scrollTop=0;document.querySelector('#source-grid .card').click();true")
        wait("Boolean(document.querySelector('#source-detail .detail-header')&&LALPreview.current)")
        assert not window.evaluate_js("Boolean(document.querySelector('#detail .detail-header'))")
        js('LALPreview.current.launch.click();true')
        wait('Boolean(LALPreview.current?.ready)', 60)
        capture('03-source-inspection-3d.png')
        assert '4 triangles' in window.evaluate_js('LALPreview.current.summary.textContent')
        js("(()=>{const preview=LALPreview.current;preview.message({source:preview.frame.contentWindow,data:{kind:'lal-3d',session:preview.session,type:'search'}});return true;})()")
        assert window.evaluate_js("document.activeElement===$('source-grid')")
        js('(async()=>{await LALPreview.current.enterFullscreen();return true;})()')
        wait('LALPreview.current.fullscreen&&!LALPreview.current.loadingText')
        capture('04-source-fullscreen.png')
        js('(async()=>{await LALPreview.current.exitFullscreen();return true;})()')
        report['checks'].append('Source cards reuse inspection, rendered 3D geometry and fullscreen preview; viewer find shortcut focuses the source grid')
        window.resize(680, 800)
        wait('innerWidth<761')
        assert window.evaluate_js('document.documentElement.scrollWidth<=innerWidth')
        capture('05-source-narrow.png')
        report['checks'].append('Narrow source layout has no horizontal overflow')
        js("$('close-source-browser').click();true")
        wait("!$('settings-view').hidden&&document.activeElement?.dataset.action==='browse'")
        assert not window.evaluate_js('Boolean(document.querySelector(".model-viewport iframe"))')
        assert not bridge._source_browser.sessions[one['key']][1].tickets
        js("document.querySelector('.source-browse-icon').click();true")
        wait("!$('source-browser-view').hidden&&state.sourceBrowse.items.length===40&&!state.sourceBrowse.loading")
        bridge.delay = True
        js("document.querySelector('#source-grid .card').click();true")
        assert bridge.entered.wait(10)
        js("$('close-source-browser').click();true")
        wait("!$('settings-view').hidden")
        bridge.delay = False
        bridge.unblock.set()
        time.sleep(.5)
        assert not window.evaluate_js('Boolean(LALPreview.current)')
        report['checks'].append('Icon navigation returns focus to source and releases preview; late detail cannot reopen it')
        js(f"(async()=>{{await openSourceBrowser({json.dumps(empty['key'])});return true;}})()")
        assert window.evaluate_js("!$('source-empty').hidden&&$('source-empty').textContent.includes('Scan and process')&&$('source-load-more').hidden")
        capture('06-unprocessed-source.png')
        report['checks'].append('Unprocessed source explains availability without scanning or offering a futile load action')
        js("$('close-source-browser').click();true")
        wait("!$('settings-view').hidden")
        js("$('close-settings').click();true")
        wait("!$('library-view').hidden")
        assert window.evaluate_js("$('query').value==='item0'&&state.lastSettings.query==='item0'&&savedLibraryCards.every((card,i)=>card===$('grid').children[i])")
        assert bridge._gateway.worker is None
        changed = [p for p, digest in saved.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
        assert not changed, changed
        report['checks'].append('Main query/results and all saved fixture inputs remain unchanged; no model worker loaded')
        report.update(status='passed', protected_files=len(saved))
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            capture('failure.png')
        except Exception:
            pass
    finally:
        bridge.unblock.set()
        (OUT / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['status'] == 'passed' else 1)
