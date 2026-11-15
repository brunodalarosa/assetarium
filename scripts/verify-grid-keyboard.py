"""Verify the asset grid's keyboard model and folder-tree Space in the real WebView2 shell with a synthetic pack.

The grid is one Tab stop (roving tabindex): Tab enters at the last focused card, reaches only that card's variant
chips and leaves; arrows move focus and keep the default at an edge so the page scrolls; the grid is a named group and
cards claim no popup. Folder-tree Space acts on keyup, Enter on keydown. Keys are real browser input (DevTools
Input.dispatchKeyEvent), so Tab moves focus as a user's would. Writes data/gui/<run-name>/verification.json.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed  # noqa: E402
from local_asset_library import sources  # noqa: E402
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
config, _, one, two = managed.__wrapped__(fixture)
root = fixture / 'library'
yard = root / 'Kit_1.0' / 'Yard'
yard.mkdir(parents=True)
for name in ('Car_11_R', 'Car_11_G', 'Car_11_B', 'Barrel', 'Bench', 'Cart', 'Crate', 'Fence', 'Lamp', 'Sign', 'Tree', 'Well'):
    (yard / f'{name}.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
(root / 'Kit_1.0' / 'License.txt').write_text('CC0')
added = sources.add(config, str(root))
sources.scan_source(config, added)
KEY = added['key']
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


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
CARDS = "[...$('sources-grid').querySelectorAll('.card')]"
ROW = "document.querySelector('#folder-tree [role=treeitem][data-path=\"Kit_1.0\"]')"
KEYS = {'Tab': ('Tab', 9), ' ': ('Space', 32), 'Enter': ('Enter', 13), 'ArrowRight': ('ArrowRight', 39),
        'ArrowDown': ('ArrowDown', 40), 'End': ('End', 35)}


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def browser_input(method, parameters):
    """Dispatch actual WebView2 input (trusted events with their default actions, such as Tab moving focus)."""
    from System import Action
    from System.Threading.Tasks import Task
    form = window.gui.BrowserView.instances[window.uid]
    done, errors = threading.Event(), []
    def start():
        task = form.browser.webview.CoreWebView2.CallDevToolsProtocolMethodAsync(method, json.dumps(parameters))
        def finish(task):
            if task.IsFaulted:
                errors.append(str(task.Exception))
            done.set()
        task.ContinueWith(Action[Task](finish), form.browser.syncContextTaskScheduler)
    form.Invoke(Action(start))
    assert done.wait(15) and not errors, errors


def key(name, shift=False, down=True, up=True):
    code, vk = KEYS[name]
    common = dict(key=name, code=code, windowsVirtualKeyCode=vk, modifiers=8 if shift else 0)
    if down:
        browser_input('Input.dispatchKeyEvent', dict(common, type='rawKeyDown'))
    if up:
        browser_input('Input.dispatchKeyEvent', dict(common, type='keyUp'))
    ui.js('frame()')


def focus_state():
    """Where focus is: the card index, a chip of which card, or outside the grid; and which cards take Tab."""
    return ui.js(f"""(()=>{{const cards={CARDS},a=document.activeElement,wrap=a?.closest('.card-wrap');
      return {{card:cards.indexOf(a),chip:a?.getAttribute('role')==='radio'&&wrap?cards.indexOf(wrap.querySelector('.card')):-1,
        inGrid:!!a?.closest('#sources-grid'),stops:cards.map((c,i)=>c.tabIndex===0?i:-1).filter(i=>i>=0),
        chipStops:[...$('sources-grid').querySelectorAll('.variant-chips [role=radio]')].filter(c=>c.tabIndex===0).length}}}})()""")


def tab_into_grid():
    """From the folder tree, press Tab until focus enters the grid, as a keyboard user does."""
    ui.js(f"{ROW}.focus()")
    for _ in range(80):
        key('Tab')
        state = focus_state()
        if state['inGrid']:
            return state
    raise AssertionError('Tab never reached the grid')


def prevented(index, name):
    return ui.js(f"(()=>{{const c={CARDS}[{index}];c.focus();return !c.dispatchEvent(new KeyboardEvent('keydown',{{key:'{name}',bubbles:true,cancelable:true}}))}})()")


def verify():
    try:
        ui.wait_ready()
        ui.js("(async()=>{await until(()=>lal.state.setup.open,3000).catch(()=>0);if(lal.state.setup.open)lal.closeSetup();await until(()=>!lal.state.setup.open);return true})()")
        ui.js("(async()=>{$('nav-sources').click();await until(()=>lal.state.sourcesView.tree);return true})()")
        ui.js(f"lal.inspectFolder({json.dumps(KEY)},'Kit_1.0/Yard')")
        wait(f"{CARDS}.length===10&&$('sources-grid').getAttribute('aria-busy')==='false'&&{ROW}")
        # The folder's own panel narrows the grid to one column; hidden, the cards form rows.
        ui.js("lal.setInspectorOpen(false)")
        wait("getComputedStyle($('sources-grid')).gridTemplateColumns.split(' ').length>2")
        roles = ui.js(f"({{role:$('sources-grid').getAttribute('role'),name:$('sources-grid').getAttribute('aria-label'),"
                      f"popup:{CARDS}.filter(c=>c.hasAttribute('aria-haspopup')).length,columns:getComputedStyle($('sources-grid')).gridTemplateColumns.split(' ').length}})")
        assert roles['role'] == 'group' and roles['name'] == 'Asset results' and roles['popup'] == 0, roles
        columns = roles['columns']
        assert 1 < columns < 10, roles
        report['columns'] = columns
        report['checks'].append('The grid is role=group named "Asset results"; no card has aria-haspopup')
        state = focus_state()
        assert state['stops'] == [0], state
        state = tab_into_grid()
        assert state['card'] == 0 and state['stops'] == [0], state
        report['checks'].append('Exactly one card has tabIndex=0 (the first); Tab from the folder tree enters the grid on it')
        key('ArrowRight')
        state = focus_state()
        assert state['card'] == 1 and state['stops'] == [1], state
        key('ArrowDown')
        state = focus_state()
        assert state['card'] == 1 + columns and state['stops'] == [1 + columns], state
        report['checks'].append('Real ArrowRight then ArrowDown move focus by one card and one row; only the focused card keeps tabIndex=0')
        variant = ui.js(f"{CARDS}.findIndex(c=>c.closest('.card-wrap').querySelector('.variant-badge'))")
        assert variant >= 0 and variant != 1 + columns, variant
        assert state['chipStops'] == 0, state
        key('Tab')
        state = focus_state()
        assert not state['inGrid'], state
        report['checks'].append('The next Tab leaves the grid; a card without variants has no chips in the Tab order, nor do inactive cards')
        state = tab_into_grid()
        assert state['card'] == 1 + columns, state
        report['checks'].append('Tab back into the grid lands on the last focused card')
        ui.capture('01-focused-card.png')
        ui.js(f"{CARDS}[{variant}].focus()")
        wait(f"{CARDS}[{variant}].tabIndex===0")
        state = focus_state()
        assert state['stops'] == [variant] and state['chipStops'] == 1, state
        key('Tab')
        state = focus_state()
        assert state['chip'] == variant, state
        key('Tab')
        assert not focus_state()['inGrid']
        key('Tab', shift=True)
        key('Tab', shift=True)
        assert focus_state()['card'] == variant
        report['checks'].append("Tab from the active variant card reaches its checked chip, then leaves the grid; Shift+Tab returns")
        edges = {'first ArrowLeft': prevented(0, 'ArrowLeft'), 'first ArrowUp': prevented(0, 'ArrowUp'), 'first Home': prevented(0, 'Home'),
                 'last ArrowRight': prevented(9, 'ArrowRight'), 'last ArrowDown': prevented(9, 'ArrowDown'), 'last End': prevented(9, 'End')}
        assert not any(edges.values()), edges
        inside = {'first ArrowRight': prevented(0, 'ArrowRight'), 'first ArrowDown': prevented(0, 'ArrowDown'), 'last ArrowLeft': prevented(9, 'ArrowLeft')}
        assert all(inside.values()), inside
        report['edges'] = {'not_prevented_at_edge': edges, 'prevented_inside': inside}
        report['checks'].append('An arrow (or Home/End) with no card that way keeps its default so the page scrolls; inside the grid it is prevented')
        # Thumbnails load as cards come into view and change card heights; let them settle first.
        ui.js(f"{CARDS}.forEach(c=>c.focus())")
        wait(f"{CARDS}.every(c=>!c.querySelector('.thumb-loading'))")
        ui.js(f"{CARDS}[0].focus()")
        ui.js("frame()")
        key('End')
        visible = ui.js(f"""(async()=>{{const c={CARDS}[9];let p=c.parentElement;
          while(p&&!(p.scrollHeight>p.clientHeight&&/(auto|scroll)/.test(getComputedStyle(p).overflowY)))p=p.parentElement;
          const seen=()=>{{const r=c.getBoundingClientRect(),v=p?p.getBoundingClientRect():{{top:0,bottom:innerHeight}};
            return r.top>=Math.max(0,v.top)-1&&r.bottom<=Math.min(innerHeight,v.bottom)+1}};
          await until(seen,2000).catch(()=>0);const r=c.getBoundingClientRect(),v=p?.getBoundingClientRect();
          return {{focused:document.activeElement===c,inView:seen(),card:[r.top,r.bottom],scroller:p&&[p.id||p.className.slice(0,40),v.top,v.bottom,p.scrollTop,p.scrollHeight-p.clientHeight],inner:innerHeight}}}})()""")
        assert visible['focused'] and visible['inView'], visible
        report['checks'].append('End focuses the last card and scrolls it into view')
        ui.js(f"{CARDS}[0].click()")
        wait("lal.state.inspector.open&&lal.state.source.selected")
        first = ui.js("lal.state.source.selected")
        ui.js(f"{CARDS}[0].focus()")
        key('ArrowRight')
        wait(f"lal.state.source.selected!=={json.dumps(first)}&&lal.state.source.selected==={CARDS}[1].dataset.id")
        assert focus_state()['stops'] == [1]
        report['checks'].append('With the inspector open, a real ArrowRight selects the card it moves to (selection follows arrows)')
        ui.capture('02-inspector-follow.png')
        ui.js(f"{ROW}.focus()")
        key(' ', up=False)
        held = ui.js("lal.state.sourcesView.path")
        key(' ', down=False)
        wait("lal.state.sourcesView.path==='Kit_1.0'")
        assert held == 'Kit_1.0/Yard', held
        ui.js(f"lal.inspectFolder({json.dumps(KEY)},'Kit_1.0/Yard')")
        wait("lal.state.sourcesView.path==='Kit_1.0/Yard'")
        wait(f"{ROW}")
        ui.js(f"{ROW}.focus()")
        key('Enter', up=False)
        wait("lal.state.sourcesView.path==='Kit_1.0'")
        key('Enter', down=False)
        report['checks'].append('Folder tree: Space keydown does nothing, its keyup opens the folder; Enter opens it on keydown')
        assert not bridge._gateway.model_requested
        now = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        assert now == originals
        report['checks'].append('Original files are byte-identical; no inference worker or model was loaded')
        report.update(status='passed')
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
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
