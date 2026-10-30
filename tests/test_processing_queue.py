"""The implicit processing queue (decision 0023)."""
from datetime import datetime
from pathlib import Path

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

    def start(config, operation, key=None, asset_ids=None, queue_item=None):
        token = f'token-{len(started)}'
        started.append({'operation': operation, 'key': key, 'asset_ids': asset_ids, 'item': queue_item})
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


def test_previews_go_ahead_of_descriptions_and_overnight_holds_descriptions(fake):
    config, one, two, started, finish, monkeypatch = fake
    queue.add(config, 'previews', {'key': one['key']})
    monkeypatch.setattr(queue, 'resolve', lambda config, action, scope: {'ids': ['asset_x'], 'blocked': {}, 'kinds': {'model_3d': 1}, 'records': []})
    queue.add(config, 'descriptions', {'key': two['key']})
    queue.add(config, 'previews', {'key': two['key']})
    assert [i['action'] for i in queue.state(config)['up_next']] == ['previews', 'descriptions']
    queue.control(config, 'overnight', value={'enabled': True, 'start': '00:00', 'end': '00:01'})
    monkeypatch.setattr(queue, 'in_window', lambda window, moment=None: False)
    finish(one['key'])
    assert started[-1]['operation'] == 'process'  # The second previews item, not the held descriptions.
    finish(two['key'])
    assert len(started) == 2 and queue.state(config)['up_next'][0]['held']
    monkeypatch.setattr(queue, 'in_window', lambda window, moment=None: True)
    queue.advance(config)
    assert started[-1]['operation'] == 'describe'


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
    queue.after_restart(config)
    assert queue.state(config)['paused'] and queue.advance(config) is None
    queue.control(config, 'resume')
    assert len(started) == started_before + 1


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
    assert queue.in_window({'start': '22:00', 'end': '07:00'}, datetime(2026, 1, 1, 23, 0))
    assert not queue.in_window({'start': '22:00', 'end': '07:00'}, datetime(2026, 1, 1, 12, 0))
