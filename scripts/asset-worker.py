"""Private persistent embedding worker; its stdout is JSON IPC, never diagnostics."""
from pathlib import Path
import contextlib
import json
import os
import sys
import queue
import threading
import time
import gc

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
wire = sys.stdout
with contextlib.redirect_stdout(sys.stderr):
    from local_asset_library.config import load_project_config
    from local_asset_library.embedding_backend import EmbeddingBackend
    from local_asset_library.mcp_assets import AssetService, error_payload
    config = load_project_config(root)
    service = AssetService(config, backend_factory=EmbeddingBackend)
    from local_asset_library.gpu_queue import lease,batch_requested,peer_requested
    from local_asset_library.config import ConfigError
    # Load native CPU libraries before starting the blocking input thread.
    # Windows SciPy/OpenBLAS DLL initialization can wait on that thread otherwise.
    # This private process is created only for an explicitly requested semantic query.
    from sentence_transformers import SentenceTransformer
requests = queue.Queue()
def read_requests():
    # Do not hold TextIOWrapper's input lock while importing inference libraries.
    # Some libraries inspect stdin; a blocked buffered reader can deadlock that inspection.
    pending=b''
    descriptor=sys.stdin.fileno()
    try:
        while True:
            chunk=os.read(descriptor,4096)
            if not chunk:break
            pending+=chunk
            while b'\n' in pending:
                item,pending=pending.split(b'\n',1)
                requests.put(item.decode('utf-8'))
        if pending:
            requests.put(pending.decode('utf-8'))
    finally:
        requests.put(None)
threading.Thread(target=read_requests, daemon=True).start()
owned = None
last = time.monotonic()
def unload():
    global owned
    if service.backend is not None:
        if getattr(service.backend,'model',None) is not None:
            service.backend.model.to('cpu')
            service.backend.model=None
        service.backend = None
        gc.collect()
        if 'torch' in sys.modules:
            sys.modules['torch'].cuda.empty_cache()
    if owned is not None:
        owned.__exit__(None, None, None)
        owned = None
while True:
    try:
        line = requests.get(timeout=0.5)
    except queue.Empty:
        if owned and (time.monotonic() - last > 60 or batch_requested(config) or peer_requested(config)):
            unload()
        continue
    if line is None:
        unload()
        break
    try:
        with contextlib.redirect_stdout(sys.stderr):
            request = json.loads(line)
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
            payload, image, evidence = service.execute(request['name'], request['arguments'])
        result = dict(payload=payload, image=image, evidence=evidence, is_error=False)
    except Exception as exc:
        result = dict(payload=error_payload(exc), image=None, evidence={'fault':str(exc)}, is_error=True)
    wire.write(json.dumps(result, separators=(',', ':'), ensure_ascii=False) + '\n')
    wire.flush()
    last = time.monotonic()
