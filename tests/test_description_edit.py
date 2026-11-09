"""Owner edits of a description (overlay schema v1), its search update, Generate and Try again for one asset."""
import hashlib
import json
import re

import numpy as np
import pytest

from test_incremental import BatchBackend, library, pending_captions  # noqa: F401 -- fixtures
from test_sources import managed, ready_source  # noqa: F401 -- fixtures
from local_asset_library import library_view, processing_queue as queue, source_operations, sources
from local_asset_library.captions import overlay_for, save_edit
from local_asset_library.catalog import detail
from local_asset_library.config import ConfigError
from local_asset_library.desktop_service import DesktopService
from local_asset_library.incremental import process, working
from local_asset_library.membership import records
from local_asset_library.retrieval import SearchEngine, observations
from local_asset_library.settings import save_general_settings

NEW = 'A blue wooden barrel with dark iron hoops, a round lid and a short spout near the bottom edge.'


def words(text, role='query'):
    """A bag-of-words test double: shared words make vectors close; it never stands in for the real model."""
    vector = np.zeros(768, dtype=np.float32)
    for word in re.findall(r'[a-z]+', text.lower()):
        vector[int(hashlib.sha256(word.encode()).hexdigest(), 16) % 768] += 1
    return vector / (np.linalg.norm(vector) or 1)


@pytest.fixture
def described(managed):
    config, backend, one, two = managed
    backend.text = words
    work = ready_source(config, backend, one)
    return config, backend, one, work, records(work)[0]


def update_search(config, backend, source):
    """What the queued search update runs: the embeddings stage, then the folder's publication."""
    scoped = sources.bound(config, source)
    process(scoped, 'embeddings', limit=1000, backend=backend)
    source_operations.publish_source(scoped)
    sources.aggregate(config)


def ranked(config, backend, text):
    response, _ = SearchEngine(config, backend).search(text, 'description', limit=10)
    return [(r['asset_id'], round(r['score'], 6)) for r in response['results']]


def test_an_edit_changes_what_search_finds(described):
    config, backend, one, work, record = described
    identifier = record['asset_id']
    assert len({score for _, score in ranked(config, backend, 'blue wooden barrel iron hoops')}) == 1  # All alike before.
    saved = DesktopService(config).edit_description(identifier, {'description': NEW, 'colors': 'blue\nbrown'})
    assert saved['status'] == 'saved' and saved['edited'] == ['colors', 'description'] and saved['asset_id'] == identifier
    update_search(config, backend, one)
    found = ranked(config, backend, 'blue wooden barrel iron hoops')
    assert found[0][0] == identifier and found[0][1] > found[1][1]
    old = ranked(config, backend, 'red synthetic triangular object')
    assert old[-1][0] == identifier and old[0][1] > old[-1][1]
    # The generated original stays in the record; the overlay holds the owner's text.
    assert detail(work, identifier)['description']['description'].startswith('A red synthetic')
    assert observations(work, detail(work, identifier))['description'] == NEW


def test_only_changed_fields_are_stored_and_an_edit_back_drops_them(described):
    config, _, _, work, record = described
    original = record['description']
    assert save_edit(work, record, {'description': NEW, 'shape': original['shape'], 'identity': original['identity']})['edited'] == ['description']
    overlay, _ = overlay_for(work, record)
    assert overlay['schema_version'] == 1 and set(overlay['description']) == {'description'}
    assert save_edit(work, record, {'description': '  ' + original['description'] + '\n'}) == {'status': 'saved', 'edited': []}
    assert overlay_for(work, record)[0]['description'] == {}
    assert save_edit(work, record, {'description': original['description']})['status'] == 'unchanged'


def test_an_edit_that_breaks_a_rule_saves_nothing(described):
    config, _, _, work, record = described
    with pytest.raises(ValueError, match='10-170 words'):
        save_edit(work, record, {'description': 'Too short.'})
    with pytest.raises(ValueError, match='visual description fields'):
        save_edit(work, record, {'suggested_uses': ['games']})
    with pytest.raises(ValueError, match='Core visual attributes'):
        save_edit(work, record, {'colors': ''})
    assert overlay_for(work, record)[0]['description'] == {}


