"""Fresh storage-change verification receipts; preserve prior asset evidence."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from local_asset_library import hash_cache; hash_cache.require_fresh()  # Byte audit: never reuse recorded hashes (decision 0004).
from local_asset_library.catalog import save_json, query, verify_source
from local_asset_library.captions import file_hash
from local_asset_library.config import load_config


def snapshot():
    paths = ["data/catalog.sqlite", "data/embeddings/index.sqlite", "data/pilot/selection-manifest.json",
             "runtime/caption/uv.lock", "runtime/embedding/uv.lock", "runtime/mcp/uv.lock", "uv.lock"]
    return {name: file_hash(ROOT / name) for name in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["snapshot", "base", "caption", "embedding", "preview"])
    parser.add_argument("--run-name", default="", help="New receipt suffix for a changed verification context")
    args = parser.parse_args()
    mode = args.mode
    if args.run_name and (not args.run_name.isascii() or not args.run_name.replace("-", "").isalnum()):
        parser.error("Run name must contain only ASCII letters, digits and hyphens")
    config = load_config(ROOT / "config.example.toml", ROOT)
    suffix = "-" + args.run_name if args.run_name else ""
    target = config.output_path("data", f"storage/{mode}{suffix}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump({"status": "running", "mode": mode}, stream)
    report = {"mode": mode, "status": "running"}
    try:
        if mode == "snapshot":
            report["hashes"] = snapshot()
        elif mode == "base":
            report["source"] = verify_source(config)
            result = query(config, "apple", 5)
            assert result
            report["keyword_results"] = len(result)
            expected = json.loads((ROOT / "data/storage/snapshot.json").read_text())["hashes"]
            assert snapshot() == expected, "Catalog, index, pilot or dependency locks changed"
            report["preserved_hashes"] = expected
        elif mode == "caption":
            from local_asset_library.caption_backend import QwenBackend
            contract = json.loads((ROOT / "docs/caption-model.json").read_text())
            backend = QwenBackend(config, contract)
            try:
                manifest = json.loads(config.output_path("data", "inspection/processed-manifest.json").read_text())
                view = (ROOT / manifest["assets"][0]["result_path"]).parent / "three_quarter.png"
                text, metrics = backend.generate([{"path": view.relative_to(ROOT).as_posix(),
                    "sha256": file_hash(view), "view_label": "three_quarter"}],
                    "Describe the visible object in one short sentence.", max_new_tokens=128)
                assert text.strip() and metrics["image_tokens"] > 0
                report.update(text=text, metrics=metrics, model_weights_verified=True)
            finally:
                backend.close()
        elif mode == "preview":
            from local_asset_library.mcp_assets import AssetService
            from local_asset_library.retrieval import pilot_records
            record = pilot_records(config)[0]
            payload, image, _ = AssetService(config).execute("get_asset", {
                "asset_id": record["asset_id"], "include_preview": True, "include_metadata": True})
            assert image and payload["selected_source"]
            blob = base64.b64decode(image, validate=True)
            assert hashlib.sha256(blob).hexdigest() == payload["preview"]["sha256"]
            report.update(preview=payload["preview"], source=payload["selected_source"], image_bytes=len(blob))
        else:
            from local_asset_library.embedding_backend import EmbeddingBackend
            from local_asset_library.mcp_assets import AssetService
            from local_asset_library.retrieval import SearchEngine, pilot_records, preview_file
            backend = EmbeddingBackend(config)
            engine = SearchEngine(config, backend)
            checks = []
            report["checks"] = checks
            for channel in ("description", "image", "keyword_description", "combined"):
                result, evidence = engine.search("a small red apple with a leaf", channel)
                assert result["results"]
                assert evidence["query_metrics"]["finite"]
                checks.append({"mode": channel, "results": len(result["results"]),
                               "query_metrics": evidence["query_metrics"]})
                save_json(target, report)
            record = pilot_records(config)[0]
            preview = next(p for p in record["previews"] if p["view_label"] == "three_quarter")
            view = preview_file(config, preview)
            vector = backend.image(view)
            assert len(vector) == 768 and backend.last_metrics["pixel_tensor_shapes"]
            checks.append({"mode": "actual_image_embedding", "metrics": backend.last_metrics})
            result, evidence = engine.search("", "reference", view.relative_to(ROOT).as_posix())
            assert result["results"] and evidence["query_metrics"]["modality"] == "image"
            checks.append({"mode": "reference", "results": len(result["results"]),
                           "query_metrics": evidence["query_metrics"]})
            payload, image, _ = AssetService(config).execute("get_asset", {
                "asset_id": record["asset_id"], "include_preview": True, "include_metadata": True})
            assert image and payload["selected_source"]
            assert hashlib.sha256(base64.b64decode(image, validate=True)).hexdigest() == payload["preview"]["sha256"]
            report.update(preview=payload["preview"], source=payload["selected_source"],
                          contract_fingerprint=backend.fingerprint, resources=backend.resources(),
                          model_weights_verified=True)
        report["status"] = "passed"
    except Exception as exc:
        report.update(status="faulty", reason=str(exc), traceback=traceback.format_exc())
    save_json(target, report)
    print(json.dumps(report, indent=2))
    return report["status"] != "passed"


if __name__ == "__main__":
    sys.exit(main())
