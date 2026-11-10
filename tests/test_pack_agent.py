"""Pack structure tools for agents and the app's Agent activity (decision 0029)."""
import json

import pytest

from test_pack_profiles import kit, pack  # noqa: F401 -- fixtures
from test_sources import managed  # noqa: F401 -- fixtures
from local_asset_library import agent_activity, library_store, pack_agent, pack_profiles, sources
from local_asset_library.config import ConfigError
from local_asset_library.mcp_assets import SCHEMAS, validate


def call(config, name, **args):
    validate(name, args)
    return pack_agent.execute(config, name, args, {'name': 'test-agent'})


def test_names_collapse_into_short_patterns():
    lines, more = pack_agent.collapse(['Car_11_R.obj', 'Car_11_G.obj', 'Car_11_B.obj'] + [f'Rock_{n:02}.fbx' for n in range(1, 21)]
                                      + ['License.txt', 'readme.md'])
    assert lines[:2] == ['Rock_{01..20}.fbx (20)', 'Car_11_{B,G,R}.obj (3)'] and 'License.txt' in lines and not more


def test_an_outline_is_one_bounded_folder_level(kit):
    config, one = kit
    top = call(config, 'get_pack_outline', library_folder=one['key'], path='Kit_1.0')
    folders = {f['name']: f for f in top['folders']}
    assert set(folders) == {'Cars', 'Rocks', 'Unity FBX'} and folders['Rocks']['assets'] == {'model_3d': 3}
    assert top['in_pack'] == 'Kit_1.0' and top['file_patterns'] == ['License.txt'] and top['serialized_characters'] <= pack_agent.CAP
    rocks = call(config, 'get_pack_outline', library_folder=one['key'], path='Kit_1.0/Rocks')
    assert rocks['file_patterns'] == ['Rock_{01,02,03}.obj (3)']
    paged = call(config, 'get_pack_outline', library_folder=one['key'], path='Kit_1.0', limit=2)
    assert len(paged['folders']) == 2 and paged['next_cursor'] == 2
    with pytest.raises(ConfigError, match='No folder'):
        call(config, 'get_pack_outline', library_folder=one['key'], path='Kit_1.0/Nope')


def test_instant_proposals_apply_at_once_and_undo(kit):
    config, one = kit
    rules = [{'kind': 'variant_axis', 'folder': 'Rocks', 'values': ['numbers'], 'note': 'recolors of one rock'}]
    result = call(config, 'propose_profile', library_folder=one['key'], pack='Kit_1.0', rules=rules, note='Rocks are variants')
    assert result['status'] == 'applied' and result['effect'] == ['6 assets → 3 cards, 2 with variants (now 5 cards)']
    assert pack_profiles.history(config, one['key'], 'Kit_1.0')[0]['origin'] == {
        'by': 'agent', 'agent': 'test-agent', 'note': 'Rocks are variants', 'approved': 'auto', 'proposal': result['proposal_id']}
    undone = pack_agent.decide(config, result['proposal_id'], 'undo')
    assert undone['state'] == 'undone' and pack_profiles.current(config, one, 'Kit_1.0') == []
    with pytest.raises(ConfigError, match='Only an applied proposal'):
        pack_agent.decide(config, result['proposal_id'], 'undo')


def test_undoing_a_first_proposal_restores_the_owners_earlier_answers(kit):
    config, one = kit
    library_store.save_answer(config, one['id'], 'Kit_1.0', 'pack_name', 'Starter Kit')  # Saved before any profile version.
    rules = [{'kind': 'variant_axis', 'folder': 'Rocks', 'values': ['numbers']}]
    result = call(config, 'propose_profile', library_folder=one['key'], pack='Kit_1.0', rules=rules)
    assert result['status'] == 'applied' and pack_profiles.current(config, one, 'Kit_1.0') == rules
    pack_agent.decide(config, result['proposal_id'], 'undo')
    assert pack_profiles.current(config, one, 'Kit_1.0') == [{'kind': 'pack_name', 'value': 'Starter Kit'}]


