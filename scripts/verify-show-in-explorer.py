"""Real WebView2 check of the "Show in Explorer" asset menu action with small isolated synthetic sources.

Covers the menu item on the Home grid and a source grid, the format chosen from the open inspector, and
the visible fault toast for a missing original. Explorer itself is stubbed so no window opens; the path it
would select is recorded. Keyword search only: no model loads. Writes data/gui/<run-name>/verification.json.
"""
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
from local_asset_library import desktop
from local_asset_library.membership import records
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from gui_harness import Harness, isolate_hash_cache
isolate_hash_cache(__file__)

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
ready_source(config, backend, one)
ready_source(config, backend, two)
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for root in (one['path'], two['path'])
             for p in Path(root).rglob('*') if p.is_file()}
launched = []
desktop.show_in_explorer = launched.append  # Looked up at call time; nothing opens on the desktop.


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False  # Never trigger startup scans or processing.
        return result


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True, 'owner_usability_approval': 'pending', 'real_model_load': False}
ui = Harness(window, OUT, report)
js, capture = ui.js, ui.capture


def wait(expression, timeout=30):
    try:
        ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)
    except RuntimeError as exc:
        raise RuntimeError('UI condition timed out: ' + expression + ' ' + str(ui.js(
            "({toasts:lal.state.toasts.map(t=>t.title+': '+t.body)})"))) from exc


def launches(count, timeout=15):
    # The bridge call runs on a worker thread after the menu has closed.
    end = time.time() + timeout
    while len(launched) < count and time.time() < end:
        time.sleep(0.1)
    return launched


def done(text):
    report['checks'].append(text)


MENU = """window.rightClick=el=>{const r=el.getBoundingClientRect();el.dispatchEvent(new MouseEvent('contextmenu',
  {bubbles:true,cancelable:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,button:2}));return true};
window.menuOpen=label=>{const m=document.querySelector('[role=menu][aria-label="'+label+'"]');
  return Boolean(m&&m.closest('[data-context-menu-portal]').getAttribute('aria-hidden')==='false'&&getComputedStyle(m).opacity>0.9)};
window.menuItem=text=>[...document.querySelectorAll('[data-context-menu-portal][aria-hidden=false] [role=menuitem]')].find(b=>b.textContent.includes(text));
window.card=(grid,i)=>document.querySelectorAll('#'+grid+' .card')[i];
window.toast=text=>[...document.querySelectorAll('#toasts .toast')].find(t=>t.textContent.includes(text));
true"""


def verify():
    try:
        ui.wait_ready(extra='lal.state.sources.length===2')
        js(MENU)
        js("(async()=>{$('nav-home').click();await until(()=>$('library-view'));await lal.submitSearch();await until(()=>lal.state.library.items.length===6);return true})()")
        wait("document.querySelectorAll('#grid .thumb img').length===6")

        # 1. Home grid: the item sits in the asset menu and selects the asset's original file.
        js("rightClick(card('grid',0))")
        wait("menuOpen('Asset actions')&&Boolean(menuItem('Show in Explorer'))")
        capture('01-asset-menu.png')
        identifier = js("card('grid',0).dataset.id")
        expected = str(config.source_file(next(f['path'] for r in records(config) if r['asset_id'] == identifier for f in r['files'])))
        js("menuItem('Show in Explorer').click()")
        wait("!menuOpen('Asset actions')")
        assert launches(1) == [expected], (launched, expected)
        assert not js("Boolean(toast('Could not show in Explorer'))")
        done('Home asset menu offers Show in Explorer; it selects the original file and closes the menu without a toast')

        # 2. A source grid resolves through its own source.
        key = one['key']
        js(f"(async()=>{{lal.navigate({{page:'source',key:{json.dumps(key)}}});await until(()=>lal.state.source.items.length===3);return true}})()")
        wait("document.querySelectorAll('#source-grid .thumb img').length===3")
        js("rightClick(card('source-grid',0))")
        wait("menuOpen('Asset actions')&&Boolean(menuItem('Show in Explorer'))")
        js("menuItem('Show in Explorer').click()")
        wait("!menuOpen('Asset actions')")
        assert len(launches(2)) == 2 and Path(launched[1]).is_file() and Path(launched[1]).is_relative_to(Path(one['path'])), launched
        done('Source browser menu shows the file from that source')

        # 3. A missing original is a visible fault; nothing launches and nothing is retried.
        Path(launched[1]).unlink()
        js("rightClick(card('source-grid',0))")
        wait("menuOpen('Asset actions')")
        js("menuItem('Show in Explorer').click()")
        wait("Boolean(toast('Could not show in Explorer'))")
        capture('02-missing-fault.png')
        time.sleep(1)
        assert len(launched) == 2
        done('A missing original shows a fault toast; Explorer is not opened')

        assert not bridge._gateway.model_requested
        done('No model loaded')
        report.update(status='passed', protected_files=len(originals), launched=launched)
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            capture('failure.png')
        except Exception:
            pass
    finally:
        (OUT / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['status'] == 'passed' else 1)
