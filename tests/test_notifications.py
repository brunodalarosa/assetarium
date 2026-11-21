"""Optional descriptions: notices, the per-source describe run and the bridge (decision 0033)."""
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
    """The notices the panel lists; dismissed ones are hidden, not deleted (see ``hidden``)."""
    return [item for item in notifications.load(config)['items'] if not item.get('hidden')]


def hidden(config):
    return [item['id'] for item in notifications.load(config)['items'] if item.get('hidden')]


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
    assert not items(config) and hidden(config) == ['ready-fixture-id']
    notifications.notify_ready(config, SOURCE, 9)
    [notice] = items(config)
    assert not notice['read'] and notice['missing'] == 9 and notice['again'] and not hidden(config)
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


def test_list_trims_hidden_notices_before_read_ones(config):
    for i in range(notifications.LIMIT):
        notifications.notify_report(config, SOURCE, f'token-{i:03}', 'complete', written=i)
    notifications.act(config, 'read', 'report-token-000')
    notifications.act(config, 'dismiss', 'report-token-049')  # The newest, but hidden.
    notifications.notify_report(config, SOURCE, 'token-new', 'complete', written=1)
    ids = {item['id'] for item in notifications.load(config)['items']}
    assert 'report-token-049' not in ids and 'report-token-000' in ids and 'report-token-new' in ids


COLLECTION = {'id': 'c1', 'name': 'Props', 'items': ['a', 'b']}


def test_dismiss_hides_and_restore_brings_back_without_losing_facts(config):
    notifications.notify_report(config, SOURCE, 't1', 'stopped', written=1, failed=0, remaining=2, reason='GPU')
    notifications.notify_collection(config, COLLECTION, 'added', 'Added 2 assets')
    notifications.notify_setup_proposal(config, {'id': 'p1', 'key': 'k', 'path': 'p', 'version': 1})
    notifications.notify_ready(config, SOURCE, 5)
    notifications.act(config, 'dismiss', 'report-t1')
    stored = {item['id']: item for item in notifications.load(config)['items']}
    assert stored['report-t1']['hidden'] and stored['report-t1']['read'] and stored['report-t1']['reason'] == 'GPU'
    # Dismiss all without ids hides every shown notice except the proposal, which must be decided.
    notifications.act(config, 'dismiss_all')
    assert [item['id'] for item in items(config)] == ['proposal-p1']
    assert set(hidden(config)) == {'report-t1', 'collection-c1', 'ready-fixture-id'}
    assert notifications.load(config)['dismissed'] == {'fixture-id': 5}
    notifications.act(config, 'dismiss', 'proposal-p1')
    assert [item['id'] for item in items(config)] == ['proposal-p1']
    # Undo restores a list; restoring a ready notice forgets its "Not now", so the same count keeps it shown.
    notifications.act(config, 'restore', ['collection-c1', 'ready-fixture-id'])
    assert set(hidden(config)) == {'report-t1'} and notifications.load(config)['dismissed'] == {}
    notifications.notify_ready(config, SOURCE, 5)
    assert 'ready-fixture-id' in {item['id'] for item in items(config)}
    notifications.act(config, 'dismiss_all', ['collection-c1'])
    assert set(hidden(config)) == {'report-t1', 'collection-c1'}
    notifications.act(config, 'restore', 'report-t1')
    assert hidden(config) == ['collection-c1']


def test_hidden_notice_returns_marked_again_only_when_reissued_with_new_facts(config):
    notifications.notify_collection(config, COLLECTION, 'added', 'Added 2 assets')
    notifications.notify_setup_change(config, 's1', [{'key': 'a', 'value': 1}])
    notifications.notify_ready(config, SOURCE, 5)
    notifications.act(config, 'dismiss_all')
    # Reloading, reconciling unchanged facts or finishing a setup session brings nothing back.
    notifications.reconcile(config, [status(5)])
    notifications.notify_setup_change(config, 's1', [], finished=True)
    notifications.notify_ready(config, SOURCE, 4)
    assert not items(config) and len(hidden(config)) == 3
    assert next(i for i in notifications.load(config)['items'] if i['id'] == 'setup-s1')['finished']
    # Reconcile follows a growing count but keeps the notice hidden; only a re-issue shows it, marked again.
    notifications.reconcile(config, [status(9)])
    assert not items(config)
    notifications.notify_ready(config, SOURCE, 9)
    notifications.notify_collection(config, COLLECTION, 'removed', 'Removed 1 asset')
    notifications.notify_setup_change(config, 's1', [{'key': 'b', 'value': 2}])
    shown = {item['id']: item for item in items(config)}
    assert set(shown) == {'ready-fixture-id', 'collection-c1', 'setup-s1'} and all(i['again'] for i in shown.values())
    assert not shown['collection-c1']['read'] and len(shown['setup-s1']['changes']) == 2
    # A shown notice re-issued is not "again"; reading clears the mark.
    notifications.notify_collection(config, COLLECTION, 'added', 'Added 1 asset')
    notifications.act(config, 'read_all')
    assert not any(item.get('again') for item in items(config))


def test_reconcile_seeds_existing_sources_once_and_follows_status(config):
    other = {'key': 'other', 'id': 'other-id', 'name': 'Other'}
    statuses = [status(7), {**status(3, enabled=False), **other}]
    notifications.reconcile(config, statuses)
    assert [(i['id'], i['missing']) for i in items(config)] == [('ready-fixture-id', 7)]
    notifications.act(config, 'dismiss', 'ready-fixture-id')
    # Seeding happens once; a dismissed notice does not come back on later launches.
    notifications.reconcile(config, statuses)
    assert not items(config) and hidden(config) == ['ready-fixture-id']
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
    monkeypatch.setattr(operations, 'scan_source', lambda *a, **kwargs: {'failed': 0, 'needs_processing': False,
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
        # The bridge serves hidden notices too (the panel counts them with Show); a list restores at once.
        assert saved['status'] == 'saved' and [n['hidden'] for n in saved['notifications']] == [True]
        assert bridge.notification_action('explode')['status'] == 'faulty'
        assert [n['hidden'] for n in bridge.sources()['notifications']] == [True]
        restored = bridge.notification_action('restore', [saved['notifications'][0]['id']])
        assert restored['status'] == 'saved' and not restored['notifications'][0].get('hidden')
        assert json.loads(notifications.path(config).read_text())['seeded_existing']
    finally:
        bridge._close()
