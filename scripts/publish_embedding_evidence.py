"""Small versioned measurement summary; full local receipts/rankings stay ignored."""
from pathlib import Path
import json
from local_asset_library.catalog import save_json

root = Path(__file__).resolve().parents[1]
def read(name):
    return json.loads((root / "data/embeddings" / name).read_text(encoding="utf-8"))
verification = read("verification.json")
capability = read("capability.json")
timings = read("cold-warm-timings.json")
summary = {"date": "2026-10-11", "status": "step5 technical evidence; no benchmark verdict or owner relevance approval",
           "verification": verification,
           "capability": {k: v for k, v in capability.items() if k != "contract"},
           "runtime_checks": read("runtime-checks.json"),
           "download": {k: v for k, v in read("model-download.json").items() if k != "files"},
           "demonstrations": read("demonstrations.json"),
           "cold_warm": {"definitions": timings["definitions"], "measurements":
                         [{k: v for k, v in m.items() if k not in {"stderr", "stdout_non_result_lines"}} for m in timings["measurements"]]}}
save_json(root / "docs/embedding-evidence.json", summary)
print("Published docs/embedding-evidence.json")
