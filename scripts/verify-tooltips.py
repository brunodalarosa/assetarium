"""Real WebView2 check that every visible control says what it does (a tooltip) or is marked self-explaining.

Walks Home (grid and filters), Library (inspector and folder panel), Asset processing, Collections, one collection,
Settings, the notifications and agent panels and every setup step. On each, every visible button, switch, tab,
checkbox and radio outside an open menu or listbox must carry `data-tooltip` or `data-no-tooltip` (set by the
primitives in frontend/src/ui/primitives.tsx). Form fields with a visible label (beUI Switch and Checkbox) and select
triggers, which show their value, count as labeled. Then one tooltip is opened by hover and one by keyboard focus.
Small isolated synthetic sources; no model or Blender run. Writes data/gui/<run-name>/report.json.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source
from local_asset_library import asset_collections, library_view, sources
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.incremental import working
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
library_view.blockers = lambda config: {}  # No Blender or search runtime here; nothing is processed.
ASSETS = [r['asset_id'] for r in sources.read_records(working(sources.bound(config, one)))]
COLLECTION = asset_collections.create(config, 'Tooltip check', 'Synthetic members for the tooltip audit.', ASSETS[:3], one['key'])['collection_id']


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False  # Never trigger startup scans or processing.
        return result


# Lists every visible control on screen that has neither marker; the audit fails on any.
AUDIT = r"""window.tipAudit=()=>{
  const shown=e=>e.getClientRects().length>0&&getComputedStyle(e).visibility!=='hidden'&&!e.closest('[aria-hidden=true],[inert]');
  const labeled=e=>(['switch','checkbox'].includes(e.getAttribute('role'))&&[...(e.labels||[])].some(l=>l.textContent.trim()))
    ||e.getAttribute('aria-haspopup')==='listbox';
  const controls=[...document.querySelectorAll('button,[role=button],[role=switch],[role=tab],[role=checkbox],[role=radio]')]
    .filter(e=>shown(e)&&!e.closest('[role=menu],[role=listbox]'));
  const missing=controls.filter(e=>!e.matches('[data-tooltip],[data-no-tooltip]')&&!labeled(e))
    .map(e=>[e.tagName.toLowerCase(),e.id,e.getAttribute('role'),e.getAttribute('aria-label'),e.textContent.trim().slice(0,40),String(e.className).slice(0,60)].filter(Boolean).join(' | '));
  return {controls:controls.length,tooltips:controls.filter(e=>e.matches('[data-tooltip]')).length,
    self_explaining:controls.filter(e=>e.matches('[data-no-tooltip]')).length,missing};
};
window.tipText=()=>[...document.querySelectorAll('[role=tooltip]')].map(t=>t.textContent.trim()).join(' / ');
true"""

os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': {}, 'audit': {}, 'synthetic_only': True, 'owner_visual_approval': 'pending'}
ui = Harness(window, OUT, report)
js = ui.js


def audit(screen, ready, shot=None):
    """Wait for the screen, then record and require a marker on every visible control."""
    js(f"until(()=>{ready},20000).then(()=>frame()).then(()=>new Promise(r=>setTimeout(r,250)))", 40)
    result = js('tipAudit()')
    report['audit'][screen] = result
    if shot:
        ui.capture(shot)
    assert result['controls'] > 0 and not result['missing'], {screen: result}


def verify():
    try:
        ui.wait_ready()
        js(AUDIT)
        js("(async()=>{await until(()=>lal.state.setup.open,3000).catch(()=>0);if(lal.state.setup.open)lal.closeSetup();await until(()=>!lal.state.setup.open);return true})()", 20)
        js("lal.navigate({page:'home'});lal.browse();true")
        audit('home', "document.querySelector('#results-grid .card, .card[data-id]')", '01-home.png')
        js("lal.setFiltersOpen(true);true")
        audit('home-filters', "$('apply-filters')")
        js("lal.setFiltersOpen(false);true")
        js(f"lal.openSources({json.dumps(one['key'])},'',{json.dumps(ASSETS[0])});lal.setInspectorOpen(true);true")
        audit('library-inspector', "document.querySelector('#detail .detail-header h2')&&document.querySelector('#sources-collection .card')", '02-library-inspector.png')
        js(f"lal.inspectFolder({json.dumps(one['key'])},'');true")
        audit('library-folder', "$('folder-panel')&&document.querySelector('[data-action=rescan]')", '03-library-folder.png')
        js("lal.navigate({page:'processing'});true")
        audit('processing', "$('processing-view')&&$('nothing-running')")
        js("lal.navigate({page:'collections'});true")
        audit('collections', "document.querySelector('.collection-card')")
        js(f"lal.openCollection({json.dumps(COLLECTION)});true")
        audit('collection', "$('collection-view')&&document.querySelector('#collection-grid .card')&&$('collection-select')", '04-collection.png')
        js("lal.navigate({page:'settings',tab:'general'});true")
        audit('settings', "$('save-general-settings')&&$('blender-status')", '05-settings.png')
        js("lal.setNotificationsOpen(true);true")
        audit('notifications', "$('notifications-read-all')")
        js("lal.setNotificationsOpen(false);lal.setAgentOpen(true);true")
        audit('agent-activity', "$('agent-activity-panel')")
        js("lal.setAgentOpen(false);true")
        js("(async()=>{await lal.openSetup();await until(()=>$('setup-wizard'));return true})()", 30)
        steps = js("lal.SETUP_STEPS")
        for index, step in enumerate(steps):
            js(f"lal.goToSetupStep({index});true")
            audit(f'setup-{step}', f"lal.state.setup.step==={index}&&!lal.state.setup.loading&&$('setup-step-title')", f'06-setup-{index}-{step}.png' if step in ('welcome', 'review') else None)
        js("lal.closeSetup();true")

        # A pointer resting on a control opens its tooltip after the delay; it says what the action does.
        js(f"lal.openSources({json.dumps(one['key'])},'');true")
        ui.check('hover_opens_the_tooltip', """until(()=>$('add-library-folder')).then(async()=>{const b=$('add-library-folder');
          b.dispatchEvent(new PointerEvent('pointerenter',{pointerId:1,pointerType:'mouse',buttons:0}));
          await until(()=>tipText(),8000);const text=tipText(),tip=document.querySelector('[role=tooltip]');
          const described=(b.getAttribute('aria-describedby')||'').split(' ').includes(tip.id);
          // Leaving starts a grace corridor toward the tooltip; moving well away from both closes it.
          b.dispatchEvent(new PointerEvent('pointerleave',{pointerId:1,pointerType:'mouse',buttons:0,clientX:0,clientY:0}));
          document.dispatchEvent(new PointerEvent('pointermove',{pointerId:1,pointerType:'mouse',clientX:2,clientY:innerHeight-2}));
          await until(()=>!tipText(),8000);
          return {opens:text.startsWith('Choose a folder of assets to add'),described,closes:!tipText()}})""", 40)
        # Focus that arrives by keyboard shows the tooltip at once and names it as the control's description.
        ui.check('keyboard_focus_opens_the_tooltip', """(async()=>{const chip=$('status-failed');
          window.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true}));chip.focus();
          await until(()=>tipText(),4000);const text=tipText(),tip=document.querySelector('[role=tooltip]');
          const described=(chip.getAttribute('aria-describedby')||'').split(' ').includes(tip.id);
          await frame();return {opens:text==='Shows only assets with a recorded failure',described}})()""", 30)
        ui.capture('07-keyboard-tooltip.png')
        js("document.activeElement.blur();true")
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture('failure.png')
        except Exception:
            pass
    finally:
        (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        bridge._allow_close = True
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
bridge._close()
record_profile_outcome(bridge, profile)
print(json.dumps({k: v for k, v in report.items() if k != 'traceback'}, indent=2))
raise SystemExit(0 if report['status'] == 'passed' else 1)
