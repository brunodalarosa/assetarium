"""Search checks files only for the candidates that can reach the results (synthetic library)."""
from copy import deepcopy

import pytest

from test_retrieval import indexed
from test_mcp_assets import update
from local_asset_library import retrieval
from local_asset_library.catalog import save_json
from local_asset_library.mcp_assets import AssetService
from local_asset_library.retrieval import SearchEngine, fuse
from local_asset_library.search_policy import RRF_WEIGHTS


def ids(response):
    return [r['asset_id'] for r in response['results']]


def order(config, backend, mode, **kwargs):
    """The full healthy order: every candidate checked."""
    return ids(search(config, backend, mode, limit=40, **kwargs)[0])


def search(config, backend, mode, query='obj', **kwargs):
    if mode == 'reference':
        return SearchEngine(config, backend).search(mode=mode, **kwargs)
    return SearchEngine(config, backend).search(query, mode, **kwargs)


def broken(config, record):
    config.source_file(record['files'][0]['path']).write_bytes(b'changed')


@pytest.fixture
def checks(monkeypatch):
    calls = []
    original = retrieval.source_check
    def counted(config, record):
        calls.append(record['asset_id'])
        return original(config, record)
    monkeypatch.setattr(retrieval, 'source_check', counted)
    return calls


@pytest.mark.parametrize('mode', ['keyword', 'description', 'image', 'keyword_description', 'combined', 'reference'])
def test_healthy_order_matches_full_verification(indexed, checks, mode):
    config, backend, records = indexed
    kwargs = {'reference': records[0]['previews'][0]['path']} if mode == 'reference' else {}
    full = order(config, backend, mode, **kwargs)
    assert len(full) == 40 and len(set(checks)) == 40
    for limit in (1, 5, 20):
        checks.clear()
        response, evidence = search(config, backend, mode, limit=limit, **kwargs)
        assert ids(response) == full[:limit] and not evidence['excluded']
        assert len(checks) == limit  # Only the shortlist is checked, once each.
        eligible = evidence['eligible_channel_rankings']
        expected = fuse(eligible, RRF_WEIGHTS[mode]) if mode in {'combined', 'keyword_description'} else next(iter(eligible.values()))
        assert ids(response) == [r['asset_id'] for r in expected[:limit]]


@pytest.mark.parametrize('mode', ['keyword', 'combined', 'reference'])
def test_broken_top_candidate_is_left_out_counted_and_replaced(indexed, mode):
    config, backend, records = indexed
    kwargs = {'reference': records[0]['previews'][0]['path']} if mode == 'reference' else {}
    full = order(config, backend, mode, **kwargs)
    top = next(r for r in records if r['asset_id'] == full[0])
    broken(config, top)
    response, evidence = search(config, backend, mode, limit=5, **kwargs)
    assert top['asset_id'] not in ids(response) and len(ids(response)) == 5
    if mode == 'keyword':
        assert ids(response) == full[1:6]  # The next asset takes its place.
    else:
        assert set(ids(response)) <= set(full[1:])
    assert evidence['excluded'] == [{'asset_id': top['asset_id'], 'channel': 'all',
                                     'reason': 'Source content is stale: ' + top['files'][0]['path']}]
    for ranking in evidence['channel_rankings'].values():
        assert top['asset_id'] not in {r['asset_id'] for r in ranking}


def test_broken_asset_outside_the_shortlist_is_never_checked(indexed, checks):
    config, backend, records = indexed
    full = order(config, backend, 'keyword')
    last = next(r for r in records if r['asset_id'] == full[-1])
    broken(config, last)
    checks.clear()
    response, evidence = search(config, backend, 'keyword', limit=5)
    assert ids(response) == full[:5] and not evidence['excluded']
    assert checks == full[:5] and last['asset_id'] not in checks
    payload, _, _ = AssetService(config).execute('search_assets', {'query': 'obj', 'mode': 'keyword', 'limit': 5})
    assert payload['fault_count'] == 0 and payload['faults'] == []


def test_many_broken_candidates_walk_on_until_the_shortlist_is_full(indexed, checks):
    config, backend, records = indexed
    full = order(config, backend, 'keyword')
    for identifier in full[:30]:
        broken(config, next(r for r in records if r['asset_id'] == identifier))
    checks.clear()
    response, evidence = search(config, backend, 'keyword', limit=5)
    assert ids(response) == full[30:35]
    assert [e['asset_id'] for e in evidence['excluded']] == full[:30]
    assert sorted(checks) == sorted(full[:35])  # Each candidate checked once, nothing past the shortlist.


