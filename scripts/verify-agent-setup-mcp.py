"""Real STDIO check of agent setup (decision 0016) on an isolated empty project. Not evidence of agent use.

Copies this checkout's code into scratch/agent-setup-mcp/<run-name>/project and links the
prepared mcp environment (nothing is installed; the owner's library and configuration are never
touched). A scripted MCP client launches scripts/asset-mcp.py exactly as clients do and walks:
a broken configuration (setup-only server), then the full flow on a valid empty project — refused
writes without a session, the user's session, apply_setup, validate_blender (real Blender when
one is found; a non-Blender file is refused), propose → reject → propose → apply (the user's
decisions call the backend in this process, as the app's buttons do), finish_setup, connection
records and notices. Report: data/mcp/agent-setup/<run-name>/report.json
"""
import argparse
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not re.fullmatch('[a-z0-9-]{1,40}', args.run_name):
    raise SystemExit('Invalid run name')
out = ROOT / 'data/mcp/agent-setup' / args.run_name
out.mkdir(parents=True, exist_ok=False)
project = ROOT / 'scratch/agent-setup-mcp' / args.run_name / 'project'
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
report = {'status': 'running', 'platform': sys.platform, 'project': str(project), 'checks': [], 'unverified': []}


def check(name, condition, detail=None):
    report['checks'].append({'check': name, 'passed': bool(condition), **({'detail': detail} if detail is not None else {})})
    if not condition:
        raise AssertionError(f'{name}: {detail}')


def build():
    skip = shutil.ignore_patterns('__pycache__', '*.pyc')
    for name in ('src', 'scripts'):
        shutil.copytree(ROOT / name, project / name, ignore=skip)
    (project / 'docs').mkdir()
    for name in ('config.example.toml', 'docs/caption-model.json', 'docs/embedding-model.json'):
        shutil.copy2(ROOT / name, project / name)
    if os.name == 'nt':
        made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(project / '.venv-mcp'), str(ROOT / '.venv-mcp')], capture_output=True)
        if made.returncode:
            raise RuntimeError(made.stderr.decode(errors='replace'))
    else:
        (project / '.venv-mcp').symlink_to(ROOT / '.venv-mcp', target_is_directory=True)


class Client:
    """The real client launch: the mcp interpreter running scripts/asset-mcp.py over STDIO."""
    def __init__(self, label):
        python = project / ('.venv-mcp/Scripts/python.exe' if os.name == 'nt' else '.venv-mcp/bin/python')
        self.stderr = (out / f'{label}-stderr.log').open('w', encoding='utf-8')
        self.process = subprocess.Popen([str(python), str(project / 'scripts/asset-mcp.py')], cwd=out, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.stderr, text=True, encoding='utf-8', creationflags=NO_WINDOW)
        self.lines, self.sequence = queue.Queue(), 0
        threading.Thread(target=self._read, daemon=True).start()
        self.init = self.send('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                             'clientInfo': {'name': 'agent-setup-check', 'version': '1'}})['result']
        self.send('notifications/initialized', notification=True)

    def _read(self):
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, method, params=None, notification=False):
        message = {'jsonrpc': '2.0', 'method': method, **({'params': params} if params is not None else {})}
        if not notification:
            self.sequence += 1
            message['id'] = self.sequence
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()
        while not notification:
            line = self.lines.get(timeout=240)
            if line is None:
                raise RuntimeError('Server exited')
            response = json.loads(line)  # Anything but protocol on stdout fails here.
            if response.get('id') == self.sequence:
                return response

    def call(self, name, arguments=None):
        result = self.send('tools/call', {'name': name, 'arguments': arguments or {}})['result']
        text = result['content'][0]['text']
        return json.loads(text), bool(result.get('isError')), len(text)

    def close(self):
        self.process.stdin.close()
        code = self.process.wait(30)
        self.stderr.close()
        return code


def records():
    folder = project / 'data/mcp/connections'
    return [json.loads(p.read_text(encoding='utf-8')) for p in folder.glob('*.json')] if folder.is_dir() else []


