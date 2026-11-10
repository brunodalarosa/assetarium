"""The implicit processing queue (decision 0023)."""
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from test_sources import managed, ready_source  # noqa: F401 -- fixtures
from local_asset_library import library_view, processing_queue as queue, source_operations, sources
from local_asset_library.config import ConfigError
from local_asset_library.publication import atomic_json


@pytest.fixture
def fake(managed, monkeypatch):
    """Operations are recorded instead of spawned; each stays running until the test ends it."""
    config, backend, one, two = managed
    started, status = [], {}

    def start(config, operation, key=None, asset_ids=None, queue_item=None, owner=None):
        token = f'token-{len(started)}'
        started.append({'operation': operation, 'key': key, 'asset_ids': asset_ids, 'item': queue_item, 'owner': owner})
        status[key] = {'status': 'processing', 'token': token}
        return {'status': 'started', 'token': token}
    monkeypatch.setattr(source_operations, 'start', start)
    monkeypatch.setattr(source_operations, 'operation_status', lambda scoped: status.get(scoped.source_key, {'status': 'idle'}))
    monkeypatch.setattr(source_operations, 'cancel', lambda scoped: status.update({scoped.source_key: {'status': 'cancelled', 'token': status[scoped.source_key]['token']}}))
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    for source in (one, two):
        sources.scan_source(config, source)

    def finish(key):
        status[key] = {**status[key], 'status': 'complete'}
        return queue.advance(config)
    return config, one, two, started, finish, monkeypatch


def test_previews_start_at_once_and_the_scope_is_resolved_when_an_item_starts(fake):
    config, one, two, started, finish, _ = fake
    first = queue.add(config, 'previews', {'key': one['key']})
    assert first['status'] == 'started' and len(started[0]['asset_ids']) == 3
    second = queue.add(config, 'previews', {'key': two['key']})
    assert second['status'] == 'queued' and len(started) == 1
    (Path(two['path']) / 'late.obj').write_text('v 0 0 0\n')
    sources.scan_source(config, two)  # Added after queueing: the item still takes it, because it resolves at start.
    finish(one['key'])
    assert started[1]['key'] == two['key'] and len(started[1]['asset_ids']) == 4
    assert queue.state(config)['recent'][0]['status'] == 'complete'


def test_previews_go_ahead_of_descriptions(fake):
    config, one, two, started, finish, monkeypatch = fake
    queue.add(config, 'previews', {'key': one['key']})
    monkeypatch.setattr(queue, 'resolve', lambda config, action, scope: {'ids': ['asset_x'], 'blocked': {}, 'kinds': {'model_3d': 1}, 'records': []})
    queue.add(config, 'descriptions', {'key': two['key']})
    queue.add(config, 'previews', {'key': two['key']})
    assert [i['action'] for i in queue.state(config)['up_next']] == ['previews', 'descriptions']
    finish(one['key'])
    assert started[-1]['operation'] == 'process'  # The second previews item, though descriptions were added first.
    finish(two['key'])
    assert started[-1]['operation'] == 'describe' and 'overnight' not in queue.state(config)


def test_an_item_that_found_its_folder_busy_starts_when_that_operation_ends(fake):
    config, one, _, started, _, monkeypatch = fake
    real = source_operations.start
    busy = {'scan': True}
    monkeypatch.setattr(source_operations, 'start', lambda *a, **k: {'status': 'busy'} if busy['scan'] else real(*a, **k))
    assert queue.add(config, 'previews', {'key': one['key']})['status'] == 'queued' and not started
    assert queue.state(config)['up_next'][0]['status'] == 'waiting' and not queue.state(config)['paused']
    busy['scan'] = False
    queue.advance(config)  # What every operation (the scan here) does when it ends.
    assert len(started) == 1 and queue.state(config)['running']


def test_a_leftover_queue_is_paused_after_a_restart_until_resumed(fake):
    config, one, two, started, finish, _ = fake
    queue.add(config, 'previews', {'key': one['key']})
    queue.add(config, 'previews', {'key': two['key']})
    finish(one['key'])
    value = queue.load(config)
    value['items'][0]['status'] = 'waiting'  # The app closed with work still waiting.
    value['items'] = [i for i in value['items'] if i['status'] == 'waiting']
    queue.save(config, value)
    started_before = len(started)
    queue.claim(config, os.getpid())
    assert queue.state(config)['paused'] and queue.advance(config) is None
    queue.control(config, 'resume')
    assert len(started) == started_before + 1


