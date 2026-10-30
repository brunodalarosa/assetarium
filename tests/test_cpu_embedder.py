"""CPU search embedder (decision 0018): the setting, composition root, identity, readiness and setup."""
from argparse import Namespace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from local_asset_library import embedding_cpu, engines, setup_core
from local_asset_library.catalog import digest
from local_asset_library.config import Config, ConfigError, venv_python
from local_asset_library.mcp_assets import SCHEMAS
from local_asset_library.publication import atomic_json
from local_asset_library.retrieval import recorded_contract
from local_asset_library.settings import general_settings, save_general_settings, search_device
from test_sources import managed, ready_source  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    return Config(root, tmp_path / 'originals', None)


def test_search_device_defaults_to_cuda_and_saves_cpu(config):
    assert search_device(config) == 'cuda' and general_settings(config)['search_device'] == 'cuda'
    saved = save_general_settings(config, 8, None, None, None, None, None, 'cpu')
    assert saved['search_device'] == 'cpu' == search_device(config)
    assert save_general_settings(config, 9)['search_device'] == 'cpu'  # Omitted keeps what is saved.
    with pytest.raises(ConfigError, match='where search runs'):
        save_general_settings(config, 8, None, None, None, None, None, 'rocm')
    assert search_device(config) == 'cpu'


class FakeCpuBackend:
    def __init__(self, config):
        self.threads = []
        self.torch = type('Torch', (), {'set_num_threads': staticmethod(self.threads.append)})


def test_composition_root_builds_the_embedder_for_the_saved_device(config, monkeypatch):
    built = []
    monkeypatch.setattr('local_asset_library.embedding_backend.EmbeddingBackend', lambda c: built.append('cuda') or 'cuda-backend')
    monkeypatch.setattr('local_asset_library.embedding_cpu.EmbeddingCpuBackend', lambda c: built.append('cpu') or FakeCpuBackend(c))
    monkeypatch.setattr('local_asset_library.embedding_backend.runtime_contract', lambda c: {'device': 'cuda:0'})
    monkeypatch.setattr('local_asset_library.embedding_cpu.runtime_contract', lambda c: {'device': 'cpu'})
    assert engines.embedder(config) == 'cuda-backend' and engines.embedder_contract(config) == {'device': 'cuda:0'}
    save_general_settings(config, 8, None, None, None, None, None, 'cpu')
    cpu = engines.embedder(config)
    assert isinstance(cpu, FakeCpuBackend) and engines.embedder_contract(config) == {'device': 'cpu'}
    assert built == ['cuda', 'cpu']
    from local_asset_library.search_speed import threads
    assert cpu.threads == [threads(config)[0]] == [engines.cpu_threads()]  # Untested, no setting: every thread.


def test_cpu_contract_has_its_own_identity_and_keeps_the_cuda_adapter_untouched(monkeypatch):
    base = {'model_id': 'google/embeddinggemma-2', 'dtype': 'bfloat16', 'device': 'cuda:0', 'adapter_sha256': 'b' * 64,
            'runtime_lock_sha256': 'c' * 64, 'versions': {'torch': '2.10.0+cpu'}}
    monkeypatch.setattr(embedding_cpu, 'cuda_contract', lambda c: dict(base))
    monkeypatch.setattr(embedding_cpu, 'installed_lock', lambda: 'runtime/embedding-cpu/uv.lock')
    contract = embedding_cpu.runtime_contract(SimpleNamespace(project_root=ROOT))
    lock = hashlib.sha256((ROOT / 'runtime/embedding-cpu/uv.lock').read_bytes()).hexdigest()
    assert contract['device'] == 'cpu' and contract['dtype'] == 'bfloat16'
    assert contract['base_adapter_sha256'] == 'b' * 64 != contract['adapter_sha256']
    assert contract['runtime_lock'] == 'runtime/embedding-cpu/uv.lock' and contract['runtime_lock_sha256'] == lock
    assert set(contract['hashed_files']) == {'adapter_sha256', 'base_adapter_sha256', 'runtime_lock_sha256'}
    assert digest(contract) != digest(base)  # CPU vectors never share an index with CUDA vectors.
    # Both locks pin the same packages apart from the Torch build.
    pins = lambda name: set(json.loads(json.dumps(
        [line for line in (ROOT / name / 'pyproject.toml').read_text(encoding='utf-8').splitlines() if '==' in line])))
    assert {p.replace('+cu128', '+cpu') for p in pins('runtime/embedding')} == pins('runtime/embedding-cpu')


