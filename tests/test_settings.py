"""Saved user limits govern real coordinator gates without processing assets."""
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from local_asset_library.config import Config, ConfigError
from local_asset_library.publication import atomic_json
from local_asset_library.settings import (GIB, general_settings, save_general_settings,
                                          settings_path, storage_budget, caption_batch_size)
from local_asset_library.incremental import policy
from local_asset_library import source_operations as operations


@pytest.fixture
def config(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    value = Config(root, tmp_path / 'originals', None)
    atomic_json(root / 'docs/library-membership.json', {
        'schema_version': 1, 'approved': True, 'packs': ['fixture'],
        'budget': {'total_allocated_bytes': 10 * GIB, 'peak_additional_allocated_bytes': 3 * GIB}})
    return value


def test_default_preserves_historical_policy_until_user_saves(config):
    assert general_settings(config)['storage_budget_gib'] == 10
    assert storage_budget(config)['peak_additional_allocated_bytes'] == 3 * GIB
    assert not settings_path(config).exists()


def test_saved_total_survives_reload_and_source_binding_without_hidden_growth_cap(config):
    original = (config.project_root / 'docs/library-membership.json').read_bytes()
    result = save_general_settings(config, '24')
    assert result == {'status': 'saved', 'storage_budget_gib': 24, 'processing_formats': ['fbx', 'gltf', 'obj'],
                      'caption_batch_size': 8, 'descriptions_enabled': True, 'description_engine': 'builtin',
                      'description_server': {'url': 'http://127.0.0.1:8080/v1', 'model': ''}}
    rebound = replace(config, metadata_root=config.source_root / 'metadata-lal', source_key='fixture')
    assert general_settings(rebound)['storage_budget_gib'] == 24
    assert settings_path(rebound) == settings_path(config)
    assert not config.source_root.exists()
    assert policy(config)['budget'] == {'total_allocated_bytes': 24 * GIB, 'peak_additional_allocated_bytes': 24 * GIB}
    assert (config.project_root / 'docs/library-membership.json').read_bytes() == original


@pytest.mark.parametrize('value', ['', None, True, [], {}, 0, -1, 1.5, 'nan', 'inf', 1048577])
def test_invalid_limit_preserves_saved_settings(config, value):
    save_general_settings(config, 24)
    before = settings_path(config).read_bytes()
    with pytest.raises(ConfigError, match='whole number'):
        save_general_settings(config, value)
    assert settings_path(config).read_bytes() == before


def test_caption_batch_size_defaults_to_eight_and_saves_with_other_settings(config):
    assert general_settings(config)['caption_batch_size'] == 8 == caption_batch_size(config)
    assert save_general_settings(config, 24, ['gltf'], '4')['caption_batch_size'] == 4
    rebound = replace(config, metadata_root=config.source_root / 'metadata-lal', source_key='fixture')
    assert caption_batch_size(rebound) == 4
    # Saving other settings keeps the chosen batch size.
    assert save_general_settings(config, 30)['caption_batch_size'] == 4
    assert general_settings(config)['processing_formats'] == ['gltf']


@pytest.mark.parametrize('value', [0, 3, 16, -1, True, 'eight', '', 4.0, [8]])
def test_invalid_caption_batch_size_preserves_saved_settings(config, value):
    save_general_settings(config, 24, None, 2)
    before = settings_path(config).read_bytes()
    with pytest.raises(ConfigError, match='batch size of 1, 2, 4 or 8'):
        save_general_settings(config, 24, None, value)
    assert settings_path(config).read_bytes() == before


def test_bad_saved_caption_batch_size_is_a_visible_fault(config):
    save_general_settings(config, 24)
    value = json.loads(settings_path(config).read_text(encoding='utf-8'))
    atomic_json(settings_path(config), dict(value, caption_batch_size=64))
    with pytest.raises(ConfigError, match='batch size'):
        caption_batch_size(config)


def test_bad_saved_limit_never_silently_uses_another_budget(config):
    atomic_json(settings_path(config), {'schema_version': 1, 'storage_budget_bytes': -1})
    with pytest.raises(ConfigError, match='Invalid saved storage budget'):
        storage_budget(config)
    save_general_settings(config, 24)
    assert general_settings(config)['storage_budget_gib'] == 24


def coordinator(config, monkeypatch, allocations, after_stage=None):
    calls, states = [], []
    monkeypatch.setattr(operations, 'bound', lambda *args: config)
    monkeypatch.setattr(operations, 'state', lambda config, **kw: states.append(kw))
    monkeypatch.setattr(operations, 'scan_source', lambda *args: {'failed': 0, 'needs_processing': False})
    monkeypatch.setattr(operations, 'ensure_index', lambda *args: None)
    monkeypatch.setattr(operations, 'cancelled', lambda *args: False)
    monkeypatch.setattr(operations, 'publish_source', lambda *args: None)
    monkeypatch.setattr(operations, 'aggregate', lambda *args: None)
    from local_asset_library import source_storage
    values = iter(allocations)
    monkeypatch.setattr(source_storage, 'receipt', lambda *args: {'totals': {'allocated_bytes': next(values)}})
    def run(command, **kwargs):
        calls.append(command)
        if after_stage:
            after_stage()
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(operations.subprocess, 'run', run)
    return calls, states


def test_processing_accepts_existing_usage_and_growth_above_historical_limits(config, monkeypatch):
    save_general_settings(config, 24)
    calls, states = coordinator(config, monkeypatch, [11 * GIB, 15 * GIB, 16 * GIB, 17 * GIB])
    operations.process_source(config, {'key': 'fixture', 'id': 'fixture-id', 'name': 'fixture'}, 'test-token')
    # Importing runs inspection and search data only; descriptions are a separate run.
    assert len(calls) == 2 and states[-1]['status'] == 'complete'
    assert [c[c.index('--stage') + 1] for c in calls] == ['inspection', 'embeddings']


def test_exhausted_budget_starts_no_asset_worker(config, monkeypatch):
    save_general_settings(config, 1)
    calls, _ = coordinator(config, monkeypatch, [GIB])
    with pytest.raises(ConfigError, match='Settings → General'):
        operations.process_source(config, {'key': 'fixture', 'id': 'fixture-id', 'name': 'fixture'}, 'test-token')
    assert not calls


def test_changed_limit_is_applied_at_next_stage_check(config, monkeypatch):
    save_general_settings(config, 24)
    calls, states = coordinator(config, monkeypatch, [11 * GIB, 13 * GIB],
                                 after_stage=lambda: save_general_settings(config, 12))
    with pytest.raises(ConfigError, match='completed work is preserved'):
        operations.process_source(config, {'key': 'fixture', 'id': 'fixture-id', 'name': 'fixture'}, 'test-token')
    assert len(calls) == 1 and all(s['status'] != 'complete' for s in states)


def test_publication_growth_is_checked_before_reporting_completion(config, monkeypatch):
    save_general_settings(config, 24)
    calls, states = coordinator(config, monkeypatch, [11 * GIB, 15 * GIB, 16 * GIB, 25 * GIB])
    with pytest.raises(ConfigError, match='completed work is preserved'):
        operations.process_source(config, {'key': 'fixture', 'id': 'fixture-id', 'name': 'fixture'}, 'test-token')
    assert len(calls) == 2 and all(s['status'] != 'complete' for s in states)


def test_gpu_memory_reason_from_stage_worker_reaches_the_source_card(config, monkeypatch):
    save_general_settings(config, 24)
    calls, states = coordinator(config, monkeypatch, [11 * GIB])
    reason = 'Not enough GPU memory for description batch size 8. Lower it in Settings → General'
    def failing(command, **kwargs):
        calls.append(command)
        atomic_json(operations.stage_fault_path(config, 'test-token'), {'reason': reason})
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(operations.subprocess, 'run', failing)
    with pytest.raises(ConfigError, match='batch size 8. Lower it'):
        operations.process_source(config, {'key': 'fixture', 'id': 'fixture-id', 'name': 'fixture'}, 'test-token')
    assert len(calls) == 1


def test_cancelling_caption_stage_names_the_batch():
    assert operations.finishing('caption') == 'Finishing the current batch before stopping'
    assert operations.finishing('inspection') == 'Finishing the current asset before stopping'


def test_interface_preferences_default_validate_and_never_touch_budget_settings(config):
    from local_asset_library.settings import interface_path, interface_settings, save_interface_settings
    assert interface_settings(config) == {'status': 'ready', 'appearance': 'system', 'inspector_width': 440}
    saved = save_interface_settings(config, appearance='dark')
    assert saved == {'status': 'saved', 'appearance': 'dark', 'inspector_width': 440}
    assert save_interface_settings(config, inspector_width=5000)['inspector_width'] == 960  # clamped
    assert save_interface_settings(config, inspector_width=12)['inspector_width'] == 320
    assert interface_settings(config)['appearance'] == 'dark'  # width saves keep the appearance
    with pytest.raises(ConfigError, match='Match Windows'):
        save_interface_settings(config, appearance='sepia')
    with pytest.raises(ConfigError, match='pixels'):
        save_interface_settings(config, inspector_width=True)
    # Presentation lives apart from settings.json, so budget validation never sees it.
    assert not settings_path(config).exists() and interface_path(config).exists()
    assert general_settings(config)['storage_budget_gib'] == 10


def test_damaged_interface_preferences_reset_presentation_only(config):
    from local_asset_library.settings import interface_path, interface_settings
    interface_path(config).parent.mkdir(parents=True, exist_ok=True)
    interface_path(config).write_text('{not json', encoding='utf-8')
    assert interface_settings(config)['appearance'] == 'system'
    atomic_json(interface_path(config), {'appearance': 'neon', 'inspector_width': 'wide'})
    assert interface_settings(config) == {'status': 'ready', 'appearance': 'system', 'inspector_width': 440}

def test_model_preparation_uses_unique_allocation_and_saved_budget(config, monkeypatch):
    from local_asset_library import model_storage, source_storage
    monkeypatch.setattr(source_storage, 'measure_all', lambda _: {'totals': {'allocated_bytes': 5 * GIB}, 'faults': []})
    save_general_settings(config, 12)
    assert model_storage.project_allocation(config) == {'allocated_bytes': 5 * GIB, 'faults': 0, 'budget_bytes': 12 * GIB}


def test_fresh_install_uses_neutral_policy_without_owner_contract(tmp_path):
    from local_asset_library.library_policy import DEFAULT_BUDGET, contract, library_mode
    root = tmp_path / 'project'
    root.mkdir()
    value = Config(root, tmp_path / 'originals', None)
    assert storage_budget(value) == DEFAULT_BUDGET and contract(value)['packs'] == []
    assert not library_mode(value) and library_mode(replace(value, sources_registry=root / 'sources.json'))
