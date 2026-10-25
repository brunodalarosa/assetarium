"""Real WebView2 check that the mouse's dedicated Back (button 3) and Forward (button 4) buttons navigate like the rail arrows.

Uses a small isolated synthetic source only for the app config; no model loads. The buttons are sent as
mouseup events (what the web view reports for them). Writes data/gui/<run-name>/verification.json.
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
from test_sources import managed
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
report = {'status': 'running', 'checks': [], 'synthetic_only': True, 'real_model_load': False}
ui = Harness(window, OUT, report)
js = ui.js
PRESS = "window.press=b=>{const e=new MouseEvent('mouseup',{bubbles:true,cancelable:true,button:b});window.dispatchEvent(e);return e.defaultPrevented};true"


def page():
    return js("(()=>{const r=lal.state.history[lal.state.historyIndex];return r.page})()")


def done(text):
    report['checks'].append(text)


def verify():
    try:
        ui.wait_ready()
        js(PRESS)
        assert page() == 'home'
        js("press(3)")  # Nothing before Home: stays put.
        js("press(4)")
        assert page() == 'home' and js("lal.state.historyIndex") == 0
        done('Back and Forward at the ends of the history do nothing')

        js("lal.navigate({page:'collections'})")
        js("lal.navigate({page:'processing'})")
        assert page() == 'processing'
        assert js("press(3)") is True  # Default action is suppressed.
        assert page() == 'collections'
        js("press(3)")
        assert page() == 'home'
        js("press(4)")
        assert page() == 'collections'
        js("press(4)")
        assert page() == 'processing'
        done('Button 3 goes back and button 4 goes forward through the app history')

        js("press(3)")
        js("press(0)")
        js("press(1)")
        js("press(2)")
        assert page() == 'collections'
        done('Left, middle and right buttons do not navigate')

        js("(async()=>{lal.openSetup();await until(()=>lal.state.setup.open);return true})()")
        js("press(3)")
        assert page() == 'collections'
        js("lal.closeSetup()")
        js("press(3)")
        assert page() == 'home'
        done('Ignored while the setup wizard is open')

        assert not bridge._gateway.model_requested
        done('No model loaded')
        report.update(status='passed')
    except Exception as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture('failure.png')
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
