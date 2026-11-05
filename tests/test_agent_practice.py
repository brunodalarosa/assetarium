"""Practice runs the real pack workflow but leaves no generated session or real-library changes."""
import asyncio
import json
import logging
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

import pytest

from local_asset_library import agent_practice as practice
from local_asset_library.config import Config, ConfigError
from local_asset_library.publication import read_json, atomic_json


@pytest.fixture
def owner(tmp_path):
    project = tmp_path / 'app'
    project.mkdir()
    return Config(project, tmp_path / 'real-assets', None, sources_registry=project / 'data/library/sources.json')


def begin(owner):
    started = practice.action(owner, 'start')
    assert started['status'] == 'started', started
    key = started['key']
    end = time.monotonic() + 10
    while time.monotonic() < end:
        look = practice.action(owner, 'look', key)
        if look['status'] == 'done':
            break
        assert look['status'] == 'running', look
        time.sleep(.01)
    result = practice.action(owner, 'add', key)
    assert result['status'] == 'added', result
    return key, result


def call(owner, key, name, **args):
    result, error = practice.tool(owner, key, name, dict(library_folder=key, **args), {'name': 'scripted-agent'})
    assert not error, result
    return result


def organize(owner, key):
    listed = call(owner, key, 'list_packs')
    for pack in listed['packs']:
        call(owner, key, 'get_pack_outline', path=pack['pack'])
        call(owner, key, 'get_profile', pack=pack['pack'])
    changes = [('Village Props', [{'kind': 'engine_copy', 'folder': 'Unity Models', 'of': 'Models'}]),
               ('Castle Kit/v1.2', [{'kind': 'pack', 'folder': '', 'value': 'merge'}]),
               ('Terrain Pack', [{'kind': 'image_kind', 'folder': 'Art', 'value': 'texture'}]),
               ('Hero Pack', [{'kind': 'image_kind', 'folder': 'Art', 'value': 'image'}])]
    for pack, rules in changes:
        call(owner, key, 'propose_profile', pack=pack, rules=rules)
    state = practice.action(owner, 'status', key)
    decisions = [{'id': p['id'], 'decision': 'apply'} for p in state['proposals']]
    preview = practice.action(owner, 'preview', key, decisions)
    assert all(p['status'] == 'ready' for p in preview['packs']), preview
    result = practice.action(owner, 'commit', key, decisions)
    assert not result['faults'], result


def test_actual_tools_scans_and_owner_review_pass_and_cleanup(owner):
    key, added = begin(owner)
    assert key in added['prompt'] and 'say' in added['prompt']
    organize(owner, key)
    status = practice.action(owner, 'status', key)
    assert status['complete'], {c['label']: c['passed'] for c in status['checks']}
    result = practice.action(owner, 'finish', key)
    assert result['cleaned'] and all(c['passed'] for c in result['checks']), result
    assert not practice._parent(owner).exists()
    assert not (owner.project_root / 'data').exists()
    assert not (owner.project_root / 'cache').exists()


def test_marking_signals_reviewed_is_not_success(owner):
    key, _ = begin(owner)
    for pack in call(owner, key, 'list_packs')['packs']:
        call(owner, key, 'finish_structure', pack=pack['pack'])
    state = practice.action(owner, 'status', key)
    assert not state['complete'] and any(not c['passed'] for c in state['checks'])
    assert practice.action(owner, 'cancel', key)['cleaned']


def test_pending_proposals_remain_for_review_and_finish_reports_them(owner):
    key, _ = begin(owner)
    call(owner, key, 'propose_profile', pack='Village Props', rules=[{'kind': 'exclude', 'folder': 'Unity Models'}])
    state = practice.action(owner, 'status', key)
    assert len(state['proposals']) == 1
    assert not state['checks'][1]['passed']
    finished = practice.action(owner, 'finish', key)
    assert finished['waiting'] == 1 and finished['cleaned']


def test_late_calls_cannot_recreate_files_or_fall_back(owner):
    key, _ = begin(owner)
    assert practice.action(owner, 'cancel', key)['cleaned']
    with pytest.raises(ConfigError, match='ended'):
        practice.tool(owner, key, 'list_packs', {'library_folder': key})
    assert practice.action(owner, 'status', key)['status'] == 'faulty'
    assert not practice._parent(owner).exists()
    assert not (owner.project_root / 'data').exists()


