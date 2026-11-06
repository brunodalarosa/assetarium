"""Verify excluded folders and duplicate export folder suggestions (decision 0019) in the real WebView2 shell.

A synthetic source has Exports/FBX + Exports/gLTF and a third copy named "Engine Copy". Checks the
suggestion on Asset sources and Asset processing, Group and Undo, an exclusion chip and its removal,
the narrow layout, and that originals are untouched and no model loads. Writes data/gui/<run-name>/.
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
from test_source_exports import TWENTY, kit, near_kit  # noqa: E402
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
root = kit(fixture / 'kit')
added = sources.add(config, str(root))
sources.scan_source(config, added)
# A near miss: Unity FBX lacks prop_19 and repeats prop_0 in a second subfolder.
near = sources.add(config, str(near_kit(fixture / 'near', copy=TWENTY[:19], repeated=('prop_0',))))
sources.scan_source(config, near)
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def assets():
    return len(sources.read_records(working(sources.bound(config, added))))


def wait_assets(count, timeout=90):
    """An answer hides its suggestion at once; the rescan runs in its own process, so wait for its result."""
    deadline = time.monotonic() + timeout
    while assets() != count:
        if time.monotonic() > deadline:
            raise AssertionError(f'expected {count} assets after the rescan, found {assets()}')
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
KIT = "document.querySelector('#folder-panel')"  # The library folder's panel on the Asset sources tab (decision 0023).
IDLE = "lal.state.sources.find(s=>s.key==='kit')&&!['queued','running','cancelling'].includes((lal.state.sources.find(s=>s.key==='kit').operation||{}).status)"


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        ui.wait_ready(extra="lal.state.sources.length===4")  # Two fixture sources, the kit and the near miss.
        ui.js("$('nav-sources').click()")
        wait("lal.state.sourcesView.tree&&lal.state.sourcesView.tree.attention")
        ui.capture('01-attention.png')
        report['checks'].append('The Asset sources rail item shows that a duplicate export answer waits')
        ui.js("lal.inspectFolder('kit','')")
        wait(f"{KIT}&&{KIT}.querySelector('.export-suggestion')")
        text = ui.js(f"{KIT}.querySelector('.export-suggestion').textContent")
        assert 'In Exports, Engine Copy, FBX, gLTF have the same 3 model names' in text and 'FBX and gLTF are already grouped' in text, text
        assert ui.js(f"[...{KIT}.querySelectorAll('.export-suggestion button')].map(b=>b.textContent).join('|')") == \
            'Group as alternate files|Exclude extra folders|Keep separate'
        ui.js(f"{KIT}.scrollIntoView()")
        ui.capture('02-sources-suggestion.png')
        report['checks'].append('The link opens Asset sources; the suggestion names the folders, the match count and three answers')
        assert assets() == 6
        ui.js(f"{KIT}.querySelector('[data-action=group]').click()")
        wait(f"{IDLE}&&!{KIT}.querySelector('.export-suggestion')&&{KIT}.querySelector('.export-answers')")
        wait_assets(3)
        wait(IDLE)
        assert ui.js(f"{KIT}.querySelector('.export-answers').textContent.includes('Grouped: Exports / Engine Copy, FBX, gLTF')")
        ui.capture('03-grouped.png')
        report['checks'].append('Group saves the answer, rescans and leaves 3 assets with their copies attached; the answer is listed with Undo')
        ui.js(f"{KIT}.querySelector('.export-answers [data-action=undo]').click()")
        wait_assets(6)
        wait(f"{IDLE}&&{KIT}.querySelector('.export-suggestion')&&!{KIT}.querySelector('.export-answers')")
        report['checks'].append('Undo forgets the answer; the rescan separates the copies and the suggestion returns')
        ui.js(f"""(async()=>{{const row={KIT};const input=row.querySelector('input[id^=exclude-]');type(input.id,'Engine*');await frame();
          row.querySelector('.source-folders form').requestSubmit();return true}})()""")
        wait_assets(3)
        wait(f"{IDLE}&&{KIT}.querySelector('[aria-label=\"Excluded folder patterns\"]')&&!{KIT}.querySelector('.export-suggestion')")
        wait(f"{IDLE}&&{KIT}.querySelector('.source-folders').textContent.includes('3 files in 1 excluded folder')")
        assert sources.excluded_folders(sources.bound(config, added)) == ['Engine*']
        ui.capture('04-excluded.png')
        report['checks'].append('An exclusion chip is saved, the rescan skips the folder and the hint counts its 3 files')
        ui.js(f"{KIT}.querySelector('[aria-label=\"Stop excluding Engine*\"]').click()")
        wait_assets(6)
        wait(f"{IDLE}&&!{KIT}.querySelector('[aria-label=\"Excluded folder patterns\"]')&&{KIT}.querySelector('.export-suggestion')")
        report['checks'].append('Removing the chip rescans and brings the folder and its suggestion back')
        NEAR = "document.querySelector('#folder-panel')"
        ui.js(f"lal.inspectFolder('{near['key']}','')")
        wait(f"lal.state.sourcesView.key==='{near['key']}'&&{NEAR}&&{NEAR}.querySelector('.export-suggestion')")
        text = ui.js(f"{NEAR}.querySelector('.export-suggestion').textContent")
        assert 'In Pack, FBX, Unity FBX, gLTF share 18 model names' in text, text
        assert '2 in FBX and 2 in gLTF are not in every folder; 1 name repeats inside Unity FBX. Those stay as they are.' in text, text
        assert 'Excluding stops scanning the extra folders (Unity FBX), including 1 name that would not be grouped.' in text, text
        ui.js(f"{NEAR}.querySelector('.export-suggestion').scrollIntoView()")
        ui.capture('04b-near-miss.png')
        report['checks'].append('A near miss says how many names the folders share, which names stay as they are, '
                                'and what excluding would also skip')
        window.resize(680, 900)
        wait('innerWidth<761')
        wait("$('sources-view').scrollWidth<=$('sources-view').clientWidth+1", 10)  # Once the resize has settled.
        ui.capture('05-narrow.png')
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
