"""Verify an incomplete search runtime in the real WebView2 shell with synthetic sources.

A `.venv-embedding` holding only the base project (what a wrapper sync without --project leaves)
must give a search error naming the install command, start no worker and keep no fault; Settings →
General → Search lists it as missing with the command, and Check again sees it fixed. Writes
data/gui/<run-name>/verification.json.
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
from local_asset_library.config import venv_python  # noqa: E402
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
config, _, _, _ = managed.__wrapped__(fixture)
site = config.project_root / '.venv-embedding/Lib/site-packages'


def install(name, version):
    info = site / f'{name}-{version}.dist-info'
    info.mkdir(parents=True)
    (info / 'METADATA').write_text(f'Metadata-Version: 2.1\nName: {name.replace("_", "-")}\nVersion: {version}\n', encoding='utf-8')


python = venv_python(config.project_root, '.venv-embedding')
python.parent.mkdir(parents=True)
python.write_bytes(b'')
install('numpy', '2.3.4')
install('local_asset_library', '0.1.0')

os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = DesktopBridge(config)  # Prestarts the worker as the app does; the check must stop it first.
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True}
ui = Harness(window, OUT, report)
RUNTIME = "document.querySelector('#search-readiness [data-item=embedding_runtime]')"


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        ui.wait_ready()
        assert bridge._gateway.worker is None and bridge._gateway.worker_phase.startswith('unavailable: The search runtime')
        report['checks'].append('App start prepares no worker from an incomplete runtime and records why')
        ui.js("(async()=>{lal.setQuery('crate');await lal.submitSearch();return true})()")
        wait("$('error')&&$('error').textContent.includes('Install it with')")
        error = ui.js("$('error').textContent")
        assert 'missing torch, sentence-transformers' in error and 'embedding-runtime.ps1 sync --locked --project runtime/embedding' in error
        assert bridge._gateway.worker is None and bridge._gateway.worker_fault is None
        ui.capture('01-search-error.png')
        report['checks'].append('Search names the missing packages and the install command; no worker starts, no fault is kept')
        ui.js("lal.navigate({page:'settings',tab:'general'})")
        wait(f"{RUNTIME}")
        ui.js("$('search-card').scrollIntoView()")
        assert ui.js(f"{RUNTIME}.dataset.ready==='false'&&{RUNTIME}.textContent.includes('sync --locked --project runtime/embedding')")
        ui.capture('02-settings-missing.png')
        report['checks'].append('Settings → Search lists the runtime as missing with its install command')
        install('torch', '2.10.0+cu128')
        install('sentence_transformers', '6.1.0')
        ui.js("$('search-readiness-check').click()")
        wait(f"{RUNTIME}&&{RUNTIME}.dataset.ready==='true'")
        ui.capture('03-settings-ready.png')
        report['checks'].append('Check again sees the installed runtime as ready')
        window.resize(680, 900)
        wait('innerWidth<761')
        ui.js("$('search-card').scrollIntoView()")
        assert ui.js("$('settings-view').scrollWidth<=$('settings-view').clientWidth+1")
        ui.capture('04-narrow.png')
        report['checks'].append('Narrow layout has no horizontal overflow')
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
