"""Real WebView2 check of agent setup (decision 0016) with a real STDIO MCP client, on an isolated fresh project.

The app shows both setup paths; Set up with my agent opens the session and the panel waits; a
scripted client launches the fixture's own scripts/asset-mcp.py (code copied, mcp environment
linked; the owner's library is never touched) and the panel flips to connected; values the agent
applies appear live with "Set by agent"; the Blender proposal card rejects and applies (a fresh
check in the app); finish leads to the review, where a change is saved as the user's; ending
access refuses the next write; the manual path still opens. Light and dark screenshots.
Writes data/gui/<run-name>/report.json.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests'), str(ROOT / 'scripts')]
from gui_harness import Harness, isolate_hash_cache
isolate_hash_cache(__file__)
from local_asset_library import setup_core
from local_asset_library.config import load_project_config
from local_asset_library.desktop import DesktopBridge, create_window, profile_path, record_profile_outcome
from local_asset_library.publication import atomic_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not args.run_name.replace('-', '').isalnum():
    parser.error('Invalid run name')
OUT = ROOT / 'data/gui' / args.run_name
FIXTURE = ROOT / 'scratch' / args.run_name / 'project'
OUT.mkdir(parents=True, exist_ok=False)
FIXTURE.mkdir(parents=True, exist_ok=False)
os.environ.update(PYTHONNET_RUNTIME='netfx', TEMP=str(ROOT / 'scratch/tmp-mcp'), TMP=str(ROOT / 'scratch/tmp-mcp'))
report = {'status': 'running', 'checks': {}, 'screenshots': [], 'synthetic_only': True, 'owner_visual_review': 'pending',
          'real_agent': False, 'unverified': []}
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

skip = shutil.ignore_patterns('__pycache__', '*.pyc')
for name in ('src', 'scripts'):
    shutil.copytree(ROOT / name, FIXTURE / name, ignore=skip)
for relative in ('config.example.toml', 'docs/caption-model.json', 'docs/embedding-model.json'):
    (FIXTURE / relative).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, FIXTURE / relative)
made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(FIXTURE / '.venv-mcp'), str(ROOT / '.venv-mcp')], capture_output=True)
if made.returncode:
    raise SystemExit(made.stderr.decode(errors='replace'))
# A configured Blender that no longer exists, so the installed one needs the user's approval.
missing = str(FIXTURE / 'old-blender' / 'blender.exe')
(FIXTURE / 'config.local.toml').write_text(setup_core.with_blender((ROOT / 'config.example.toml').read_text(encoding='utf-8'), missing), encoding='utf-8')
config = load_project_config(FIXTURE)


class Agent:
    """A scripted MCP client launching the fixture's server exactly as agent clients do."""
    def __init__(self):
        self.stderr = (OUT / 'agent-stderr.log').open('w', encoding='utf-8')
        self.process = subprocess.Popen([str(FIXTURE / '.venv-mcp/Scripts/python.exe'), str(FIXTURE / 'scripts/asset-mcp.py')], cwd=OUT,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr, text=True, encoding='utf-8',
                                        creationflags=NO_WINDOW)
        self.lines, self.sequence = queue.Queue(), 0
        threading.Thread(target=lambda: [self.lines.put(line) for line in self.process.stdout] and self.lines.put(None), daemon=True).start()
        self.send('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'agent-setup-check', 'version': '1'}})
        self.send('notifications/initialized', notification=True)
        self.tools = [tool['name'] for tool in self.send('tools/list')['result']['tools']]  # As every client does on connect.

    def send(self, method, params=None, notification=False):
        message = {'jsonrpc': '2.0', 'method': method, **({'params': params} if params is not None else {})}
        if not notification:
            self.sequence += 1
            message['id'] = self.sequence
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()
        while not notification:
            response = json.loads(self.lines.get(timeout=240))
            if response.get('id') == self.sequence:
                return response

    def call(self, name, arguments=None):
        result = self.send('tools/call', {'name': name, 'arguments': arguments or {}})['result']
        return json.loads(result['content'][0]['text']), bool(result.get('isError'))

    def close(self):
        self.process.stdin.close()
        code = self.process.wait(30)
        self.stderr.close()
        return code


bridge = DesktopBridge(config)
import webview
window = create_window(config, bridge)
profile = profile_path(config, bridge, window)
ui = Harness(window, OUT, report)


def wait(expression, timeout=30):
    ui.js('until(()=>(%s),%d)' % (expression, timeout * 1000), timeout + 5)


def shoot(label):
    for name in ('light', 'dark'):
        ui.js(f"(async()=>{{await lal.setAppearance('{name}');await frame();return true}})()")
        ui.capture(f'{label}-{name}.png')
    ui.js("(async()=>{await lal.setAppearance('light');await frame();return true})()")


def verify():
    agent = None
    try:
        ui.wait_ready()
        wait("$('setup-wizard')&&$('setup-paths')&&lal.state.setup.env")
        ui.check('welcome_offers_two_equal_paths', """(async()=>({agent:!!$('setup-agent-start'), manual:!!$('setup-manual'),
          equal:$('setup-paths').children.length===2, noSession:!lal.state.setup.agent.session.open}))()""")
        shoot('00-welcome-paths')
        ui.js("$('setup-agent-start').click()")
        wait("$('agent-panel')&&$('agent-panel').dataset.session==='open'&&$('agent-connection')")
        ui.check('session_opened_by_the_click_and_panel_waits', """(async()=>({waiting:$('agent-connection').dataset.state==='waiting',
          minutes:$('agent-session').textContent.includes('59 minutes')||$('agent-session').textContent.includes('60 minutes'),
          honest:!/server is running/i.test(document.body.innerText), privacy:$('agent-privacy').textContent.includes('cloud'),
          tabs:$('agent-snippet-tabs').querySelectorAll('[role=tab]').length===4,
          allowlist:$('agent-snippet').textContent.includes('enabled_tools')&&$('agent-snippet').textContent.includes('finish_setup'),
          prompt:$('agent-prompt').textContent.includes('get_setup_status')}))()""")
        ui.js("(async()=>{$('agent-snippet-tabs').querySelector('[data-client=\"claude-code\"]').click();await frame();return true})()")
        ui.check('client_tabs_switch_snippets', "$('agent-snippet').dataset.client==='claude-code'&&$('agent-snippet').textContent.startsWith('claude mcp add')")
        shoot('01-agent-waiting')
        agent = Agent()
        wait("$('agent-connection').dataset.state==='connected'", 30)
        ui.check('panel_flips_to_connected_with_the_client_name', "$('agent-connection').textContent.includes('agent-setup-check is connected')")
        shoot('02-agent-connected')
        applied, error = agent.call('apply_setup', {'storage_budget_gib': 30, 'processing_formats': ['gltf'], 'engine_hint': 'godot'})
        assert not error and applied['status'] == 'applied', applied
        wait("$('agent-values').querySelector('[data-key=processing_formats] [data-set-by=agent]')", 15)
        ui.check('agent_values_appear_live_with_attribution', """(async()=>({formats:$('agent-values').querySelector('[data-key=processing_formats]').textContent.includes('glTF'),
          budget:$('agent-values').querySelector('[data-key=storage_budget_gib]').textContent.includes('30 GiB')}))()""")
        wait("lal.state.notifications.some(n=>n.kind==='setup_changed')", 15)
        report['checks']['agent_change_raises_a_notice'] = True
        status, _ = agent.call('get_setup_status')
        found = [c['path'] for c in status['blender']['candidates'] if c['path'] != missing]
        if found:
            checked, _ = agent.call('validate_blender', {'path': found[0]})
            assert checked['status'] in {'passed', 'warning'}, checked
            first, _ = agent.call('propose_setup', {'blender_path': found[0]})
            assert first['status'] == 'pending', first
            wait("document.querySelector('.agent-proposal')", 15)
            ui.check('proposal_card_shows_path_and_version', f"""(async()=>({{path:document.querySelector('.agent-proposal').textContent.includes({json.dumps(found[0])}),
              version:document.querySelector('.agent-proposal').textContent.includes('checked as Blender '),
              notice:lal.state.notifications.some(n=>n.kind==='setup_proposal')}}))()""")
            shoot('03-proposal-card')
            ui.js("document.querySelector('.agent-reject').click()")
            wait("!document.querySelector('.agent-proposal')", 15)
            assert agent.call('get_setup_status')[0]['proposals'][-1]['state'] == 'rejected'
            assert setup_core.configured_blender(config)[1] == missing
            report['checks']['reject_saves_nothing_and_agent_sees_it'] = True
            agent.call('propose_setup', {'blender_path': found[0]})
            wait("document.querySelector('.agent-proposal')", 15)
            ui.js("document.querySelector('.agent-apply').click()")
            wait("!document.querySelector('.agent-proposal')", 200)
            assert setup_core.configured_blender(config)[1] == found[0]
            assert agent.call('get_setup_status')[0]['proposals'][-1]['state'] == 'applied'
            ui.check('apply_saves_after_a_fresh_check_and_shows_attribution',
                     "$('agent-values').querySelector('[data-key=blender]').textContent.includes('approved by you')")
        else:
            report['unverified'].append('No Blender found: the proposal card ran only in pytest')
        finished, error = agent.call('finish_setup')
        assert not error and finished['status'] == 'completed', finished
        wait("$('agent-review')", 15)
        shoot('04-agent-finished')
        ui.js("$('agent-review').click()")
        wait("$('setup-wizard').dataset.step==='review'&&$('setup-summary')")
        ui.check('review_shows_who_set_each_value', "$('setup-summary').querySelectorAll('[data-set-by=agent]').length>=2")
        shoot('05-review')
        ui.js("(async()=>{lal.goToSetupStep(3);await until(()=>$('setup-budget'));type('setup-budget','45');await frame();"
              "lal.goToSetupStep(6);await until(()=>$('setup-summary'));await frame();return true})()")
        ui.check('review_edit_is_marked_as_changed', "$('setup-summary').querySelector('[data-step=storage]').textContent.includes('Changed by you')")
        ui.js("$('setup-save').click()")
        wait("lal.state.setup.result&&$('setup-saved-title')", 60)
        record = json.loads((FIXTURE / 'data/library/setup.json').read_text(encoding='utf-8'))
        settings = json.loads((FIXTURE / 'data/library/settings.json').read_text(encoding='utf-8'))
        assert settings['storage_budget_bytes'] == 45 * 1024**3 and settings['processing_formats'] == ['gltf']
        assert record['values']['storage_budget_gib']['set_by'] == 'user' and record['values']['processing_formats']['set_by'] == 'agent', record
        report['checks']['review_saves_only_the_users_change_as_theirs'] = True
        ui.js("(async()=>{lal.closeSetup();await lal.openSetup();await until(()=>$('agent-panel'));return true})()")
        ui.check('open_session_reopens_the_panel', "$('agent-panel').dataset.session==='open'")
        ui.js("$('agent-end').click()")
        wait("$('agent-panel').dataset.session==='closed'&&$('agent-reopen')")
        refused, error = agent.call('apply_setup', {'storage_budget_gib': 60})
        assert error and refused['status'] == 'refused', refused
        report['checks']['ending_access_refuses_the_next_write'] = True
        shoot('06-access-ended')
        assert agent.close() == 0
        agent = None
        wait("$('agent-connection').dataset.state==='waiting'", 15)
        report['checks']['disconnect_returns_to_waiting'] = True
        ui.js("$('agent-leave').click()")
        wait("$('setup-wizard').dataset.step==='blender'&&!lal.state.setup.agentMode")
        report['checks']['manual_path_still_opens'] = True
        ui.js("(async()=>{lal.closeSetup();$('nav-settings').click();await until(()=>$('run-agent-setup'));return true})()")
        report['checks']['settings_offers_setup_with_agent'] = True
        assert not bridge._gateway.model_requested
        report.update(status='passed')
    except BaseException as exc:
        report.update(status='faulty', reason=str(exc), traceback=traceback.format_exc())
        try:
            ui.capture('failure.png')
        except Exception:
            pass
    finally:
        if agent:
            agent.close()
        from scratch_links import release
        release(FIXTURE / '.venv-mcp')  # scratch/ stays safe to delete (AGENTS.md).
        atomic_json(OUT / 'report.json', report)
        bridge._close()
        window.destroy()


window.events.loaded += lambda: threading.Thread(target=verify, daemon=True).start()
webview.start(gui='edgechromium', debug=False, private_mode=True, storage_path=str(profile))
record_profile_outcome(bridge, profile)
print(json.dumps({k: report.get(k) for k in ('status', 'reason', 'unverified')} | {'checks': len(report['checks']), 'screenshots': len(report['screenshots'])}))
raise SystemExit(report['status'] != 'passed')
