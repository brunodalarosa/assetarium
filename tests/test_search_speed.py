"""CPU threads for search data: the speed test's choice, the owner's setting and the count used (decision 0022)."""
import json
from pathlib import Path

import pytest

from test_cpu_embedder import config  # noqa: F401  (fixture)
from local_asset_library import engines, search_speed, source_operations
from local_asset_library.config import ConfigError
from local_asset_library.settings import general_settings, save_general_settings


class FakeBackend:
    """Seconds per image by thread count, so the choice can be checked without a model."""
    def __init__(self, speeds):
        self.speeds, self.current, self.calls = speeds, None, []
        self.torch = type('Torch', (), {'set_num_threads': staticmethod(self.set)})

    def set(self, count):
        self.current = count
        self.calls.append(count)

    def image(self, path):
        assert Path(path).is_file()
        return self.speeds.get(self.current, 0)


@pytest.fixture
def timed(config, monkeypatch):
    monkeypatch.setattr(engines, 'cpu_threads', lambda: 32)
    monkeypatch.setattr(search_speed, 'counts', lambda: [16, 24, 32])
    clock = [0.0]
    monkeypatch.setattr(search_speed.time, 'perf_counter', lambda: clock[0])
    original = FakeBackend.image

    def image(self, path):
        clock[0] += original(self, path)
    monkeypatch.setattr(FakeBackend, 'image', image)
    return config


def test_the_test_keeps_the_fewest_threads_within_three_percent_of_the_fastest(timed):
    config = timed
    backend = FakeBackend({16: 1.14, 24: 0.89, 32: 0.88})
    result = search_speed.run(config, backend)
    assert result['chosen'] == 24 and [r['threads'] for r in result['results']] == [16, 24, 32]
    assert {r['threads']: r['seconds_per_image'] for r in result['results']} == {16: 1.14, 24: 0.89, 32: 0.88}
    assert backend.calls == [16, 24, 32, 32, 24, 16]  # Two passes, the second in reverse order.
    assert search_speed.saved(config)['chosen'] == 24
    assert not config.output_path('scratch', 'search-test').exists()  # Its synthetic images are removed.
    assert search_speed.threads(config) == (24, 'fastest in the speed test')


def test_a_clearly_faster_count_wins_and_a_cancelled_test_saves_nothing(timed):
    config = timed
    assert search_speed.run(config, FakeBackend({16: 1.2, 24: 1.0, 32: 0.8}))['chosen'] == 32
    search_speed.probe_path(config).unlink()
    assert search_speed.run(config, FakeBackend({}), cancelled=lambda: True) == {'cancelled': True}
    assert search_speed.saved(config) is None


def test_a_test_from_another_machine_or_runtime_is_not_used(timed, monkeypatch):
    config = timed
    search_speed.run(config, FakeBackend({16: 1.1, 24: 0.9, 32: 0.9}))
    monkeypatch.setattr(engines, 'cpu_threads', lambda: 16)
    assert search_speed.saved(config) is None
    assert search_speed.threads(config) == (16, 'every logical thread (not speed-tested yet)')


def test_the_owners_setting_wins_and_is_capped_on_a_smaller_machine(timed, monkeypatch):
    config = timed
    search_speed.run(config, FakeBackend({16: 1.1, 24: 0.9, 32: 0.9}))
    save_general_settings(config, 8, search_threads=28)
    assert general_settings(config)['search_threads'] == 28
    assert search_speed.threads(config) == (28, 'your setting')
    save_general_settings(config, 8)  # Omitted: kept.
    assert general_settings(config)['search_threads'] == 28
    monkeypatch.setattr(engines, 'cpu_threads', lambda: 16)
    assert search_speed.threads(config) == (16, 'your setting')
    monkeypatch.setattr(engines, 'cpu_threads', lambda: 32)
    for bad in (0, 33, 'many', 2.5):
        with pytest.raises(ConfigError, match='1 to 32 CPU threads'):
            save_general_settings(config, 8, search_threads=bad)
    save_general_settings(config, 8, search_threads='auto')
    assert general_settings(config)['search_threads'] is None
    assert search_speed.threads(config) == (24, 'fastest in the speed test')


def test_search_data_tests_first_when_needed_and_only_on_the_cpu(timed):
    config = timed
    backend = FakeBackend({16: 1.1, 24: 0.9, 32: 0.9})
    assert search_speed.ensure(config, backend) is None and backend.calls == []  # Search on the GPU.
    save_general_settings(config, 8, None, None, None, None, None, 'cpu')
    phases = []
    assert search_speed.ensure(config, backend, progress=phases.append)['chosen'] == 24
    assert phases[0] == 'Testing search speed on this computer' and backend.calls[-1] == 24
    backend.calls.clear()
    search_speed.ensure(config, backend)
    assert backend.calls == [24]  # Already tested: only the chosen count is set.


def test_the_cpu_embedder_uses_the_count_chosen(timed, monkeypatch):
    config = timed
    built = []
    monkeypatch.setattr('local_asset_library.embedding_cpu.EmbeddingCpuBackend', lambda c: built.append(FakeBackend({})) or built[-1])
    save_general_settings(config, 8, None, None, None, None, None, 'cpu', search_threads=20)
    assert engines.embedder(config).calls == [20]


def test_test_again_runs_the_search_part_in_the_search_runtime(timed, monkeypatch):
    config = timed
    save_general_settings(config, 8, None, None, None, None, None, 'cpu')
    phases, commands = [], []
    monkeypatch.setattr(source_operations, 'state', lambda c, **kw: phases.append(kw))
    monkeypatch.setattr('local_asset_library.render_devices.run', lambda c, progress, cancelled: {
        'cancelled': False, 'chosen': 'cpu', 'results': [{'key': 'cpu', 'label': 'CPU', 'best': {'processes': 2}}]})

    def search(command, **kwargs):
        commands.append(command)
        search_speed.run(config, FakeBackend({16: 1.1, 24: 0.9, 32: 0.9}))
        return type('Done', (), {'returncode': 0})()
    monkeypatch.setattr(source_operations.subprocess, 'run', search)
    source_operations.render_test(config, 'token')
    assert 'search-test' in commands[0] and 'embedding-cpu' in ' '.join(commands[0])
    assert phases[-1]['phase'] == 'Speed test finished: CPU, 2 at a time; search data 24 CPU threads'
    search_speed.probe_path(config).unlink()
    monkeypatch.setattr(source_operations.subprocess, 'run', lambda command, **kwargs: type('Failed', (), {'returncode': 1})())
    source_operations.render_test(config, 'token')
    assert phases[-1]['phase'].endswith('search data not tested (the CPU search runtime or its model is not ready)')
