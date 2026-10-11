"""Run only the established pilot; generation uses the isolated runtime."""
import argparse
from pathlib import Path
import json

from local_asset_library.catalog import detail, save_json
from local_asset_library.config import load_config
from local_asset_library.caption_backend import QwenBackend
from local_asset_library.captions import image_inputs, run_batch, review_artifact, publish
from local_asset_library.inspection import load_pilot
from local_asset_library.caption_review import highlight_faults

parser = argparse.ArgumentParser()
parser.add_argument("command", choices=["smoke", "calibration", "pilot", "review"])
parser.add_argument("--prompt-version", choices=["v1", "v2"], default="v1")
parser.add_argument("--retry-faults", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
config = load_config(root / "config.example.toml", root)
if args.command == "review":
    assets = load_pilot(config)["assets"]
    for asset in assets:
        record = detail(config, asset["asset_id"])
        if record.get("caption_provenance"):
            publish(config, asset["asset_id"], {"status": record["processing"]["caption"],
                    "description": record["description"], "suggested_uses": record.get("suggested_uses", [])}, record["caption_provenance"])
    print(highlight_faults(config, review_artifact(config, assets, "pilot-" + args.prompt_version), assets))
    raise SystemExit(0)
contract = json.loads((root / "docs/caption-model.json").read_text(encoding="utf-8"))
backend = QwenBackend(config, contract)
try:
    if args.command == "smoke":
        assets = load_pilot(config)["assets"]
        cases = []
        for index in (0, 10):
            inputs = image_inputs(config, detail(config, assets[index]["asset_id"]))
            answer, metrics = backend.generate(inputs, "What object is shown in these views? State its main body color and two visible parts in one sentence. Describe pixels only.", 128)
            cases.append({"asset_id": assets[index]["asset_id"], "inputs": inputs, "answer": answer, "metrics": metrics})
        report = {"model": backend.contract, "settings": backend.settings, "cases": cases,
                  "resources": backend.resources(), "comprehension_review": "pending"}
        save_json(config.output_path("data", "captions/smoke.json"), report)
        print(json.dumps(report, indent=2))
    else:
        report = run_batch(config, backend, args.command, args.prompt_version, args.retry_faults)
        from local_asset_library.captions import CALIBRATION_INDICES
        assets = load_pilot(config)["assets"]
        if args.command == "calibration":
            assets = [assets[i] for i in CALIBRATION_INDICES]
        highlight_faults(config, config.output_path("data", f"captions/review/{args.command}-{args.prompt_version}.html"), assets)
        print(json.dumps({k: v for k, v in report.items() if k != "outcomes"}))
        save_json(config.output_path("data", f"captions/{args.command}-{args.prompt_version}-resources.json"), backend.resources())
finally:
    backend.close()
