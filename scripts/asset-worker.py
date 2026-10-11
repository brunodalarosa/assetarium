"""Private persistent embedding worker; its stdout is JSON IPC, never diagnostics."""
from pathlib import Path
import contextlib
import json
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
wire = sys.stdout
with contextlib.redirect_stdout(sys.stderr):
    from local_asset_library.config import load_config
    from local_asset_library.embedding_backend import EmbeddingBackend
    from local_asset_library.mcp_assets import AssetService, error_payload
    config = load_config(root / 'config.example.toml', root)
    service = AssetService(config, backend_factory=EmbeddingBackend)
for line in sys.stdin:
    try:
        with contextlib.redirect_stdout(sys.stderr):
            request = json.loads(line)
            payload, image, evidence = service.execute(request['name'], request['arguments'])
        result = dict(payload=payload, image=image, evidence=evidence, is_error=False)
    except Exception as exc:
        result = dict(payload=error_payload(exc), image=None, evidence={'fault':str(exc)}, is_error=True)
    wire.write(json.dumps(result, separators=(',', ':'), ensure_ascii=False) + '\n')
    wire.flush()