def dead_pid():
    process = subprocess.Popen([sys.executable, '-c', 'pass'])
    process.wait()
    return process.pid


def test_closing_the_app_stops_its_work_and_reopening_offers_continue(fake):
    config, one, two, started, finish, _ = fake
    queue.claim(config, os.getpid(), 'app.log')
    queue.add(config, 'previews', {'key': one['key']})
    queue.add(config, 'previews', {'key': two['key']})
    assert started[0]['owner'] == os.getpid()  # The work it starts stops with the app.
    assert queue.running_item(config)['waiting'] == 1
    assert queue.release(config, os.getpid()) == 2
    value = queue.load(config)
    assert [i['status'] for i in value['items']] == ['waiting', 'waiting'] and value['paused'] and value['owner']['closing']
    assert 'token' not in value['items'][0] and queue.running_item(config) is None
    assert queue.owner_gone(config, os.getpid())  # Closed on purpose: the items stay for Continue.
    queue.claim(config, os.getpid() + 1)  # The next app start.
    state = queue.state(config)
    assert state['paused'] and state['stopped_on_close'] == 2 and len(started) == 1
    queue.control(config, 'resume')
    state = queue.state(config)
    assert len(started) == 2 and started[1]['key'] == one['key'] and state['stopped_on_close'] == 0


def test_after_a_crash_nothing_resumes_and_recent_says_why(fake):
    config, one, two, started, finish, _ = fake
    queue.claim(config, os.getpid(), 'app.log')
    queue.add(config, 'previews', {'key': one['key']})
    queue.add(config, 'previews', {'key': two['key']})
    assert not queue.owner_gone(config, os.getpid())  # The worker saw its app vanish without closing.
    value = queue.load(config)
    assert not value['items'] and [r['status'] for r in value['recent'][:2]] == ['stopped', 'stopped']
    assert value['recent'][0]['log'] == 'app.log' and 'closed unexpectedly' in value['recent'][0]['reason']
    # A crash with no worker running: the next start moves what waited to Recent as well.
    queue.claim(config, dead_pid(), 'crashed.log')
    queue.control(config, 'pause')
    queue.add(config, 'previews', {'key': two['key']})
    queue.claim(config, os.getpid())
    value = queue.load(config)
    assert not value['items'] and value['recent'][0]['log'] == 'crashed.log' and not value['paused']


def test_work_started_from_a_terminal_has_no_owner(fake):
    config, one, _, started, _, _ = fake
    queue.claim(config, dead_pid())
    queue.add(config, 'previews', {'key': one['key']})
    assert started[0]['owner'] is None


def test_an_operation_stops_when_its_app_is_gone(fake):
    config, one, _, _, _, _ = fake
    owner = dead_pid()  # The app that started it, gone without closing.
    queue.claim(config, owner)
    queue.add(config, 'previews', {'key': one['key']})
    scoped = sources.bound(config, one)
    ended = []
    source_operations.watch_owner(config, scoped, owner, poll=0.01, end=lambda: ended.append(True)).join(5)
    value = source_operations.read_json(scoped.output_path('data', 'library/source-operation.json'))
    assert ended and value['status'] == 'faulty' and 'closed unexpectedly' in value['reason']


def test_ending_an_operation_ends_every_process_it_started(tmp_path):
    marker = tmp_path / 'grandchild.pid'
    script = tmp_path / 'operation.py'
    script.write_text(f'''import subprocess, sys, time
sys.path.insert(0, {str(Path(__file__).parents[1] / "src")!r})
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
open({str(marker)!r}, "w").write(str(child.pid))
from local_asset_library.source_operations import end_tree
end_tree()
''', encoding='utf-8')
    operation = subprocess.Popen([sys.executable, str(script)], start_new_session=os.name != 'nt')
    assert operation.wait(30) != 0
    from local_asset_library.gpu_queue import process_alive
    deadline = time.monotonic() + 10
    while process_alive(int(marker.read_text())) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not process_alive(int(marker.read_text()))


