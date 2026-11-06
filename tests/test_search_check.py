"""The search check runs on built-in sample images, never library assets (decision 0026)."""
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from test_sources import managed  # noqa: F401 -- fixtures
from local_asset_library import engines, search_check
from local_asset_library.config import ConfigError


class Backend:
    """Vectors that keep cube with cube and sphere with sphere (or swap them when ``confused``)."""

    def __init__(self, confused=False):
        self.contract, self.last_metrics, self.confused = {'device': 'cuda:0', 'model': 'test'}, {}, confused

    def image(self, path):
        return np.array([1.0, 0.0]) if 'cube' in str(path) else np.array([0.0, 1.0])

    def text(self, query, role='query'):
        cube = 'cube' in query
        return np.array([0.0, 1.0]) if cube == self.confused else np.array([1.0, 0.0]) if cube else np.array([0.5, 0.5])

    def resources(self):
        return {}


def test_the_check_images_ship_with_assetarium():
    assert [p.name for p in sorted(search_check.IMAGES.glob('*.png'))] == ['blue-cube.png', 'red-sphere.png']
    assert all(p.stat().st_size < 100_000 for p in search_check.IMAGES.glob('*.png'))


def test_a_passing_check_records_the_receipt_search_needs(managed):
    config = managed[0]
    assert not engines.capability_ready(config, 'cuda')['ready']
    report = search_check.record(config, Backend())
    saved = json.loads(config.output_path('data', 'embeddings/capability.json').read_text(encoding='utf-8'))
    assert saved['inputs'][0]['query'] == 'A blue cube' and saved == json.loads(json.dumps(report))
    assert engines.capability_ready(config, 'cuda')['ready'] and not engines.capability_ready(config, 'cpu')['ready']


def test_a_model_that_mixes_the_shapes_up_records_nothing(managed):
    config = managed[0]
    receipt = config.output_path('data', 'embeddings/capability.json')
    before = receipt.read_bytes() if receipt.exists() else None
    with pytest.raises(ConfigError, match='did not match'):
        search_check.record(config, Backend(confused=True))
    assert (receipt.read_bytes() if receipt.exists() else None) == before


SAMPLES = Path(__file__).resolve().parents[1] / 'samples' / 'Sample assets'


def with_samples(config):
    shutil.copytree(SAMPLES, config.project_root / 'samples' / 'Sample assets')
    return config


def test_the_built_in_samples_are_three_tiny_glb_models():
    names = sorted(p.name for p in SAMPLES.iterdir())
    assert names == ['Blue cube.glb', 'Green pyramid.glb', 'License.txt', 'Red sphere.glb']
    assert all(p.stat().st_size < 20_000 for p in SAMPLES.glob('*.glb'))


def test_setup_adds_the_samples_once_and_only_that_folder_may_sit_inside_assetarium(managed):
    from local_asset_library import setup_core, sources
    config = with_samples(managed[0])
    result = setup_core.save_setup(config, {'include_samples': True})
    assert result['status'] == 'saved' and result['samples']['status'] == 'added'
    folder = next(s for s in sources.registry(config)['sources'] if s['key'] == result['samples']['key'])
    assert Path(folder['path']) == sources.samples_folder(config)
    assert setup_core.save_setup(config, {'include_samples': True})['samples']['status'] == 'present'
    assert 'samples' not in setup_core.save_setup(config, {})
    with pytest.raises(ConfigError, match='must not overlap Assetarium'):
        sources.validate_directory(config, str(config.project_root / 'samples'))


def test_missing_samples_are_reported_and_the_other_choices_still_save(managed):
    from local_asset_library import setup_core
    config = managed[0]
    result = setup_core.save_setup(config, {'include_samples': True, 'storage_budget_gib': 33})
    assert result['status'] == 'partial' and 'samples/Sample assets' in result['samples']['reason']
    assert result['settings']['storage_budget_gib'] == 33


def test_an_agent_adds_the_samples_when_the_user_says_yes(managed):
    from local_asset_library import setup_agent, sources
    config = with_samples(managed[0])
    assert any(q['id'] == 'samples' and q['suggestion'] is True for q in setup_agent.ask_user(
        config, {'gpu': {'status': 'none', 'nvidia': [], 'other': []}, 'disk': {'free_gib': 100}}, {}, None))
    result = setup_agent.apply_setup(config, {'answers': {'samples': True}})
    assert result['samples']['status'] == 'added' and len(sources.registry(config)['sources']) == 3
    with pytest.raises(ConfigError, match='samples must be true or false'):
        setup_agent.apply_setup(config, {'answers': {'samples': 'yes'}})


def test_run_check_is_offered_only_when_it_can_pass(managed, monkeypatch):
    config = managed[0]
    item = lambda: next(i for i in engines.search_readiness(config, {'status': 'none', 'nvidia': [], 'other': []}, 'cpu')
                        if i['id'] == 'embedding_capability')
    monkeypatch.setattr(engines, 'runtime_ready', lambda config, runtime: {'ready': True, 'cpu_only_torch': True})
    monkeypatch.setattr(engines, 'weights_ready', lambda config, runtime: {'ready': False, 'state': 'absent', 'reason': 'absent'})
    assert item()['action'] is None and item()['command'] is None
    monkeypatch.setattr(engines, 'weights_ready', lambda config, runtime: {'ready': True, 'state': 'verified'})
    assert item()['action'] == 'search_check' and 'built-in sample images' in item()['detail']
