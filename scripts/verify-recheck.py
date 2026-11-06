"""Verify Recheck failures (decision 0020) on Asset processing in the real WebView2 shell, with synthetic sources.

One asset failed the file check only because of its OBJ alternate; another has a Blender failure that
must stay recorded. Checks the button, the neutral dialog, Cancel, Retry, the released state and the
close-only "Nothing to retry" dialog. Writes data/gui/<run-name>/verification.json.
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
from test_alternate_faults import fail, kit  # noqa: E402
from local_asset_library import recheck, sources  # noqa: E402
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
added = sources.add(config, str(kit(fixture / 'kit')))
sources.scan_source(config, added)
work = working(sources.bound(config, added))
records = sorted(sources.read_records(work), key=lambda r: r['display_name'])
fail(work, records[0], 'inspection', 'Dependency unavailable or unresolved: C:/Users/author/Desktop/atlas.png')
fail(work, records[1], 'inspection', 'Missing, rejected or unresolved texture dependencies: atlas')
sources.scan_source(config, added)


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
CARD = "document.querySelector('article[data-source=kit]')"
BUTTON = CARD + ".querySelector('[data-action=recheck]')"


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        ui.wait_ready(extra="lal.state.sources.length===3")
        ui.js("$('nav-processing').click()")
        wait(f"{CARD}&&{BUTTON}")
        assert ui.js(f"{BUTTON}.textContent.includes('Recheck failures')")
        report['checks'].append('A source with recorded failures shows Recheck failures on its Asset processing card')
        ui.js(f"{BUTTON}.click()")
        wait("$('confirm-dialog').open&&$('confirm-accept')")
        title, body = ui.js("[$('confirm-title').textContent,$('confirm-body').textContent]")
        assert title == 'Retry 1 asset?' and 'not rendered from had a problem' in body and 'Other recorded failures stay' in body, (title, body)
        assert ui.js("!$('confirm-accept').className.includes('danger')")
        ui.capture('01-retry-dialog.png')
        report['checks'].append('The dialog counts exactly the check failure that now passes, explains it and is not styled as a deletion')
        ui.js("$('confirm-cancel').click()")
        wait("!$('confirm-dialog').open")
        assert recheck.preview(config, added['key'])['retry'] == 1
        report['checks'].append('Cancel changes nothing')
        ui.js(f"{BUTTON}.click()")
        wait("$('confirm-dialog').open&&$('confirm-accept')")
        ui.js("$('confirm-accept').click()")
        wait("!$('confirm-dialog').open")
        state = {r['display_name']: r for r in sources.read_records(work)}
        assert state[records[0]['display_name']]['processing']['inspection'] == 'pending'
        assert state[records[1]['display_name']]['processing']['inspection'] == 'failed'
        report['checks'].append('Retry releases only that asset (pending, evidence kept); the Blender failure stays recorded')
        wait(f"{CARD}&&{BUTTON}")
        ui.js(f"{BUTTON}.click()")
        wait("$('confirm-dialog').open&&$('confirm-title').textContent==='Nothing to retry'")
        assert ui.js("!$('confirm-accept')&&$('confirm-cancel').textContent==='Close'")
        ui.capture('02-nothing-to-retry.png')
        ui.js("$('confirm-cancel').click()")
        report['checks'].append('Rechecking again shows Nothing to retry with only Close')
        window.resize(680, 900)
        wait('innerWidth<761')
        assert ui.js("$('processing-view').scrollWidth<=$('processing-view').clientWidth+1")
        report['checks'].append('Narrow layout has no horizontal overflow')
        assert not bridge._gateway.model_requested
        report['checks'].append('No inference worker or model was loaded')
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
