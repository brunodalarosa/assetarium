"""Optional descriptions: notices, the per-source describe run and the bridge (decision 0008)."""
from collections import Counter
import json
from types import SimpleNamespace

import pytest

from test_settings import config, coordinator
from test_sources import managed, ready_source, failed_caption
from local_asset_library import notifications, sources
from local_asset_library import source_operations as operations
from local_asset_library.config import ConfigError
from local_asset_library.incremental import working, update_record
from local_asset_library.membership import records
from local_asset_library.publication import atomic_json
from local_asset_library.settings import GIB, save_general_settings

SOURCE = {'key': 'fixture', 'id': 'fixture-id', 'name': 'Fixture pack'}


def status(missing, enabled=True, operation=None, **extra):
    return {**SOURCE, 'enabled': enabled, 'scanned': True, 'operation': operation or {},
            'descriptions': {'complete': 0, 'missing': missing, 'failed': 0, 'unavailable': 0}, **extra}


def items(config):
    return notifications.load(config)['items']


def test_ready_notice_is_one_per_source_and_not_now_stays_quiet_until_new_assets(config):
    notifications.notify_ready(config, SOURCE, 0)
    assert not items(config)
    notifications.notify_ready(config, SOURCE, 5)
    notifications.act(config, 'read', 'ready-fixture-id')
    notifications.notify_ready(config, SOURCE, 4)
    [notice] = items(config)
    # Fewer missing keeps the read notice and its time; it only updates the count.
    assert notice['read'] and notice['missing'] == 4
    notifications.act(config, 'dismiss', 'ready-fixture-id')
    notifications.notify_ready(config, SOURCE, 4)
    assert not items(config)
    notifications.notify_ready(config, SOURCE, 9)
    [notice] = items(config)
    assert not notice['read'] and notice['missing'] == 9
    # Starting a run resolves the notice and forgets the earlier "Not now".
    notifications.act(config, 'dismiss', 'ready-fixture-id')
    notifications.clear_ready(config, SOURCE['id'])
    notifications.notify_ready(config, SOURCE, 2)
    assert items(config)[0]['missing'] == 2


def test_reports_are_idempotent_per_run_and_marked_read(config):
    for _ in range(2):
        notifications.notify_report(config, SOURCE, 'token-a', 'complete', written=3, failed=0, remaining=0)
    notifications.notify_report(config, SOURCE, 'token-b', 'stopped', written=1, failed=0, remaining=2, reason='GPU')
    assert [i['id'] for i in items(config)] == ['report-token-b', 'report-token-a']
    notifications.act(config, 'read_all')
    assert all(i['read'] for i in items(config))
    with pytest.raises(ValueError):
        notifications.notify_report(config, SOURCE, 'token-c', 'unknown')
    with pytest.raises(ValueError):
        notifications.act(config, 'delete_everything')


def test_list_is_bounded_without_dropping_unread_first(config):
    for i in range(notifications.LIMIT + 5):
        notifications.notify_report(config, SOURCE, f'token-{i:03}', 'complete', written=i)
        if i < 10:
            notifications.act(config, 'read', f'report-token-{i:03}')
    kept = items(config)
    assert len(kept) == notifications.LIMIT
    assert sum(i['read'] for i in kept) == 5  # Five oldest read reports were trimmed first.


def test_reconcile_seeds_existing_sources_once_and_follows_status(config):
    other = {'key': 'other', 'id': 'other-id', 'name': 'Other'}
    statuses = [status(7), {**status(3, enabled=False), **other}]
    notifications.reconcile(config, statuses)
    assert [(i['id'], i['missing']) for i in items(config)] == [('ready-fixture-id', 7)]
    notifications.act(config, 'dismiss', 'ready-fixture-id')
    # Seeding happens once; a dismissed notice does not come back on later launches.
    notifications.reconcile(config, statuses)
    assert not items(config)
    notifications.notify_ready(config, SOURCE, 9)
    notifications.reconcile(config, [status(6)])
    assert items(config)[0]['missing'] == 6
    notifications.reconcile(config, [status(0)])
    assert not items(config)
    # The dismissed count follows what is still missing, so later imports notify again.
    assert notifications.load(config)['dismissed'] == {}
    notifications.notify_ready(config, SOURCE, 1)
    notifications.reconcile(config, [])
    assert not items(config)


