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
                       'summary': 'Semantic and image search. Needs an NVIDIA GPU with CUDA and BF16, the search '
                                  'runtime and about 1.5 GB of model weights.'}}
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


def embedder(config):
    """The configured Embedder adapter (EmbeddingGemma is the only one in this version)."""
    from .embedding_backend import EmbeddingBackend
    return EmbeddingBackend(config)


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
    found = {d.metadata['Name'].lower() for site in sites for d in importlib.metadata.distributions(path=[str(site)])
             if d.metadata and d.metadata['Name']}
    missing = [name for name in RUNTIME_PACKAGES[runtime] if name not in found]
    return {'ready': python.is_file() and not missing, 'environment': environment,
            'missing_packages': missing if python.is_file() else list(RUNTIME_PACKAGES[runtime])}


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
    runtime = runtime_ready(config, 'embedding')
    weights = weights_ready(config, 'embedding')
    search = [{'id': 'embedding_runtime', 'label': 'Search runtime (.venv-embedding)', 'ready': runtime['ready'],
               'command': None if runtime['ready'] else command(config, 'embedding', 'sync --locked --project runtime/embedding')},
              {'id': 'embedding_weights', 'label': 'Search model weights (EmbeddingGemma, about 1.5 GB)', 'ready': weights['ready'],
               'detail': weights.get('reason'),
               'command': None if weights['ready'] else command(config, 'embedding',
                   'run --locked --no-sync --project runtime/embedding python scripts/prepare_embedding_model.py')}]
    return {'engine': engine_id, 'items': items, 'search': search}
