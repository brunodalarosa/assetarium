"""One audited download after a real CUDA kernel probe and byte-budget check."""
from pathlib import Path
import json
import time
import urllib.request

from local_asset_library.catalog import save_json
from local_asset_library.captions import file_hash
from local_asset_library.config import load_config
from local_asset_library.model_storage import project_model_bytes

root = Path(__file__).resolve().parents[1]
config = load_config(root / "config.example.toml", root)
contract = json.loads((root / "docs/caption-model.json").read_text(encoding="utf-8"))
import torch
from huggingface_hub import snapshot_download
import sys

assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
x = torch.randn(32, 32, device="cuda", dtype=torch.bfloat16)
assert torch.isfinite(x @ x).all()
torch.cuda.synchronize()
probe = {"torch": torch.__version__, "cuda": torch.version.cuda,
         "device": torch.cuda.get_device_name(), "capability": list(torch.cuda.get_device_capability()),
         "arch_list": torch.cuda.get_arch_list(), "bf16_kernel": "passed",
         "cuda_free_total_bytes": list(torch.cuda.mem_get_info())}
url = f"https://huggingface.co/api/models/{contract['model_id']}/revision/{contract['revision']}?blobs=true"
with urllib.request.urlopen(url, timeout=30) as response:
    metadata = json.load(response)
assert metadata["sha"] == contract["revision"] and metadata["cardData"]["license"] == "apache-2.0"
selected = [f for f in metadata["siblings"] if f["rfilename"] not in {".gitattributes", "README.md"}]
expected = sum(f["size"] for f in selected)
existing = project_model_bytes(config)
generated = sum(p.stat().st_size for area in ("data", "cache", "scratch", "logs", ".venv", ".venv-caption")
                for p in (root / area).rglob("*") if p.is_file())
assert generated <= contract["generated_budget_bytes"], "Generated project budget exhausted"
assert (existing if "--verify-only" in sys.argv else existing + expected) <= contract["model_budget_bytes"], "Model budget exhausted"
save_json(config.output_path("data", "captions/model-verification-preflight.json" if "--verify-only" in sys.argv else "captions/model-preflight.json"),
          {"contract": contract, "cuda_probe": probe, "expected_download_bytes": expected,
           "existing_model_bytes": existing, "generated_project_bytes": generated,
           "generated_budget_remaining_bytes": contract["generated_budget_bytes"]-generated,
           "files": selected, "metadata_url": url})
destination = config.output_path("models", "qwen3-vl-2b/" + contract["revision"])
started = time.perf_counter()
if "--verify-only" not in sys.argv:
    snapshot_download(contract["model_id"], revision=contract["revision"], local_dir=destination,
                      allow_patterns=[f["rfilename"] for f in selected], max_workers=2)
measured = []
for item in selected:
    path = destination / item["rfilename"]
    assert path.stat().st_size == item["size"]
    sha = file_hash(path)
    if item.get("lfs"):
        assert sha == item["lfs"]["sha256"]
    measured.append({"name": item["rfilename"], "size": path.stat().st_size, "sha256": sha})
report = {"revision": contract["revision"], "verification_seconds": time.perf_counter() - started,
          "mode": "verify_only" if "--verify-only" in sys.argv else "download_and_verify",
          "download_bytes": expected, "files": measured, "cuda_probe": probe}
save_json(config.output_path("data", "captions/model-download.json"), report)
print(json.dumps(report))