def test_a_failed_description_cannot_gain_an_edit(described):
    config, _, _, work, record = described
    record['processing']['caption'], record['description'] = 'failed', None
    with pytest.raises(ConfigError, match='Only a generated description'):
        save_edit(work, record, {'description': NEW})


def test_detail_reports_each_description_state(described, monkeypatch):
    config, backend, one, work, record = described
    service = DesktopService(config)
    monkeypatch.setattr(service, 'description_setup', lambda: {'ready': True, 'reason': None})
    info = service.asset(record['asset_id'])['payload']['presentation']
    assert 'owner_review' not in info and 'owner_artistic_approval' not in info
    edit = info['description_edit']
    assert edit['state'] == 'generated' and edit['key'] == one['key'] and edit['original']['description'].startswith('A red')
    service.edit_description(record['asset_id'], {'description': NEW})
    edit = service.asset(record['asset_id'])['payload']['presentation']['description_edit']
    assert edit['state'] == 'edited' and edit['edited_fields'] == ['description']
    assert service.asset(record['asset_id'])['payload']['presentation']['observations']['description'] == NEW


@pytest.fixture
def fake_start(described, monkeypatch):
    config, backend, one, work, record = described
    started, status = [], {}

    def start(config, operation, key=None, asset_ids=None, queue_item=None, owner=None, mode=None):
        started.append({'operation': operation, 'asset_ids': asset_ids, 'mode': mode})
        status[key] = {'status': 'processing', 'token': 'token-%d' % len(started), 'asset_ids': asset_ids}
        return {'status': 'started', 'token': status[key]['token']}
    monkeypatch.setattr(source_operations, 'start', start)
    monkeypatch.setattr(source_operations, 'operation_status', lambda scoped: status.get(scoped.source_key, {'status': 'idle'}))
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    return config, one, work, record, started


def test_queue_modes_name_one_asset_in_the_matching_state(fake_start):
    config, one, work, record, started = fake_start
    identifier = record['asset_id']
    with pytest.raises(ConfigError, match='name one asset'):
        queue.add(config, 'descriptions', {'key': one['key'], 'mode': 'retry'})
    with pytest.raises(ConfigError, match='no recorded failure'):
        queue.add(config, 'descriptions', {'key': one['key'], 'asset_ids': [identifier], 'mode': 'retry'})
    result = queue.add(config, 'descriptions', {'key': one['key'], 'asset_ids': [identifier], 'mode': 'edited'})
    assert result['status'] == 'started' and started[-1] == {'operation': 'describe', 'asset_ids': [identifier], 'mode': 'edited'}
    assert result['item']['title'] == 'Update search for an edited description'
    assert queue.place(config, one['key'], [identifier]) == {'status': 'running', 'mode': 'edited', 'phase': None}


def test_try_again_queues_only_the_named_failure(fake_start):
    config, one, work, record, started = fake_start
    from test_sources import failed_caption
    failed_caption(work, record)
    sources.scan_source(config, one)
    queue.add(config, 'descriptions', {'key': one['key'], 'asset_ids': [record['asset_id']], 'mode': 'retry'})
    assert started[-1]['asset_ids'] == [record['asset_id']] and started[-1]['mode'] == 'retry'
    # A folder-wide Generate descriptions still leaves recorded failures alone.
    assert record['asset_id'] not in queue.resolve(config, 'descriptions', {'key': one['key'], 'path': '', 'asset_ids': []})['ids']


def test_an_edit_updates_search_with_descriptions_off_but_generating_is_refused(fake_start):
    config, one, work, record, started = fake_start
    save_general_settings(config, 8, descriptions_enabled=False)
    with pytest.raises(ConfigError, match='turned off'):
        queue.add(config, 'descriptions', {'key': one['key'], 'asset_ids': [record['asset_id']]})
    assert queue.add(config, 'descriptions', {'key': one['key'], 'asset_ids': [record['asset_id']], 'mode': 'edited'})['status'] == 'started'