def test_rescan_proposals_wait_for_the_owner_and_a_newer_one_replaces_them(kit):
    config, one = kit
    copy = [{'kind': 'engine_copy', 'folder': 'Unity FBX', 'of': ''}]
    first = call(config, 'propose_profile', library_folder=one['key'], pack='Kit_1.0', rules=copy)
    assert first['status'] == 'pending' and sources.excluded_folders(sources.bound(config, one)) == []
    second = call(config, 'propose_profile', library_folder=one['key'], pack='Kit_1.0', rules=[{'kind': 'exclude', 'folder': 'Unity FBX'}])
    waiting = pack_agent.proposals(config)
    assert [p['id'] for p in waiting] == [second['proposal_id']]
    assert call(config, 'finish_structure', library_folder=one['key'], pack='Kit_1.0')['status'] == 'waiting'
    applied = pack_agent.decide(config, second['proposal_id'], 'apply')
    assert applied['rescan'] and applied['state'] == 'applied'
    assert sources.excluded_folders(sources.bound(config, one)) == ['Kit_1.0/Unity FBX']
    with pytest.raises(ConfigError, match='already superseded'):
        pack_agent.decide(config, first['proposal_id'], 'apply')


def test_packs_list_their_status_and_profiles_carry_the_vocabulary(kit):
    config, one = kit
    pack(config, one, 'A/Barrel.obj', 'A/Crate.obj', 'A/Door.obj', 'B/Barrel.obj', 'B/Crate.obj', 'B/Door.obj', root='Kit_1.0/Props')
    listed = call(config, 'list_packs', status='needs_structure')
    assert [p['pack'] for p in listed['packs']] == ['Kit_1.0'] and 'repeat in several folders' in listed['packs'][0]['reasons'][0]
    profile = call(config, 'get_profile', library_folder=one['key'], pack='Kit_1.0')
    assert profile['signals']['status'] == 'needs_structure' and set(profile['vocabulary']) == set(pack_profiles.KINDS)
    assert call(config, 'finish_structure', library_folder=one['key'], pack='Kit_1.0')['status'] == 'reviewed'
    assert call(config, 'list_packs', status='needs_structure')['packs'] == []


def test_activity_turns_call_logs_into_sentences(kit):
    config, one = kit
    run = config.output_path('data', 'mcp/runs/feed-test')
    run.mkdir(parents=True)
    calls = [('2026-10-31T10:00:00+00:00', 'say', {'message': 'Looking for engine copies'}, {'status': 'noted'}, False),
             ('2026-10-31T10:00:01+00:00', 'get_pack_outline', {'library_folder': one['key'], 'path': 'Kit_1.0'}, {'status': 'outline'}, False),
             ('2026-10-31T10:00:02+00:00', 'propose_profile', {'library_folder': one['key'], 'pack': 'Kit_1.0'},
              {'status': 'pending', 'proposal_id': 'prop_1', 'effect': ['1 file skipped']}, False),
             ('2026-10-31T10:00:03+00:00', 'get_profile', {'library_folder': one['key'], 'pack': 'X'}, {'reason': 'No such pack'}, True)]
    (run / 'calls.jsonl').write_text(''.join(json.dumps({'utc': u, 'tool': t, 'arguments': a, 'response': r, 'is_error': e}) + '\n'
                                             for u, t, a, r, e in calls), encoding='utf-8')
    feed = agent_activity.recent(config)
    assert [(e['kind'], e['text']) for e in feed['entries']] == [
        ('say', 'Looking for engine copies'), ('read', f"Reading {one['key']} / Kit_1.0"),
        ('waiting', f"Proposed rules for {one['key']} / Kit_1.0, waiting for you: 1 file skipped"),
        ('refused', 'Get profile refused: No such pack')]
    assert feed['entries'][2]['proposal_id'] == 'prop_1' and not feed['working']
    assert agent_activity.recent(config, '2026-10-31T10:00:02+00:00')['entries'][0]['tool'] == 'get_profile'
    assert agent_activity.token(config)


def test_every_pack_tool_has_a_schema():
    assert set(pack_agent.TOOLS) <= set(SCHEMAS) and pack_agent.WRITE < set(pack_agent.TOOLS)


