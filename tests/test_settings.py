"""Saved user limits govern real coordinator gates without processing assets."""
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from local_asset_library.config import Config, ConfigError
from local_asset_library.publication import atomic_json
from local_asset_library.settings import (GIB, general_settings, save_general_settings,
                                          settings_path, storage_budget)
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
    assert result == {'status': 'saved', 'storage_budget_gib': 24}
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
    calls, states = coordinator(config, monkeypatch, [11 * GIB, 15 * GIB, 16 * GIB, 17 * GIB, 18 * GIB])
    operations.process_source(config, {'key': 'fixture'}, 'test-token')
    assert len(calls) == 3 and states[-1]['status'] == 'complete'


def test_exhausted_budget_starts_no_asset_worker(config, monkeypatch):
    save_general_settings(config, 1)
    calls, _ = coordinator(config, monkeypatch, [GIB])
    with pytest.raises(ConfigError, match='Settings → General'):
        operations.process_source(config, {'key': 'fixture'}, 'test-token')
    assert not calls


def test_changed_limit_is_applied_at_next_stage_check(config, monkeypatch):
    save_general_settings(config, 24)
    calls, states = coordinator(config, monkeypatch, [11 * GIB, 13 * GIB],
                                 after_stage=lambda: save_general_settings(config, 12))
    with pytest.raises(ConfigError, match='completed work is preserved'):
        operations.process_source(config, {'key': 'fixture'}, 'test-token')
    assert len(calls) == 1 and all(s['status'] != 'complete' for s in states)


def test_publication_growth_is_checked_before_reporting_completion(config, monkeypatch):
    save_general_settings(config, 24)
    calls, states = coordinator(config, monkeypatch, [11 * GIB, 15 * GIB, 16 * GIB, 17 * GIB, 25 * GIB])
    with pytest.raises(ConfigError, match='completed work is preserved'):
        operations.process_source(config, {'key': 'fixture'}, 'test-token')
    assert len(calls) == 3 and all(s['status'] != 'complete' for s in states)
