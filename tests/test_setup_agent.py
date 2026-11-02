"""Agent setup through MCP (decisions 0016, 0024): no session gate, proposals, degraded mode, connection records, notices, bounds."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from local_asset_library import mcp_server, notifications, setup_agent, setup_core
from local_asset_library.config import ConfigError
from local_asset_library.mcp_assets import DETAIL_CAP, SCHEMAS, SETUP_TOOLS, WRITE_TOOLS, validate
from local_asset_library.settings import general_settings, settings_path
from test_setup_core import project_with_example

NAME = 'blender.exe' if os.name == 'nt' else 'blender'
START = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
CLOCK = [START]  # The injected clock; tests move it.


@pytest.fixture
def project(tmp_path, monkeypatch):
    config = project_with_example(tmp_path)
    (config.project_root / 'docs').mkdir()
    (config.project_root / 'docs/library-membership.json').write_text(json.dumps(
        {'budget': {'total_allocated_bytes': 10 * 1024**3, 'peak_additional_allocated_bytes': 3 * 1024**3}}), encoding='utf-8')
    monkeypatch.setattr(setup_core, 'gpu_report', lambda run=None: {'status': 'none', 'nvidia': [], 'other': []})
    monkeypatch.setattr('local_asset_library.inspection.blender_candidates', lambda config: [])  # Never this computer's Blender.
    monkeypatch.setattr(setup_agent, '_environment', {})
    monkeypatch.setattr(setup_agent, '_verifying', {})
    CLOCK[:] = [START]
    monkeypatch.setattr(setup_agent, "clock", lambda: CLOCK[0])
    return config


@pytest.fixture
def blender(project, monkeypatch):
    """A file named like Blender that this process 'checked'; nothing runs it."""
    path = project.project_root.parent / 'tools' / NAME
    path.parent.mkdir()
    path.write_bytes(b'synthetic')
    monkeypatch.setattr(setup_core, '_probe', lambda *a: pytest.fail('nothing may run'))
    monkeypatch.setattr(setup_core, 'processed_models', lambda config: 0)
    monkeypatch.setattr(setup_core, 'blender_change', lambda config, chosen: 'write')
    def check(config, chosen):
        setup_core._validated[setup_core._identity(chosen)] = {'status': 'passed', 'version': '5.2.2'}
        return {'status': 'passed', 'path': chosen, 'checks': [{'id': 'file', 'status': 'passed'}], 'version': '5.2.2', 'change': 'write', 'rerender': 0}
    monkeypatch.setattr(setup_core, 'check_blender', check)
    return str(path)


def call(config, name, args=None):
    gateway = mcp_server.Gateway(config)
    result = asyncio.run(gateway.call(name, args or {}))
    return json.loads(result.content[0].text), result.is_error, gateway


def test_setup_tools_are_declared_described_and_annotated():
    assert SETUP_TOOLS <= set(SCHEMAS) and SETUP_TOOLS <= set(mcp_server.DESCRIPTIONS)
    assert {'apply_setup', 'propose_setup', 'finish_setup'} <= WRITE_TOOLS and 'get_setup_status' not in WRITE_TOOLS
    assert mcp_server.annotation('get_setup_status')['readOnlyHint']
    for name in ('apply_setup', 'propose_setup', 'finish_setup', 'validate_blender'):
        hints = mcp_server.annotation(name)
        assert not hints['readOnlyHint'] and not hints['destructiveHint'] and not hints['openWorldHint']
    assert mcp_server.annotation('edit_collection')['destructiveHint']
    assert mcp_server.tool_names(None) == ['get_setup_status']
    assert 'cloud' in mcp_server.DESCRIPTIONS['get_setup_status']
    for name, args in (('apply_setup', {'caption_batch_size': 3}), ('apply_setup', {'processing_formats': ['blend']}),
                       ('apply_setup', {'description_server': {'url': 'http://127.0.0.1:1/v1', 'token': 'x'}}),
                       ('apply_setup', {'storage_budget_gib': True}), ('validate_blender', {'path': 3}), ('get_setup_status', {'path': '/x'}),
                       ('propose_setup', {'blender_path': 'C:\\b\n'}), ('apply_setup', {'engine_hint': 'cryengine'})):
        with pytest.raises(ConfigError):
            validate(name, args)


def test_writes_need_no_session_and_one_notice_collects_a_day(project, blender):
    # Decision 0024 replaced the session gate with tiers: applying is recorded and noticed, Blender is only proposed.
    assert call(project, 'apply_setup', {'storage_budget_gib': 20})[0]['status'] == 'applied'
    CLOCK[0] = START + timedelta(hours=1)
    assert call(project, 'apply_setup', {'storage_budget_gib': 30})[0]['status'] == 'applied'
    notices = [item for item in notifications.load(project)['items'] if item['kind'] == 'setup_changed']
    assert len(notices) == 1 and general_settings(project)['storage_budget_gib'] == 30
    assert call(project, 'validate_blender', {'path': blender})[0]['status'] == 'passed'
    assert not hasattr(setup_agent, 'open_session') and 'session' not in setup_agent.status(project)


def test_apply_validates_like_the_wizard_and_records_the_agent(project, monkeypatch):
    for bad in ({'storage_budget_gib': 0}, {'description_engine': 'local-server', 'description_server': {'url': 'http://example.com/v1', 'model': 'm'}}, {}):
        payload, error, _ = call(project, 'apply_setup', bad)
        assert error and payload['status'] == 'faulty'
    assert not settings_path(project).exists()
    monkeypatch.setattr(setup_core, 'check_server', lambda config, url, model='': {'status': 'connected', 'url': url, 'models': ['vision'], 'model_found': True})
    payload, error, _ = call(project, 'apply_setup', {'processing_formats': ['gltf'], 'engine_hint': 'godot', 'description_engine': 'local-server',
                                                     'description_server': {'url': 'http://127.0.0.1:8080/v1', 'model': 'vision'}})
    assert not error and payload['status'] == 'applied' and payload['server_check']['model_found']
    assert set(payload['changed']) == {'processing_formats', 'description_engine', 'description_server', 'engine_hint'}
    record = json.loads(setup_core.setup_path(project).read_text(encoding='utf-8'))
    assert {record['values'][k]['set_by'] for k in payload['changed']} == {'agent'} and record['engine_hint'] == ['godot']
    assert call(project, 'apply_setup', {'processing_formats': ['gltf']})[0]['status'] == 'unchanged'
    notice = next(item for item in notifications.load(project)['items'] if item['kind'] == 'setup_changed')
    assert {change['key'] for change in notice['changes']} == set(payload['changed'])


def test_proposal_is_pending_until_the_user_applies_or_rejects_it(project, blender, monkeypatch):
    payload, error, _ = call(project, 'propose_setup', {'blender_path': blender})
    assert error and 'validate_blender' in payload['reason']  # Only a path checked in this process.
    assert call(project, 'validate_blender', {'path': blender})[0]['status'] == 'passed'
    first = call(project, 'propose_setup', {'blender_path': blender})[0]
    assert first['status'] == 'pending' and first['proposal']['version'] == '5.2.2'
    assert not (project.project_root / 'config.local.toml').exists()  # Proposing writes no configuration.
    assert any(item['kind'] == 'setup_proposal' for item in notifications.load(project)['items'])
    payload, error, _ = call(project, 'finish_setup')
    assert error and 'waiting for the user' in payload['reason']
    second = call(project, 'propose_setup', {'blender_path': blender})[0]['proposal']
    states = {p['id']: p['state'] for p in call(project, 'get_setup_status')[0]['proposals']}
    assert states == {first['proposal']['id']: 'superseded', second['id']: 'pending'}
    assert setup_agent.decide(project, second['id'], 'reject')['status'] == 'rejected'
    assert not (project.project_root / 'config.local.toml').exists()
    with pytest.raises(ConfigError, match='no longer pending'):
        setup_agent.decide(project, second['id'], 'apply')
    third = call(project, 'propose_setup', {'blender_path': blender})[0]['proposal']
    result = setup_agent.decide(project, third['id'], 'apply')
    assert result['status'] == 'applied' and result['blender']['status'] == 'saved'
    record = json.loads(setup_core.setup_path(project).read_text(encoding='utf-8'))
    assert record['values']['blender'] == {**record['values']['blender'], 'set_by': 'agent', 'approved_by': 'user'}
    assert not any(item['kind'] == 'setup_proposal' for item in notifications.load(project)['items'])
    assert call(project, 'get_setup_status')[0]['proposals'][-1]['state'] == 'applied'
    assert call(project, 'finish_setup')[0]['status'] == 'review'  # The user's Looks good completes it.
    assert json.loads(setup_core.setup_path(project).read_text(encoding='utf-8'))['by'] == 'agent'


def test_a_file_changed_after_the_agents_check_is_not_applied(project, blender):
    call(project, 'validate_blender', {'path': blender})
    proposal = call(project, 'propose_setup', {'blender_path': blender})[0]['proposal']
    Path(blender).write_bytes(b'swapped for something else')
    result = setup_agent.decide(project, proposal['id'], 'apply')
    assert result['status'] == 'failed' and 'changed' in result['proposal']['reason']
    assert not (project.project_root / 'config.local.toml').exists()


def test_unconfirmed_rerender_keeps_the_proposal_pending(project, blender, monkeypatch):
    monkeypatch.setattr(setup_core, 'processed_models', lambda config: 7)
    call(project, 'validate_blender', {'path': blender})
    proposal = call(project, 'propose_setup', {'blender_path': blender})[0]['proposal']
    assert proposal['rerender'] == 7
    with pytest.raises(ConfigError, match='rendered again'):
        setup_agent.decide(project, proposal['id'], 'apply')
    assert setup_agent.load(project)[0]['proposals'][-1]['state'] == 'pending'


def test_validate_blender_never_runs_other_programs(project, monkeypatch):
    monkeypatch.setattr(setup_core, '_probe', lambda *a: pytest.fail('nothing may run'))
    other = project.project_root / ('cmd.exe' if os.name == 'nt' else 'sh')
    other.write_bytes(b'x')
    folder = project.project_root / 'dir' / NAME
    folder.mkdir(parents=True)
    script = project.project_root / ('blender.bat' if os.name == 'nt' else 'blender.sh')
    script.write_bytes(b'x')
    for path in (str(other), str(folder), str(script), 'blender', str(project.project_root / 'missing' / NAME)):
        payload, error, _ = call(project, 'validate_blender', {'path': path})
        assert not error and payload['status'] == 'failed' and payload['checks'][0]['id'] == 'file'


def test_degraded_mode_reports_the_fault_and_the_fix_and_nothing_else(tmp_path):
    gateway = mcp_server.Gateway(None, root=tmp_path, config_fault=(ConfigError('Shared model directory is missing'), 'config.local.toml'))
    status = json.loads(asyncio.run(gateway.call('get_setup_status', {})).content[0].text)
    assert status['status'] == 'faulty' and status['mode'] == 'setup_only'
    assert 'config.local.toml' in status['fix'] and 'models = "models"' in status['fix']
    refused = asyncio.run(gateway.call('search_assets', {'query': 'x'}))
    assert refused.is_error and 'Setup-only' in json.loads(refused.content[0].text)['reason']
    lines = (gateway.audit_root / 'calls.jsonl').read_text(encoding='utf-8').splitlines()
    assert [json.loads(line)['tool'] for line in lines] == ['get_setup_status', 'search_assets']
    assert gateway.audit_root.is_relative_to(tmp_path / 'data/mcp/runs')
    assert setup_agent.config_fix('Something new', 'config.local.toml').startswith('Compare config.local.toml')


def test_broken_config_starts_the_setup_only_server(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(mcp_server, 'load_project_config', lambda root: (_ for _ in ()).throw(ConfigError('Shared model directory is missing')))
    async def serve(config, root=None, config_fault=None):
        seen.update(config=config, fault=str(config_fault[0]), file=config_fault[1])
    monkeypatch.setattr(mcp_server, 'serve', serve)
    mcp_server.main()
    assert seen['config'] is None and seen['fault'] == 'Shared model directory is missing' and seen['file'].startswith('config.')


def test_connection_records_create_detect_and_go_stale(tmp_path):
    record = setup_agent.write_connection(tmp_path, 'run', 'normal')
    assert [c['pid'] for c in setup_agent.connections(tmp_path)] == [os.getpid()]
    setup_agent.note_client(tmp_path, os.getpid(), {'name': 'Codex', 'version': '1.0'})
    assert setup_agent.connections(tmp_path)[0]['client'] == {'name': 'Codex', 'version': '1.0'}
    done = subprocess.run([sys.executable, '-c', 'import os; print(os.getpid())'], capture_output=True, text=True)
    dead = int(done.stdout)
    (setup_agent.connections_dir(tmp_path) / f'{dead}.json').write_text(json.dumps(dict(record, pid=dead)), encoding='utf-8')
    assert [c['pid'] for c in setup_agent.connections(tmp_path)] == [os.getpid()]  # An exited process is not connected.
    assert [alive for _, _, alive in setup_agent.connection_token(tmp_path)].count(False) == 1
    setup_agent.write_connection(tmp_path, 'run2', 'normal')  # A new server prunes records of dead ones.
    assert not (setup_agent.connections_dir(tmp_path) / f'{dead}.json').exists()
    setup_agent.remove_connection(tmp_path)
    assert setup_agent.connections(tmp_path) == []


def test_client_name_comes_from_the_initialize_request(project):
    from types import SimpleNamespace
    gateway = mcp_server.Gateway(project)
    setup_agent.write_connection(project.project_root, gateway.run_id, 'normal')
    ctx = SimpleNamespace(session=SimpleNamespace(client_params=SimpleNamespace(client_info=SimpleNamespace(name='claude-code', version='2.1'))))
    gateway.note_client(ctx)
    assert setup_agent.connections(project.project_root)[0]['client']['name'] == 'claude-code'
    other = mcp_server.Gateway(project)
    other.note_client(SimpleNamespace(session=SimpleNamespace(client_params=None)))  # Optional on newer protocols.
    setup_agent.remove_connection(project.project_root)


def test_status_reveals_only_what_setup_needs_and_stays_bounded(project, monkeypatch):
    monkeypatch.setenv('LAL_SECRET_PROBE', 'do-not-leak')
    status = setup_agent.status(project)
    text = json.dumps(status)
    raw = json.dumps(status, ensure_ascii=False)
    assert 'do-not-leak' not in raw and str(project.project_root) not in raw and json.dumps(str(project.project_root))[1:-1] not in raw
    assert {'os', 'gpu', 'disk', 'blender', 'settings', 'set_by', 'proposals', 'missing', 'next_actions', 'privacy'} <= set(status)
    assert all(action['for'] != 'session' for action in status['next_actions'])
    assert set(status['disk']) == {'free_gib', 'total_gib'}
    payload, error, _ = call(project, 'get_setup_status')
    assert not error and payload['serialized_characters'] <= DETAIL_CAP


def test_instructions_carry_a_setup_hint_until_setup_is_finished(project):
    assert 'get_setup_status' in mcp_server.instructions(project)
    setup_core.save_setup(project, {'storage_budget_gib': 20})
    assert mcp_server.instructions(project) == mcp_server.INSTRUCTIONS
    assert 'get_setup_status' in setup_agent.PROCEDURE and 'answers' in setup_agent.PROCEDURE and 'ask_user' in setup_agent.GUIDE


def test_snippets_list_every_tool_for_allowlisting_clients(project):
    snippets = {item['id']: item for item in setup_agent.snippets(project.project_root)}
    assert set(snippets) == {'codex', 'claude-code', 'opencode', 'generic'}
    import tomllib
    codex = tomllib.loads(snippets['codex']['text'])['mcp_servers']['local_asset_library']
    assert codex['enabled_tools'] == list(SCHEMAS) and codex['args'] == [str(project.project_root / 'scripts/asset-mcp.py')]
    assert json.loads(snippets['generic']['text'])['mcpServers']['local_asset_library']['cwd'] == str(project.project_root)
    remove, add = snippets['claude-code']['text'].splitlines()  # Re-running replaces an entry left by a moved checkout.
    assert remove == 'claude mcp remove --scope user local_asset_library' and add.startswith('claude mcp add --scope user local_asset_library -- ')


def registered(project, tmp_path, script=None, python=None):
    """Synthetic client settings in a fake home: a Claude Code user entry, an unrelated server and secret, a project entry."""
    home = tmp_path / 'home'
    (home / '.codex').mkdir(parents=True)
    python = python or str(project.project_root / '.venv-mcp/python.exe')
    script = script or str(project.project_root / 'scripts/asset-mcp.py')
    for path in (python, script):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text('', encoding='utf-8')
    entry = {'type': 'stdio', 'command': python, 'args': [script], 'env': {'TOKEN': 'secret'}}
    gone = str(tmp_path / 'old/scripts/asset-mcp.py')
    (home / '.claude.json').write_text(json.dumps({'oauthAccount': {'email': 'x'}, 'mcpServers': {'local_asset_library': entry, 'other': entry},
                                                   'projects': {'D:/game': {'mcpServers': {'local_asset_library': dict(entry, args=[gone])}}, 'D:/x': []}}), encoding='utf-8')
    (home / '.codex/config.toml').write_text('[mcp_servers.local_asset_library]\ncommand = "uv"\nargs = ["run", "asset"]\n', encoding='utf-8')
    return home


def test_registrations_report_only_this_server_and_whether_it_starts_this_checkout(project, tmp_path):
    home = registered(project, tmp_path)
    found = setup_agent.registrations(project.project_root, home, {})
    assert [(item['label'], item['scope'], item['state']) for item in found] == [
        ('Claude Code', 'user', 'ok'), ('Claude Code', 'project', 'missing'), ('Codex', 'user', 'unrecognized')]
    assert 'secret' not in json.dumps(found) and 'oauth' not in json.dumps(found)  # Only this server's command and script.
    assert found[1]['fix'] == 'In D:/game, run: claude mcp remove --scope local local_asset_library' and found[0]['fix'] is None
    assert setup_agent.client_files(home, {'CLAUDE_CONFIG_DIR': str(tmp_path / 'c')})[0][2] == tmp_path / 'c/.claude.json'
    assert setup_agent.client_files(None, {'LAL_CLIENT_HOME': str(home), 'CODEX_HOME': 'elsewhere'})[1][2] == home / '.codex/config.toml'


def test_registration_of_a_moved_or_other_checkout_is_a_problem_with_a_fix(project, tmp_path):
    other = tmp_path / 'other'
    home = registered(project, tmp_path, script=str(other / 'scripts/asset-mcp.py'))
    user = setup_agent.registrations(project.project_root, home, {})[0]
    assert user['state'] == 'other_checkout' and 'Claude Code command' in user['fix']
    (other / 'scripts/asset-mcp.py').unlink()  # The copy is deleted; the parsed file is cached but the check is not.
    assert setup_agent.registrations(project.project_root, home, {})[0]['state'] == 'missing'
    (home / '.claude.json').write_text('{damaged', encoding='utf-8')
    damaged = setup_agent.registrations(project.project_root, home, {})[0]
    assert damaged['state'] == 'unreadable' and 'not checked' in damaged['reason']
    assert setup_agent.registrations(project.project_root, tmp_path / 'nobody', {}) == []


def test_app_and_cli_show_registration_problems(project, tmp_path, monkeypatch, capsys):
    from local_asset_library import owner_commands
    home = registered(project, tmp_path, script=str(tmp_path / 'gone/scripts/asset-mcp.py'))
    (tmp_path / 'gone/scripts/asset-mcp.py').unlink()
    monkeypatch.setenv('LAL_CLIENT_HOME', str(home))
    state = setup_agent.app_state(project)
    assert state['registrations'][0]['state'] == 'missing' and 'changes nothing' in state['registration_note']
    result = owner_commands.setup_command(owner_commands.parser().parse_args(['setup', 'agent', 'check']), project)
    out = capsys.readouterr().out
    assert result['status'] == 'faulty' and 'no longer exists' in out and 'Fix: Run the Claude Code command' in out
    owner_commands.setup_command(owner_commands.parser().parse_args(['setup', 'agent']), project)
    assert capsys.readouterr().out.startswith('Warning: Claude Code starts a copy of Assetarium that no longer exists.')


def test_cli_shows_how_to_connect_and_proposals_need_an_interactive_terminal(project, monkeypatch, capsys):
    from local_asset_library import owner_commands
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    assert owner_commands.setup_command(owner_commands.parser().parse_args(['setup', 'agent']), project)['prompt'] == setup_agent.SETUP_PROMPT
    assert 'claude mcp add' in capsys.readouterr().out
    with pytest.raises(ConfigError, match='interactive terminal'):
        owner_commands.setup_command(owner_commands.parser().parse_args(['setup', 'agent', 'proposals']), project)


def test_damaged_agent_record_is_kept_and_blocks_proposals(project):
    setup_agent.store_path(project).parent.mkdir(parents=True, exist_ok=True)
    setup_agent.store_path(project).write_text('{damaged', encoding='utf-8')
    assert 'kept for review' in setup_agent.load(project)[1] and 'kept for review' in setup_agent.app_state(project)['fault']
    with pytest.raises(ConfigError, match='kept for review'):
        setup_agent._change(project, lambda value: None)
    assert setup_agent.store_path(project).read_text(encoding='utf-8') == '{damaged'


# ------------------------------ guided setup ------------------------------

RTX = {'status': 'nvidia', 'nvidia': [{'name': 'RTX test', 'vram_gib': 12.0, 'driver': '1', 'compute_capability': 12.0}], 'other': []}


def test_status_checks_itself_and_asks_only_the_users_questions(project, monkeypatch):
    status = setup_agent.status(project)
    assert status['guide'] == setup_agent.GUIDE and 'one message' in status['guide']
    assert [q['id'] for q in status['ask_user']] == ['engines', 'descriptions', 'samples', 'storage_gib']
    descriptions = status['ask_user'][1]
    assert 'local model server' in descriptions['ask'] and 'Settings' in descriptions['why'] and descriptions['suggestion'] is False
    assert status['ask_user'][3]['suggestion'] == 20 and status['ask_user'][0]['several'] and status['ask_user'][2]['suggestion'] is True
    assert {line['id'] for line in status['found']} >= {'gpu', 'disk', 'blender'}
    assert next(line for line in status['found'] if line['id'] == 'blender')['ok'] is False
    assert any(action['for'] == 'blender' and action['kind'] == 'install' for action in status['next_actions'])
    monkeypatch.setattr(setup_core, 'gpu_report', lambda run=None: RTX)
    monkeypatch.setattr(setup_agent, '_environment', {})
    descriptions = setup_agent.status(project)['ask_user'][1]
    assert 'RTX test' in descriptions['why'] and descriptions['suggestion'] is True


def test_answers_derive_settings_and_say_why(project, monkeypatch):
    monkeypatch.setattr(setup_core, 'gpu_report', lambda run=None: RTX)
    payload, error, _ = call(project, 'apply_setup', {'answers': {'engines': ['godot', 'unity'], 'descriptions': True, 'storage_gib': 40}})
    assert not error and payload['status'] == 'applied'
    settings = payload['settings']
    assert settings['processing_formats'] == ['fbx', 'gltf'] and settings['description_engine'] == 'builtin'
    assert settings['caption_batch_size'] == 8 and settings['search_device'] == 'cuda' and settings['storage_budget_gib'] == 40
    assert {item['key'] for item in payload['implied']} == {'processing_formats', 'description_engine', 'caption_batch_size', 'search_device'}
    assert all(item['because'] for item in payload['implied']) and 'next_actions' in payload
    assert json.loads(setup_core.setup_path(project).read_text(encoding='utf-8'))['engine_hint'] == ['godot', 'unity']
    # An explicit value overrides what an answer implied.
    payload = call(project, 'apply_setup', {'answers': {'engines': ['unreal']}, 'processing_formats': ['obj']})[0]
    assert payload['settings']['processing_formats'] == ['obj'] and 'processing_formats' not in {i['key'] for i in payload['implied']}


def test_without_bf16_descriptions_need_a_running_server_or_wait_for_settings(project, monkeypatch):
    payload, error, _ = call(project, 'apply_setup', {'answers': {'descriptions': True}})
    assert error and 'model_server' in payload['reason'] and 'Settings' in payload['reason']
    payload, error, _ = call(project, 'apply_setup', {'answers': {'descriptions': 'yes'}})
    assert error
    payload = call(project, 'apply_setup', {'answers': {'descriptions': False, 'engines': ['unsure']}})[0]
    assert payload['settings']['descriptions_enabled'] is False and payload['settings']['search_device'] == 'cpu'
    assert payload['settings']['processing_formats'] == ['fbx', 'gltf', 'obj']
    monkeypatch.setattr(setup_core, 'check_server', lambda config, url, model='': {'status': 'connected', 'url': url, 'models': ['vl'], 'model_found': True})
    payload = call(project, 'apply_setup', {'answers': {'descriptions': True, 'model_server': {'url': 'http://127.0.0.1:1234/v1', 'model': 'vl'}}})[0]
    assert payload['settings']['description_engine'] == 'local-server' and payload['server_check']['model_found']


def test_finish_waits_for_the_users_review_and_looks_good_completes(project):
    payload = call(project, 'apply_setup', {'answers': {'descriptions': False, 'storage_gib': 30}, 'finish': True})[0]
    assert payload['finish']['status'] == 'review' and 'choose the folders' in payload['finish']['next']
    assert mcp_server.instructions(project) == mcp_server.INSTRUCTIONS + mcp_server.REVIEW_HINT
    assert setup_core.setup_state(project)['record']['state'] == 'review'
    notice = next(item for item in notifications.load(project)['items'] if item['kind'] == 'setup_changed')
    assert notice['finished']
    assert setup_core.confirm_review(project)['status'] == 'completed'
    record = setup_core.setup_state(project)['record']
    assert record['state'] == 'completed' and record['by'] == 'agent' and record['reviewed_utc']
    with pytest.raises(ConfigError, match='not waiting'):
        setup_core.confirm_review(project)


def test_undo_brings_back_the_value_an_agent_replaced(project):
    before = general_settings(project)['storage_budget_gib']
    call(project, 'apply_setup', {'answers': {'storage_gib': 55, 'engines': ['godot']}})
    assert general_settings(project)['storage_budget_gib'] == 55
    assert setup_core.undo_value(project, 'storage_budget_gib') == {'status': 'undone', 'key': 'storage_budget_gib', 'value': before}
    assert general_settings(project)['storage_budget_gib'] == before
    record = json.loads(setup_core.setup_path(project).read_text(encoding='utf-8'))
    assert record['values']['storage_budget_gib']['set_by'] == 'user'
    with pytest.raises(ConfigError, match='Only a value your agent changed'):
        setup_core.undo_value(project, 'storage_budget_gib')
    assert setup_core.undo_value(project, 'engine_hint')['value'] is None
    assert json.loads(setup_core.setup_path(project).read_text(encoding='utf-8'))['engine_hint'] is None


def test_validate_blender_defaults_to_the_configured_one_and_explains_itself(project, blender, monkeypatch):
    payload, error, _ = call(project, 'validate_blender')
    assert error and 'Give path' in payload['reason'] and 'no Blender is configured' in payload['reason']
    setup_core.write_blender(project, blender)
    monkeypatch.setattr(setup_core, 'blender_change', lambda config, chosen: 'unchanged')
    fake = setup_core.check_blender
    monkeypatch.setattr(setup_core, 'check_blender', lambda config, chosen: {**fake(config, chosen), 'change': 'unchanged'})
    payload = call(project, 'validate_blender')[0]
    assert payload['status'] == 'passed' and payload['path'] == blender and 'nothing to propose' in payload['next']
    payload = call(project, 'propose_setup', {'blender_path': blender})[0]
    assert payload['status'] == 'already_applied' and payload['version'] == '5.2.2'
    found = next(line for line in setup_agent.status(project)['found'] if line['id'] == 'blender')
    assert found['ok'] and 'configured and passed' in found['text']


def weights(project, damaged=False):
    """A synthetic pinned revision: contract, manifest and the files placed by hand (no receipt)."""
    import hashlib
    files = {'config.json': b'{}', 'model.safetensors': b'weights' * 100}
    docs = project.project_root / 'docs'
    docs.mkdir(exist_ok=True)
    (docs / 'embedding-model.json').write_text(json.dumps({'revision': 'rev1'}), encoding='utf-8')
    (docs / 'embedding-model-files.json').write_text(json.dumps({'revision': 'rev1', 'files': [
        {'name': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in files.items()]}), encoding='utf-8')
    folder = project.project_root / 'models/embeddinggemma-2/rev1'
    folder.mkdir(parents=True)
    for name, data in files.items():
        (folder / name).write_bytes(data.replace(b'w', b'W') if damaged and name == 'model.safetensors' else data)


def test_weights_placed_by_hand_are_verified_locally_never_downloaded(project):
    from local_asset_library import engines
    weights(project)
    ready = engines.weights_ready(project, 'embedding')
    assert ready['state'] == 'present' and not ready['ready'] and 'downloads nothing' in ready['reason']
    item = next(i for i in engines.search_readiness(project, device='cpu') if i['id'] == 'embedding_weights')
    assert 'setup verify-weights embedding' in item['command'] and 'prepare_embedding_model' not in item['command']
    action = next(a for a in setup_agent.actions(project) if a['for'] == 'embedding_weights')
    assert action['kind'] == 'tool' and action['tool'] == 'verify_weights'
    payload = call(project, 'verify_weights', {'model': 'embedding'})[0]
    assert payload['status'] == 'verified' and payload['models']['embedding']['state'] == 'verified'
    receipt = json.loads((project.project_root / 'data/embeddings/model-download.json').read_text(encoding='utf-8'))
    assert receipt['mode'] == 'verify_local' and receipt['download_bytes'] == 0
    assert engines.weights_ready(project, 'embedding')['state'] == 'verified'
    assert call(project, 'verify_weights')[0]['status'] == 'nothing_to_verify'


def test_weights_that_differ_are_a_visible_fault_and_write_no_receipt(project):
    weights(project, damaged=True)
    payload = call(project, 'verify_weights', {'model': 'embedding'})[0]
    assert payload['status'] == 'faulty' and 'model.safetensors' in payload['models']['embedding']['reason']
    assert not (project.project_root / 'data/embeddings/model-download.json').exists()


def test_cli_verifies_weights_placed_by_hand(project, capsys):
    from types import SimpleNamespace
    from local_asset_library.owner_commands import verify_weights_command
    weights(project)
    result = verify_weights_command(SimpleNamespace(model='all', json=False), project)
    assert result['status'] == 'ready' and result['models']['embedding']['status'] == 'verified'
    assert result['models']['caption']['status'] == 'absent'
    assert 'Search model: verified' in capsys.readouterr().out
