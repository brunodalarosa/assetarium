"""Audited single-revision download, with real device and remaining-budget checks."""
from pathlib import Path
import json
import sys
import time
import urllib.request

import torch
from huggingface_hub import snapshot_download
from local_asset_library.catalog import save_json
from local_asset_library.captions import file_hash
from local_asset_library.config import load_project_config
from local_asset_library.model_storage import project_allocation, project_model_bytes

root = Path(__file__).resolve().parents[1]
config = load_project_config(root)
contract = json.loads((root / "docs/embedding-model.json").read_text(encoding="utf-8"))
# --device cpu probes the CPU search engine (decision 0018); the default stays the CUDA probe.
cpu = sys.argv[sys.argv.index("--device") + 1] == "cpu" if "--device" in sys.argv else False
if cpu:
    x = torch.ones(32, 32, dtype=torch.bfloat16)
    assert torch.isfinite(x @ x).all()
else:
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    x = torch.ones(32, 32, device="cuda", dtype=torch.bfloat16)
    assert torch.isfinite(x @ x).all()
    torch.cuda.synchronize()
url = f"https://huggingface.co/api/models/{contract['model_id']}/revision/{contract['revision']}?blobs=true"
with urllib.request.urlopen(url, timeout=30) as response:
    metadata = json.load(response)
assert metadata["sha"] == contract["revision"] and metadata["cardData"]["license"] == contract["license"]
files = [f for f in metadata["siblings"] if f["rfilename"] not in {".gitattributes", "README.md"}]
expected = sum(f["size"] for f in files)
model_bytes = project_model_bytes(config)
allocation = project_allocation(config)  # Shared unique-allocation accounting and the saved budget.
generated = allocation["allocated_bytes"]
assert not allocation["faults"], "Storage accounting has faults; run scripts/storage-report.py"
assert generated <= allocation["budget_bytes"], "Storage budget (Settings → General) exhausted"
assert model_bytes + (0 if "--verify-only" in sys.argv else expected) <= contract["model_budget_bytes"]
if cpu:
    probe_key, probe = "cpu_probe", {"torch": torch.__version__, "device": "cpu", "bf16_kernel": "passed",
                                     "cpu_capability": torch.backends.cpu.get_cpu_capability(),
                                     "threads": torch.get_num_threads()}
else:
    probe_key, probe = "cuda_probe", {"torch": torch.__version__, "cuda": torch.version.cuda, "device": torch.cuda.get_device_name(),
                                      "capability": list(torch.cuda.get_device_capability()), "bf16_kernel": "passed",
                                      "free_total_cuda_bytes": list(torch.cuda.mem_get_info())}
save_json(config.output_path("data", "embeddings/model-preflight.json"),
          {"expected_download_bytes": expected, "existing_model_bytes": model_bytes,
           "generated_bytes": generated, "contract": contract, probe_key: probe, "files": files})
destination = config.output_path("models", "embeddinggemma-2/" + contract["revision"])
started = time.perf_counter()
if "--verify-only" not in sys.argv:
    snapshot_download(contract["model_id"], revision=contract["revision"], local_dir=destination,
                      allow_patterns=[f["rfilename"] for f in files], max_workers=2)
verified = []
for item in files:
    path = destination / item["rfilename"]
    assert path.stat().st_size == item["size"]
    sha = file_hash(path)
    if item.get("lfs"):
        assert sha == item["lfs"]["sha256"]
    verified.append({"name": item["rfilename"], "size": item["size"], "sha256": sha})
report = {"revision": contract["revision"], "download_bytes": expected, "files": verified,
          "elapsed_seconds": time.perf_counter() - started, probe_key: probe}
save_json(config.output_path("data", "embeddings/model-download.json"), report)
print(json.dumps({k: v for k, v in report.items() if k != "files"}))
