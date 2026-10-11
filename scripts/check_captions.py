"""Measured catalog invariants before/after local caption inference."""
from contextlib import closing
from pathlib import Path
import json
import sys

from local_asset_library.config import load_config
from local_asset_library.catalog import read_database, save_json, digest
from local_asset_library.captions import image_inputs, validate_caption, overlay_for, effective_caption

root = Path(__file__).resolve().parents[1]
config = load_config(root / "config.example.toml", root)
with closing(read_database(config)) as db:
    records = [json.loads(row[0]) for row in db.execute("SELECT record FROM assets ORDER BY asset_id")]
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    foreign = db.execute("PRAGMA foreign_key_check").fetchall()
    fts = db.execute("SELECT count(*) FROM asset_fts").fetchone()[0]
modifiable = {"description", "suggested_uses", "caption_provenance", "owner_overlay", "effective_caption"}
def unchanged(record):
    result = {k: v for k, v in record.items() if k not in modifiable and k != "processing"}
    result["processing"] = {k: v for k, v in record["processing"].items() if k != "caption"}
    return digest(result)
baseline_path = config.output_path("data", "evidence/step4-catalog-before.json")
if "--before" in sys.argv:
    assert not baseline_path.exists(), "Do not overwrite original baseline"
    save_json(baseline_path, {r["asset_id"]: unchanged(r) for r in records})
    print("Saved 883-record immutable-field baseline")
    raise SystemExit(0)
baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
assert {r["asset_id"]: unchanged(r) for r in records} == baseline
complete = [r for r in records if r["processing"]["caption"] == "complete"]
failed = [r for r in records if r["processing"]["caption"] in {"failed", "unsupported"}]
pilot = json.loads(config.output_path("data", "pilot/selection-manifest.json").read_text(encoding="utf-8"))
pilot_ids = {a["asset_id"] for a in pilot["assets"]}
assert len(complete) + len(failed) == 40
assert {r["asset_id"] for r in complete + failed} == pilot_ids
views = 0
for record in complete:
    validate_caption({**record["description"], "suggested_uses": record["suggested_uses"]})
    inputs = image_inputs(config, record)
    views += len(inputs)
    assert inputs == record["caption_provenance"]["input_views"]
    assert record["caption_provenance"]["owner_caption_review"] == "pending"
    assert record["caption_provenance"]["owner_artistic_suitability"] == "pending"
    overlay, _ = overlay_for(config, record)
    assert effective_caption(record, overlay) == record["effective_caption"]
    original = json.loads(config.output_path("data", record["caption_provenance"]["result_path"][5:]).read_text(encoding="utf-8"))
    assert record["description"] == original["description"], "UTF-8 canonical response changed"
    for attempt in record["caption_provenance"]["attempts"]:
        if attempt["status"] == "complete":
            assert len(attempt["metrics"]["image_grid_thw"]) == len(inputs)
            assert attempt["metrics"]["image_tokens"] > 0
for record in failed:
    assert record["description"] is None
    if record["caption_provenance"]["input_views"]:
        inputs = image_inputs(config, record)
        assert inputs == record["caption_provenance"]["input_views"]
        views += len(inputs)
        for attempt in record["caption_provenance"]["attempts"]:
            if "metrics" in attempt:
                assert len(attempt["metrics"]["image_grid_thw"]) == len(inputs)
                assert attempt["metrics"]["image_tokens"] > 0
assert integrity == "ok" and not foreign and fts == 883
assert all(not r["embeddings"] for r in records)
report = {"catalog_records": len(records), "caption_complete": len(complete), "caption_failed": len(failed),
          "verified_input_views": views, "untouched_nonpilot_records": len(records)-40,
          "preserved_all_noncaption_fields": True, "integrity": integrity, "foreign_key_errors": foreign,
          "fts_rows": fts, "embeddings": "not_started", "owner_reviews": "pending",
          "canonical_utf8_captions_preserved": True}
save_json(config.output_path("data", "evidence/step4-catalog-check.json"), report)
print(json.dumps(report))
