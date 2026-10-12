"""Record only AI technical review, bound to viewed results and image hashes."""
import argparse
from pathlib import Path
import json
from datetime import datetime, timezone

from local_asset_library.config import load_config
from local_asset_library.catalog import detail, encoded, save_json
from local_asset_library.captions import file_hash, publish
from local_asset_library.caption_quality import review_findings

parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=["calibration-v1", "calibration-v2", "pilot-v2"])
parser.add_argument("--notes", type=Path, required=True)
parser.add_argument("--approve-prompt", choices=["v2"])
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
config = load_config(root / "config.example.toml", root)
report_path = config.output_path("data", f"captions/{args.phase}-report.json")
report = json.loads(report_path.read_text(encoding="utf-8"))
notes = json.loads(args.notes.read_text(encoding="utf-8"))
assert set(notes["assets"]) == {o["asset_id"] for o in report["outcomes"]}
receipts = []
for outcome in report["outcomes"]:
    record = detail(config, outcome["asset_id"])
    result_path = config.output_path("data", f"captions/{args.phase}/{outcome['asset_id']}.json")
    if not result_path.exists():
        result_path = config.output_path("data", record["caption_provenance"]["result_path"][5:])
    result = json.loads(result_path.read_text(encoding="utf-8"))
    for view in result["provenance"]["input_views"]:
        assert file_hash(config.output_path("data", view["path"][5:])) == view["sha256"]
    receipts.append({"asset_id": outcome["asset_id"], "result_sha256": file_hash(result_path),
                     "caption_fingerprint": result["provenance"]["fingerprint"],
                     "input_views": result["provenance"]["input_views"], "observations": notes["assets"][outcome["asset_id"]]})
    if record["caption_provenance"]["fingerprint"] == result["provenance"]["fingerprint"]:
        note = notes["assets"][outcome["asset_id"]]
        findings = review_findings(note)
        provenance = {**record["caption_provenance"], "ai_review": "technically_reviewed",
                      "ai_review_observations": notes["assets"][outcome["asset_id"]],
                      "visual_faults": findings,
                      "ai_review_scope": notes["scope"]}
        # Original UTF-8 model result is canonical, including cached phase results.
        publish(config, outcome["asset_id"], result, provenance)
receipt = {"status": "technically_reviewed", "reviewer": "Codex AI; not Bruno approval",
           "utc": datetime.now(timezone.utc).isoformat(), "scope": notes["scope"],
           "report_sha256": file_hash(report_path), "receipts": receipts,
           "owner_caption_review": "pending", "owner_artistic_suitability": "pending"}
if args.approve_prompt:
    assert args.phase == "calibration-v2"
    receipt["approved_prompt_sha256"] = file_hash(root / f"prompts/caption-{args.approve_prompt}.txt")
    save_json(config.output_path("data", "captions/calibration-review.json"), receipt)
save_json(config.output_path("data", f"captions/{args.phase}-review.json"), receipt)
print(json.dumps({"status": receipt["status"], "assets": len(receipts), "owner_reviews": "pending"}))
