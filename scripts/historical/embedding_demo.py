"""Small real demonstrations and timing measurements; no benchmark labels/verdict."""
from pathlib import Path
import json
import time

from local_asset_library.catalog import save_json, detail, encoded
from local_asset_library.config import load_project_config
from local_asset_library.embedding_backend import EmbeddingBackend
from local_asset_library.retrieval import SearchEngine, index_pilot, resolved_detail

started = time.perf_counter()
root = Path(__file__).resolve().parents[2]
config = load_project_config(root)
backend = EmbeddingBackend(config)
engine = SearchEngine(config, backend)
index = index_pilot(config, backend)
save_json(config.output_path("data", "embeddings/first-index-report.json"), index)
reference = next(p["path"] for p in detail(config, "asset_24e2752dbb26ecd19677091f78243709")["previews"]
                 if p.get("origin") == "rendered" and p["view_label"] == "three_quarter")
queries = [
    ("keyword", "apple", None, {}, None),
    ("description", "a boxy orange-red car with wheels", None, {}, None),
    ("image", "a red apple with a green leaf", None, {}, None),
    ("combined", "a chair with a curved back and flat seat", None, {}, None),
    ("reference", "", reference, {}, None),
    ("combined", "a car with wheels", None, {"pack": "kenney_car-kit", "format": "glb", "max_triangles": 3000, "rigged": False}, None),
    ("keyword", "spaceship laser submarine", None, {}, None),
    ("combined", "a realistic purple dragon breathing fire", None, {}, None),
    ("image", "a realistic purple dragon breathing fire", None, {}, 0.95),
]
demonstrations = []
for i, (mode, text, ref, filters, floor) in enumerate(queries):
    runs = []
    for temperature in ("first_query_after_index", "warm_repeat"):
        response, evidence = engine.search(text, mode, ref, filters, min_similarity=floor)
        assert response["serialized_characters"] == len(encoded(response)) <= 6000
        evidence["timing_state"] = temperature
        save_json(config.output_path("data", f"embeddings/demos/{i:02}-{mode}-{temperature}.json"), evidence)
        runs.append({"state": temperature, "seconds": evidence["elapsed_seconds"],
                     "serialized_characters": response["serialized_characters"], "estimated_tokens": response["estimated_tokens"],
                     "status": response["status"], "names": [r["name"] for r in response["results"]],
                     "result_asset_ids": [r["asset_id"] for r in response["results"]]})
    demonstrations.append({"mode": mode, "query": text or ref, "filters": filters, "evaluation_floor": floor, "runs": runs})
resolved = resolved_detail(config, "asset_24e2752dbb26ecd19677091f78243709", "fbx")
save_json(config.output_path("data", "embeddings/demo-detail.json"), resolved)
calls_before = backend.last_metrics
reused = index_pilot(config, backend)
assert all(o.get("reused") or o["status"] == "failed" for o in reused["outcomes"])
report = {"contract_fingerprint": backend.fingerprint, "resources": backend.resources(),
          "first_index": {k: v for k, v in index.items() if k != "outcomes"},
          "unchanged_reindex": {k: v for k, v in reused.items() if k != "outcomes"},
          "demonstrations": demonstrations, "total_seconds": time.perf_counter() - started,
          "limitations": ["First queries follow indexing, so are not process/model-cold; separate CLI cold measurements required.",
                          "No benchmark verdict, human judgments or full indexing.", "Token sizes are character-based estimates."]}
save_json(config.output_path("data", "embeddings/demonstrations.json"), report)
print(json.dumps(report))
