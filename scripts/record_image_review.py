"""Record a technical image review AFTER opening the generated sheet/images."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from local_asset_library.catalog import detail, encoded, file_hash, save_json
from local_asset_library.config import load_project_config


def main():
    parser = argparse.ArgumentParser(description="Run only after reviewing images with an image-viewing tool")
    parser.add_argument("phase", choices=["representatives", "pilot"])
    parser.add_argument("--observations", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = load_project_config(root)
    report_path = config.output_path("data", f"inspection/{args.phase}-report.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    sheet = config.output_path("data", f"inspection/review/{args.phase}.png")
    with sheet.open("rb") as stream:
        sheet_hash = file_hash(stream)
    evidence_relative = f"inspection/review/{args.phase}-review.json"
    reviewed = []
    records = []
    for outcome in report["outcomes"]:
        if outcome["status"] != "complete":
            continue
        record = detail(config, outcome["asset_id"])
        previews = [p for p in record["previews"] if p.get("origin") == "rendered"]
        reviewed.append({"asset_id": record["asset_id"], "inspection_fingerprint": record["inspection_run"]["fingerprint"],
                         "views": [{"path": p["path"], "sha256": p["sha256"], "label": p["view_label"]} for p in previews]})
        for preview in previews:
            path = config.output_path("data", preview["path"].removeprefix("data/"))
            with path.open("rb") as stream:
                assert file_hash(stream) == preview["sha256"]
            preview["visual_review"] = {"technical": "passed", "evidence": "data/" + evidence_relative,
                                        "scope": "all three representative views" if args.phase == "representatives" else "three-quarter sheet plus automated checks for other views",
                                        "owner_artistic_approval": "pending"}
        records.append(record)
    if args.phase == "representatives":
        assert len(reviewed) == 4 and report["failed"] == 0
    review = {"status": "technical_pass", "reviewed_by": "Codex image-viewing tools",
              "phase": args.phase, "sheet": sheet.relative_to(root).as_posix(), "sheet_sha256": sheet_hash,
              "observations": args.observations, "assets": reviewed,
              "owner_artistic_approval": "pending", "caption_generation": "not_started"}
    save_json(config.output_path("data", evidence_relative), review)
    with closing(sqlite3.connect(config.output_path("data", "catalog.sqlite"))) as db, db:
        for record in records:
            db.execute("UPDATE assets SET record=? WHERE asset_id=?", (encoded(record), record["asset_id"]))
    report["visual_review"] = "technical_pass; owner artistic approval pending"
    report["visual_review_evidence"] = "data/" + evidence_relative
    save_json(report_path, report)
    print(json.dumps({"review": "data/" + evidence_relative, "assets": len(reviewed), "owner_artistic_approval": "pending"}))


if __name__ == "__main__":
    main()
