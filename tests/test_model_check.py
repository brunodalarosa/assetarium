"""Check my model: the driver, the outcome scoring and the trees, with scripted stand-ins for a model (decision 0024)."""
import json
import re

import pytest

from local_asset_library import model_check
from local_asset_library.config import Config
from local_asset_library.model_check_trees import trees


def oracle():
    """Does what each family needs, through the real tools: a model that gets everything right."""
    steps = {}
    by_name = {t['name']: t for t in trees()}

    def call(name, **args):
        return {'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}

    def chat(messages, tools):
        assert {t['function']['name'] for t in tools} == {'list_packs', 'get_pack_outline', 'get_profile', 'propose_profile',
                                                         'finish_structure', 'say'}
        key = re.search(r'library_folder "([^"]+)"', messages[1]['content']).group(1)
        tree, step = by_name[key], steps.get(key, 0)
        steps[key] = step + 1
        if step == 0:
            return call('list_packs', library_folder=key, status='needs_structure')
        listed = json.loads(next(m['content'] for m in reversed(messages) if m['role'] == 'tool'))
        if step > 1 or not listed.get('packs'):
            return {'content': 'DONE'}
        pack = listed['packs'][0]['pack']
        family, paths = tree['family'], tree['paths']
        if family == 'engine_copy':
            copy = tree['checks'][0]['any_of'][0].split('/', 1)[1]
            return call('propose_profile', library_folder=key, pack=pack, rules=[{'kind': 'engine_copy', 'folder': copy, 'of': 'FBX'}])
        if family == 'version_folder':
            return call('propose_profile', library_folder=key, pack=pack, rules=[{'kind': 'pack', 'folder': '', 'value': 'merge'}])
        if family.startswith('image_kind'):
            check = tree['checks'][0]
            return call('propose_profile', library_folder=key, pack=pack,
                        rules=[{'kind': 'image_kind', 'folder': check['folder'].split('/', 1)[1], 'value': check['equals']}])
        assert paths
        return call('finish_structure', library_folder=key, pack=pack)
    return chat


def idle(messages, tools):
    return {'content': 'DONE'}


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    return Config(root, tmp_path / 'sources', None)


def test_a_model_that_gets_it_right_passes_every_tree(project):
    report = model_check.run(project, None, 'oracle', full=True, chat=oracle(), run_name='oracle')
    failed = {t['name']: [c for c in t['checks'] if not c['passed']] for t in report['trees'] if not t['passed']}
    assert not failed and report['passed'] == report['total'] == len(trees()) and report['verdict'] == 'good'
    assert (project.project_root / 'data/evidence/model-check/oracle.json').exists()
    assert not (project.project_root / 'scratch/model-check/oracle').exists()  # The disposable library is gone.


def test_a_model_that_does_nothing_passes_only_what_was_fine(project):
    report = model_check.run(project, None, 'idle', chat=idle, run_name='idle')
    assert report['total'] == model_check.QUICK
    assert {t['family'] for t in report['trees'] if t['passed']} == {'fine_variants', 'fine_series'}
    assert report['verdict'] == 'weak'


def test_history_is_trimmed_to_fit_a_small_context():
    long = 'x' * 4000
    messages = [{'role': 'system', 'content': 'rules'}, {'role': 'user', 'content': 'task'}]
    for n in range(8):
        messages += [{'role': 'assistant', 'content': '', 'tool_calls': [{'id': str(n)}]}, {'role': 'tool', 'tool_call_id': str(n), 'content': long}]
    kept = model_check.trimmed(messages)
    assert kept[:2] == messages[:2] and kept[-1] == messages[-1] and model_check._tokens(kept) <= model_check.BUDGET
    assert all(m['role'] != 'tool' or m['tool_call_id'] in {k['tool_calls'][0]['id'] for k in kept if k['role'] == 'assistant'} for m in kept)