try:
    build()
    sys.path.insert(0, str(project / 'src'))
    # Phase 1: a configuration that does not load still gives an agent the fault and the fix.
    (project / 'config.local.toml').write_text((ROOT / 'config.example.toml').read_text(encoding='utf-8').replace(
        'models = "models"', "models = 'C:/lal-missing-models-folder'" if os.name == 'nt' else "models = '/lal-missing-models-folder'"), encoding='utf-8')
    client = Client('degraded')
    tools = [t['name'] for t in client.send('tools/list')['result']['tools']]
    check('degraded server lists only get_setup_status', tools == ['get_setup_status'], tools)
    check('degraded instructions say so', 'failed to load' in client.init.get('instructions', ''))
    status, error, _ = client.call('get_setup_status')
    check('degraded status names the fault and the fix', not error and status['mode'] == 'setup_only'
          and 'missing' in status['fault'] and 'config.local.toml' in status['fix'], status)
    check('degraded connection record while connected', [r['mode'] for r in records()] == ['setup_only'], records())
    _, error, _ = client.call('apply_setup', {'storage_budget_gib': 20})
    check('degraded server refuses everything else', error)
    check('degraded server exits cleanly', client.close() == 0)
    check('connection record removed on exit', records() == [], records())
    # A configured Blender that no longer exists (moved or uninstalled), so the discovered one needs the user's approval.
    # Outside the project: Blender paths are revealed by design, the project path is not.
    gone = project.parent / 'old-blender' / ('blender.exe' if os.name == 'nt' else 'blender')
    (project / 'config.local.toml').write_text((ROOT / 'config.example.toml').read_text(encoding='utf-8').replace(
        '[tools]', '[tools]\nblender = ' + json.dumps(str(gone)), 1), encoding='utf-8')

    # Phase 2: the whole flow on a valid, empty project.
    from local_asset_library import notifications, setup_agent, setup_core
    from local_asset_library.config import load_project_config
    config = load_project_config(project)
    client = Client('flow')
    check('setup hint in instructions while setup is unfinished', 'get_setup_status' in client.init.get('instructions', ''))
    listed = {t['name']: t for t in client.send('tools/list')['result']['tools']}
    check('setup tools listed', set(setup_agent.tools()) == set(listed) and {'get_setup_status', 'apply_setup', 'validate_blender',
          'propose_setup', 'finish_setup'} <= set(listed), sorted(listed))
    check('status is read-only, setup writes are not destructive', listed['get_setup_status']['annotations']['readOnlyHint']
          and not listed['apply_setup']['annotations']['destructiveHint'])
    prompts = client.send('prompts/list')['result']['prompts']
    prompt = client.send('prompts/get', {'name': 'set_up_assetarium'})['result']
    check('setup prompt offered', [p['name'] for p in prompts] == ['set_up_assetarium']
          and 'get_setup_status' in prompt['messages'][0]['content']['text'])
    check('connection record names the client', [(r['mode'], (r['client'] or {}).get('name')) for r in records()] == [('normal', 'agent-setup-check')], records())
    status, error, size = client.call('get_setup_status')
    check('status before a session', not error and not status['session']['open'] and status['next_actions'][0]['for'] == 'session'
          and size <= status['character_cap'], {k: status.get(k) for k in ('session', 'setup')})
    text = json.dumps(status, ensure_ascii=False)
    check('status does not reveal the project path', str(project) not in text and json.dumps(str(project))[1:-1] not in text)
    refused, error, _ = client.call('apply_setup', {'storage_budget_gib': 20})
    check('write refused without a session', error and refused['status'] == 'refused', refused)
    setup_agent.open_session(config, 'app')  # The user's click on "Set up with my agent".
    applied, error, _ = client.call('apply_setup', {'storage_budget_gib': 25, 'processing_formats': ['gltf'], 'engine_hint': 'godot',
                                                    'caption_batch_size': 4})
    check('apply_setup applies and records the agent', not error and applied['status'] == 'applied'
          and json.loads(setup_core.setup_path(config).read_text(encoding='utf-8'))['values']['processing_formats']['set_by'] == 'agent', applied)
    bad, error, _ = client.call('apply_setup', {'description_engine': 'local-server', 'description_server': {'url': 'http://198.51.100.7/v1', 'model': 'x'}})
    check('non-loopback model server refused', error and bad['status'] == 'faulty', bad)
    other = project / ('notepad.exe' if os.name == 'nt' else 'bash')
    other.write_bytes(b'not run')
    result, error, _ = client.call('validate_blender', {'path': str(other)})
    check('validate_blender refuses another program without running it', not error and result['status'] == 'failed'
          and result['checks'][0]['id'] == 'file', result)
    candidates = status['blender']['candidates']
    if candidates:
        path = candidates[0]['path']
        result, error, _ = client.call('validate_blender', {'path': path})
        check('validate_blender passes a real Blender', not error and result['status'] in {'passed', 'warning'}, result)
        first, error, _ = client.call('propose_setup', {'blender_path': path})
        if first['status'] == 'unchanged':
            report['unverified'].append('Blender proposal: the discovered Blender is already the one used, so nothing needed approval')
        else:
            check('proposal pending and noticed', not error and first['status'] == 'pending'
                  and any(i['kind'] == 'setup_proposal' for i in notifications.load(config)['items']), first)
            blocked, error, _ = client.call('finish_setup')
            check('finish refused while a proposal waits', error and blocked['status'] == 'refused', blocked)
            check('user rejects', setup_agent.decide(config, first['proposal']['id'], 'reject')['status'] == 'rejected')
            states = [p['state'] for p in client.call('get_setup_status')[0]['proposals']]
            check('agent sees rejected', states[-1] == 'rejected', states)
            second, _, _ = client.call('propose_setup', {'blender_path': path})
            decided = setup_agent.decide(config, second['proposal']['id'], 'apply')
            check('user applies after a fresh check', decided['status'] == 'applied'
                  and load_project_config(project).blender is not None, decided)
            check('agent sees applied', client.call('get_setup_status')[0]['proposals'][-1]['state'] == 'applied')
    else:
        report['unverified'].append('No Blender found on this computer: validate_blender and the proposal flow ran only in pytest')
    finished, error, _ = client.call('finish_setup')
    check('finish_setup completes', not error and finished['status'] == 'completed', finished)
    check('setup recorded as completed by the agent', setup_core.load_record(config)[0]['by'] == 'agent')
    notice = next((i for i in notifications.load(config)['items'] if i['kind'] == 'setup_changed'), None)
    check('one notice lists the agent changes', notice and {c['key'] for c in notice['changes']} >= {'storage_budget_gib', 'processing_formats'}, notice)
    setup_agent.end_session(config)
    refused, error, _ = client.call('apply_setup', {'storage_budget_gib': 30})
    check('write refused after the user ends the session', error and refused['status'] == 'refused')
    run = next(p for p in (project / 'data/mcp/runs').iterdir() if (p / 'calls.jsonl').exists()
               and 'finish_setup' in (p / 'calls.jsonl').read_text(encoding='utf-8'))
    calls = [json.loads(line)['tool'] for line in (run / 'calls.jsonl').read_text(encoding='utf-8').splitlines()]
    check('every call audited', calls.count('get_setup_status') >= 1 and 'apply_setup' in calls, calls)
    check('server exits cleanly', client.close() == 0)
    check('connection record removed', records() == [], records())
    report['status'] = 'passed'
except Exception as exc:
    report.update(status='failed', fault=f'{type(exc).__name__}: {exc}'[:2000])
finally:
    from scratch_links import release
    release(project / '.venv-mcp')  # scratch/ stays safe to delete (AGENTS.md).
    (out / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'checks': len(report['checks']), 'unverified': report['unverified'],
                      'fault': report.get('fault'), 'report': str(out / 'report.json')}, indent=2))
    sys.exit(0 if report['status'] == 'passed' else 1)
