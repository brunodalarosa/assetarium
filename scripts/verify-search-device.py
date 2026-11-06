"""Verify Settings → General → Search (decision 0018) in the real WebView2 shell with synthetic sources.

Checks that the device choice shows both options, saves CPU with a rebuild hint, survives reopening,
keeps the narrow layout, and loads no model. Writes data/gui/<run-name>/verification.json.
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
from test_sources import managed, ready_source  # noqa: E402
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome  # noqa: E402
from local_asset_library.publication import atomic_json  # noqa: E402
from local_asset_library.settings import search_device  # noqa: E402
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
preserved = [p for p in Path(one['path']).iterdir() if p.is_file()]
original_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved}


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True}
ui = Harness(window, OUT, report)


def wait(expression, timeout=30):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        ui.wait_ready()
        ui.js("$('nav-settings').click()")
        wait("$('settings-search-device')&&$('settings-search-device').querySelectorAll('[role=radio]').length===2"
             "&&!$('settings-search-device').querySelector('[role=radio]').disabled")
        assert ui.js("$('settings-search-device').querySelector('[data-value=cuda]').getAttribute('aria-checked')==='true'")
        assert ui.js("$('search-card').textContent.includes('NVIDIA GPU')&&$('search-card').textContent.includes('CPU')")
        report['checks'].append('Search card lists NVIDIA GPU and CPU with their summaries; the unsaved default is NVIDIA GPU')
        ui.js("(async()=>{$('settings-search-device').querySelector('[data-value=cpu]').click();await frame();"
              "$('save-general-settings').click();return true})()")
        wait("$('general-settings-message').textContent.startsWith('Saved.')")
        assert search_device(config) == 'cpu'
        assert ui.js("$('general-settings-message').textContent.includes('Search now runs on the CPU')"
                     "&&$('general-settings-message').textContent.includes('search check')")
        ui.js("$('search-card').scrollIntoView()")
        ui.capture('01-search-cpu-saved.png')
        report['checks'].append('Choosing CPU saves search_device=cpu and the confirmation says to run the search check and process again')
        ui.js("(async()=>{$('nav-home').click();await until(()=>$('library-view'));$('nav-settings').click();return true})()")
        # Settings reloads on return; Save stays disabled until the reload finishes.
        wait("$('settings-search-device')&&$('settings-search-device').querySelector('[data-value=cpu]').getAttribute('aria-checked')==='true'"
             "&&!$('save-general-settings').disabled")
        ui.js("(async()=>{$('save-general-settings').click();return true})()")
        wait("$('general-settings-message').textContent.startsWith('Saved.')")
        assert ui.js("!$('general-settings-message').textContent.includes('Search now runs')")
        report['checks'].append('Reopening keeps CPU selected; saving without a change adds no rebuild hint')
        window.resize(680, 900)
        wait('innerWidth<761')
        ui.js("$('search-card').scrollIntoView()")
        assert ui.js("$('settings-view').scrollWidth<=$('settings-view').clientWidth+1")
        ui.capture('02-search-narrow.png')
        report['checks'].append('Narrow layout has no horizontal overflow')
        assert not bridge._gateway.model_requested
        assert original_hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved}
        report['checks'].append('Originals are byte-identical; no inference worker or model was loaded')
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
