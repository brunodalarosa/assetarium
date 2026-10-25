"""Private persistent embedding worker; its stdout is JSON IPC, never diagnostics.

The worker only turns text or an image into a vector (decision 0005). Catalog,
verification and ranking stay in the calling process. It may start when the app
opens: libraries load immediately, while the model loads, behind the GPU lease,
only for the first embedding request and unloads after ten idle minutes.
"""
from pathlib import Path
import contextlib
import json
import os
import sys
import queue
import threading
import time
import gc

IDLE_UNLOAD_SECONDS = 600
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
wire = sys.stdout
wire_lock = threading.Lock()


def send(value):
    with wire_lock:
        wire.write(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n')
        wire.flush()


with contextlib.redirect_stdout(sys.stderr):
    from local_asset_library.config import load_project_config, ConfigError
    from local_asset_library.embedding_backend import runtime_contract
    from local_asset_library.engines import embedder
    from local_asset_library.mcp_assets import error_payload
    from local_asset_library.gpu_queue import lease, batch_requested, peer_requested
    config = load_project_config(root)
    # Load native CPU libraries before starting the blocking input thread.
    # Windows SciPy/OpenBLAS DLL initialization can wait on that thread otherwise.
    from sentence_transformers import SentenceTransformer  # noqa: F401
send({'event': 'ready'})
requests = queue.Queue()


def read_requests():
    # Do not hold TextIOWrapper's input lock while importing inference libraries.
    # Some libraries inspect stdin; a blocked buffered reader can deadlock that inspection.
    pending = b''
    descriptor = sys.stdin.fileno()
    try:
        while True:
            chunk = os.read(descriptor, 4096)
            if not chunk:
                break
            pending += chunk
            while b'\n' in pending:
                item, pending = pending.split(b'\n', 1)
                requests.put(item.decode('utf-8'))
        if pending:
            requests.put(pending.decode('utf-8'))
    finally:
        requests.put(None)


threading.Thread(target=read_requests, daemon=True).start()
busy = threading.Event()


def heartbeat():
    # Lets the caller tell a slow first model load from a hung worker.
    while True:
        time.sleep(5)
        if busy.is_set():
            send({'event': 'heartbeat'})


threading.Thread(target=heartbeat, daemon=True).start()
backend = None
contract = None
owned = None
last = time.monotonic()


def unload():
    global backend, owned
    if backend is not None:
        if getattr(backend, 'model', None) is not None:
            backend.model.to('cpu')
            backend.model = None
        backend = None
        gc.collect()
        if 'torch' in sys.modules:
            sys.modules['torch'].cuda.empty_cache()
        send({'event': 'unloaded'})
    if owned is not None:
        owned.__exit__(None, None, None)
        owned = None


def embed(request):
    global backend, owned, contract
    if request.get('op') == 'contract':
        if contract is None:
            contract = runtime_contract(config)
        return {'contract': contract}
    if request.get('op') not in {'text', 'image'}:
        raise ConfigError('Unknown embedding worker request')
    if batch_requested(config):
        unload()
        raise ConfigError('Inference queue busy with an owned batch; browse/keyword/detail remain available.')
    if owned and peer_requested(config):
        unload()
        time.sleep(0.1)
    if owned is None:
        owned = lease(config, 'search-worker', timeout=5)
        try:
            owned.__enter__()
        except Exception:
            owned = None
            raise
    if backend is None:
        send({'event': 'loading_model'})
        backend = embedder(config)
        contract = backend.contract
        send({'event': 'model_ready'})
    if request['op'] == 'text':
        vector = backend.text(request['text'], role=request.get('role', 'query'))
    else:
        vector = backend.image(Path(request['path']))
    return {'vector': [float(x) for x in vector], 'metrics': dict(backend.last_metrics), 'contract': backend.contract}


while True:
    try:
        line = requests.get(timeout=0.5)
    except queue.Empty:
        if owned and (time.monotonic() - last > IDLE_UNLOAD_SECONDS or batch_requested(config) or peer_requested(config)):
            unload()
        continue
    if line is None:
        unload()
        break
    busy.set()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = {'result': embed(json.loads(line)), 'is_error': False}
    except Exception as exc:
        result = {'result': None, 'is_error': True, 'payload': error_payload(exc), 'fault': str(exc) or type(exc).__name__}
    finally:
        busy.clear()
    send(result)
    last = time.monotonic()
