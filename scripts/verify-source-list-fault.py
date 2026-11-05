"""Verify the source list after a crash in the real WebView2 shell with synthetic sources.

One library folder whose saved data cannot be read shows its fault on its own tree row and panel while the
other stays listed (Asset sources), and a folder list that fails to load says so instead of an empty
library. Writes data/gui/<run-name>/verification.json.
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

    def library_tree(self):
        if fail['list']:
            return {'status': 'faulty', 'reason': 'synthetic list failure'}
        return super().library_tree()


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
        ROWS = "[...document.querySelectorAll('#folder-tree [role=treeitem][aria-level=\"1\"]')]"
        ui.js("$('nav-sources').click()")
        wait(f"{ROWS}.length===2&&{ROWS}.some(r=>r.querySelector('.unreadable'))")
        assert ui.js(f"{ROWS}.filter(r=>r.querySelector('.unreadable')).map(r=>r.dataset.key).join()") == one['key']
        ui.js(f"lal.inspectFolder({json.dumps(one['key'])},'')")
        wait("$('folder-fault')&&$('folder-fault').textContent.includes('attempt to write a readonly database')")
        assert not ui.js("!!$('sources-empty')")
        ui.capture('01-one-folder-unreadable.png')
        report['checks'].append('Asset sources lists both library folders; only the unreadable one says it can’t be read, with the reason')
        fail.update(source=False, list=True)
        atomic_json(config.output_path('data', 'library/source-cancel.json'), {'token': 'touch'})  # Changes the sources token.
        wait("$('sources-error')&&$('sources-error').textContent.includes('synthetic list failure')&&!$('sources-empty')")
        assert ui.js(f"{ROWS}.length===2")  # The folders shown before stay listed.
        ui.capture('02-list-failed.png')
        report['checks'].append('A folder list that fails to load says so and that folders and results are kept; '
                                'the page never claims the library is empty')
        fail['list'] = False
        atomic_json(config.output_path('data', 'library/source-cancel.json'), {'token': 'touch-again'})
        wait("!$('sources-error')")
        report['checks'].append('The error clears as soon as the list loads again')
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
