"""New isolated relocation smoke checks; never rewrite existing inference evidence."""
from pathlib import Path
import json
import sys
import traceback

from local_asset_library.config import load_project_config
from local_asset_library.captions import file_hash
from local_asset_library.catalog import save_json

root = Path(__file__).resolve().parents[1]
from local_asset_library import hash_cache; hash_cache.require_fresh()  # Byte audit: never reuse recorded hashes (decision 0004).
config = load_project_config(root)
mode = sys.argv[1]
report = {"mode": mode, "models_root": str(config.storage_root("models")), "status": "running"}
target = config.output_path("data", "model-relocation/" + mode + ".json")
if target.exists():
    raise RuntimeError("Existing smoke evidence retained; no automatic retry")
save_json(target, report)
try:
    if mode == "embedding":
        from local_asset_library.embedding_backend import EmbeddingBackend
        from local_asset_library.retrieval import SearchEngine
        backend = EmbeddingBackend(config)
        result, evidence = SearchEngine(config, backend).search("a small red apple with a leaf", "keyword_description")
        assert result["results"]
        from local_asset_library.mcp_assets import AssetService
        payload, image, detail_evidence = AssetService(config).execute("get_asset", {
            "asset_id": result["results"][0]["asset_id"], "include_preview": True, "include_metadata": True})
        assert image and payload["selected_source"]
        report.update(search=result, preview=payload["preview"], source=payload["selected_source"],
                      contract_fingerprint=backend.fingerprint, resources=backend.resources())
    elif mode == "caption":
        from local_asset_library.caption_backend import QwenBackend
        contract = json.loads((root / "docs/caption-model.json").read_text(encoding="utf-8"))
        backend = QwenBackend(config, contract)
        try:
            manifest = json.loads(config.output_path("data", "inspection/processed-manifest.json").read_text(encoding="utf-8"))
            inspected = root / manifest["assets"][0]["result_path"]
            view = inspected.parent / "three_quarter.png"
            text, metrics = backend.generate([{"path": view.relative_to(root).as_posix(),
                "sha256": file_hash(view), "view_label": "three_quarter"}],
                "Describe the visible object in one short sentence.", max_new_tokens=128)
            assert text.strip() and metrics["image_tokens"] > 0
            report.update(text=text, metrics=metrics, model_path=str(config.output_path("models", "qwen3-vl-2b/" + contract["revision"])))
        finally:
            backend.close()
    else:
        raise ValueError("Unknown mode")
    report["status"] = "passed"
except Exception as exc:
    report.update(status="faulty", reason=str(exc), traceback=traceback.format_exc())
finally:
    save_json(target, report)
print(json.dumps(report))
if report["status"] != "passed":
    raise SystemExit(1)