def test_mcp_fault_count_covers_checked_candidates_only(indexed):
    config, backend, records = indexed
    full = order(config, backend, 'keyword')
    for identifier in (full[1], full[-1]):
        broken(config, next(r for r in records if r['asset_id'] == identifier))
    payload, _, evidence = AssetService(config).execute('search_assets', {'query': 'obj', 'mode': 'keyword', 'limit': 5})
    assert ids(payload) == [full[0], *full[2:6]]
    assert payload['fault_count'] == 1 and [f['asset_id'] for f in payload['faults']] == [full[1]]
    assert payload['faults'][0]['status'] == 'faulty' and payload['faults'][0]['channel'] == 'all'


def test_stale_description_leaves_only_its_channel(indexed):
    config, backend, records = indexed
    response, _ = search(config, backend, 'combined', query='item00')
    assert ids(response)[0] == records[0]['asset_id']
    overlay = {'schema_version': 1, 'description': {'colors': ['blue']}, 'suggested_uses': None,
               'caption_review': 'pending', 'artistic_suitability': 'pending', 'notes': ''}
    save_json(config.output_path('data', f"captions/corrections/{records[0]['asset_id']}.json"), overlay)
    response, evidence = search(config, backend, 'combined', query='item00')
    assert records[0]['asset_id'] in ids(response) and not evidence['excluded']
    assert records[0]['asset_id'] not in {r['asset_id'] for r in evidence['channel_rankings']['description']}
    assert {r['asset_id'] for r in evidence['channel_rankings']['image']} >= {records[0]['asset_id']}


def test_stale_view_gives_way_to_the_next_view(indexed):
    config, backend, records = indexed
    record = deepcopy(records[0])
    _, evidence = search(config, backend, 'image', limit=1)
    first = next(r for r in evidence['channel_rankings']['image'] if r['asset_id'] == record['asset_id'])['input']['path']
    other = next(p['path'] for p in record['previews'] if p['path'] != first)
    config.output_path('data', first[5:]).write_bytes(b'changed')
    response, evidence = search(config, backend, 'image', limit=1)
    assert ids(response) == [record['asset_id']]
    assert [(e['asset_id'], e['channel']) for e in evidence['excluded']] == [(record['asset_id'], 'image')]
    best = next(r for r in evidence['channel_rankings']['image'] if r['asset_id'] == record['asset_id'])
    assert best['input']['path'] == other
    config.output_path('data', other[5:]).write_bytes(b'changed')
    response, evidence = search(config, backend, 'image', limit=1)
    # With no usable view the asset leaves the image channel; it is not excluded from search as a whole.
    assert ids(response) != [record['asset_id']] and {e['channel'] for e in evidence['excluded']} == {'image'}
    assert record['asset_id'] not in {r['asset_id'] for r in evidence['channel_rankings']['image']}


def test_many_unusable_views_are_taken_in_one_walk(indexed, monkeypatch):
    config, backend, records = indexed
    full = order(config, backend, 'image')
    for record in records:
        if record['asset_id'] != full[-1]:
            for preview in record['previews']:
                config.output_path('data', preview['path'][5:]).write_bytes(b'changed')
    rebuilds = []
    original = retrieval.view_ranking
    def counted(views):
        rebuilds.append(1)
        return original(views)
    monkeypatch.setattr(retrieval, 'view_ranking', counted)
    response, evidence = search(config, backend, 'image', limit=1)
    assert ids(response) == [full[-1]]
    assert len(evidence['excluded']) == 78 and {e['channel'] for e in evidence['excluded']} == {'image'}
    # The first ranking, then one re-rank per walk that met failures; it does not grow with the failures.
    assert len(rebuilds) <= 3


def test_unreadable_preview_reference_only_drops_its_view(indexed):
    import sqlite3
    config, backend, records = indexed
    full = order(config, backend, 'image')
    _, evidence = search(config, backend, 'image', limit=1)
    path = next(r for r in evidence['channel_rankings']['image'] if r['asset_id'] == full[0])['input']['path']
    with sqlite3.connect(config.output_path('data', 'embeddings/index.sqlite')) as db:
        changed = db.execute("UPDATE vectors SET preview='{bad' WHERE asset_id=? AND channel='image' AND preview LIKE ?",
                             (full[0], f'%{path}%')).rowcount
        last = db.execute("UPDATE vectors SET preview='{bad' WHERE asset_id=? AND channel='image'", (full[-1],)).rowcount
    assert changed == 1 and last == 2
    response, evidence = search(config, backend, 'image', limit=1)
    # The search still answers; the candidate's unreadable view is recorded and its other view is used.
    assert len(ids(response)) == 1
    assert [(e['asset_id'], e['channel']) for e in evidence['excluded']] == [(full[0], 'image')]
    best = next(r for r in evidence['channel_rankings']['image'] if r['asset_id'] == full[0])
    assert best['input'] and best['input']['path'] != path
    # An unreadable reference outside the shortlist is not checked and does not stop the search.
    assert full[-1] in {r['asset_id'] for r in evidence['channel_rankings']['image']}
