"""Read-only pilot classification/parity and protected-input verification; no model runs."""
import argparse
from collections import Counter
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from local_asset_library.caption_quality import caption_quality, caption_summary
from local_asset_library.config import load_project_config
from local_asset_library.desktop_service import DesktopService
from local_asset_library.mcp_assets import AssetService
from local_asset_library.retrieval import pilot_records
from local_asset_library.captions import file_hash


def protected():
    paths = [ROOT / p for p in ("data/catalog.sqlite", "data/embeddings/index.sqlite",
             "data/pilot/selection-manifest.json", "docs/caption-pilot-review.json",
             "docs/caption-contract.md", "uv.lock", "runtime/mcp/uv.lock",
             "runtime/caption/uv.lock", "runtime/embedding/uv.lock")]
    for folder in ("data/captions", "data/inspection", "docs/evaluation"):
        paths.extend(p for p in (ROOT / folder).rglob("*") if p.is_file())
    return {p.relative_to(ROOT).as_posix(): file_hash(p) for p in paths}


def keyword_rankings(service, records):
    return {r["asset_id"]: [(item["asset_id"], item["score"], item["matching_channels"])
                           for item in service.execute("search_assets", {"query": r["display_name"], "mode": "keyword"})[0]["results"]]
            for r in records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["before", "after"])
    args = parser.parse_args()
    folder = ROOT / "data/caption-classification"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (args.mode + ".json")
    config = load_project_config(ROOT)
    records = pilot_records(config)
    service = AssetService(config)
    report = {"status": "running", "protected": protected(), "rankings": keyword_rankings(service, records)}
    # Create the receipt before verification; keep failure evidence if a check fails.
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream)
    try:
        if args.mode == "after":
            before = json.loads((folder / "before.json").read_text(encoding="utf-8"))
            assert report["protected"] == before["protected"], "Protected inputs changed"
            assert json.loads(json.dumps(report["rankings"])) == before["rankings"], "Keyword ranking changed"
            desktop = DesktopService(config)
            browse = {i["asset_id"]: i for i in desktop.browse()["items"]}
            summaries = {}
            for record in records:
                identifier = record["asset_id"]
                quality = caption_quality(config, record)
                assert quality["classification"] in {"classified", "no_findings"}
                summary = caption_summary(config, record)
                payload, _, _ = service.execute("get_asset", {"asset_id": identifier, "include_metadata": True})
                ui = desktop.asset(identifier)["payload"]["presentation"]
                for response in (browse[identifier], payload, ui):
                    assert all(response[key] == value for key, value in summary.items())
                assert payload["metadata"]["caption_quality"] == ui["caption_quality"] == quality
                assert payload["metadata"]["caption_fault_evidence"] == (record.get("caption_provenance") or {}).get("visual_faults", [])
                search, _, _ = service.execute("search_assets", {"query": record["display_name"], "mode": "keyword"})
                for candidate in search["results"]:
                    expected = caption_summary(config, service.record(candidate["asset_id"]))
                    assert all(candidate[k] == v for k, v in expected.items())
                summaries[identifier] = {"name": record["display_name"], **summary}
            report.update(counts=dict(Counter(s["caption_status"] for s in summaries.values())), assets=summaries,
                          protected_count=len(report["protected"]), model_loaded=False,
                          checks=["All 40 browse/detail/MCP classifications agree", "Keyword candidate classification agrees",
                                  "All 40 keyword query rankings unchanged", "Original caption/review/catalog/index hashes unchanged"])
        report["status"] = "passed"
    except Exception as exc:
        report.update(status="faulty", reason=str(exc))
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"protected", "rankings", "assets"}}, indent=2))
    return report["status"] != "passed"


if __name__ == "__main__":
    sys.exit(main())
