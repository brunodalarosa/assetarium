"""Summarize real inference and project byte accounting, not estimates."""
from pathlib import Path
import json
import statistics
import math

from local_asset_library.catalog import save_json
from local_asset_library.catalog import detail
from local_asset_library.config import load_config
from local_asset_library.model_storage import project_model_bytes

root = Path(__file__).resolve().parents[1]
config = load_config(root / "config.example.toml", root)
report = json.loads((root / "data/captions/pilot-v2-report.json").read_text(encoding="utf-8"))
attempts = [a for o in report["outcomes"] for a in o["attempts"] if "metrics" in a]
times = [a["metrics"]["elapsed_seconds"] for a in attempts]
resources = json.loads((root / "data/captions/pilot-v2-resources.json").read_text(encoding="utf-8"))
sizes = {}
for name in ("models", "data", "cache", "scratch", "logs", ".venv", ".venv-caption"):
    path = root / name
    sizes[name] = sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0
sizes["models"] = project_model_bytes(config)
generation = [o for o in report["outcomes"] if not o["cached"]]
records = [detail(config, o["asset_id"]) for o in report["outcomes"]]
summary = {"pilot_complete": report["complete"], "pilot_failed": report["failed"],
    "pilot_batch_seconds": report["elapsed_seconds"], "reused_calibration_assets": len(report["outcomes"])-len(generation),
    "new_pilot_assets": len(generation), "pilot_total_inference_attempts_including_calibration": len(attempts),
    "assets_requiring_corrective_response": sum(len(o["attempts"])>1 for o in report["outcomes"]),
    "inference_seconds_all_pilot_attempts_including_calibration": sum(times),
    "inference_p50_seconds": statistics.median(times),
    "inference_p95_seconds_nearest_rank": sorted(times)[math.ceil(0.95*len(times))-1],
    "schema_valid_description_words_range": [min(len(r["description"]["description"].split()) for r in records if r["description"]), max(len(r["description"]["description"].split()) for r in records if r["description"])],
    "visual_review_faulty_assets": sum(bool(r["caption_provenance"].get("visual_faults")) for r in records),
    "input_tokens_range": [min(a["metrics"]["input_tokens"] for a in attempts), max(a["metrics"]["input_tokens"] for a in attempts)],
    "image_tokens_range": [min(a["metrics"]["image_tokens"] for a in attempts), max(a["metrics"]["image_tokens"] for a in attempts)],
    "resources_pilot_process": resources, "area_bytes": sizes,
    "total_project_managed_bytes": sum(sizes.values()),
    "model_download_budget_remaining_bytes": 8589934592-sizes["models"],
    "model_budget_accounting": "This project's two pinned revisions in configured model storage; other projects and revisions excluded",
    "generated_project_budget_remaining_bytes_conservative": 21474836480-sum(v for k,v in sizes.items() if k!="models"),
    "byte_count_method": "sum regular file logical sizes, including separate installed-runtime/cache copies; no blocks/compression estimate"}
save_json(config.output_path("data", "captions/measurements.json"), summary)
print(json.dumps(summary, indent=2))