def test_line_ending_tolerance_follows_the_contracts_own_hashed_files(config):
    lock = config.project_root / 'runtime/embedding-cpu/uv.lock'
    lock.parent.mkdir(parents=True)
    lock.write_bytes(b'version = 1\r\n')
    lf = hashlib.sha256(b'version = 1\n').hexdigest()
    crlf = hashlib.sha256(b'version = 1\r\n').hexdigest()
    files = {'runtime_lock_sha256': 'runtime/embedding-cpu/uv.lock'}
    atomic_json(config.output_path('data', 'embeddings/capability.json'),
                {'contract': {'device': 'cpu', 'runtime_lock_sha256': lf, 'hashed_files': files}})
    current = {'device': 'cpu', 'runtime_lock_sha256': crlf, 'hashed_files': files}
    assert recorded_contract(config, current)['runtime_lock_sha256'] == lf
    lock.write_bytes(b'version = 2\r\n')  # A real change is never hidden.
    changed = dict(current, runtime_lock_sha256=hashlib.sha256(b'version = 2\r\n').hexdigest())
    assert recorded_contract(config, changed) == changed


def test_published_index_contract_reconciles_line_endings_without_a_receipt(config):
    # Vectors from a library store built on an LF checkout, searched from a CRLF one with no search check yet.
    lock = config.project_root / 'runtime/embedding-cpu/uv.lock'
    lock.parent.mkdir(parents=True)
    lock.write_bytes(b'version = 1\r\n')
    lf = hashlib.sha256(b'version = 1\n').hexdigest()
    crlf = hashlib.sha256(b'version = 1\r\n').hexdigest()
    files = {'runtime_lock_sha256': 'runtime/embedding-cpu/uv.lock'}
    published = config.project_root / 'data/library/embedding-contract.json'
    atomic_json(published, {'contract': json.dumps({'device': 'cpu', 'runtime_lock_sha256': lf, 'hashed_files': files})})
    current = {'device': 'cpu', 'runtime_lock_sha256': crlf, 'hashed_files': files}
    assert recorded_contract(config, current)['runtime_lock_sha256'] == lf
    changed = dict(current, runtime_lock_sha256=hashlib.sha256(b'version = 2\r\n').hexdigest())
    lock.write_bytes(b'version = 2\r\n')
    assert recorded_contract(config, changed) == changed  # A real change still needs a reindex.
    lock.write_bytes(b'version = 1\r\n')
    # A search check recorded with the current bytes decides first.
    atomic_json(config.output_path('data', 'embeddings/capability.json'), {'contract': current})
    assert recorded_contract(config, current) == current


def fake_runtime(config, torch_version):
    python = venv_python(config.project_root, '.venv-embedding')
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_bytes(b'')
    site = config.project_root / '.venv-embedding/Lib/site-packages'
    for name, version in (('torch', torch_version), ('sentence_transformers', '6.1.0')):
        info = site / f'{name}-{version}.dist-info'
        info.mkdir(parents=True)
        (info / 'METADATA').write_text(f'Metadata-Version: 2.1\nName: {name.replace("_", "-")}\nVersion: {version}\n', encoding='utf-8')


def test_search_readiness_follows_the_device(config):
    no_gpu = {'status': 'none', 'nvidia': [], 'other': ['AMD Radeon RX 6800']}
    cuda = {item['id']: item for item in engines.search_readiness(config, no_gpu)}
    assert not cuda['search_gpu']['ready'] and 'CPU' in cuda['search_gpu']['detail']
    assert 'runtime/embedding ' in cuda['embedding_runtime']['command'] + ' '
    cpu = {item['id']: item for item in engines.search_readiness(config, no_gpu, 'cpu')}
    assert 'search_gpu' not in cpu and 'runtime/embedding-cpu' in cpu['embedding_runtime']['command']
    assert cpu['embedding_weights']['command'].endswith('prepare_embedding_model.py --device cpu')
    assert not cpu['embedding_capability']['ready'] and 'record-embedding-capability.py' in cpu['embedding_capability']['command']
    fake_runtime(config, '2.10.0+cpu')
    assert {i['id']: i for i in engines.search_readiness(config, no_gpu, 'cpu')}['embedding_runtime']['ready']
    mismatch = {i['id']: i for i in engines.search_readiness(config, no_gpu, 'cuda')}['embedding_runtime']
    assert not mismatch['ready'] and 'CPU-only' in mismatch['detail'] and 'runtime/embedding ' in mismatch['command'] + ' '


def test_incomplete_search_runtime_names_its_fix_and_is_not_retained(config):
    import asyncio
    from local_asset_library.mcp_assets import TransientFault
    from local_asset_library.mcp_server import Gateway
    python = venv_python(config.project_root, '.venv-embedding')
    python.parent.mkdir(parents=True)
    python.write_bytes(b'')
    # What a wrapper sync without --project leaves behind: the base project, no torch or sentence-transformers.
    info = config.project_root / '.venv-embedding/Lib/site-packages/numpy-2.3.4.dist-info'
    info.mkdir(parents=True)
    (info / 'METADATA').write_text('Metadata-Version: 2.1\nName: numpy\nVersion: 2.3.4\n', encoding='utf-8')
    gateway = Gateway(config)
    async def search():
        with pytest.raises(TransientFault, match='sync --locked --project runtime/embedding$') as fault:
            await gateway.embed({'op': 'text', 'text': 'x', 'role': 'query'})
        assert 'missing torch, sentence-transformers' in str(fault.value)
        assert gateway.worker is None and gateway.worker_fault is None  # The next search tries again.
        await gateway.close()
    asyncio.run(search())
    save_general_settings(config, 8, None, None, None, None, None, 'cpu')
    assert engines.search_runtime_fault(config).endswith('--project runtime/embedding-cpu')  # The saved device's lock.
    fake_runtime(config, '2.10.0+cpu')
    assert engines.search_runtime_fault(config) is None