def test_reconcile_reports_describe_runs_that_stopped_without_a_report(config):
    interrupted = {'operation': 'describe', 'token': 't1', 'status': 'interrupted', 'reason': 'Operation stopped'}
    faulty = {'operation': 'describe', 'token': 't2', 'status': 'faulty', 'reason': 'Integrity check failed'}
    processing = {'operation': 'process', 'token': 't3', 'status': 'interrupted'}
    for operation in (interrupted, faulty, processing):
        notifications.reconcile(config, [status(0, operation=operation)])
    reports = {i['id']: i for i in items(config)}
    assert set(reports) == {'report-t1', 'report-t2'}
    assert reports['report-t1']['outcome'] == 'interrupted' and reports['report-t2']['outcome'] == 'stopped'
    before = notifications.path(config).read_bytes()
    notifications.reconcile(config, [status(0, operation=faulty)])
    assert notifications.path(config).read_bytes() == before  # No rewrite while nothing changed.


def describe_coordinator(config, monkeypatch, allocations, counts, run=None):
    calls, states = coordinator(config, monkeypatch, allocations)
    values = iter(Counter(c) for c in counts)
    monkeypatch.setattr(operations, 'description_counts', lambda scoped: next(values))
    if run:
        monkeypatch.setattr(operations.subprocess, 'run', lambda command, **kw: (calls.append(command), run(command))[1])
    return calls, states


def test_describe_runs_caption_then_vectors_publishes_and_reports(config, monkeypatch):
    save_general_settings(config, 24)
    calls, states = describe_coordinator(config, monkeypatch, [11 * GIB, 12 * GIB, 12 * GIB],
        [{'complete': 2, 'missing': 5, 'failed': 1}, {'complete': 6, 'missing': 0, 'failed': 2}])
    operations.describe_source(config, SOURCE, 'run-1')
    assert [c[c.index('--stage') + 1] for c in calls] == ['caption', 'embeddings']
    assert states[-1]['status'] == 'complete_with_faults'
    [report] = items(config)
    assert report['outcome'] == 'complete_with_failures' and (report['written'], report['failed'], report['remaining']) == (4, 1, 0)


def test_describe_stop_and_cancel_still_publish_and_report(config, monkeypatch):
    save_general_settings(config, 24)
    reason = 'Not enough GPU memory for description batch size 8. Lower it in Settings → General'
    def oom(command):
        atomic_json(operations.stage_fault_path(config, 'run-2'), {'reason': reason})
        return SimpleNamespace(returncode=1)
    published = []
    calls, states = describe_coordinator(config, monkeypatch, [11 * GIB],
        [{'complete': 2, 'missing': 8}, {'complete': 4, 'missing': 6}], run=oom)
    monkeypatch.setattr(operations, 'publish_source', lambda scoped: published.append(scoped))
    operations.describe_source(config, SOURCE, 'run-2')
    assert len(calls) == 1 and len(published) == 1
    assert states[-1]['status'] == 'faulty' and states[-1]['reason'] == reason
    report = items(config)[0]
    assert (report['outcome'], report['written'], report['remaining'], report['reason']) == ('stopped', 2, 6, reason)
    calls, states = describe_coordinator(config, monkeypatch, [11 * GIB], [{'missing': 3}, {'missing': 3}])
    monkeypatch.setattr(operations, 'cancelled', lambda *args: True)
    operations.describe_source(config, SOURCE, 'run-3')
    assert not calls and states[-1]['status'] == 'cancelled'
    assert items(config)[0]['id'] == 'report-run-3' and items(config)[0]['outcome'] == 'cancelled'


