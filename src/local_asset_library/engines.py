"""Composition root for inference adapters, plus the engine table setup reads (decision 0015).

The only place that chooses and constructs a description engine or an embedder.
Readiness checks here are static: they read files and package metadata and never
import Torch, load a model, contact a server or start a process.
"""
import json
import os
from pathlib import Path

from .config import ConfigError, venv_python

BUILTIN, SERVER = 'builtin', 'local-server'
# One small data table; a later model list replaces it without changing callers.
DESCRIPTION_ENGINES = {
    BUILTIN: {'id': BUILTIN, 'label': 'Built in', 'name': 'Qwen3-VL-2B-Instruct', 'kind': 'transformers',
              'status': 'tested', 'batching': True, 'runtime': 'caption', 'model_contract': 'docs/caption-model.json',
              'summary': 'Runs inside Assetarium. Needs an NVIDIA GPU with CUDA and BF16 (RTX 30-series or newer), '
                         'the description runtime and about 4.3 GB of model weights. This is the tested setup.'},
    SERVER: {'id': SERVER, 'label': 'Local model server', 'name': 'OpenAI-compatible server', 'kind': 'openai-compatible',
             'status': 'experimental', 'batching': False,
             'summary': 'Assetarium sends previews to a model server already running on this computer: llama.cpp, '
                        'Ollama, LM Studio or another OpenAI-compatible server. The server decides which GPU it uses, '
                        'so this is the way to use AMD and other GPUs. Choose a vision model; Qwen3-VL-2B-Instruct is '
                        'the one we have checked. Only addresses on this computer are accepted. Assetarium never '
                        'starts or installs the server.'},
}
EMBEDDERS = {BUILTIN: {'id': BUILTIN, 'name': 'EmbeddingGemma 2', 'kind': 'sentence-transformers', 'runtime': 'embedding',
                       'model_contract': 'docs/embedding-model.json', 'status': 'tested',
                       'summary': 'Semantic and image search with EmbeddingGemma 2 (about 1.5 GB of model weights), on an '
                                  'NVIDIA GPU or on the CPU.'}}
# Where the embedder runs (decision 0018). Each device has its own vector identity; switching re-indexes.
SEARCH_DEVICES = {
    'cuda': {'id': 'cuda', 'label': 'NVIDIA GPU', 'project': 'runtime/embedding', 'status': 'tested',
             'summary': 'Needs an NVIDIA GPU with CUDA and BF16 (RTX 30-series or newer). Fastest: about 0.1 s per image.'},
    'cpu': {'id': 'cpu', 'label': 'CPU', 'project': 'runtime/embedding-cpu', 'status': 'tested',
            'summary': 'Runs on any x86-64 CPU with the same model and precision, so search results match closely. '
                       'Indexing images is slower (about 0.8 s per image on a 16-core CPU); searching feels the same.'}}
RUNTIME_PACKAGES = {'caption': ('torch', 'transformers'), 'embedding': ('torch', 'sentence-transformers')}
WEIGHTS = {'caption': ('captions/model-download.json', 'qwen3-vl-2b'),
           'embedding': ('embeddings/model-download.json', 'embeddinggemma-2')}


def active(config):
    from .settings import description_engine_settings
    return description_engine_settings(config)


def description_engine(config):
    """The configured DescriptionEngine adapter, constructed for this run."""
    choice = active(config)
    if choice['engine'] == SERVER:
        from .engine_server import ServerEngine
        return ServerEngine(config, choice['server']['url'], choice['server']['model'])
    from .engine_transformers import TransformersQwenEngine
    return TransformersQwenEngine(config)


def search_device(config):
    from .settings import search_device as saved
    return saved(config)


def cpu_threads():
    """Logical threads this process may use (all of them, including simultaneous multithreading)."""
    return (os.process_cpu_count() if hasattr(os, 'process_cpu_count') else None) or os.cpu_count() or 1


