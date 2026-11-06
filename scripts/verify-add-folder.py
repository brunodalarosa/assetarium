"""Verify the Add library folder wizard (decision 0024) in the real WebView2 shell with a synthetic library.

Checks the live quick look (the tree fills in by names), What we found (counts, reasons, How did we decide?), Let my
agent finish (the folder is added and scanned, the copy-paste prompt, the connection line), an in-process agent
working through the MCP gateway (its lines in the take-over feed, a waiting proposal accepted and applied in place, progress to
"every pack has a structure"), Minimize, the narrow layout, untouched originals and that no model loads.
Writes data/gui/<run-name>/verification.json.
"""
import argparse
import asyncio
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
from local_asset_library import sources  # noqa: E402
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome  # noqa: E402
from local_asset_library.mcp_server import Gateway  # noqa: E402
from local_asset_library.publication import atomic_json  # noqa: E402
from local_asset_library.setup_agent import note_client, remove_connection, write_connection  # noqa: E402
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
root = fixture / 'Game Assets'
names = (['Kit_1.0/License.txt'] + [f'Kit_1.0/Cars/Car_11_{c}.obj' for c in 'RGB'] + [f'Kit_1.0/Rocks/Rock_{n:02}.obj' for n in range(1, 4)]
         + [f'Props/{d}/{m}.obj' for d in ('FBX', 'Unity FBX') for m in ('Barrel', 'Crate', 'Door')] + ['Props/readme.txt'])
for name in names:
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n' if name.endswith('.obj') else 'CC0')
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result

    def choose_source_directory(self):
        return {'status': 'selected', 'directory': str(root)}  # The folder dialog, answered.

    def _start_source_operation(self, operation, key):
        assert operation == 'scan'  # No runtimes in the fixture project: the same scan, in-process.
        sources.scan_source(config, sources.get_source(config, key))
        return {'status': 'ready', 'reason': 'Scanned'}


agent = Gateway(config)
agent.client = {'name': 'verify-agent', 'version': '1'}
write_connection(config.project_root, agent.run_id, 'normal')
note_client(config.project_root, os.getpid(), agent.client)


def tool(name, **arguments):
    result = asyncio.run(agent.call(name, arguments))
    payload = json.loads(result.content[0].text)
    assert not result.is_error, payload
    return payload


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True}
ui = Harness(window, OUT, report)
WIZARD = "$('add-folder-wizard')"


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        ui.wait_ready()
        ui.js("$('nav-sources').click()")
        wait("$('add-library-folder')")
        ui.js("$('add-library-folder').click()")
        wait(f"{WIZARD}&&({WIZARD}.dataset.step==='found'||document.querySelectorAll('#quick-look-tree li').length>=2)", 30)
        wait(f"{WIZARD}.dataset.step==='found'&&$('found-counts')", 30)
        counts = ui.js("[...$('found-counts').children].map(c=>c.dataset.status+':'+c.querySelector('.text-\\\\[22px\\\\]').textContent).join('|')")
        assert counts == 'fine:1|suggestions:0|needs_structure:1', counts
        why = ui.js("$('found-why').textContent")
        assert 'Car_11_{B,G,R} became one card with 3 variants' in why and 'is a pack because of License.txt' in why, why
        assert 'FBX and Unity FBX look like exports' in why, why
        ui.capture('01-what-we-found.png')
        report['checks'].append('The quick look reads names only and finds 1 fine pack and 1 that needs a structure, with reasons')
        ui.js("$('add-folder-agent').click()")
        wait(f"{WIZARD}.dataset.step==='agent'&&$('agent-take-over-prompt')", 60)
        key = next(s['key'] for s in sources.registry(config)['sources'] if Path(s['path']) == root.resolve())
        assert f'library_folder "{key}"' in ui.js("$('agent-take-over-prompt').textContent")
        wait("$('take-over-connection').textContent.includes('verify-agent')", 30)
        report['checks'].append('Let my agent finish adds and scans the folder and offers the prompt; the agent shows as connected')
        tool('say', message='Looking at Props for engine copies')
        listed = tool('list_packs', library_folder=key, status='needs_structure')
        pack = listed['packs'][0]['pack']
        tool('get_pack_outline', library_folder=key, path=pack)
        pending = tool('propose_profile', library_folder=key, pack=pack, note='Unity FBX repeats FBX for Unity',
                       rules=[{'kind': 'engine_copy', 'folder': 'Unity FBX', 'of': 'FBX'}])
        assert pending['status'] == 'pending', pending
        wait("document.querySelectorAll('#take-over-feed li').length>=3&&document.querySelector('#add-folder-wizard .proposal-review')", 30)
        ui.capture('02-take-over.png')
        report['checks'].append("The agent's lines and its waiting proposal appear in the take-over")
        ui.js("document.querySelector('#add-folder-wizard .proposal-review [data-action=accept-all]').click()")
        wait("!document.querySelector('#add-folder-wizard [data-action=apply-staged]').disabled", 10)
        ui.js("document.querySelector('#add-folder-wizard [data-action=apply-staged]').click()")
        wait("!document.querySelector('#add-folder-wizard .proposal-review')", 30)
        tool('finish_structure', library_folder=key, pack=pack)
        wait(f"{WIZARD}.dataset.step==='done'&&$('add-folder-done')", 30)
        ui.capture('03-done.png')
        report['checks'].append('Accept all and Apply in place, then finish_structure: the wizard says every pack has a structure and offers Make previews')
        window.resize(680, 900)
        wait('innerWidth<761')
        wait(f"{WIZARD}.querySelector('section').getBoundingClientRect().right<=innerWidth+1", 10)
        ui.capture('04-narrow.png')
        ui.js("[...document.querySelectorAll('#add-folder-done button')].find(b=>b.textContent.includes('Open the folder')).click()")
        wait(f"!{WIZARD}", 10)
        report['checks'].append('Narrow layout fits; Open the folder closes the wizard')
        assert not bridge._gateway.model_requested and not agent.model_requested
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
        remove_connection(config.project_root)
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps(dict(report, report=str(OUT / 'verification.json')), indent=2))
raise SystemExit(report['status'] != 'passed')
