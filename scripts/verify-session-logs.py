"""Verify session logs in the real WebView2 shell with a synthetic library.

Starts an app session in the fixture project, opens the real window and bridge, lets the page poll, makes one call
the backend refuses and runs a child process that joins the session. Checks that one file holds the app's and the
child's lines with their levels, that polls collapse into repeat counts, that the refusal is a warning, that a
follower started before the app (what the console launcher runs) prints the session from its first line to
"Session ended", and that originals stay untouched. Writes data/gui/<run-name>/verification.json.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed  # noqa: E402
from local_asset_library import logs, sources  # noqa: E402
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
for name in ('Kit_1.0/Rocks/Rock_01', 'Kit_1.0/Rocks/Rock_02', 'Kit_1.0/Cars/Car_A'):
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / f'{name}.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
sources.scan_source(config, sources.add(config, str(root)))
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

# The fixture project's own logs folder; children inherit the session through the environment.
folder = fixture / 'logs'
logs.folder = lambda _root: folder
os.environ.pop(logs.ENV, None)
followed = io.StringIO()
follower = threading.Thread(target=logs.show, args=(fixture,), daemon=True,
                            kwargs={'follow': True, 'wait_new': True, 'kind': 'app', 'level': 'debug', 'out': followed,
                                    'color': False, 'poll': 0.05})
follower.start()
time.sleep(0.3)
session = logs.start(fixture, 'app', 'debug')


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
report = {'status': 'running', 'checks': [], 'synthetic_only': True, 'session': session.name}
ui = Harness(window, OUT, report)
CHILD = ("import logging, sys; sys.path.insert(0, sys.argv[1]); from local_asset_library import logs; "
         "logs.start(sys.argv[2], 'operation', process='scan'); log = logging.getLogger('local_asset_library.sources'); "
         "[log.info('Scanned pack %d', i) for i in range(3)]; log.warning('A pack has no license file')")


def verify():
    try:
        ui.wait_ready()
        time.sleep(4)  # Let the page poll a few times.
        refused = bridge.agent_proposal('prop_missing', 'apply')  # The same bridge path the page's calls take.
        assert refused['status'] == 'faulty', refused
        child = subprocess.run([sys.executable, '-c', CHILD, str(ROOT / 'src'), str(fixture)], timeout=60)
        assert child.returncode == 0
        ui.capture('01-app.png')
        report.update(status='checked')
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
    finally:
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
logs.stop()
follower.join(timeout=15)
try:
    assert report['status'] == 'checked', report.get('reason')
    text = session.read_text(encoding='utf-8')
    lines = text.splitlines()
    timed = re.compile(r'^\d\d:\d\d:\d\d\.\d{3} (DEBUG|INFO|WARNING|ERROR)\s+[\w-]+\[\d+\] [\w.]+: ')
    assert all(timed.match(line) or line.startswith((' ', 'Traceback', '  ')) for line in lines), 'a torn or unformatted line'
    assert 'Session started · kind=app' in lines[0] and lines[-1].endswith('session: Session ended')
    report['checks'].append('One session file, named by start time and kind, from "Session started" to "Session ended"')
    calls = [line for line in lines if ' DEBUG ' in line and ' desktop: ' in line]
    assert calls and any('↻ repeated' in line for line in calls), 'polls did not collapse'
    report['checks'].append(f'Bridge calls are debug lines; repeated polls collapse into counts ({len(calls)} call lines)')
    assert any(' WARNING ' in line and 'agent_proposal refused · reason=This proposal is not saved any more' in line for line in lines)
    report['checks'].append('A refused call is a warning with its reason')
    child = [line for line in lines if re.search(r' scan\[\d+\] ', line)]
    assert len(child) == 5 and 'Joined the session' in child[0] and ' WARNING ' in child[-1], child
    report['checks'].append('A child process joins the session: its lines carry its name and pid in the same file')
    assert not follower.is_alive() and followed.getvalue().startswith('Waiting for Assetarium to start…')
    shown = followed.getvalue().splitlines()[2:]
    assert shown == lines, (len(shown), len(lines))
    report['checks'].append('A follower started before the app printed every line of the session and stopped at its end')
    assert session.with_name(session.stem + '.worker.log').parent == folder
    now = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    assert now == originals and not bridge._gateway.model_requested
    report['checks'].append('Original files are byte-identical; no model was loaded')
    report['lines'] = len(lines)
    report.update(status='passed')
except BaseException as exc:
    report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
atomic_json(OUT / 'verification.json', report)
print(json.dumps(dict(report, report=str(OUT / 'verification.json')), indent=2))
raise SystemExit(report['status'] != 'passed')
