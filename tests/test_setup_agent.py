"""Agent setup through MCP (decision 0016): session gate, proposals, degraded mode, connection records, notices, bounds."""
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
    monkeypatch.setattr(setup_agent, '_environment', {})
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
                       ('apply_setup', {'storage_budget_gib': True}), ('validate_blender', {}), ('get_setup_status', {'path': '/x'}),
                       ('propose_setup', {'blender_path': 'C:\\b\n'}), ('apply_setup', {'engine_hint': 'cryengine'})):
        with pytest.raises(ConfigError):
            validate(name, args)


def test_every_write_is_refused_without_a_session_and_after_expiry(project, blender):
    for name, args in (('apply_setup', {'storage_budget_gib': 20}), ('validate_blender', {'path': blender}),
                       ('propose_setup', {'blender_path': blender}), ('finish_setup', {})):
        payload, error, _ = call(project, name, args)
        assert error and payload['status'] == 'refused' and 'Set up with my agent' in payload['reason']
    assert not settings_path(project).exists() and not setup_core.setup_path(project).exists()
    setup_agent.open_session(project, 'app')
    assert call(project, 'apply_setup', {'storage_budget_gib': 20})[0]['status'] == 'applied'
    CLOCK[0] = START + timedelta(minutes=setup_agent.SESSION_MINUTES)
    payload, error, _ = call(project, 'apply_setup', {'storage_budget_gib': 30})
    assert error and payload['status'] == 'refused' and general_settings(project)['storage_budget_gib'] == 20
    assert not call(project, 'get_setup_status')[1]  # Read-only status stays available.
    with pytest.raises(ConfigError):
        setup_agent.open_session(project, 'mcp')


def test_apply_validates_like_the_wizard_and_records_the_agent(project, monkeypatch):
    setup_agent.open_session(project, 'app')
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
    assert {record['values'][k]['set_by'] for k in payload['changed']} == {'agent'} and record['engine_hint'] == 'godot'
    assert call(project, 'apply_setup', {'processing_formats': ['gltf']})[0]['status'] == 'unchanged'
    notice = next(item for item in notifications.load(project)['items'] if item['kind'] == 'setup_changed')
    assert {change['key'] for change in notice['changes']} == set(payload['changed'])


def test_proposal_is_pending_until_the_user_applies_or_rejects_it(project, blender, monkeypatch):
    setup_agent.open_session(project, 'app')
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
    assert call(project, 'finish_setup')[0]['status'] == 'completed'
    assert json.loads(setup_core.setup_path(project).read_text(encoding='utf-8'))['by'] == 'agent'


def test_a_file_changed_after_the_agents_check_is_not_applied(project, blender):
    setup_agent.open_session(project, 'app')
    call(project, 'validate_blender', {'path': blender})
    proposal = call(project, 'propose_setup', {'blender_path': blender})[0]['proposal']
    Path(blender).write_bytes(b'swapped for something else')
    result = setup_agent.decide(project, proposal['id'], 'apply')
    assert result['status'] == 'failed' and 'changed' in result['proposal']['reason']
    assert not (project.project_root / 'config.local.toml').exists()


def test_unconfirmed_rerender_keeps_the_proposal_pending(project, blender, monkeypatch):
    monkeypatch.setattr(setup_core, 'processed_models', lambda config: 7)
    setup_agent.open_session(project, 'app')
    call(project, 'validate_blender', {'path': blender})
    proposal = call(project, 'propose_setup', {'blender_path': blender})[0]['proposal']
    assert proposal['rerender'] == 7
    with pytest.raises(ConfigError, match='rendered again'):
        setup_agent.decide(project, proposal['id'], 'apply')
    assert setup_agent.load(project)[0]['proposals'][-1]['state'] == 'pending'


def test_validate_blender_never_runs_other_programs(project, monkeypatch):
    monkeypatch.setattr(setup_core, '_probe', lambda *a: pytest.fail('nothing may run'))
    setup_agent.open_session(project, 'app')
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
    assert status['next_actions'][0]['for'] == 'session' and not status['session']['open']
    assert set(status['disk']) == {'free_gib', 'total_gib'}
    payload, error, _ = call(project, 'get_setup_status')
    assert not error and payload['serialized_characters'] <= DETAIL_CAP


def test_instructions_carry_a_setup_hint_until_setup_is_finished(project):
    assert 'get_setup_status' in mcp_server.instructions(project)
    setup_core.save_setup(project, {'storage_budget_gib': 20})
    assert mcp_server.instructions(project) == mcp_server.INSTRUCTIONS
    assert 'get_setup_status' in setup_agent.PROCEDURE and 'local-server' in setup_agent.PROCEDURE


def test_snippets_list_every_tool_for_allowlisting_clients(project):
    snippets = {item['id']: item for item in setup_agent.snippets(project.project_root)}
    assert set(snippets) == {'codex', 'claude-code', 'opencode', 'generic'}
    import tomllib
    codex = tomllib.loads(snippets['codex']['text'])['mcp_servers']['local_asset_library']
    assert codex['enabled_tools'] == list(SCHEMAS) and codex['args'] == [str(project.project_root / 'scripts/asset-mcp.py')]
    assert json.loads(snippets['generic']['text'])['mcpServers']['local_asset_library']['cwd'] == str(project.project_root)
    assert 'claude mcp add' in snippets['claude-code']['text']


def test_cli_agent_session_needs_an_interactive_terminal(project, monkeypatch):
    from local_asset_library import owner_commands
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    args = owner_commands.parser().parse_args(['setup', 'agent'])
    with pytest.raises(ConfigError, match='interactive terminal'):
        owner_commands.setup_command(args, project)
    assert not setup_agent.session_state(project)['open']


def test_damaged_agent_record_is_kept_and_counts_as_no_session(project):
    setup_agent.store_path(project).parent.mkdir(parents=True, exist_ok=True)
    setup_agent.store_path(project).write_text('{damaged', encoding='utf-8')
    assert not setup_agent.session_state(project)['open'] and 'kept for review' in setup_agent.session_state(project)['fault']
    with pytest.raises(ConfigError, match='kept for review'):
        setup_agent.open_session(project, 'app')
    assert setup_agent.store_path(project).read_text(encoding='utf-8') == '{damaged'
