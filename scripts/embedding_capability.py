"""Real pilot pixels and text, not endpoint/model-load-only verification."""
from pathlib import Path
import json
import numpy as np
from local_asset_library.config import load_config
from local_asset_library.catalog import detail, save_json
from local_asset_library.embedding_backend import EmbeddingBackend
from local_asset_library.captions import file_hash

root = Path(__file__).resolve().parents[1]
config = load_config(root / "config.example.toml", root)
backend = EmbeddingBackend(config)
ids = ["asset_bb8f82724d7856f4fa86b9f0759f2791", "asset_24e2752dbb26ecd19677091f78243709"]
image_vectors, text_vectors, metrics = [], [], []
inputs = []
for identifier, text in zip(ids, ("a boxy orange-red car with wheels", "a red apple with a green leaf")):
    record = detail(config, identifier)
    view = next(p for p in record["previews"] if p.get("origin") == "rendered" and p["view_label"] == "three_quarter")
    path = config.output_path("data", view["path"][5:])
    assert file_hash(path) == view["sha256"]
    image_vectors.append(backend.image(path))
    metrics.append(dict(backend.last_metrics))
    text_vectors.append(backend.text(text))
    metrics.append(dict(backend.last_metrics))
    inputs.append({"asset_id": identifier, "path": view["path"], "sha256": view["sha256"], "query": text})
document = backend.text("A red apple with a green leaf and short stem.", role="document")
metrics.append(dict(backend.last_metrics))
assert not np.allclose(image_vectors[0], image_vectors[1])
assert not np.allclose(text_vectors[0], text_vectors[1])
report = {"contract": backend.contract, "contract_fingerprint": backend.fingerprint, "inputs": inputs,
          "actual_text_and_image_inference": True, "reference_image_query_support": True,
          "text_image_similarities": (np.array(text_vectors) @ np.array(image_vectors).T).tolist(),
          "image_image_similarities": (np.array(image_vectors) @ np.array(image_vectors).T).tolist(),
          "document_norm": float(np.linalg.norm(document)), "metrics": metrics, "resources": backend.resources(),
          "limitation": "Capability proof using two real assets; no human relevance or benchmark verdict."}
save_json(config.output_path("data", "embeddings/capability.json"), report)
print(json.dumps({k: v for k, v in report.items() if k != "contract"}))
