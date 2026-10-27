"""Verify the source list after a crash in the real WebView2 shell with synthetic sources.

One source whose saved data cannot be read shows its fault on its own card while the other stays
listed (Settings → Asset sources and Asset processing), and a source list that fails to load says
so instead of "No asset sources yet". Writes data/gui/<run-name>/verification.json.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source  # noqa: E402
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
config, backend, one, two = managed.__wrapped__(fixture)
for source in (one, two):
    ready_source(config, backend, source)
original = sources._format_status
fail = {'source': True, 'list': False}


def unreadable(scoped, *rest):
    if fail['source'] and scoped.source_key == one['key']:
        raise sqlite3.OperationalError('attempt to write a readonly database')
    return original(scoped, *rest)


sources._format_status = unreadable


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result

    def sources(self):
        if fail['list']:
            return {'status': 'faulty', 'reason': 'synthetic list failure'}
        return super().sources()


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config, prestart_worker=False)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True}
ui = Harness(window, OUT, report)


def wait(expression, timeout=30):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        ui.wait_ready()
        ui.js("(async()=>{$('nav-settings').click();await until(()=>document.querySelector('[role=tab]'));"
              "[...document.querySelectorAll('[role=tab]')].find(t=>t.textContent.includes('Asset sources')).click();return true})()")
        wait(f"$('source-list')&&$('source-list').textContent.includes({json.dumps(one['name'])})"
             f"&&$('source-list').textContent.includes({json.dumps(two['name'])})")
        assert ui.js("$('source-list').textContent.includes('could not be read (attempt to write a readonly database)')")
        assert not ui.js("!!$('sources-empty')")
        ui.capture('01-settings-one-source-unreadable.png')
        report['checks'].append('Settings → Asset sources lists both sources; only the unreadable one shows its fault')
        ui.js("$('nav-processing').click()")
        wait(f"$('source-warnings')&&$('source-warnings').textContent.includes({json.dumps(two['name'])})"
             "&&$('source-warnings').textContent.includes('Scan fault')")
        ui.capture('02-processing-one-source-unreadable.png')
        report['checks'].append('Asset processing shows the fault on that source card and keeps the other card')
        fail.update(source=False, list=True)
        atomic_json(config.output_path('data', 'library/source-cancel.json'), {'token': 'touch'})  # Changes the sources token.
        wait("$('sources-error')&&$('sources-error').textContent.includes('synthetic list failure')")
        assert ui.js("!$('processing-view').textContent.includes('No asset sources yet')")
        ui.capture('03-processing-list-failed.png')
        ui.js("(async()=>{$('nav-settings').click();await until(()=>document.querySelector('[role=tab]'));"
              "[...document.querySelectorAll('[role=tab]')].find(t=>t.textContent.includes('Asset sources')).click();return true})()")
        wait("$('sources-error')&&!$('sources-empty')")
        ui.capture('04-settings-list-failed.png')
        report['checks'].append('A source list that fails to load says so and that sources and results are kept; '
                                'neither page claims "No asset sources yet"')
        fail['list'] = False
        atomic_json(config.output_path('data', 'library/source-cancel.json'), {'token': 'touch-again'})
        wait(f"!$('sources-error')&&$('source-list').textContent.includes({json.dumps(one['name'])})")
        report['checks'].append('The error clears and the sources return as soon as the list loads again')
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
