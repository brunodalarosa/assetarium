"""Check the real pilot's stored evidence without importing or changing sources."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

from local_asset_library.catalog import detail, query, save_json
from local_asset_library.config import load_project_config


def main():
    root = Path(__file__).resolve().parents[2]
    config = load_project_config(root)
    manifest_path = config.output_path("data", "pilot/selection-manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == "844d495098a7442e481ac2a3b703f312f38804460d15d353e0a9b116f0f75459"
    records = [detail(config, asset["asset_id"]) for asset in manifest["assets"]]
    assert len(records) == 40 and len({r["asset_id"] for r in records}) == 40
    views = []
    for record in records:
        assert record["inspection_run"]["status"] == "complete"
        assert record["technical"]["inspected_path"] == record["primary_inspection_path"]
        assert record["technical"]["autoexec_enabled"] is False
        previews = [p for p in record["previews"] if p.get("origin") == "rendered"]
        assert {"front", "side", "three_quarter"} <= {p["view_label"] for p in previews}
        for preview in previews:
            path = config.output_path("data", preview["path"].removeprefix("data/"))
            assert hashlib.sha256(path.read_bytes()).hexdigest() == preview["sha256"]
            assert not preview["quality"]["empty"] and not preview["quality"]["off_frame"]
            assert preview["visual_review"]["technical"] == "passed"
        views.extend(previews)
    before = json.loads(config.output_path("data", "evidence/step3-pilot-before.json").read_text(encoding="utf-8"))
    after = json.loads(config.output_path("data", "evidence/step3-pilot-after.json").read_text(encoding="utf-8"))
    before_map = {item["path"]: item for item in before}
    after_map = {item["path"]: item for item in after}
    assert all(after_map[path] == item for path, item in before_map.items())
    assert all(item["matches_catalog"] for item in after)
    with sqlite3.connect(config.output_path("data", "catalog.sqlite")) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        all_records = [json.loads(row[0]) for row in db.execute("SELECT record FROM assets")]
        assert len(all_records) == 883
        assert all(r["description"] is None and not r["embeddings"] for r in all_records)
        assert sum(r["technical"] is not None for r in all_records) == 40
        assert db.execute("SELECT count(*) FROM asset_fts").fetchone()[0] == 883
    examples = []
    for name, pack in [("sedan", "kenney_car-kit"), ("sedan-sports", "kenney_car-kit"), ("apple", "kenney_food-kit"), ("BirchTree_1", "quaternius_ultimate-nature-pack")]:
        record = next(r for r in records if r["display_name"] == name and r["pack_id"] == pack)
        technical = record["technical"]
        examples.append({"name": name, "format": technical["inspected_format"], "objects": technical["object_count"],
                         "mesh_objects": technical["mesh_object_count"], "geometry": technical["evaluated_instance_totals"],
                         "world_bounds": technical["world_bounds"], "units": technical["units"],
                         "materials": len(technical["materials"]), "armatures": len(technical["armatures"]),
                         "actions": len(technical["animation_clips"])})
    searches = {terms: query(config, terms, 5) for terms in ("Apple Green", "BirchTree Snow", "chair rounded")}
    assert all(searches.values())
    report = {"pilot_assets": len(records), "rendered_views": len(views), "source_files_verified": len(after),
              "faulty_assets": [{"asset_id": r["asset_id"], "name": r["display_name"],
                                  "faults": r["inspection_run"]["source_faults"]}
                                 for r in records if r["inspection_run"]["source_faults"]],
              "formats": dict(Counter(r["technical"]["inspected_format"] for r in records)),
              "views": dict(Counter(p["view_label"] for p in views)), "metadata_examples": examples,
              "keyword_searches": searches, "sqlite_integrity": "ok", "catalog_records": 883,
              "caption_and_embeddings": "not_started", "unchanged_pilot_manifest": True}
    save_json(config.output_path("data", "evidence/step3-catalog-check.json"), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
