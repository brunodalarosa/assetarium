"""Verify variant groups and pack profiles (decision 0024) in the real WebView2 shell with a synthetic pack.

Checks one card per variant group with its corner badge and chips, that a chip switches the card, the inspector's
variant picker and "Generate separate descriptions for each variant" switch (saved as a pack profile rule), the pack's
Structure section (rules, versions, restore), the narrow layout, untouched originals and that no model loads.
Writes data/gui/<run-name>/verification.json.
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
from local_asset_library import pack_profiles, sources  # noqa: E402
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
kit = root / 'Kit_1.0'
for name in ('Cars/Car_11_R', 'Cars/Car_11_G', 'Cars/Car_11_B', 'Rocks/Rock_01', 'Rocks/Rock_02', 'Rocks/Rock_03'):
    (kit / name).parent.mkdir(parents=True, exist_ok=True)
    (kit / f'{name}.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
(kit / 'License.txt').write_text('CC0')
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
CARD = "document.querySelector('#sources-grid .card-wrap:has(.variant-badge)')"


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        ui.wait_ready()
        ui.js(f"lal.inspectFolder({json.dumps(KEY)},'Kit_1.0/Cars')")
        wait(f"{CARD}&&{CARD}.querySelectorAll('.variant-chips [role=radio]').length===3")
        assert ui.js(f"{CARD}.querySelector('.variant-badge').textContent.trim()") == '3'
        assert ui.js("document.querySelectorAll('#sources-grid .card').length") == 1
        assert ui.js(f"[...{CARD}.querySelectorAll('.variant-chips [role=radio]')].map(c=>c.textContent).join('|')") == 'B|G|R'
        ui.capture('01-variant-card.png')
        report['checks'].append('Car_11_R/G/B are one card with a "3" corner badge and chips B, G, R')
        ui.js(f"(async()=>{{[...{CARD}.querySelectorAll('.variant-chips [role=radio]')][1].click();await frame();return true}})()")
        wait(f"{CARD}.querySelector('.card-name').textContent==='Car_11_G'")
        report['checks'].append('Clicking chip G shows Car_11_G on the card')
        ui.js(f"{CARD}.querySelector('.card').click()")
        wait("document.querySelector('.variant-group')&&document.querySelectorAll('.variant-group [role=radio]').length===3")
        assert ui.js("document.querySelector('.variant-group [aria-checked=true]').textContent") == 'G'
        ui.capture('02-inspector-variants.png')
        report['checks'].append('The inspector lists the 3 variants with G selected and the separate descriptions switch')
        ui.js("document.querySelector('#separate-descriptions [role=switch]').click()")
        wait("document.querySelector('#separate-descriptions [role=switch]').getAttribute('aria-checked')==='true'", 30)
        rules = pack_profiles.current(config, sources.get_source(config, KEY), 'Kit_1.0')
        assert rules == [{'kind': 'separate_descriptions', 'group': 'Cars/Car_11'}], rules
        report['checks'].append('Turning the switch on saves a separate_descriptions rule in the Kit_1.0 profile')
        ui.js(f"lal.inspectFolder({json.dumps(KEY)},'Kit_1.0')")
        wait("document.querySelector('#pack-profile .profile-rules')", 30)
        assert ui.js("document.querySelector('#pack-profile .profile-rules').textContent.includes('Each variant of “Cars/Car_11”')")
        ui.js("[...document.querySelectorAll('#pack-profile button')].find(b=>b.textContent.includes('versions')).click()")
        wait("document.querySelectorAll('#pack-profile .profile-history li').length===2")
        ui.capture('03-pack-structure.png')
        report['checks'].append('The pack Structure section shows the rule as a sentence and 2 versions')
        ui.js("document.querySelector('#pack-profile .profile-history li:last-child button').click()")
        wait("!document.querySelector('#pack-profile .profile-rules')", 30)
        assert pack_profiles.current(config, sources.get_source(config, KEY), 'Kit_1.0') == []
        report['checks'].append('Restoring version 1 removes the rule (saved as version 3)')
        window.resize(680, 900)
        wait('innerWidth<761')
        wait("$('sources-view').scrollWidth<=$('sources-view').clientWidth+1", 10)
        ui.capture('04-narrow.png')
        report['checks'].append('Narrow layout has no horizontal overflow')
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