def test_a_waiting_search_update_is_not_queued_twice_and_shows_its_place(fake_start):
    config, one, work, record, started = fake_start
    scope = {'key': one['key'], 'asset_ids': [record['asset_id']], 'mode': 'edited'}
    first = queue.add(config, 'descriptions', scope)
    assert first['status'] == 'started'
    # Another edit while the first update runs needs one more run; further edits share it while it waits.
    second, third = queue.add(config, 'descriptions', scope), queue.add(config, 'descriptions', scope)
    assert second['status'] == 'queued' and second['item']['id'] == third['item']['id'] and len(started) == 1
    assert queue.place(config, one['key'], [record['asset_id']])['status'] == 'running'  # The running one shows first.



def test_a_waiting_item_shows_its_place_in_line(fake_start, managed):
    config, one, work, record, started = fake_start
    two = managed[3]
    sources.scan_source(config, two)
    assert queue.add(config, 'previews', {'key': two['key']})['status'] == 'started'
    queue.add(config, 'descriptions', {'key': one['key'], 'asset_ids': [record['asset_id']], 'mode': 'edited'})
    assert queue.place(config, one['key'], [record['asset_id']]) == {'status': 'waiting', 'mode': 'edited', 'position': 2, 'paused': False}


def test_try_again_generates_a_recorded_failure_once(library):
    from test_captions import caption
    config, _ = library
    work = pending_captions(config)
    good = json.dumps(caption())
    result = process(config, 'caption', 6, backend=BatchBackend([good, '{}', good, good, good, good]))
    assert result['failed'] == 1
    failed = next(r['asset_id'] for r in records(work) if r['processing']['caption'] == 'failed')
    assert process(config, 'caption', dry_run=True)['pending'] == 0
    assert process(config, 'caption', dry_run=True, asset_ids={failed}, retry={failed})['pending_ids'] == [failed]
    backend = BatchBackend([good])
    again = process(config, 'caption', 6, backend=backend, asset_ids={failed}, retry={failed})
    assert backend.batches == [1] and again['complete'] == 1
    assert detail(working(config), failed)['processing']['caption'] == 'complete'


def test_a_search_update_runs_no_description_model(managed, monkeypatch):
    config, _, one, _ = managed
    ran = []
    monkeypatch.setattr(source_operations, 'operation_status', lambda scoped: {'mode': 'edited'})
    monkeypatch.setattr(source_operations, 'check_budget', lambda *args: None)
    monkeypatch.setattr(source_operations.subprocess, 'run',
                        lambda command, **kwargs: ran.append(command[command.index('--stage') + 1]) or type('Done', (), {'returncode': 0})())
    assert source_operations.run_stages(config, one, sources.bound(config, one), 'token', 'describe', 0)
    assert ran == ['embeddings']


def test_editing_a_shared_variant_description_edits_its_group(managed, monkeypatch):
    from test_variant_groups import scanned
    from local_asset_library.incremental import update_record
    config, backend, one, _ = managed
    monkeypatch.setattr(library_view, 'blockers', lambda config: {})
    scanned(config, one, 'Car_A', 'Car_B')
    work = ready_source(config, backend, one)
    ids = {r['display_name']: r['asset_id'] for r in records(work)}
    variant = detail(work, ids['Car_B'])
    variant.update(description=None, caption_provenance=None)
    variant['processing']['caption'] = 'pending'
    update_record(work, variant)
    source_operations.publish_source(sources.bound(config, one))
    sources.aggregate(config)
    sources.scan_source(config, one)
    service = DesktopService(config)
    edit = service.asset(ids['Car_B'])['payload']['presentation']['description_edit']
    assert edit['asset_id'] == ids['Car_A'] and edit['shared_variants'] == 2 and edit['state'] == 'generated'
    saved = service.edit_description(ids['Car_B'], {'description': NEW})
    assert saved['asset_id'] == ids['Car_A'] and saved['shared_variants'] == 2
    assert observations(work, detail(work, ids['Car_A']))['description'] == NEW
    assert overlay_for(work, detail(work, ids['Car_B']))[0]['description'] == {}  # The variant has no text of its own.
