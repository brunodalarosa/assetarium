"""Real WebView2 check of agent setup (decisions 0029, 0031) with a real STDIO MCP client, on an isolated fresh project.

The app shows both setup paths; Set up with my agent shows the panel (no session to open) and it waits; a
synthetic Claude Code entry for a deleted copy is named with its fix, and Check again confirms the repair; a
scripted client launches the fixture's own scripts/asset-mcp.py (code copied, mcp environment
linked; the owner's library is never touched) and the panel flips to connected; values the agent
answers appear live with "Set by agent"; the Blender proposal card rejects and applies (a fresh
check in the app); finishing switches the open panel to the agent's report (every value with its
source), Undo brings a replaced value back, Looks good completes setup and leads to Asset sources;
the report's Change opens a step whose save is the user's; the panel reopens; the manual path
still opens. Light and dark screenshots.
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
for name in ('src', 'scripts', 'samples'):
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
# Synthetic agent settings: Claude Code still starts a deleted copy, as after moving the checkout. Never the owner's real ones.
CLIENT_HOME = FIXTURE / 'client-home'
CLIENT_HOME.mkdir()
os.environ['LAL_CLIENT_HOME'] = str(CLIENT_HOME)


def register(script):
    entry = {'type': 'stdio', 'command': str(FIXTURE / '.venv-mcp/Scripts/python.exe'), 'args': [str(script)], 'env': {}}
    (CLIENT_HOME / '.claude.json').write_text(json.dumps({'mcpServers': {'local_asset_library': entry}}), encoding='utf-8')


register(FIXTURE.parent / 'moved-away/scripts/asset-mcp.py')


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
          equal:$('setup-paths').children.length===2}))()""")
        shoot('00-welcome-paths')
        ui.js("$('setup-agent-start').click()")
        wait("$('agent-panel')&&$('agent-connection')")
        ui.check('panel_opens_without_a_session_and_waits', """(async()=>({waiting:$('agent-connection').dataset.state==='waiting',
          access:$('agent-access').textContent.includes('whenever it is connected'),
          honest:!/server is running/i.test(document.body.innerText), privacy:$('agent-privacy').textContent.includes('cloud'),
          freedom:$('agent-freedom').textContent.includes('pause agents or undo a session'),
          tabs:$('agent-snippet-tabs').querySelectorAll('[role=tab]').length===4,
          allowlist:$('agent-snippet').textContent.includes('enabled_tools')&&$('agent-snippet').textContent.includes('finish_setup'),
          prompt:$('agent-prompt').textContent.includes('get_setup_status')}))()""")
        ui.check('stale_registration_is_named_with_its_path_and_a_fix', """(async()=>{const item=document.querySelector('.agent-registration');
          return {client:item?.dataset.client==='claude-code', state:item?.dataset.state==='missing',
          path:item?.textContent.includes('moved-away'), connection:$('agent-connection').textContent.includes('Fix the agent entry'),
          note:$('agent-registration-note').textContent.includes('changes nothing and sends nothing anywhere')}})()""")
        shoot('01-agent-stale-registration')
        ui.js("(async()=>{document.querySelector('.agent-registration-show').click();await frame();return true})()")
        ui.check('fix_shows_the_self_repairing_claude_command', """(async()=>({tab:$('agent-snippet').dataset.client==='claude-code',
          remove:$('agent-snippet').textContent.startsWith('claude mcp remove --scope user local_asset_library'),
          add:$('agent-snippet').textContent.includes('claude mcp add --scope user local_asset_library')}))()""")
        register(FIXTURE / 'scripts/asset-mcp.py')  # As if the user ran the command.
        ui.js("$('agent-registrations-check').click()")
        wait("$('agent-registrations').dataset.problems==='0'&&$('agent-registrations-ok')", 15)
        ui.check('check_again_confirms_this_copy', "$('agent-registrations-ok').textContent.includes('Claude Code starts this copy')")
        shoot('01-agent-waiting')
        agent = Agent()
        # The client name is recorded after initialize, a moment after the connection itself.
        wait("$('agent-connection').dataset.state==='connected'&&$('agent-connection').textContent.includes(' is connected')", 30)
        ui.check('panel_flips_to_connected_with_the_client_name', "$('agent-connection').textContent.includes('agent-setup-check is connected')")
        shoot('02-agent-connected')
        status, _ = agent.call('get_setup_status')
        assert status['guide'] and [q['id'] for q in status['ask_user']] == ['engines', 'descriptions', 'samples', 'storage_gib'], status['ask_user']
        report['checks']['status_carries_the_guide_and_only_the_users_questions'] = True
        applied, error = agent.call('apply_setup', {'answers': {'engines': ['godot'], 'descriptions': False, 'storage_gib': 30, 'samples': True}})
        assert not error and applied['status'] == 'applied' and applied['settings']['processing_formats'] == ['gltf'], applied
        assert applied['samples']['status'] == 'added', applied  # The user said yes to the built-in samples (decision 0031).
        report['checks']['agent_adds_the_samples_when_the_user_says_yes'] = True
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
        assert not error and finished['status'] == 'review', finished
        # The open panel follows the agent: finishing shows its report, not the Welcome page.
        wait("$('setup-report')&&$('setup-report').dataset.state==='review'", 15)
        ui.check('finish_shows_the_agents_report', """(async()=>({title:$('setup-step-title').textContent.includes('Your agent set up Assetarium'),
          rows:$('setup-report-rows').children.length>=5, agent:$('setup-report-rows').textContent.includes('Set by agent'),
          checked:$('setup-report-rows').textContent.includes('Checked by agent'), next:$('setup-next').textContent.includes('asset folders'),
          looksGood:!!$('setup-looks-good'), noSkip:!$('setup-skip-all'),
          rail:[...document.querySelectorAll('nav[aria-label="Setup steps"] li')].filter(li=>li.querySelector('svg')).length>=5}))()""")
        shoot('04-agent-report')
        ui.js("(async()=>{document.querySelector('[data-row=storage] .report-undo').click();"
              "await until(()=>!document.querySelector('[data-row=storage] .report-undo'));return true})()")
        record = json.loads((FIXTURE / 'data/library/setup.json').read_text(encoding='utf-8'))
        assert record['values']['storage_budget_gib']['set_by'] == 'user', record
        ui.check('undo_brings_back_the_replaced_value', "$('setup-report-rows').querySelector('[data-row=storage]').textContent.includes('Set by you')")
        ui.js("$('setup-looks-good').click()")
        wait("!$('setup-wizard')&&lal.state.history[lal.state.historyIndex].page==='sources'", 15)
        assert json.loads((FIXTURE / 'data/library/setup.json').read_text(encoding='utf-8'))['state'] == 'completed'
        report['checks']['looks_good_completes_and_leads_to_asset_sources'] = True
        ui.js("(async()=>{await lal.openSetup();await until(()=>$('setup-report'));return true})()")
        ui.check('reopened_setup_shows_the_completed_report', """(async()=>({state:$('setup-report').dataset.state==='completed',
          title:$('setup-step-title').textContent.includes('Setup complete'), close:!!$('setup-close-report')}))()""")
        shoot('05-report-completed')
        ui.js("(async()=>{document.querySelector('[aria-label=\"Change Storage budget\"]').click();await until(()=>$('setup-budget'));"
              "type('setup-budget','45');await frame();lal.goToSetupStep(lal.SETUP_STEPS.indexOf('review'));await until(()=>$('setup-summary'));await frame();return true})()")
        ui.check('review_edit_is_marked_as_changed', "$('setup-summary').querySelector('[data-step=storage]').textContent.includes('Changed by you')")
        ui.js("$('setup-save').click()")
        wait("lal.state.setup.result&&$('setup-saved-title')", 60)
        record = json.loads((FIXTURE / 'data/library/setup.json').read_text(encoding='utf-8'))
        settings = json.loads((FIXTURE / 'data/library/settings.json').read_text(encoding='utf-8'))
        assert settings['storage_budget_bytes'] == 45 * 1024**3 and settings['processing_formats'] == ['gltf']
        assert record['values']['storage_budget_gib']['set_by'] == 'user' and record['values']['processing_formats']['set_by'] == 'agent', record
        report['checks']['review_saves_only_the_users_change_as_theirs'] = True
        ui.js("(async()=>{lal.closeSetup();await lal.openSetup();await until(()=>$('setup-report-agent'));$('setup-report-agent').click();"
              "await until(()=>$('agent-panel'));return true})()")
        ui.check('the_panel_reopens', "!!$('agent-panel')&&!!$('agent-access')&&!$('agent-copy-prompt')")
        shoot('06-panel-reopened')
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
