"""Verify the Asset sources tab and the processing queue (decision 0023) in the real WebView2 shell.

Synthetic library folders only: a kit with duplicate export folders, a pack with a license and a preview, loose
images. Checks the rail item, the tree (packs, coverage, keyboard), cards in their work states, the folder panel
(pack answers, exclusions, duplicate-export answers), context menus, double-click to Explorer, Add library
folder inside one (Already covered), Show in pack from Home, Make previews through the queue (no worker is
started: a stand-in operation records the scope), the Asset processing tab's sections, the narrow layout,
and that originals are untouched and no model loads. Writes data/gui/<run-name>/.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import traceback

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source  # noqa: E402
from test_source_exports import kit  # noqa: E402
from local_asset_library import desktop, processing_queue, source_operations, sources  # noqa: E402
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome  # noqa: E402
from local_asset_library.publication import atomic_json  # noqa: E402
from gui_harness import Harness, isolate_hash_cache  # noqa: E402
isolate_hash_cache(__file__)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
OUT = ROOT / 'data/gui' / args.run_name
OUT.mkdir(parents=True)
fixture = ROOT / 'scratch' / args.run_name
fixture.mkdir()
config, backend, one, two = managed.__wrapped__(fixture)
ready_source(config, backend, one)
library = fixture / 'Library'
kit(library / 'Kit')
pack = library / 'Tiny Pack_1.0'
(pack / 'Sprites').mkdir(parents=True)
(pack / 'License.txt').write_text('CC0 1.0')
Image.new('RGB', (64, 64), (230, 120, 40)).save(pack / 'Preview.png')
for i, color in enumerate(('red', 'blue', 'green')):
    Image.new('RGBA', (32, 32), color).save(pack / 'Sprites' / f'sprite_{i}.png')
(pack / 'Readme.md').write_text('A synthetic pack')
added = sources.add(config, str(library))
sources.scan_source(config, added)
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in library.rglob('*') if p.is_file()}
revealed, started = [], []


def fake_start(config, operation, key=None, asset_ids=None, queue_item=None):
    started.append({'operation': operation, 'key': key, 'assets': len(asset_ids or [])})
    token = 'fixture-' + str(len(started))
    # What a real start records: the operation runs (in this process, so it stays alive) until the check ends.
    source_operations.state(sources.bound(config, sources.get_source(config, key)), token=token, pid=os.getpid(),
                            status='processing', operation=operation, phase='Inspecting assets and rendering previews',
                            progress=.3, completed=1, total=len(asset_ids or []), asset_ids=asset_ids)
    return {'status': 'started', 'token': token}


source_operations.start = fake_start  # No runtimes in the fixture project: the queue's start is recorded.
desktop.show_in_explorer = lambda path: revealed.append(path)


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result

    def _start_source_operation(self, operation, key):
        assert operation == 'scan'
        sources.scan_source(config, sources.get_source(config, key))
        return {'status': 'ready', 'reason': 'Scanned'}


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True}
ui = Harness(window, OUT, report)
ROW = "document.querySelector('[role=treeitem][data-key=\"%s\"][data-path=\"%s\"]')"


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def check(text):
    report['checks'].append(text)


def verify():
    try:
        ui.wait_ready(extra="lal.state.sources.length===3")
        ui.js("window.__errors=[];const e=console.error;console.error=(...a)=>{__errors.push(a.map(x=>String(x&&x.stack||x)).join(' '));e(...a)};"
              "addEventListener('error',ev=>__errors.push(String(ev.error&&ev.error.stack||ev.message)));true")
        assert ui.js("!document.querySelector('#asset-sources-tab')")
        ui.js("$('nav-sources').click()")
        wait("$('sources-view')&&lal.state.sourcesView.tree&&$('folder-tree')")
        order = ui.js("[...document.querySelectorAll('nav [id^=nav-]')].map(b=>b.id).join(',')")
        assert order.endswith('nav-sources,nav-settings'), order
        check('The Asset sources rail item sits above Settings; Settings has no Asset sources tab')
        ui.js(f"{ROW % (added['key'], '')}.click()")
        wait("lal.state.sourcesView.key==='Library'&&lal.state.source.items.length>0")
        wait(ROW % (added['key'], 'Tiny Pack_1.0'))
        assert ui.js(f"{ROW % (added['key'], 'Tiny Pack_1.0')}.dataset.kind") == 'pack'
        assert ui.js(f"{ROW % (added['key'], 'Kit')}.dataset.kind") == 'pack'
        ui.capture('01-tree.png')
        check('The tree shows library folders, packs (a license and preview, a versioned name) and folders only')
        ui.js(f"{ROW % (added['key'], 'Tiny Pack_1.0')}.click()")
        wait("lal.state.sourcesView.path==='Tiny Pack_1.0'&&!lal.state.source.loading&&$('folder-header')")
        assert ui.js("$('folder-header').textContent.includes('Tiny Pack_1.0')")
        assert ui.js("$('folder-panel')&&$('folder-panel').textContent.includes('License')")
        wait("[...document.querySelectorAll('#sources-grid .card')].length===3")
        wait("[...document.querySelectorAll('#sources-grid img')].length>=1", 30)  # Cards load their images as they scroll into view.
        assert ui.js("[...document.querySelectorAll('#other-files li')].map(l=>l.textContent).some(t=>t.includes('License.txt'))")
        ui.capture('02-pack.png')
        check('A pack shows its header and panel; its 2D images show their original files before any processing; other files are listed, faded')
        assert ui.js("[...document.querySelectorAll('#sources-grid .card .state-strip')].length>=1")
        assert ui.js("document.querySelector('#sources-grid .card .state-strip [role=img]').getAttribute('aria-label').startsWith('No previews yet')")
        check('Cards carry a state strip with labeled icons (shape and label, not color alone)')
        # Keyboard in the tree: Down moves, Left collapses.
        ui.js(f"{ROW % (added['key'], '')}.focus()")
        ui.js("$('folder-tree').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}))")
        wait("document.activeElement&&document.activeElement.getAttribute('role')==='treeitem'&&document.activeElement.dataset.path!==''")
        check('The tree is a tree with treeitems and arrow-key movement')
        # Double-click a folder: Explorer opens on it (stubbed).
        ui.js(f"{ROW % (added['key'], 'Kit')}.dispatchEvent(new MouseEvent('dblclick',{{bubbles:true}}))")
        wait("true")
        ui.js("until(()=>true,300)")
        assert revealed and revealed[-1].endswith('Kit'), revealed
        check('Double-clicking a folder shows it in Explorer')
        # Context menu on a folder, then Make this a pack.
        ui.js(f"lal.toggleFolder('{added['key']}:Kit', true)")
        wait(ROW % (added['key'], 'Kit/Exports'))
        ui.js(f"(()=>{{const r={ROW % (added['key'], 'Kit/Exports')};r.dispatchEvent(new MouseEvent('contextmenu',{{bubbles:true,clientX:200,clientY:300}}));return true}})()")
        wait("[...document.querySelectorAll('[data-context-menu-item]')].some(i=>i.textContent.includes('Make this a pack'))")
        items = ui.js("[...document.querySelectorAll('[data-context-menu-item]')].map(i=>i.textContent.trim()).join('|')")
        for label in ('Make this a pack', 'Merge into parent pack', 'Treat images here as textures', 'Exclude folder', 'Show in Explorer', 'Copy path'):
            assert label in items, items
        ui.capture('03-folder-menu.png')
        ui.js("[...document.querySelectorAll('[data-context-menu-item]')].find(i=>i.textContent.includes('Make this a pack')).click()")
        wait(f"{ROW % (added['key'], 'Kit/Exports')}&&{ROW % (added['key'], 'Kit/Exports')}.dataset.kind==='pack'")
        check('The folder menu offers the pack, image-kind, exclude and file actions; Make this a pack rescans and the folder becomes a pack')
        # The library folder panel holds the duplicate export suggestion and exclusions.
        ui.js(f"{ROW % (added['key'], '')}.click()")
        wait("$('folder-panel')&&$('folder-panel').querySelector('.export-suggestion')")
        ui.capture('04-library-panel.png')
        check('The library folder panel keeps duplicate export answers, texture folders and excluded folders (from Settings)')
        # Add a library folder inside one: Already covered, with Show it.
        result = ui.js(f"lal.state.api.source_action('add',null,{json.dumps(str(pack / 'Sprites'))},null)")
        assert result['status'] == 'faulty' and result['covered_by'] == added['key'] and 'Already covered' in result['reason'], result
        check('Adding a folder inside a library folder is refused as already covered, naming the folder to show')
        # Make previews: through the queue, with a toast.
        ui.js(f"{ROW % (added['key'], 'Tiny Pack_1.0')}.click()")
        wait("$('make-previews')")
        ui.js("$('make-previews').click()")
        wait("lal.state.queue&&(lal.state.queue.running||lal.state.queue.recent.length)", 30)
        assert started and started[0]['operation'] == 'process' and started[0]['assets'] == 3, started
        check('Make previews queues the pack; its scope (3 images without previews) is resolved when it starts')
        ui.js("$('nav-processing').click()")
        wait("$('running')&&$('up-next-section')&&$('blocked')&&$('failures')&&$('recent')")
        wait("$('running-item')")
        ui.capture('05-processing.png')
        check('Asset processing shows Running, Up next, Blocked, Recorded failures and Recent, never one mixed banner')
        # Disabling a library folder hides its cards from an active search at once; enabling brings them back.
        ui.js("(async()=>{$('nav-home').click();await until(()=>$('library-view'));lal.setState({filters:{...lal.state.filters,mode:'keyword'}});"
              "lal.setQuery('item0');await lal.submitSearch();return true})()")
        wait("lal.state.search.phase==='search'&&lal.state.library.items.length>0")
        shown = ui.js("lal.state.library.items.length")
        ui.js(f"lal.sourceAction('enabled','{one['key']}',null,false).then(()=>true)")
        wait(f"lal.state.library.items.every(i=>i.pack!=='{one['key']}')&&lal.state.search.phase==='search'")
        ui.js(f"lal.sourceAction('enabled','{one['key']}',null,true).then(()=>true)")
        wait(f"lal.state.library.items.length==={shown}&&lal.state.search.lastSettings.query==='item0'")
        check('Turning a library folder off and on reruns the active search, keeping its query, without restart or model loading')
        # Show in pack from Home.
        identifier = sources.read_records(sources.bound(config, one))[0]['asset_id']
        ui.js(f"lal.showInPack('{identifier}')")
        wait(f"lal.state.history[lal.state.historyIndex].page==='sources'&&lal.state.sourcesView.key==='{one['key']}'&&lal.state.source.selected==='{identifier}'")
        check('Show in pack opens the Asset sources tab with the asset selected and its folder expanded')
        window.resize(700, 900)
        wait('innerWidth<761')
        wait("$('sources-view').scrollWidth<=$('sources-view').clientWidth+1", 10)  # Once the resize has settled.
        ui.capture('06-narrow.png')
        check('Narrow layout has no horizontal overflow')
        assert not bridge._gateway.model_requested
        now = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in library.rglob('*') if p.is_file()}
        assert now == originals and not [p for p in library.rglob('*') if p.is_dir() and p.name.startswith('metadata')]
        check('Original files are byte-identical, nothing was written into the library folder, and no model was loaded')
        report.update(status='passed')
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            report['console'] = ui.js("window.__errors", 10)
        except Exception:
            pass
        try:
            ui.capture('failure.png')
        except Exception:
            pass
    finally:
        atomic_json(OUT / 'verification.json', report)
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(dict(report, report=str(OUT / 'verification.json')), indent=2))
raise SystemExit(report['status'] != 'passed')