def test_removing_a_cancelling_item_again_keeps_it_until_its_operation_ends(fake):
    config, one, two, started, finish, monkeypatch = fake
    monkeypatch.setattr(source_operations, 'cancel', lambda scoped: None)  # The batch takes a while to stop.
    queue.add(config, 'previews', {'key': one['key']})
    queue.add(config, 'previews', {'key': two['key']})
    identifier = queue.load(config)['items'][0]['id']
    queue.control(config, 'remove', identifier)
    queue.control(config, 'remove', identifier)
    assert [i['status'] for i in queue.load(config)['items']] == ['cancelling', 'waiting'] and len(started) == 1
    finish(one['key'])
    assert queue.load(config)['recent'][0]['id'] == identifier and len(started) == 2


def test_thresholds_ask_first_for_long_work_and_offer_undo_in_between(fake):
    config, one, _, started, _, monkeypatch = fake
    for seconds, expected, undo in ((60, 'started', False), (20 * 60, 'started', True), (45 * 60, 'confirm', None)):
        monkeypatch.setattr(queue, 'estimate', lambda config, action, found, s=seconds: {
            'assets': 3, 'kinds': {'model_3d': 3}, 'seconds': [s * .7, s], 'measured': True, 'disk_bytes': 1, 'budget_reached': False,
            'budget_bytes': None, 'used_bytes': None})
        result = queue.add(config, 'previews', {'key': one['key']})
        assert result['status'] == expected
        if expected == 'confirm':
            assert 'Make previews (3 assets)' == result['confirm_label']
            assert queue.add(config, 'previews', {'key': one['key']}, confirmed=True)['status'] in {'started', 'queued'}
        else:
            assert result['undo'] is undo
            queue.control(config, 'remove', result['item']['id'])



def test_a_big_job_with_no_measurement_yet_asks_first(fake):
    config, one, _, started, _, monkeypatch = fake
    def estimate(assets, seconds=None, budget=None, used=None):
        return lambda config, action, found: {'assets': assets, 'kinds': {'model_3d': assets}, 'seconds': seconds,
                                              'measured': seconds is not None, 'disk_bytes': None, 'budget_reached': False,
                                              'budget_bytes': budget, 'used_bytes': used}
    monkeypatch.setattr(queue, 'estimate', estimate(4000))  # A fresh install: no speed test, no history.
    result = queue.add(config, 'previews', {'key': one['key']})
    assert result['status'] == 'confirm' and 'no measurement yet' in result['body'] and not started
    monkeypatch.setattr(queue, 'estimate', estimate(4000, [60, 90], budget=10 * 2**30))  # Timed, but no storage receipt.
    result = queue.add(config, 'previews', {'key': one['key']})
    assert result['status'] == 'confirm' and "Storage use isn't measured yet" in result['body']
    monkeypatch.setattr(queue, 'estimate', estimate(100))  # Small enough to start on the click, measured or not.
    assert queue.add(config, 'previews', {'key': one['key']})['status'] == 'started'


def test_blocked_only_scope_is_refused_with_its_fix(fake):
    config, one, _, started, _, monkeypatch = fake
    monkeypatch.setattr(library_view, 'blockers', lambda config: {'previews': {
        'reason': 'Blender is not set up', 'fix': 'Set up Blender in Settings', 'stages': ['inspection', 'previews'], 'types': ['model_3d']}})
    with pytest.raises(ConfigError, match='Blender is not set up. Set up Blender'):
        queue.add(config, 'previews', {'key': one['key']})
    assert not started


def test_estimates_use_the_speed_test_and_recent_runs_or_say_no_measurement(fake):
    config, one, _, _, _, monkeypatch = fake
    found = queue.resolve(config, 'previews', {'key': one['key'], 'path': '', 'asset_ids': []})
    monkeypatch.setattr(queue, '_render_rate', lambda config: None)
    value = queue.estimate(config, 'previews', found)
    assert value['seconds'] is None and 'no measurement yet' in queue.describe_estimate(value)
    monkeypatch.setattr(queue, '_render_rate', lambda config: 4.0)
    assert queue.estimate(config, 'previews', found)['seconds'][1] > 0
    batches = config.library_store() / 'folders' / one['id'] / 'library/batches'
    atomic_json(batches / 'inspection-a.json', {'elapsed_seconds': 100, 'complete': 10, 'failed': 0})
    assert queue._batch_rate(config, 'inspection') == 10
