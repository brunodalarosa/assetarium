"""Verify agent freedom (decision 0029) in the real WebView2 shell with a synthetic library folder.

An in-process MCP gateway plays the agent through Gateway.call (the STDIO path). It creates a collection, applies a
pack profile that rescans (at once, one scan), and queues Make previews while the owner's queue is paused (the job
waits, never resumes the owner's queue, and Asset processing names the agent). The owner turns on Pause agents in
Agent activity: the agent's next write is refused, its reads go on, and the held job says why. The owner then runs
Undo all for the session from the drawer: the collection, the profile and the waiting job go back, with one rescan.
Also checks the narrow layout, untouched originals and that no model loads.
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
from local_asset_library import agent_sessions, asset_collections, pack_profiles, processing_queue, source_operations, sources  # noqa: E402
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
for name in ('Rocks/Rock_01', 'Rocks/Rock_02', 'Unity FBX/Rocks/Rock_01'):
    (kit / name).parent.mkdir(parents=True, exist_ok=True)
    (kit / f'{name}.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
(kit / 'License.txt').write_text('CC0')
added = sources.add(config, str(root))
sources.scan_source(config, added)
KEY = added['key']
originals = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

# The fixture project has no runtimes to start workers in: scans run in-process; processing is recorded, never run.
scans, jobs = [], []


def start(config_, operation, key=None, **kwargs):
    if operation == 'scan':
        scans.append(key)
        sources.scan_source(config, sources.get_source(config, key))
        return {'status': 'started', 'token': 'scan'}
    jobs.append((operation, key))
    return {'status': 'busy', 'reason': 'Recorded by the verification'}


source_operations.start = start
from local_asset_library import library_view  # noqa: E402
library_view.blockers = lambda config: {}  # No Blender in the fixture; nothing here renders.


class FixtureBridge(DesktopBridge):
    def context(self):
        result = super().context()
        result['managed_sources'] = False
        return result

    def _start_source_operation(self, operation, key, quiet=False):
        return start(config, operation, key)


agent = Gateway(config)
agent.client = {'name': 'verify-agent', 'version': '1'}
write_connection(config.project_root, agent.run_id, 'normal')
note_client(config.project_root, os.getpid(), agent.client)


def tool(tool_name, error=False, **arguments):
    result = asyncio.run(agent.call(tool_name, arguments))
    payload = json.loads(result.content[0].text)
    assert result.is_error == error, payload
    return payload


os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
import webview  # noqa: E402
bridge = FixtureBridge(config)
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
report = {'status': 'running', 'checks': [], 'synthetic_only': True}
ui = Harness(window, OUT, report)


def wait(expression, timeout=60):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def verify():
    try:
        ui.wait_ready()
        made = tool('edit_collection', action='create', name='Agent picks', description='Rocks for the cave level')
        profile_result = tool('propose_profile', library_folder=KEY, pack='Kit_1.0', rules=[{'kind': 'exclude', 'folder': 'Unity FBX'}])
        assert profile_result['status'] == 'applied' and profile_result['scan'] == 'started' and scans == [KEY], (profile_result, scans)
        assert sources.excluded_folders(sources.bound(config, sources.get_source(config, KEY))) == ['Kit_1.0/Unity FBX']
        report['checks'].append('A rescanning profile applies at once and starts one scan (no owner Apply)')
        processing_queue.control(config, 'pause')
        job = tool('start_processing', action='previews', library_folder=KEY)
        state = processing_queue.state(config)
        assert job['status'] == 'queued' and state['paused'] and state['up_next'][0]['by'] == 'agent' and not jobs, (job, state)
        report['checks'].append("An agent's job waits in the owner's paused queue and never resumes it")
        ui.js("lal.navigate({page:'processing'});true")
        wait("document.querySelector('#up-next .agent-job')&&document.querySelector('#up-next .agent-job').textContent.includes('verify-agent')")
        ui.capture('01-agent-job-in-queue.png')
        report['checks'].append('Asset processing names the agent on its job, with the Bot sign')
        ui.js("lal.setAgentOpen(true)")
        wait("$('agent-sessions')&&$('agent-sessions').textContent.includes('verify-agent')&&$('agent-sessions').textContent.includes('1 job')")
        ui.js("$('agent-pause').querySelector('button,[role=switch]').click()")
        wait("[...document.querySelectorAll('.toast')].some(t=>t.textContent.includes('Agents paused'))&&$('agent-pause').textContent.includes('Agents are paused')", 20)
        assert agent_sessions.paused(config)
        refused = tool('edit_collection', error=True, action='rename', collection_id=made['collection_id'], name='Renamed')
        assert refused['status'] == 'refused' and 'Paused by the owner' in refused['reason'], refused
        assert tool('list_collections')['total_matching'] == 1
        assert tool('say', message='Paused; waiting for the owner')['status']
        ui.capture('02-paused.png')
        report['checks'].append('Pause agents (one switch) refuses the next agent write with "Paused by the owner"; reads and say go on')
        ui.js("lal.setAgentOpen(false)")
        wait("$('agent-jobs-held')&&$('agent-jobs-held').textContent.includes('Turn agents back on')")
        report['checks'].append('The held job says why it waits, with Turn agents back on (P5)')
        ui.js("lal.setAgentOpen(true)")
        wait("document.querySelector('#agent-sessions .agent-session button')")
        ui.js("document.querySelector('#agent-sessions .agent-session button').click()")
        wait("$('confirm-dialog').open")
        assert ui.js("$('confirm-body').textContent.includes('Settings stay as they are')")
        ui.capture('03-undo-all-confirm.png')
        ui.js("$('confirm-accept').click()")
        wait("[...document.querySelectorAll('.toast')].some(t=>t.textContent.includes('Undid 3 changes'))", 30)
        assert asset_collections.load(config)['collections'] == []
        assert sources.excluded_folders(sources.bound(config, sources.get_source(config, KEY))) == []
        assert pack_profiles.current(config, sources.get_source(config, KEY), 'Kit_1.0') == []
        assert processing_queue.state(config)['up_next'] == [] and scans == [KEY, KEY] and not jobs
        wait("$('agent-sessions').textContent.includes('undone')")
        report['checks'].append('Undo all removes the collection, reverts the profile with one rescan and withdraws the waiting job')
        ui.js("lal.setAgentOpen(false)")
        ui.js("lal.navigate({page:'settings'});true")
        ui.js("lal.setAgentsPaused(false)")
        wait("[...document.querySelectorAll('.toast')].some(t=>t.textContent.includes('Agents are on again'))")
        assert not agent_sessions.paused(config)
        report['checks'].append('The owner turns agents back on from the app')
        window.resize(680, 900)
        wait('innerWidth<761')
        ui.js("lal.setAgentOpen(true)")
        wait("$('agent-activity-panel')&&$('agent-activity-panel').getBoundingClientRect().right<=innerWidth+1&&$('agent-pause').getBoundingClientRect().right<=innerWidth", 10)
        ui.capture('04-narrow.png')
        report['checks'].append('The drawer with the switch and sessions fits the narrow window')
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