def test_cancel_before_folder_add(owner):
    started = practice.action(owner, 'start')
    assert practice.action(owner, 'cancel', started['key'])['cleaned']
    assert not practice._parent(owner).exists()


def test_recovery_removes_only_dead_session(owner):
    key, _ = begin(owner)
    practice.recover(owner)
    root = practice._root(owner, key)
    marker = read_json(root / 'session.json')
    atomic_json(root / 'session.json', dict(marker, pid=-1))
    practice.recover(owner)
    assert not practice._parent(owner).exists()


def test_one_live_session_and_bad_keys(owner):
    key, _ = begin(owner)
    assert practice.action(owner, 'start')['status'] == 'faulty'
    assert practice.action(owner, 'cancel', 'agent-practice-../../data')['status'] == 'faulty'
    assert practice.action(owner, 'cancel', key)['cleaned']


def test_gateway_uses_same_connection_without_permanent_audit(owner):
    from local_asset_library.mcp_server import Gateway
    key, _ = begin(owner)
    async def run():
        gateway = Gateway(owner)
        root = gateway.audit_root
        result = await gateway.call('get_profile', {'library_folder': key, 'pack': 'Village Props'})
        assert not result.is_error, result
        result = await gateway.call('say', {'message': 'Reviewing the practice packs'})
        assert not result.is_error
        result = await gateway.call('list_packs', {})
        assert all(p['library_folder'] == key for p in json.loads(result.content[0].text)['packs'])
        assert not list(root.iterdir())
        practice.action(owner, 'cancel', key)
        result = await gateway.call('say', {'message': 'A late call'})
        assert result.is_error and not list(root.iterdir())
        assert gateway._practice_key is None  # Later unscoped calls reach the real library again.
        await gateway.close()
    asyncio.run(run())
    assert not practice._parent(owner).exists()


def test_cleanup_failure_is_visible_and_explicit_retry_works(owner, monkeypatch):
    key, _ = begin(owner)
    erase = practice._erase
    monkeypatch.setattr(practice, '_erase', lambda root: (_ for _ in ()).throw(PermissionError('file is locked')))
    result = practice.action(owner, 'finish', key)
    assert not result['cleaned'] and result['reason'] == 'file is locked'
    with pytest.raises(ConfigError, match='ended'):
        practice.tool(owner, key, 'list_packs', {})
    monkeypatch.setattr(practice, '_erase', erase)
    assert practice.action(owner, 'cancel', key)['cleaned']


def test_cleanup_refuses_links_outside_session(owner, tmp_path):
    key, _ = begin(owner)
    root = practice._root(owner, key)
    outside = tmp_path / 'keep.txt'
    outside.write_text('keep')
    link = root / 'link.txt'
    try:
        link.symlink_to(outside)
    except OSError:
        practice.action(owner, 'cancel', key)
        pytest.skip('File symlinks unavailable')
    result = practice.action(owner, 'cancel', key)
    assert not result['cleaned'] and outside.read_text() == 'keep'
    link.unlink()
    assert practice.action(owner, 'cancel', key)['cleaned']


def test_practice_never_opens_shared_hash_database(owner, monkeypatch):
    from local_asset_library import hash_cache
    def forbidden():
        raise AssertionError('Practice must not open the shared hash cache')
    monkeypatch.setattr(hash_cache, '_database', forbidden)
    key, _ = begin(owner)
    organize(owner, key)
    assert practice.action(owner, 'finish', key)['cleaned']


def test_logs_keep_normal_events_but_not_practice_details(owner):
    from local_asset_library.logs import SessionHandler
    from local_asset_library.transient import work
    path = owner.project_root / 'session.log'
    handler = SessionHandler(path, 'app')
    record = lambda text: logging.LogRecord('test', logging.INFO, __file__, 1, text, (), None)
    try:
        handler.emit(record('normal event'))
        with work():
            handler.emit(record('private practice detail'))
        handler.flush_repeats()
        assert 'normal event' in path.read_text()
        assert 'private practice detail' not in path.read_text()
    finally:
        handler.close()


