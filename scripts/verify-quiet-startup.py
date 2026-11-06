"""Real WebView2 check of the quiet launch check (decision 0027).

At launch the app asks for a check of every library folder. While it runs, the top-bar activity shows
"Checking for changes" with no phase or percentage; an unchanged check reloads neither the folder tree nor
the shown folder's cards and shows no toast. A check that finds a new asset says so in one toast. Small
isolated synthetic sources; the check runs in this process, slowed so its states can be observed.
Writes data/gui/<run-name>/verification.json and screenshots.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_sources import managed, ready_source  # noqa: E402
from local_asset_library import source_operations, sources  # noqa: E402
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome  # noqa: E402
from gui_harness import Harness, isolate_hash_cache  # noqa: E402
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
ready_source(config, backend, one)
ready_source(config, backend, two)
for source in (one, two):
    sources.scan_source(config, source)  # Published and rescanned: the launch check finds nothing new.
sources.aggregate(config)

SLOW = 4.0
scan_source = sources.scan_source
def slowed(*a, **k):
    time.sleep(SLOW)
    return scan_source(*a, **k)
source_operations.scan_source = slowed
checks = []


class FixtureBridge(DesktopBridge):
    def _start_source_operation(self, operation, key, quiet=False):
        """What a real start records, with the scan in this process (no runtimes in the fixture project)."""
        assert operation == 'scan' and key is None and quiet
        token = f'check{len(checks)}'.ljust(32, '0')
        source_operations.state(config, token=token, pid=os.getpid(), status='queued', phase='Queued', progress=0,
                                operation='scan', key=None, quiet=True, changes=None, reason=None)
        thread = threading.Thread(target=source_operations.scan_all, args=(config, token), daemon=True)
        checks.append(thread)
        thread.start()
        return {'status': 'started', 'token': token}


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True, 'owner_visual_approval': 'pending'}
ui = Harness(window, OUT, report)
js = ui.js
ROW = "document.querySelector('[role=treeitem][data-key=\"%s\"][data-path=\"%s\"]')"
# Count folder and tree reloads, and note whether a check was running when each was asked for.
COUNT = r"""window.calls=[];window.fixtureApi=window.fixtureApi||lal.state.api;
stubApi(Object.fromEntries(['library_items','library_tree'].map(n=>[n,(...a)=>{
  calls.push({name:n,checking:['queued','scanning','publishing'].includes(lal.state.globalScan?.status)});return fixtureApi[n](...a)}])));
window.toasts=()=>[...document.querySelectorAll('.toast')].map(t=>t.textContent);true"""


def wait(expression, timeout=30):
    try:
        js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)
    except RuntimeError as exc:
        raise RuntimeError('UI condition timed out: ' + expression) from exc


def done(text):
    report['checks'].append(text)


def verify():
    try:
        ui.wait_ready()
        wait("lal.state.globalScan?.quiet===true&&$('activity')?.textContent.includes('Checking for changes')", 20)
        text = js("$('activity').textContent")
        assert 'Scanning' not in text and '%' not in text, text
        done('The launch check shows "Checking for changes" with no phase or percentage')
        js("$('nav-sources').click();true")
        wait("$('sources-view')&&lal.state.sourcesView.tree")
        js(f"{ROW % (one['key'], '')}.click();true")
        wait("lal.state.sourcesView.key&&!lal.state.source.loading&&lal.state.source.items.length>0")
        js(COUNT)
        js("window.itemsRef=lal.state.source.items;window.treeRef=lal.state.sourcesView.tree;true")
        ui.capture('01-checking.png', settle=.2)
        wait("lal.state.globalScan?.status==='complete'", 30)
        js("new Promise(r=>setTimeout(r,3500))", 10)  # Two more change polls after the check ends.
        result = js("({calls, same:lal.state.source.items===itemsRef, tree:lal.state.sourcesView.tree===treeRef, toasts:toasts(), changes:lal.state.globalScan.changes})")
        report['unchanged'] = result
        assert not [c for c in result['calls'] if c['checking']], result['calls']
        assert result['same'] and result['tree'], result
        assert not any('Library updated' in t for t in result['toasts']), result['toasts']
        assert result['changes'] == {'new': 0, 'changed': 0, 'removed': 0}, result['changes']
        done('An unchanged check reloads neither the tree nor the shown folder while it runs, keeps the cards and shows no toast')
        wait("!$('activity')||!$('activity').textContent.includes('Checking')", 10)
        (Path(one['path']) / 'added.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
        js("lal.sourceAction('check');true")
        wait("$('activity')?.textContent.includes('Checking for changes')", 10)
        wait("toasts().some(t=>t.includes('Library updated')&&t.includes('1 new'))", 30)
        wait("lal.state.source.items.some(i=>i.name==='added'||i.display_name==='added')&&lal.state.source.total===4", 15)
        wait("$('sources-view').textContent.includes('4 assets')", 10)
        ui.capture('02-updated.png', settle=.2)
        done('A check that finds a new asset says so in one quiet toast ("Library updated · 1 new")')
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
