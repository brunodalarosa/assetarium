"""Descriptions turned off (decision 0014): enforced by the backend, and nothing existing is lost."""
import json
from types import SimpleNamespace

import pytest

from local_asset_library import notifications, overnight, sources
from local_asset_library import source_operations as operations
from local_asset_library.config import ConfigError
from local_asset_library.incremental import process, update_record, working
from local_asset_library.membership import records
from local_asset_library.settings import descriptions_enabled, general_settings, save_general_settings
from local_asset_library.sources import description_state
from test_notifications import SOURCE, items, status
from test_settings import config  # noqa: F401 (fixture)
from test_sources import managed, ready_source  # noqa: F401 (fixture)


def turn_off(config):
    save_general_settings(config, 8, None, None, False)


def test_setting_round_trips_and_keeps_the_batch_size(config):
    assert descriptions_enabled(config) is True
    save_general_settings(config, 8, None, 2)
    turn_off(config)
    value = general_settings(config)
    assert value['descriptions_enabled'] is False and value['caption_batch_size'] == 2
    with pytest.raises(ConfigError, match='switch'):
        save_general_settings(config, 8, None, None, 'off')
    save_general_settings(config, 8, None, None, True)
    assert descriptions_enabled(config) and general_settings(config)['caption_batch_size'] == 2


def test_ready_notices_stay_quiet_and_not_now_waits(config):
    notifications.notify_ready(config, SOURCE, 5)
    notifications.act(config, 'dismiss', 'ready-fixture-id')
    notifications.notify_ready(config, SOURCE, 7)
    assert [item['missing'] for item in items(config)] == [7]
    turn_off(config)
    notifications.reconcile(config, [status(7)])
    assert not items(config)  # The ready notice is stale while descriptions are off.
    notifications.notify_ready(config, SOURCE, 9)
    assert not items(config)
    assert notifications.load(config)['dismissed'] == {'fixture-id': 5}  # "Not now" is kept for later.
    save_general_settings(config, 8, None, None, True)
    notifications.notify_ready(config, SOURCE, 9)
    assert [item['missing'] for item in items(config)] == [9]


def test_first_launch_seeding_waits_for_descriptions(config):
    turn_off(config)
    notifications.reconcile(config, [status(4)])
    assert not items(config) and not notifications.load(config)['seeded_existing']
    save_general_settings(config, 8, None, None, True)
    notifications.reconcile(config, [status(4)])
    assert [item['kind'] for item in items(config)] == ['descriptions_ready']


def missing_one(config, backend, source):
    work = ready_source(config, backend, source)
    record = records(work)[0]
    record['description'] = record['caption_provenance'] = None
    record['processing']['caption'] = 'pending'
    update_record(work, record)
    sources.scan_source(config, source)
    return work


def test_describe_is_refused_and_status_says_why(managed, monkeypatch):
    config, backend, one, _ = managed
    missing_one(config, backend, one)
    turn_off(config)
    monkeypatch.setattr(operations.subprocess, 'Popen', lambda *a, **kw: pytest.fail('No worker may start'))
    with pytest.raises(ConfigError, match='Descriptions are turned off'):
        operations.start(config, 'describe', one['key'])
    current = sources.source_status(config, one)
    assert current['descriptions_enabled'] is False and current['descriptions']['missing'] == 1


def test_caption_stage_writes_nothing_and_existing_descriptions_stay(managed):
    config, backend, one, _ = managed
    work = missing_one(config, backend, one)
    scoped = sources.bound(config, one)
    before = {r['asset_id']: (description_state(r), r.get('description')) for r in records(working(scoped))}
    pending = process(scoped, 'caption', 10, dry_run=True)['pending_ids']
    turn_off(config)
    result = process(scoped, 'caption', 10, backend=SimpleNamespace(generate_batch=lambda *a: pytest.fail('no model')))
    assert result['descriptions_disabled'] and result['pending'] == 0
    after = {r['asset_id']: (description_state(r), r.get('description')) for r in records(working(scoped))}
    assert after == before and 'complete' in {state for state, _ in after.values()}
    save_general_settings(config, 8, None, None, True)
    assert process(scoped, 'caption', 10, dry_run=True)['pending_ids'] == pending  # Back on: the same work, nothing re-queued.


def test_turning_off_mid_run_stops_after_the_finished_batch(managed):
    config, backend, one, _ = managed
    missing_one(config, backend, one)
    scoped = sources.bound(config, one)
    operations.state(scoped, operation='describe', status='processing', token='off1')
    turn_off(config)
    with pytest.raises(ConfigError, match='turned off'):
        operations.worker_stage(config, one, 'caption', 'off1')
    fault = json.loads(operations.stage_fault_path(scoped, 'off1').read_text(encoding='utf-8'))
    assert fault['reason'] == operations.DESCRIPTIONS_STOPPED


def test_overnight_runs_refuse_to_start(config):
    turn_off(config)
    with pytest.raises(ConfigError, match='turned off'):
        overnight.caption_batch(config, 'unused', lambda work: pytest.fail('no engine'))
