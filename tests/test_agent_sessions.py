"""Agent sessions (decision 0029): Pause agents, agent processing and Undo all for one session."""
import asyncio
import json

import pytest

from test_collections import ready  # noqa: F401 -- fixtures
from test_pack_profiles import kit, pack  # noqa: F401 -- fixtures
from test_processing_queue import fake  # noqa: F401 -- fixtures
from test_sources import managed  # noqa: F401 -- fixtures
from local_asset_library import agent_sessions, asset_collections as collections, asset_tags, mcp_server, pack_agent, pack_profiles
from local_asset_library import processing_queue as queue, sources
from local_asset_library.config import ConfigError

RUN = 'a' * 32


def call(config, name, args, gateway=None):
    gateway = gateway or mcp_server.Gateway(config)
    result = asyncio.run(gateway.call(name, args))
    return json.loads(result.content[0].text), result.is_error, gateway


def test_a_session_journals_tag_and_collection_edits_and_undo_all_reverses_them(ready):
    config, _, _, _, ids = ready
    asset_tags.change(config, ids[:1], add=['owner'])  # The owner's own edit: never in a session.
    with agent_sessions.active(RUN, {'name': 'test-agent'}):
        asset_tags.change(config, ids[:2], add=['crate'])
        made = collections.create(config, 'Props', '', ids[:2], actor='agent')['collection_id']
        collections.update(config, made, name='Props v2', actor='agent')
        kept = collections.create(config, 'Kept', '', ids[:1], actor='agent')['collection_id']
    collections.add(config, kept, ids[2:3])  # The owner changed it after the agent: Undo all keeps it.
    session = agent_sessions.summary(config, RUN)
    assert session['agent'] == 'test-agent' and session['counts'] == {'tags': 1, 'collection': 3} and not session['undone']
    result = agent_sessions.undo(config, RUN)
    assert result['undone'] == ['Collection “Props v2”', 'Collection “Props”', 'Tags on 2 assets']
    assert result['skipped'] == [{'what': 'Collection “Kept”', 'reason': 'It changed after this edit (or was deleted), so it was kept as it is'}]
    assert asset_tags.tags_for(config, ids[0]) == ['owner'] and asset_tags.tags_for(config, ids[1]) == []
    names = [c['name'] for c in collections.load(config)['collections']]
    assert names == ['Kept']
    assert agent_sessions.summary(config, RUN)['undone']['undone'] == 3
    with pytest.raises(ConfigError, match='already ran'):
        agent_sessions.undo(config, RUN)


def test_tags_changed_after_the_session_are_kept(ready):
    config, _, _, _, ids = ready
    with agent_sessions.active(RUN):
        asset_tags.change(config, ids[:2], add=['crate'])
    asset_tags.change(config, ids[:1], add=['mine'])
    result = agent_sessions.undo(config, RUN)
    assert result['skipped'][0]['reason'].startswith('1 of 2 assets changed tags since')
    assert asset_tags.tags_for(config, ids[0]) == ['crate', 'mine'] and asset_tags.tags_for(config, ids[1]) == []


def test_undo_all_reverts_the_sessions_profiles_and_scans_each_folder_once(kit, monkeypatch):
    config, one = kit
    from local_asset_library import source_operations
    monkeypatch.setattr(source_operations, 'start', lambda *a, **k: {'status': 'started'})
    with agent_sessions.active(RUN):
        for rules in ([{'kind': 'exclude', 'folder': 'Unity FBX'}], [{'kind': 'variant_axis', 'folder': 'Rocks', 'values': ['numbers']}]):
            pack_agent.propose(config, {'library_folder': one['key'], 'pack': 'Kit_1.0', 'rules': rules}, {'name': 'test-agent'})
    assert pack_profiles.history(config, one['key'], 'Kit_1.0')[0]['origin']['session'] == RUN
    result = agent_sessions.undo(config, RUN)
    assert len(result['undone']) == 2 and not result['skipped'] and result['rescan'] == [one['key']]
    assert pack_profiles.current(config, one, 'Kit_1.0') == [] and sources.excluded_folders(sources.bound(config, one)) == []


