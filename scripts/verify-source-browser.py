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
from gui_harness import Harness

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
parser.add_argument('--kaykit-regressions', action='store_true')
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
pending_id = None
if args.kaykit_regressions:
    from local_asset_library.incremental import working, update_record
    from local_asset_library.membership import records
    from local_asset_library.source_operations import publish_source
    # Reproduce oversized optional evidence on the first browsed source card.
    scope = sources.bound(config, one)
    record = next(r for r in records(working(scope)) if r['display_name'] == 'extra00')
    record['inspection_run'] = {'source_faults': [], 'errors': ['Synthetic optional evidence ' * 1600]}
    update_record(working(scope), record)
    publish_source(scope)
    # A different source has a genuinely unattempted preview, not a failure.
    scope = sources.bound(config, two)
    record = next(r for r in records(working(scope)) if r['display_name'] == 'item1')
    pending_id = record['asset_id']
    record.update(technical=None, previews=[], description=None, caption_provenance=None, inspection_run=None)
    record['processing'].update(inspection='pending', previews='pending', caption='pending', embeddings='pending')
    update_record(working(scope), record)
    publish_source(scope)
    sources.aggregate(config)
    sources.scan_source(config, one)
    sources.scan_source(config, two)
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


ui = Harness(window, OUT, report)


def wait(expression, timeout=30):
    try:
        ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)
    except RuntimeError as exc:
        raise RuntimeError('UI condition timed out: ' + expression + ' ' + str(ui.js(
            "({main:$('error')?.textContent,source:$('source-browser-error')?.textContent})"))) from exc


js = ui.js
capture = ui.capture
SOURCE_READY = "$('source-browser-view')&&lal.state.source.items.length===40&&!lal.state.source.loading"


def verify():
    try:
        ui.wait_ready(extra='lal.state.sources.length===3')
        js("(async()=>{await lal.submitSearch();await until(()=>lal.state.library.items.length===3);return true})()")
        if args.kaykit_regressions:
            selector = '#grid .card[data-id="' + pending_id + '"]'
            wait('Boolean(document.querySelector(' + json.dumps(selector) + ')?.textContent.includes("Preview pending"))')
            assert not js('document.querySelector(' + json.dumps(selector) + ').textContent.includes("Preview fault")')
            report['checks'].append('Never-generated preview is labeled pending without a false preview-fault badge')
        js("""(async()=>{lal.setState({filters:{...lal.state.filters,mode:'keyword'}});lal.setQuery('item0');await lal.submitSearch();
          window.savedLibraryIds=[...$('grid').children].map(c=>c.dataset.id);return true})()""")
        js("(async()=>{$('nav-settings').click();await until(()=>$('asset-sources-tab'));$('asset-sources-tab').click();return true})()")
        wait("$('settings-view')&&document.querySelectorAll('.source-browse-link').length===3")
        capture('01-source-links.png')
        assert js("document.querySelector('.source-browse-link').getAttribute('aria-label').includes('Browse assets')")
        # Clicking the label and icon follows the same button action.
        js("document.querySelector('.source-browse-link span:first-child').click()")
        wait(SOURCE_READY)
        wait("document.querySelectorAll('#source-grid .thumb img').length>=4")
        assert js("$('source-browser-status').textContent.includes('51 saved assets')&&$('source-browser-status').textContent.includes('Disabled')")
        assert js("!$('search-form')")
        assert js("$('source-browser-view').scrollHeight>$('source-browser-view').clientHeight")
        capture('02-disabled-source-grid.png')
        report['checks'].append('Name opens disabled source with 51 saved assets, its own scroll area and no search form')
        js("$('source-browser-view').scrollTop=$('source-browser-view').scrollHeight")
        wait('lal.state.source.items.length===51&&!lal.state.source.loading')
        assert js("new Set([...$('source-grid').children].map(x=>x.dataset.id)).size===51&&!$('source-load-more')")
        report['checks'].append('Scrolling loads the final batch without duplicates or losing earlier cards')
        js("$('source-browser-view').scrollTop=0;document.querySelector('#source-grid .card').click()")
        wait("Boolean(document.querySelector('#inspector .detail-header')&&window.LALPreview.current&&!lal.state.source.detail.loading)")
        if args.kaykit_regressions:
            assert js('!LALPreview.current.launch.disabled&&Boolean(LALPreview.current.item.image)')
            assert not js("$('detail').textContent.includes('deterministic cap')||$('detail').textContent.includes('No verified source')")
            report['checks'].append('Large optional metadata preserves detail image, verified source and enabled interactive preview')
        assert js("lal.state.library.selected===null&&lal.state.source.selected!==null")
        js('LALPreview.current.launch.click()')
        wait('Boolean(LALPreview.current?.ready)', 60)
        capture('03-source-inspection-3d.png')
        assert '4 triangles' in js('LALPreview.current.summary.textContent')
        js("(()=>{const preview=LALPreview.current;preview.message({source:preview.frame.contentWindow,data:{kind:'lal-3d',session:preview.session,type:'search'}});return true;})()")
        assert js("document.activeElement===$('source-grid')")
        js('(async()=>{await LALPreview.current.enterFullscreen();return true;})()')
        wait('LALPreview.current.fullscreen&&!LALPreview.current.loadingText')
        capture('04-source-fullscreen.png')
        js('(async()=>{await LALPreview.current.exitFullscreen();return true;})()')
        report['checks'].append('Source cards reuse inspection, rendered 3D geometry and fullscreen preview; viewer find shortcut focuses the source grid')
        window.resize(680, 800)
        wait('innerWidth<761')
        assert js("$('source-browser-view').scrollWidth<=$('source-browser-view').clientWidth+1")
        capture('05-source-narrow.png')
        report['checks'].append('Narrow source layout has no horizontal overflow; inspection floats over the grid')
        js("$('close-source-browser').click()")
        wait("$('settings-view')&&document.activeElement?.dataset.action==='browse'&&document.activeElement?.dataset.source===" + json.dumps(one['key']))
        assert not js('Boolean(document.querySelector(".model-viewport iframe"))')
        assert not bridge._source_browser.sessions[one['key']][1].tickets
        js("document.querySelector('.source-browse-icon').click()")
        wait(SOURCE_READY)
        bridge.delay = True
        js("document.querySelector('#source-grid .card').click()")
        assert bridge.entered.wait(10)
        js("$('close-source-browser').click()")
        wait("$('settings-view')")
        bridge.delay = False
        bridge.unblock.set()
        time.sleep(.5)
        assert not js('Boolean(LALPreview.current)')
        report['checks'].append('Icon navigation returns focus to source and releases preview; late detail cannot reopen it')
        js(f"(async()=>{{lal.navigate({{page:'source',key:{json.dumps(empty['key'])}}});await until(()=>$('source-empty'));return true;}})()")
        assert js("$('source-empty').textContent.includes('Scan and process')&&!$('source-load-more')")
        capture('06-unprocessed-source.png')
        report['checks'].append('Unprocessed source explains availability without scanning or offering a futile load action')
        js("$('close-source-browser').click()")
        wait("$('settings-view')")
        js("$('nav-home').click()")
        wait("$('library-view')&&document.querySelectorAll('#grid .card').length===savedLibraryIds.length")
        assert js("$('query').value==='item0'&&lal.state.search.lastSettings.query==='item0'&&savedLibraryIds.every((id,i)=>id===$('grid').children[i].dataset.id)")
        assert not bridge._gateway.model_requested
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