def test_runtime_wrappers_refuse_project_commands_without_a_project():
    import subprocess
    from local_asset_library.config import runtime_command
    for runtime in ('mcp', 'caption', 'embedding'):
        result = subprocess.run([*runtime_command(ROOT, runtime), 'sync', '--locked'], capture_output=True, text=True, timeout=60)
        assert result.returncode == 2 and '--project runtime/' + runtime in result.stderr


def test_capability_receipt_must_match_the_device(config):
    path = config.output_path('data', 'embeddings/capability.json')
    atomic_json(path, {'contract': {'device': 'cuda:0'}, 'actual_text_and_image_inference': True})
    assert engines.capability_ready(config, 'cuda') == {'ready': True}
    assert 'other search device' in engines.capability_ready(config, 'cpu')['reason']
    atomic_json(path, {'contract': {'device': 'cpu'}, 'actual_text_and_image_inference': True})
    assert engines.capability_ready(config, 'cpu') == {'ready': True}


def test_setup_suggests_cpu_without_nvidia_and_lists_both_devices(config, monkeypatch):
    monkeypatch.setattr(setup_core, 'gpu_report', lambda run=None: {'status': 'none', 'nvidia': [], 'other': ['AMD Radeon RX 6800']})
    report = setup_core.environment_report(config)
    assert report['suggested_search_device'] == 'cpu' and set(report['search_devices']) == {'cuda', 'cpu'}
    monkeypatch.setattr(setup_core, 'gpu_report', lambda run=None: {'status': 'ready', 'nvidia': [
        {'name': 'RTX', 'vram_gib': 12, 'driver': '1', 'compute_capability': 8.9}], 'other': []})
    assert setup_core.environment_report(config)['suggested_search_device'] == 'cuda'
    state = setup_core.setup_state(config)
    assert [d['id'] for d in state['search_devices']] == ['cuda', 'cpu']
    saved = setup_core.save_setup(config, {'search_device': 'cpu', 'skipped_steps': ['blender']})
    assert saved['settings']['search_device'] == 'cpu'
    assert setup_core.setup_state(config)['set_by']['search_device']['set_by'] == 'user'


def test_stages_run_in_the_environment_their_engine_needs(config):
    from local_asset_library.source_operations import stage_runtime
    assert [stage_runtime(config, s) for s in ('inspection', 'caption', 'embeddings')] == [
        ('mcp', 'mcp'), ('caption', 'caption'), ('embedding', 'embedding')]
    save_general_settings(config, 8, None, None, True, 'local-server', {'url': 'http://127.0.0.1:8080/v1', 'model': 'm'}, 'cpu')
    # A local server needs no Torch; CPU search uses its own lock in the same search environment.
    assert stage_runtime(config, 'caption') == ('mcp', 'mcp')
    assert stage_runtime(config, 'embeddings') == ('embedding', 'embedding-cpu')


def test_search_stage_names_the_search_check_while_it_is_missing(managed, monkeypatch):
    from local_asset_library import sources, source_operations as operations
    import local_asset_library.incremental as incremental
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    scoped = sources.bound(config, one)
    operations.state(scoped, operation='process', status='processing', token='w2')
    def no_receipt(*args, **kwargs):
        raise FileNotFoundError('capability.json')
    monkeypatch.setattr(incremental, 'process', no_receipt)
    save_general_settings(config, 8, None, None, None, None, None, 'cpu')
    with pytest.raises(ConfigError, match='one-time search check') as stopped:
        operations.worker_stage(config, one, 'embeddings', 'w2')
    assert 'record-embedding-capability.py' in str(stopped.value) and 'runtime/embedding-cpu' in str(stopped.value)
    fault = json.loads(operations.stage_fault_path(scoped, 'w2').read_text(encoding='utf-8'))
    assert fault['reason'] == str(stopped.value)
    # With a receipt for this device, the original fault is reported unchanged.
    atomic_json(config.output_path('data', 'embeddings/capability.json'),
                {'contract': {'device': 'cpu'}, 'actual_text_and_image_inference': True})
    with pytest.raises(FileNotFoundError):
        operations.worker_stage(config, one, 'embeddings', 'w2')


def test_agents_and_the_cli_can_set_the_device(config):
    schema = SCHEMAS['apply_setup']['properties']['search_device']
    assert schema['enum'] == ['cuda', 'cpu']
    from local_asset_library.owner_commands import settings_command
    args = Namespace(action='set', formats=None, budget_gib=None, batch_size=None, descriptions=None, engine=None,
                     server_url=None, server_model=None, search_device='cpu', json=True, quiet=True)
    assert settings_command(args, config)['search_device'] == 'cpu'