def test_agent_jobs_never_resume_the_owners_paused_queue_and_wait_while_agents_are_paused(fake):
    config, one, two, started, finish, _ = fake
    queue.control(config, 'pause')
    with agent_sessions.active(RUN):
        held = queue.add(config, 'previews', {'key': one['key']}, by='agent')
    assert held['status'] == 'queued' and queue.state(config)['paused'] and not started
    assert held['item']['by'] == 'agent'
    queue.control(config, 'resume')
    assert started[-1]['key'] == one['key']
    agent_sessions.set_paused(config, True)
    with pytest.raises(ConfigError, match='Paused by the owner'):
        queue.add(config, 'previews', {'key': two['key']}, by='agent')
    agent_sessions.set_paused(config, False)
    with agent_sessions.active(RUN):
        waiting = queue.add(config, 'previews', {'key': two['key']}, by='agent')['item']
    agent_sessions.set_paused(config, True)
    owner = queue.add(config, 'previews', {'key': two['key']})
    finish(one['key'])  # Agents are paused: the owner's item starts, the agent's waits.
    assert started[-1]['item'] == owner['item']['id'] and queue.state(config)['agents_paused']
    result = agent_sessions.undo(config, RUN)
    assert result['undone'] == [f"Job: Make previews for {two['name']}"]
    assert result['skipped'][0]['reason'] == 'It already ran or was removed; its results are kept'
    assert waiting['id'] not in [i['id'] for i in queue.state(config)['up_next']]


def test_the_gateway_refuses_agent_writes_while_paused_and_keeps_reads(ready):
    config, _, _, _, ids = ready
    agent_sessions.set_paused(config, True)
    payload, error, gateway = call(config, 'tag_assets', {'asset_ids': ids[:1], 'add': ['x']})
    assert error and payload == {'status': 'refused', 'reason': agent_sessions.PAUSED_REASON, 'tool': 'tag_assets'}
    assert call(config, 'list_collections', {}, gateway)[1] is False
    assert call(config, 'say', {'message': 'Waiting for the owner'}, gateway)[1] is False
    agent_sessions.set_paused(config, False)
    payload, error, gateway = call(config, 'tag_assets', {'asset_ids': ids[:1], 'add': ['x']}, gateway)
    assert not error and agent_sessions.summary(config, gateway.run_id)['counts'] == {'tags': 1}
    assert agent_sessions.sessions(config)[0]['run_id'] == gateway.run_id


def test_the_apps_own_gateway_is_never_an_agent_session(ready):
    config, _, _, _, ids = ready
    agent_sessions.set_paused(config, True)
    gateway = mcp_server.Gateway(config, audit_namespace='gui')
    payload, error, _ = call(config, 'tag_assets', {'asset_ids': ids[:1], 'add': ['x']}, gateway)
    assert not error and agent_sessions.summary(config, gateway.run_id) is None


def test_start_processing_returns_the_estimate_first_for_long_jobs(fake):
    config, one, _, started, _, monkeypatch = fake
    monkeypatch.setattr(queue, 'estimate', lambda config, action, found: {'assets': len(found['ids']), 'seconds': [3000, 4000],
                                                                           'budget_reached': False, 'kinds': {}, 'budget_bytes': None, 'used_bytes': None})
    monkeypatch.setattr(queue, 'describe_estimate', lambda value: 'About an hour.')
    args = {'action': 'previews', 'library_folder': one['key']}
    payload, error, gateway = call(config, 'start_processing', args)
    assert not error and payload['status'] == 'confirm' and payload['estimate'].startswith('About an hour') and not started
    payload, error, _ = call(config, 'start_processing', dict(args, confirm=True), gateway)
    assert not error and payload['status'] == 'started' and started[0]['key'] == one['key']
    assert agent_sessions.summary(config, gateway.run_id)['counts'] == {'job': 1}
    payload, error, _ = call(config, 'start_processing', dict(args, mode='retry'), gateway)
    assert error  # No retry of recorded failures through an agent (decision 0020).