def embedder(config):
    """The configured Embedder adapter: EmbeddingGemma on the saved search device, never another one."""
    if search_device(config) == 'cpu':
        from .embedding_cpu import EmbeddingCpuBackend
        backend = EmbeddingCpuBackend(config)
        # Torch defaults to one thread per physical core; more embed faster with bit-identical vectors
        # (October 26, 2026). The owner's setting or the speed test's choice; outside the hashed adapter.
        from .search_speed import threads
        backend.torch.set_num_threads(threads(config)[0])
        return backend
    from .embedding_backend import EmbeddingBackend
    return EmbeddingBackend(config)


def embedder_contract(config):
    """The vector identity the configured embedder will report, without loading the model."""
    if search_device(config) == 'cpu':
        from .embedding_cpu import runtime_contract
    else:
        from .embedding_backend import runtime_contract
    return runtime_contract(config)


def batch_size(config):
    """Assets per engine call: the saved batch size for the built-in engine, one for a server."""
    from .settings import caption_batch_size
    return caption_batch_size(config) if active(config)['engine'] == BUILTIN else 1


def generation(config):
    """(generation_mode, engine identity) that new descriptions will record, without constructing the engine."""
    choice = active(config)
    if choice['engine'] == SERVER:
        from .engine_server import MODE
        return MODE, {'engine': SERVER, 'model': choice['server']['model']}
    from .caption_batching import MODE
    return MODE, None


def command(config, runtime, *args):
    script = ('.\\scripts\\' + runtime + '-runtime.ps1') if os.name == 'nt' else ('./scripts/' + runtime + '-runtime.sh')
    return ' '.join((script, *args))


def runtime_ready(config, runtime):
    """Packages present in the runtime environment (metadata only; nothing is imported)."""
    import importlib.metadata
    environment = '.venv-' + runtime
    python = venv_python(config.project_root, environment)
    root = config.project_root / environment
    sites = list(root.glob('Lib/site-packages')) + list(root.glob('lib/python3*/site-packages'))
    found = {d.metadata['Name'].lower(): d.version for site in sites for d in importlib.metadata.distributions(path=[str(site)])
             if d.metadata and d.metadata['Name']}
    missing = [name for name in RUNTIME_PACKAGES[runtime] if name not in found]
    return {'ready': python.is_file() and not missing, 'environment': environment,
            'missing_packages': missing if python.is_file() else list(RUNTIME_PACKAGES[runtime]),
            'cpu_only_torch': str(found.get('torch', '')).endswith('+cpu')}


def weights_ready(config, runtime):
    """Receipt revision matches the contract and every file is present with its recorded size (no hashing)."""
    receipt_name, folder = WEIGHTS[runtime]
    spec = DESCRIPTION_ENGINES[BUILTIN] if runtime == 'caption' else EMBEDDERS[BUILTIN]
    try:
        contract = json.loads((config.project_root / spec['model_contract']).read_text(encoding='utf-8'))
        receipt = json.loads(config.output_path('data', receipt_name).read_text(encoding='utf-8'))
        if receipt.get('revision') != contract['revision']:
            return {'ready': False, 'reason': 'The download receipt is for another model revision'}
        for item in receipt['files']:
            path = config.output_path('models', folder + '/' + contract['revision'] + '/' + item['name'])
            if not path.is_file() or path.stat().st_size != item['size']:
                return {'ready': False, 'reason': 'Model file missing or changed: ' + item['name']}
    except (OSError, ValueError, KeyError, TypeError, ConfigError) as exc:
        return {'ready': False, 'reason': 'No verified download: ' + (str(exc) if isinstance(exc, ConfigError) else 'receipt missing')}
    return {'ready': True, 'bytes': sum(item['size'] for item in receipt['files'])}


def gpu_bf16(gpu):
    """NVIDIA with compute capability 8.0 or newer (BF16); None when unknown."""
    devices = (gpu or {}).get('nvidia') or []
    if not devices:
        return False
    capability = devices[0].get('compute_capability')
    return None if capability is None else capability >= 8.0