def test_separate_mcp_process_reads_live_session_and_refuses_it_after_cleanup(owner):
    """Real STDIO initialization and tools/call, using a separate connected server process."""
    key, _ = begin(owner)
    code = '''
import asyncio, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from local_asset_library.config import Config
from local_asset_library.mcp_server import serve
root = Path(sys.argv[2])
asyncio.run(serve(Config(root, root.parent / 'real-assets', None, sources_registry=root / 'data/library/sources.json')))
'''
    messages = queue.Queue()
    process = subprocess.Popen([sys.executable, '-c', code, str(Path(__file__).resolve().parents[1] / 'src'), str(owner.project_root)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    def read():
        for line in process.stdout:
            messages.put(json.loads(line))
        messages.put(None)
    threading.Thread(target=read, daemon=True).start()
    def send(identifier, method, params=None):
        request = {'jsonrpc': '2.0', 'method': method, **({'id': identifier} if identifier else {}),
                   **({'params': params} if params is not None else {})}
        process.stdin.write(json.dumps(request) + '\n')
        process.stdin.flush()
        if not identifier:
            return
        while True:
            response = messages.get(timeout=30)
            assert response is not None, 'MCP server exited'
            if response.get('id') == identifier:
                assert 'error' not in response, response
                return response['result']
    try:
        send(1, 'initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                              'clientInfo': {'name': 'practice-stdio-test', 'version': '1'}})
        send(None, 'notifications/initialized')
        response = send(2, 'tools/call', {'name': 'get_profile', 'arguments': {'library_folder': key, 'pack': 'Village Props'}})
        assert not response.get('isError', response.get('is_error', False)), response
        response = send(3, 'tools/call', {'name': 'say', 'arguments': {'message': 'Reading practice packs'}})
        assert not response.get('isError', response.get('is_error', False)), response
        assert len(practice.action(owner, 'status', key)['entries']) == 2
        assert practice.action(owner, 'cancel', key)['cleaned']
        response = send(4, 'tools/call', {'name': 'list_packs', 'arguments': {'library_folder': key}})
        assert response.get('isError', response.get('is_error', False)), response
        assert 'ended' in response['content'][0]['text']
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
    assert process.returncode == 0
    assert not list((owner.project_root / 'data/mcp/runs').rglob('calls.jsonl'))
    assert not practice._parent(owner).exists()


def test_desktop_close_removes_owned_session(owner):
    from local_asset_library.desktop import DesktopBridge
    bridge = DesktopBridge(owner, prestart_worker=False)
    try:
        started = bridge.practice_action('start')
        assert started['status'] == 'started', started
    finally:
        bridge._close()
    assert not practice._parent(owner).exists()


@pytest.mark.skipif(os.name != 'nt', reason='Windows delete sharing')
def test_a_locked_asset_leaves_retryable_cleanup_metadata(owner):
    key, _ = begin(owner)
    root = practice._root(owner, key)
    with next((root / key).rglob('*.obj')).open('rb'):
        result = practice.action(owner, 'finish', key)
        assert not result['cleaned'], result
        assert (root / 'session.lock').exists() and read_json(root / 'session.json')['state'] == 'closing'
    result = practice.action(owner, 'finish', key)
    assert result['cleaned'] and len(result['checks']) == 6, result
    assert not practice._parent(owner).exists()


@pytest.mark.skipif(os.name != 'nt', reason='Windows junction containment')
def test_cleanup_refuses_a_junction_without_touching_its_target(owner, tmp_path):
    key, _ = begin(owner)
    root = practice._root(owner, key)
    outside = tmp_path / 'untouched'
    outside.mkdir()
    (outside / 'keep.txt').write_text('keep')
    link = root / 'outside-link'
    made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], capture_output=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    assert made.returncode == 0, made.stderr
    try:
        assert link.is_junction()
        result = practice.action(owner, 'cancel', key)
        assert not result['cleaned'] and 'linked' in result['reason'], result
        assert (outside / 'keep.txt').read_text() == 'keep'
    finally:
        os.rmdir(link)  # Remove the junction itself, never recurse into its target.
    assert practice.action(owner, 'cancel', key)['cleaned']
