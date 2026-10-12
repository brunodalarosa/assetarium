"""Snapshot/compare original inputs without processing or replacing historical evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from local_asset_library.config import load_config
from local_asset_library.catalog import snapshot as source_snapshot, walk_source


def snapshot():
    paths = [ROOT / p for p in ("data/catalog.sqlite", "data/embeddings/index.sqlite",
        "data/pilot/selection-manifest.json", "uv.lock", "runtime/embedding/uv.lock",
        "runtime/caption/uv.lock", "src/local_asset_library/embedding_backend.py",
        "src/local_asset_library/caption_backend.py")]
    for directory in ("data/captions", "data/inspection", "docs/evaluation"):
        paths.extend(p for p in (ROOT / directory).rglob("*") if p.is_file())
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["before", "after"])
    args = parser.parse_args()
    folder = ROOT / "data/gui"
    folder.mkdir(parents=True, exist_ok=True)
    result = {"status": "running", "mode": args.mode}
    target = folder / f"preservation-{args.mode}.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream)
    try:
        result["hashes"] = snapshot()
        if args.mode == "after":
            before = json.loads((folder / "preservation-before.json").read_text(encoding="utf-8"))
            result["changed"] = sorted(k for k in before["hashes"].keys() | result["hashes"].keys()
                if before["hashes"].get(k) != result["hashes"].get(k))
            config = load_config(ROOT / "config.example.toml", ROOT)
            baseline = json.loads(config.output_path("data", "evidence/source-baseline.json").read_text(encoding="utf-8"))
            current = source_snapshot(walk_source(config))
            expected = {r["path"]: r for r in baseline}
            actual = {r["path"]: r for r in current}
            changed = sorted(k for k in expected.keys() | actual.keys() if expected.get(k) != actual.get(k))
            result["source_verification"] = {"verified": not changed, "entries": len(current), "changed_paths": changed,
                "method": "Full SHA-256/size/mtime comparison with existing inventory baseline; no catalog scan or evidence overwrite"}
            assert not result["changed"], "Preserved generated inputs changed"
            assert result["source_verification"]["verified"], "Original source content changed"
        result["status"] = "passed"
    except Exception as exc:
        result.update(status="faulty", reason=str(exc))
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "hashes"}, indent=2))
    sys.exit(result["status"] != "passed")