def test_start_describe_requires_missing_descriptions_and_clears_the_notice(managed, monkeypatch):
    config, backend, one, _ = managed
    work = ready_source(config, backend, one)
    with pytest.raises(ConfigError, match='already has a description'):
        operations.start(config, 'describe', one['key'])
    with pytest.raises(ConfigError, match='Choose an asset source'):
        operations.start(config, 'describe')
    record = records(work)[0]
    record['description'] = record['caption_provenance'] = None
    record['processing']['caption'] = 'pending'
    update_record(work, record)
    sources.scan_source(config, one)
    assert sources.source_status(config, one)['descriptions']['missing'] == 1
    notifications.notify_ready(config, one, 1)
    spawned = []
    monkeypatch.setattr(operations.subprocess, 'Popen', lambda command, **kw: spawned.append(command) or SimpleNamespace(pid=4321))
    assert operations.start(config, 'describe', one['key'])['status'] == 'started'
    assert spawned[0][2:4] == ['describe', '--token'] and spawned[0][-2:] == ['--source', one['key']]
    assert not items(config)
    sources.set_enabled(config, one['key'], False)
    with pytest.raises(ConfigError, match='Enable this asset source'):
        operations.start(config, 'describe', one['key'])


def test_description_worker_describes_only_assets_with_ready_renders(managed, monkeypatch):
    config, backend, one, _ = managed
    work = ready_source(config, backend, one)
    ready, unfinished, failed = records(work)
    for record in (ready, unfinished):
        record['description'] = record['caption_provenance'] = None
        record['processing']['caption'] = 'pending'
    unfinished['processing'].update(inspection='pending', previews='pending')
    for record in (ready, unfinished):
        update_record(work, record)
    failed_caption(work, failed)
    scoped = sources.bound(config, one)
    operations.state(scoped, operation='describe', status='processing', token='w1')
    seen = []
    def fake(scoped, stage, limit=40, backend=None, dry_run=False, asset_ids=None, **kw):
        seen.append(asset_ids)
        return {'pending': 0}
    import local_asset_library.incremental as incremental
    monkeypatch.setattr(incremental, 'process', fake)
    operations.worker_stage(config, one, 'caption', 'w1')
    # Unfinished imports and recorded failures are never described by this run.
    assert seen == [{ready['asset_id']}]
    operations.worker_stage(config, one, 'embeddings', 'w1')
    assert seen[-1] is None


def test_processing_a_source_raises_a_ready_notice_when_descriptions_are_missing(config, monkeypatch):
    save_general_settings(config, 24)
    calls, states = coordinator(config, monkeypatch, [11 * GIB, 12 * GIB, 12 * GIB, 12 * GIB])
    monkeypatch.setattr(operations, 'scan_source', lambda *a: {'failed': 0, 'needs_processing': False,
                        'descriptions': {'complete': 0, 'missing': 12, 'failed': 0, 'unavailable': 0}})
    operations.process_source(config, SOURCE, 'import-1')
    assert states[-1]['status'] == 'complete'
    [notice] = items(config)
    assert notice['kind'] == 'descriptions_ready' and notice['missing'] == 12 and notice['source_key'] == 'fixture'


def test_bridge_serves_notices_with_sources_and_their_file_changes_the_token(managed):
    from local_asset_library.desktop import DesktopBridge
    config, backend, one, _ = managed
    work = ready_source(config, backend, one)
    record = records(work)[0]
    record['description'] = record['caption_provenance'] = None
    record['processing']['caption'] = 'pending'
    update_record(work, record)
    sources.scan_source(config, one)
    bridge = DesktopBridge(config, prestart_worker=False)
    try:
        before = bridge.changes()['sources']
        result = bridge.sources()
        # First launch after the change seeds one notice per source with missing descriptions.
        assert [(n['source_key'], n['missing']) for n in result['notifications']] == [(one['key'], 1)]
        assert bridge.changes()['sources'] != before
        saved = bridge.notification_action('dismiss', result['notifications'][0]['id'])
        assert saved['status'] == 'saved' and saved['notifications'] == []
        assert bridge.notification_action('explode')['status'] == 'faulty'
        assert bridge.sources()['notifications'] == []
        assert json.loads(notifications.path(config).read_text())['seeded_existing']
    finally:
        bridge._close()