def test_staged_decisions_save_together_with_one_rescan_per_library_folder(kit):
    config, one = kit
    pack(config, one, 'License.txt', 'Props/Barrel.obj', 'Unity FBX/Props/Barrel.obj', 'Samples/Shot.obj', root='Kit_2.0')
    copy = {'kind': 'engine_copy', 'folder': 'Unity FBX', 'of': ''}
    first = call(config, 'propose_profile', library_folder=one['key'], pack='Kit_1.0', rules=[copy])
    second = call(config, 'propose_profile', library_folder=one['key'], pack='Kit_2.0', rules=[copy, {'kind': 'exclude', 'folder': 'Samples'}])
    stored = next(p['rules'] for p in pack_agent.proposals(config) if p['id'] == second['proposal_id'])  # Indexes follow the stored list.
    samples = next(i for i, r in enumerate(stored) if r['kind'] == 'exclude')
    staged = [{'id': first['proposal_id'], 'decision': 'apply'}, {'id': second['proposal_id'], 'decision': 'apply', 'leave_out': [samples]}]
    seen = pack_agent.preview(config, staged)
    assert [p['status'] for p in seen['packs']] == ['ready', 'ready'] and seen['excluded_files'] == 2 and seen['rescan'] == [one['key']]
    assert sources.excluded_folders(sources.bound(config, one)) == []
    saved = pack_agent.commit(config, staged)
    assert saved['status'] == 'saved' and saved['rescan'] == [one['key']] and not saved['faults']
    assert sorted(sources.excluded_folders(sources.bound(config, one))) == ['Kit_1.0/Unity FBX', 'Kit_2.0/Unity FBX']
    assert pack_profiles.history(config, one['key'], 'Kit_2.0')[0]['origin']['left_out'] == [{'kind': 'exclude', 'folder': 'Samples'}]
    assert pack_agent.proposals(config) == []


def test_a_failing_staged_decision_stays_waiting_and_the_rest_save(kit):
    config, one = kit
    waiting = call(config, 'propose_profile', library_folder=one['key'], pack='Kit_1.0', rules=[{'kind': 'exclude', 'folder': 'Unity FBX'}])
    staged = [{'id': 'prop_gone', 'decision': 'apply'}, {'id': waiting['proposal_id'], 'decision': 'apply', 'leave_out': [0]}]
    assert pack_agent.preview(config, staged)['packs'][0]['status'] == 'faulty'
    saved = pack_agent.commit(config, staged)
    assert saved['faults'] == [{'id': 'prop_gone', 'reason': 'This proposal is not saved any more'}]
    assert saved['decided'][0]['state'] == 'rejected' and not saved['rescan']  # Leaving every rule out rejects it.
    with pytest.raises(ConfigError, match='leave_out names a rule'):
        pack_agent.decide(config, waiting['proposal_id'], 'apply', leave_out=[5])
    with pytest.raises(ConfigError, match='Give a list'):
        pack_agent.commit(config, [])


def test_undo_is_refused_once_the_pack_changed_since_the_proposal(kit):
    config, one = kit
    rules = [{'kind': 'variant_axis', 'folder': 'Rocks', 'values': ['numbers']}]
    first = call(config, 'propose_profile', library_folder=one['key'], pack='Kit_1.0', rules=rules)
    pack_profiles.apply(config, one['key'], 'Kit_1.0', rules + [{'kind': 'pack_name', 'value': 'Starter Kit'}], {'by': 'owner'})
    with pytest.raises(ConfigError, match='changed since this proposal'):
        pack_agent.decide(config, first['proposal_id'], 'undo')
    assert {'kind': 'pack_name', 'value': 'Starter Kit'} in pack_profiles.current(config, one, 'Kit_1.0')  # Nothing erased.
    # An answer saved outside any profile version counts as a change too.
    second = call(config, 'propose_profile', library_folder=one['key'], pack='Kit_1.0', rules=rules)
    library_store.save_answer(config, one['id'], 'Kit_1.0', 'pack_name', 'Renamed')
    with pytest.raises(ConfigError, match='changed since this proposal'):
        pack_agent.decide(config, second['proposal_id'], 'undo')
