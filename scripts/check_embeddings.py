"""Read-only catalog/source preservation, persisted vectors, ranks, size and budget evidence."""
from contextlib import closing
from pathlib import Path
import json
import sqlite3

import numpy as np

from local_asset_library.catalog import digest, encoded, save_json
from local_asset_library.captions import file_hash
from local_asset_library.config import load_config
from local_asset_library.retrieval import checked_vector, index_database, pilot_records, resolved_detail

root = Path(__file__).resolve().parents[1]
config = load_config(root / "config.example.toml", root)
with closing(index_database(config, True)) as db:
    meta = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM meta")}
    rows = db.execute("SELECT * FROM vectors").fetchall()
    vectors = np.stack([checked_vector(row, meta["contract_fingerprint"]) for row in rows])
    assert digest(meta["contract"]) == meta["contract_fingerprint"]
    faults = [{"asset_id": a, "channel": c, "evidence": json.loads(e)} for a, c, e in db.execute("SELECT asset_id,channel,evidence FROM jobs WHERE status='failed'")]
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not db.execute("PRAGMA foreign_key_check").fetchall()
ids = {r["asset_id"] for r in pilot_records(config)}
assert {r[1] for r in rows}.issubset(ids) and len(ids) == 40
with sqlite3.connect(config.output_path("data", "catalog.sqlite")) as db:
    catalog_records = [json.loads(r[0]) for r in db.execute("SELECT record FROM assets")]
    assert len(catalog_records) == 883 and not any(r["embeddings"] for r in catalog_records)
    assert db.execute("SELECT count(*) FROM asset_fts").fetchone()[0] == 883
for path in config.output_path("data", "embeddings/demos").glob("*.json"):
    result = json.loads(path.read_text(encoding="utf-8"))
    response = result["response"]
    assert response["serialized_characters"] == len(encoded(response)) <= 6000
    assert len({r["asset_id"] for r in response["results"]}) == len(response["results"])
    for ranking in result["channel_rankings"].values():
        assert len({r["asset_id"] for r in ranking}) == len(ranking)
        assert all(r["asset_id"] in ids for r in ranking)
    for candidate in response["results"]:
        resolved_detail(config, candidate["asset_id"])
area_bytes = {area: sum(p.stat().st_size for p in (root / area).rglob("*") if p.is_file())
              for area in ("models", "data", "cache", "logs", "scratch", ".venv", ".venv-caption", ".venv-embedding")}
model_budget = 8 * 1024**3
generated_budget = 20 * 1024**3
generated = sum(v for k, v in area_bytes.items() if k != "models")
assert area_bytes["models"] < model_budget and generated < generated_budget
report = {"contract_fingerprint": meta["contract_fingerprint"], "contract": meta["contract"],
          "finite_normalized_vectors": len(rows), "dimensions": vectors.shape[1],
          "norm_min_max": [float(np.linalg.norm(vectors, axis=1).min()), float(np.linalg.norm(vectors, axis=1).max())],
          "description_vectors": sum(r[2] == "description" for r in rows), "image_vectors": sum(r[2] == "image" for r in rows),
          "logical_assets_indexed": len({r[1] for r in rows}), "faults": faults,
          "catalog_records": len(catalog_records), "fts_rows": 883, "pilot_manifest_sha256": file_hash(config.output_path("data", "pilot/selection-manifest.json")),
          "area_bytes": area_bytes, "total_managed_bytes": sum(area_bytes.values()),
          "model_budget_remaining_bytes": model_budget - area_bytes["models"],
          "generated_budget_remaining_bytes": generated_budget - generated,
          "method": "Regular-file logical sizes, counting cache/runtime copies conservatively; not disk blocks or compressed usage."}
save_json(config.output_path("data", "embeddings/verification.json"), report)
print(json.dumps({k: v for k, v in report.items() if k not in {"contract", "faults"}}))
