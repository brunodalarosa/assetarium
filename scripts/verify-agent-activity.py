"""Verify Agent activity and pack proposals (decision 0029) in the real WebView2 shell with a synthetic pack.

An in-process MCP gateway plays the agent (the same Gateway.call path a STDIO client uses, so every call lands in
data/mcp/runs/<run>/calls.jsonl): say, get_pack_outline, an instant proposal (applied at once, Undo in a toast and the
feed) and rescan proposals for two packs (they wait; the top-bar button counts them; the drawer groups the shared engine
copy rule, the owner accepts and rejects rules, sees a preview and applies both with one scan). Checks the live feed,
the connection line, Undo, the narrow layout, untouched originals and that no model loads.
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
from local_asset_library import pack_profiles, sources  # noqa: E402
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
root = fixture / 'library'
kit = root / 'Kit_1.0'
for name in ('Rocks/Rock_01', 'Rocks/Rock_02', 'Rocks/Rock_03', 'Cars/Car_A', 'Unity FBX/Rocks/Rock_01'):
    (kit / name).parent.mkdir(parents=True, exist_ok=True)
    (kit / f'{name}.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
(kit / 'License.txt').write_text('CC0')
second = root / 'Kit_2.0'
for name in ('Props/Barrel', 'Unity FBX/Props/Barrel', 'Samples/Shot'):
    (second / name).parent.mkdir(parents=True, exist_ok=True)
    (second / f'{name}.obj').write_text((kit / 'Cars/Car_A.obj').read_text())
(second / 'License.txt').write_text('CC0')
added = sources.add(config, str(root))
sources.scan_source(config, added)
KEY = added['key']
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


scans = []


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result

    def _start_source_operation(self, operation, key):
        # The fixture project has no runtimes to start a worker in; run the same scan in-process.
        assert operation == 'scan'
        scans.append(key)
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
PANEL = "$('agent-activity-panel')"


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        ui.wait_ready()
        ui.js("$('open-agent-activity').click()")
        wait(f"{PANEL}&&$('agent-connection').textContent.includes('verify-agent')")
        report['checks'].append('The drawer names the connected agent')
        tool('say', message='Looking at Kit_1.0 for variants and engine copies')
        tool('get_pack_outline', library_folder=KEY, path='Kit_1.0')
        wait("document.querySelectorAll('#agent-feed .agent-entry').length>=2", 30)
        assert ui.js("document.querySelector('#agent-feed [data-kind=say]').textContent.includes('Looking at Kit_1.0')")
        report['checks'].append('say and get_pack_outline appear live as sentences')
        ui.js("lal.setAgentOpen(false)")  # Toasts tell an owner who is elsewhere; the open drawer shows the line itself.
        applied = tool('propose_profile', library_folder=KEY, pack='Kit_1.0', note='Numbered rocks are recolors',
                       rules=[{'kind': 'variant_axis', 'folder': 'Rocks', 'values': ['numbers']}])
        assert applied['status'] == 'applied', applied
        wait("[...document.querySelectorAll('.toast')].some(t=>t.textContent.includes('Your agent changed a pack'))", 30)
        ui.js("lal.setAgentOpen(true)")
        wait("document.querySelector('#agent-feed [data-kind=change]')", 30)
        ui.capture('01-applied-with-undo.png')
        report['checks'].append('An instant proposal applies at once; a toast (drawer closed) and the feed offer Undo')
        copy = {'kind': 'engine_copy', 'folder': 'Unity FBX', 'of': ''}
        for pack, rules in (('Kit_1.0', [{'kind': 'variant_axis', 'folder': 'Rocks', 'values': ['numbers']}, copy]),
                            ('Kit_2.0', [copy, {'kind': 'exclude', 'folder': 'Samples', 'note': 'screenshots'}])):
            pending = tool('propose_profile', library_folder=KEY, pack=pack, rules=rules)
            assert pending['status'] == 'pending', pending
        review = ".proposal-review"
        group = lambda packs, text: f"[...document.querySelectorAll('{review} .proposal-group[data-packs=\"{packs}\"]')].find(g=>g.textContent.includes('{text}'))"
        wait(f"$('agent-waiting-count')&&$('agent-waiting-count').textContent==='2'&&document.querySelectorAll('{review} .proposal-group').length===3", 30)
        assert ui.js(f"{group(2, 'engine copy')}.textContent.includes('In 2 packs')")
        assert ui.js(f"{group(1, 'Samples')}.textContent.includes('Only in Kit_2.0')")
        assert ui.js(f"document.querySelector('{review} [data-action=apply-staged]').disabled")
        report['checks'].append('Two waiting proposals show as one folder review: the shared engine copy rule is one group "In 2 packs", '
                                'each pack-only rule says where it applies, and Apply stays disabled until rules are decided')
        ui.js(f"{group(2, 'engine copy')}.querySelector('[data-choice=accept]').click()")
        ui.js(f"{group(1, 'Variants')}.querySelector('[data-choice=accept]').click()")
        ui.js(f"{group(1, 'Samples')}.querySelector('[data-choice=reject]').click()")
        wait(f"document.querySelector('{review} .proposal-preview').textContent.includes('2 files skipped')", 30)
        assert ui.js(f"document.querySelector('{review} [data-action=apply-staged]').textContent.includes('2 packs')")
        assert not scans and sources.excluded_folders(sources.bound(config, sources.get_source(config, KEY))) == []
        ui.capture('02-staged-review.png')
        report['checks'].append('Accepting and rejecting rules saves nothing; the preview measures 2 files skipped across both packs')
        ui.js(f"document.querySelector('{review} [data-action=apply-staged]').click()")
        wait(f"!document.querySelector('{review}')&&!$('agent-waiting-count')", 30)
        assert sorted(sources.excluded_folders(sources.bound(config, sources.get_source(config, KEY)))) == ['Kit_1.0/Unity FBX', 'Kit_2.0/Unity FBX']
        assert scans == [KEY], scans
        assert pack_profiles.history(config, KEY, 'Kit_2.0')[0]['origin']['left_out'] == [{'kind': 'exclude', 'folder': 'Samples', 'note': 'screenshots'}]
        report['checks'].append('One Apply saves both packs (Samples left out and recorded), scans the library folder once and clears the badge')
        ui.js("[...document.querySelectorAll('#agent-feed [data-kind=change] button')][0].click()")
        wait("[...document.querySelectorAll('.toast')].some(t=>t.textContent.includes('Undone'))", 30)
        rules = pack_profiles.current(config, sources.get_source(config, KEY), 'Kit_1.0')
        assert rules == [{'kind': 'engine_copy', 'folder': 'Unity FBX', 'of': ''}] or rules == [], rules
        report['checks'].append('Undo restores the version before the agent change')
        window.resize(680, 900)
        wait('innerWidth<761')
        ui.js("lal.setAgentOpen(true)")
        wait(f"{PANEL}&&{PANEL}.getBoundingClientRect().right<=innerWidth+1", 10)
        ui.capture('03-narrow.png')
        report['checks'].append('The drawer fits the narrow window')
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
