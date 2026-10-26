"""Verify the texture folder suggestion (decision 0021) in the real WebView2 shell with a synthetic pack.

Checks the Asset processing line, the panel's folder options and live counts, the single-copy
switch, Apply (recipes written, remaining model listed), Undo, the narrow layout, untouched
originals and that no model loads. Writes data/gui/<run-name>/verification.json.
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
from test_sources import managed  # noqa: E402
from test_texture_folders import inspected, pack  # noqa: E402
from local_asset_library import sources  # noqa: E402
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome  # noqa: E402
from local_asset_library.incremental import working  # noqa: E402
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
root = pack(fixture / 'pack')
added = sources.add(config, str(root))
sources.scan_source(config, added)
work = working(sources.bound(config, added))
inspected(work)
sources.scan_source(config, added)
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and 'metadata-lal' not in p.parts}


def repaired():
    return sorted(r['display_name'] for r in sources.read_records(work) if r.get('texture_repair'))


def wait_for(check, timeout=60):
    deadline = time.monotonic() + timeout
    while not check():
        if time.monotonic() > deadline:
            raise AssertionError('Timed out waiting for the rescan result')
        time.sleep(0.25)


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result

    def _start_source_operation(self, operation, key):
        # The fixture project has no runtimes to start a worker in; run the same scan in-process.
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
ROW = "document.querySelector('.source-row:has([data-source=pack])')"
PANEL = ROW + ".querySelector('.texture-choice')"


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        ui.wait_ready(extra="lal.state.sources.length===3")
        ui.js("$('nav-processing').click()")
        wait("document.querySelector('[data-source=pack] .source-texture-suggestion')")
        assert ui.js("document.querySelector('[data-source=pack] .source-texture-suggestion').textContent.includes('4 models can’t find their textures')")
        report['checks'].append('Asset processing points to the texture choice for the 4 models')
        ui.js("document.querySelector('[data-source=pack] .source-texture-suggestion button').click()")
        wait(f"{ROW}&&{PANEL}&&{PANEL}.querySelectorAll('[role=radio]').length===2")
        assert ui.js(f"[...{PANEL}.querySelectorAll('[role=radio]')].map(r=>r.dataset.value).join('|')") == 'Tex/PBR|Tex/URP'
        assert ui.js(f"{PANEL}.querySelector('.texture-total').textContent.startsWith('3 fixed · 1 stays failed')")
        ui.js(f"{ROW}.scrollIntoView()")
        ui.capture('01-texture-choice.png')
        report['checks'].append('The panel offers Tex/PBR and Tex/URP and counts 3 fixed, 1 left, with single copies on')
        ui.js(f"(async()=>{{{PANEL}.querySelector('[role=checkbox]').click();await frame();return true}})()")
        wait(f"{PANEL}.querySelector('.texture-total').textContent.startsWith('2 fixed')")
        ui.js(f"(async()=>{{{PANEL}.querySelector('[role=checkbox]').click();await frame();return true}})()")
        wait(f"{PANEL}.querySelector('.texture-total').textContent.startsWith('3 fixed')")
        report['checks'].append('Switching single copies off and on updates the count live (2, then 3)')
        ui.js(f"{PANEL}.querySelector('[data-action=textures-apply]').click()")
        wait_for(lambda: repaired() == ['bush', 'cactus', 'rock'])
        wait(f"{PANEL}&&{PANEL}.querySelector('.texture-chosen')&&{PANEL}.textContent.includes('1 model can’t')")
        assert ui.js(f"{PANEL}.querySelector('.texture-chosen').textContent.includes('Textures from Tex/PBR and single copies')")
        ui.capture('02-applied.png')
        report['checks'].append('Apply writes recipes for exactly the 3 fixable models; the panel shows the choice and the 1 left')
        ui.js(f"{PANEL}.querySelector('[data-action=textures-undo]').click()")
        wait_for(lambda: repaired() == [])
        wait(f"{PANEL}&&!{PANEL}.querySelector('.texture-chosen')&&{PANEL}.textContent.includes('4 models can’t')")
        report['checks'].append('Undo drops the recipes and brings the suggestion back for all 4')
        window.resize(680, 900)
        wait('innerWidth<761')
        ui.js(f"{ROW}.scrollIntoView()")
        assert ui.js("$('settings-view').scrollWidth<=$('settings-view').clientWidth+1")
        ui.capture('03-narrow.png')
        report['checks'].append('Narrow layout has no horizontal overflow')
        assert not bridge._gateway.model_requested
        now = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and 'metadata-lal' not in p.parts}
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
