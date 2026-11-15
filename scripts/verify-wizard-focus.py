"""Verify that the add-folder wizard and setup keep keyboard focus, in the real WebView2 shell with a synthetic library.

Uses real key input (DevTools Input.dispatchKeyEvent), since synthetic KeyboardEvents never move focus: the wizard
opened with Enter puts focus on its title, the app behind is inert, Tab and Shift+Tab stay inside on the What we found
and Finish steps, and focus returns to Add library folder on Escape (close) and on Minimize. Setup opened from Settings
puts focus on its step title. Writes data/gui/<run-name>/verification.json.
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
root = fixture / 'Game Assets'
# Props repeats FBX for Unity, so it needs a structure and the Finish step stays open (no agent connects here).
for name in (['Kit/License.txt'] + [f'Kit/Rocks/Rock_{n:02}.obj' for n in range(1, 4)] + ['Props/readme.txt']
             + [f'Props/{d}/{m}.obj' for d in ('FBX', 'Unity FBX') for m in ('Barrel', 'Crate', 'Door')]):
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n' if name.endswith('.obj') else 'CC0')


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result

    def choose_source_directory(self):
        return {'status': 'selected', 'directory': str(root)}  # The folder dialog, answered.

    def _start_source_operation(self, operation, key):
        assert operation == 'scan'
        sources.scan_source(config, sources.get_source(config, key))
        return {'status': 'ready', 'reason': 'Scanned'}


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': {}, 'synthetic_only': True}
ui = Harness(window, OUT, report)
WIZARD = "$('add-folder-wizard')"
KEYS = {'Tab': ('Tab', 9), 'Enter': ('Enter', 13), 'Escape': ('Escape', 27)}


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def browser_input(method, parameters):
    """Dispatch actual WebView2 input through the DevTools protocol."""
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


def press(name, shift=False):
    code, vk = KEYS[name]
    modifiers = 8 if shift else 0
    text = {'text': '\r'} if name == 'Enter' else {}  # Enter activates a button through its key press text.
    browser_input('Input.dispatchKeyEvent', dict(type='keyDown', key=name, code=code, windowsVirtualKeyCode=vk, modifiers=modifiers, **text))
    browser_input('Input.dispatchKeyEvent', dict(type='keyUp', key=name, code=code, windowsVirtualKeyCode=vk, modifiers=modifiers))


def active():
    return ui.js("(()=>{const a=document.activeElement;return {id:a.id,tag:a.tagName,text:(a.textContent||'').trim().slice(0,40),"
                 "inWizard:!!a.closest('#add-folder-wizard'),body:a===document.body}})()")


def walk(steps, shift=False):
    """Press Tab (or Shift+Tab) and record where focus lands each time; every stop must be inside the wizard."""
    stops = []
    for _ in range(steps):
        press('Tab', shift)
        stops.append(active())
    outside = [s for s in stops if not s['inWizard']]
    assert not outside, outside
    return stops


def open_with_enter():
    ui.js("$('add-library-folder').focus()")
    assert active()['id'] == 'add-library-folder'
    press('Enter')
    wait(f"{WIZARD}&&{WIZARD}.dataset.step==='found'&&$('found-counts')", 30)


def verify():
    try:
        ui.wait_ready()
        ui.js("$('nav-sources').click()")
        wait("$('add-library-folder')")
        open_with_enter()
        title = f"{WIZARD}.querySelector('h2')"
        ui.check('found_focus_on_title_and_app_inert', f"""({{title:document.activeElement==={title},
          shellInert:$('nav-sources').closest('[inert]')!==null, opener:$('add-library-folder').closest('[inert]')!==null}})""")
        stops = walk(14) + walk(14, shift=True)
        report['checks']['found_tab_stops'] = sorted({s['id'] or s['text'] for s in stops})
        ui.capture('01-found-focus.png')
        press('Escape')
        wait(f"!{WIZARD}", 10)
        wait("document.activeElement===$('add-library-folder')", 5)
        ui.check('escape_returns_focus_to_opener', "document.activeElement===$('add-library-folder')&&!$('nav-sources').closest('[inert]')")
        open_with_enter()
        ui.js("$('add-folder-agent').click()")
        wait(f"{WIZARD}.dataset.step==='agent'&&$('agent-take-over-prompt')", 60)
        ui.check('agent_step_keeps_focus_inside', "!!document.activeElement.closest('#add-folder-wizard')")
        stops = walk(12) + walk(12, shift=True)
        report['checks']['agent_tab_stops'] = sorted({s['id'] or s['text'] for s in stops})
        ui.capture('02-agent-focus.png')
        assert ui.js(f"{WIZARD}.dataset.step") == 'agent'
        press('Escape')  # On Finish, Escape minimizes; the agent keeps working.
        wait(f"!{WIZARD}", 10)
        wait("document.activeElement&&document.activeElement.id==='add-library-folder'", 5)
        ui.check('minimize_returns_focus_to_opener', "({opener:document.activeElement.id==='add-library-folder',notInert:!$('nav-sources').closest('[inert]'),"
                 "minimized:lal.state.toasts.some(t=>t.title==='Your agent keeps working')})")
        ui.js("$('nav-settings').click()")
        wait("$('run-setup')")
        ui.js("$('run-setup').focus()")
        press('Enter')
        wait("$('setup-wizard')&&!lal.state.setup.loading", 30)
        wait("document.activeElement===$('setup-step-title')", 5)
        ui.check('setup_focus_on_step_title', "({title:document.activeElement===$('setup-step-title'),shellInert:$('nav-settings').closest('[inert]')!==null})")
        ui.capture('03-setup-focus.png')
        report.update(status='passed')
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            report['active_at_failure'] = active()
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
