"""Query-time search policy checks with synthetic candidates and embeddings."""
from copy import deepcopy

import pytest

from test_retrieval import indexed
from test_mcp_assets import update
from local_asset_library.catalog import encoded
from local_asset_library.config import ConfigError
from local_asset_library.mcp_assets import AssetService, SCHEMAS, validate
from local_asset_library.retrieval import SearchEngine, fuse
from local_asset_library.search_policy import RRF_WEIGHTS, search_character_cap


def test_documented_budgets():
    assert [search_character_cap(n) for n in (1, 5, 10, 20, 30, 40)] == [6000, 6000, 12000, 22000, 32000, 42000]


def test_conflicting_rankings_favor_image_without_raw_score_averaging():
    def ranking(ids):
        return [{'asset_id': identifier, 'score': 999999} for identifier in ids]
    rankings = {'keyword': ranking(['a', 'b']), 'description': ranking(['a', 'b']),
                'image': ranking(['b', 'a'])}
    assert fuse(rankings)[0]['asset_id'] == 'a'
    weighted = fuse(rankings, RRF_WEIGHTS['combined'])
    assert weighted[0]['asset_id'] == 'b'
    assert weighted[0]['score'] == pytest.approx(3 / 61 + 2 / 62)
    assert fuse({'keyword': ranking(['b', 'a']), 'description': ranking(['a', 'b'])})[0]['asset_id'] == 'a'


@pytest.mark.parametrize('limit', [1, 5, 10, 20, 30, 40])
@pytest.mark.parametrize('mode', ['keyword', 'description', 'image', 'keyword_description', 'combined', 'reference'])
def test_full_shortlists_across_both_layers(indexed, limit, mode):
    config, backend, records = indexed
    engine = SearchEngine(config, backend)
    args = {'mode': mode, 'limit': limit, 'filters': {}}
    if mode == 'reference':
        args.update(reference_asset_id=records[0]['asset_id'], reference_view='front')
        response, _ = engine.search(mode=mode, reference=records[0]['previews'][0]['path'], limit=limit)
    else:
        args['query'] = 'obj'  # All synthetic records have this verified keyword format.
        response, _ = engine.search('obj', mode=mode, limit=limit)
    shared, _, _ = AssetService(config, backend=backend).execute('search_assets', args)
    for payload in (response, shared):
        assert len(payload['results']) == limit
        assert len({r['asset_id'] for r in payload['results']}) == limit
        assert not payload['truncated']
        assert payload['serialized_characters'] == len(encoded(payload)) <= search_character_cap(limit)
        assert payload['estimated_tokens'] == (len(encoded(payload)) + 3) // 4
    assert [r['asset_id'] for r in response['results']] == [r['asset_id'] for r in shared['results']]


@pytest.mark.parametrize('limit', [0, 41, -1, True, 20.0, '20', None])
def test_invalid_limits_rejected_at_both_layers(indexed, limit):
    config, backend, _ = indexed
    with pytest.raises(ConfigError):
        validate('search_assets', {'query': 'obj', 'limit': limit})
    with pytest.raises(ConfigError):
        SearchEngine(config, backend).search('obj', limit=limit)


def test_default_and_explicit_mode_agree(indexed):
    config, backend, _ = indexed
    service = AssetService(config, backend=backend)
    default, _, _ = service.execute('search_assets', {'query': 'obj'})
    explicit, _, _ = service.execute('search_assets', {'query': 'obj', 'mode': 'combined', 'limit': 5})
    assert default == explicit and len(default['results']) == 5
    assert SCHEMAS['search_assets']['properties']['mode']['default'] == 'combined'
    assert SCHEMAS['search_assets']['properties']['limit']['default'] == 5
    _, evidence = SearchEngine(config, backend).search('obj')
    expected = fuse(evidence['eligible_channel_rankings'], RRF_WEIGHTS['combined'])[:5]
    assert [r['asset_id'] for r in default['results']] == [r['asset_id'] for r in expected]


@pytest.mark.parametrize('limit', [5, 20, 30, 40])
def test_oversized_records_truncate_explicitly_and_account_exactly(indexed, limit):
    config, backend, records = indexed
    for original in records:
        record = deepcopy(original)
        record['display_name'] = original['display_name'] + 'x' * 9000
        update(config, record)
    engine, _ = SearchEngine(config, backend).search('obj', 'keyword', limit=limit)
    shared, _, _ = AssetService(config).execute('search_assets', {'query': 'obj', 'mode': 'keyword', 'limit': limit})
    for payload in (engine, shared):
        assert payload['truncated'] and len(payload['results']) < limit
        assert payload['serialized_characters'] == len(encoded(payload)) <= search_character_cap(limit)
    assert [r['asset_id'] for r in shared['results']] == [r['asset_id'] for r in engine['results']]