def readiness(config, engine_id, gpu=None):
    """Static checklist for one description engine plus the search embedder, with commands for what is missing."""
    items = []
    if engine_id == BUILTIN:
        bf16 = gpu_bf16(gpu)
        items.append({'id': 'gpu', 'label': 'NVIDIA GPU with BF16', 'ready': bool(bf16),
                      'detail': None if bf16 else ('Compute capability not reported; BF16 needs 8.0 or newer'
                                                   if bf16 is None else 'Not detected on this computer')})
        runtime = runtime_ready(config, 'caption')
        items.append({'id': 'caption_runtime', 'label': 'Description runtime (.venv-caption)', 'ready': runtime['ready'],
                      'command': None if runtime['ready'] else command(config, 'caption', 'sync --locked --project runtime/caption')})
        weights = weights_ready(config, 'caption')
        items.append({'id': 'caption_weights', 'label': 'Description model weights (about 4.3 GB)', 'ready': weights['ready'],
                      'detail': weights.get('reason'),
                      'command': None if weights['ready'] else command(config, 'caption',
                          'run --locked --no-sync --project runtime/caption python scripts/prepare_caption_model.py')})
    elif engine_id == SERVER:
        server = active(config)['server']
        configured = bool(server['url'] and server['model'])
        items.append({'id': 'server', 'label': 'Server address and model', 'ready': configured,
                      'detail': None if configured else 'Not set yet. Setup only lists the server’s models; it never generates text.'})
    else:
        raise ConfigError('Unknown description engine')
    return {'engine': engine_id, 'items': items, 'search': search_readiness(config, gpu)}


def capability_ready(config, device):
    """The recorded text/image capability check matches the chosen device (static read; the contract is re-checked at use)."""
    try:
        value = json.loads(config.output_path('data', 'embeddings/capability.json').read_text(encoding='utf-8'))
        recorded = value['contract']['device']
    except (OSError, ValueError, KeyError, TypeError, ConfigError):
        return {'ready': False, 'reason': 'Not recorded yet. It needs two processed assets with previews.'}
    if recorded != ('cpu' if device == 'cpu' else 'cuda:0'):
        return {'ready': False, 'reason': 'Recorded for the other search device; record it again for this one.'}
    return {'ready': bool(value.get('actual_text_and_image_inference'))}


def search_readiness(config, gpu=None, device=None):
    """Static checklist for the search embedder on a device (the saved one by default), with commands for what is missing."""
    device = device or search_device(config)
    project = SEARCH_DEVICES[device]['project']
    items = []
    if device == 'cuda':
        bf16 = gpu_bf16(gpu)
        items.append({'id': 'search_gpu', 'label': 'NVIDIA GPU with BF16 for search', 'ready': bool(bf16),
                      'detail': None if bf16 else 'Not detected on this computer. Choose CPU for search in Settings → General.'})
    runtime = runtime_ready(config, 'embedding')
    mismatch = device == 'cuda' and runtime['ready'] and runtime['cpu_only_torch']
    items.append({'id': 'embedding_runtime', 'label': 'Search runtime (.venv-embedding)', 'ready': runtime['ready'] and not mismatch,
                  'detail': 'The installed search runtime is the CPU-only build.' if mismatch else None,
                  'command': None if runtime['ready'] and not mismatch else command(config, 'embedding', 'sync --locked --project ' + project)})
    weights = weights_ready(config, 'embedding')
    items.append({'id': 'embedding_weights', 'label': 'Search model weights (EmbeddingGemma, about 1.5 GB)', 'ready': weights['ready'],
                  'detail': weights.get('reason'),
                  'command': None if weights['ready'] else command(config, 'embedding',
                      f'run --locked --no-sync --project {project} python scripts/prepare_embedding_model.py'
                      + (' --device cpu' if device == 'cpu' else ''))})
    capability = capability_ready(config, device)
    items.append({'id': 'embedding_capability', 'label': 'Search check on two of your assets', 'ready': capability['ready'],
                  'detail': capability.get('reason'),
                  'command': None if capability['ready'] else command(config, 'embedding',
                      f'run --locked --no-sync --project {project} python scripts/record-embedding-capability.py')})
    return items
