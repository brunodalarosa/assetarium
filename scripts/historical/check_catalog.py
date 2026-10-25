"""Reproduce checks on the real step 2 catalog and saved keyword demonstrations."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from local_asset_library.catalog import read_database, save_json
from local_asset_library.config import load_project_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-logical-fingerprint")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    config = load_project_config(root)
    with closing(read_database(config)) as db:
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = db.execute("PRAGMA foreign_key_check").fetchall()
        counts = {table: db.execute("SELECT count(*) FROM " + table).fetchone()[0]
                  for table in ("assets", "files", "inventory", "asset_fts")}
    assert integrity == "ok" and not foreign_keys
    assert counts["assets"] == counts["asset_fts"]
    manifest = json.loads(config.output_path("data", "pilot/selection-manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["assets"]) == len({a["asset_id"] for a in manifest["assets"]}) == 40
    for asset in manifest["assets"]:
        for file in asset["files"]:
            config.source_file(file["path"])
        for dependency in asset["dependencies"]:
            if dependency["status"] == "available":
                config.source_file(dependency["path"])
    searches = []
    for path in sorted(config.output_path("data", "reports/search-apple.json").parent.glob("search-*.json")):
        serialized = path.read_text(encoding="utf-8-sig").strip()
        result = json.loads(serialized)
        assert len(serialized) == result["serialized_characters"] <= 6000
        assert len({a["asset_id"] for a in result["results"]}) == len(result["results"])
        for asset in result["results"]:
            for file in asset["files"]:
                actual = Path(file["path"])
                config.source_file(actual.relative_to(config.source_root).as_posix())
        searches.append({"query": result["query"], "results": len(result["results"]),
                         "names": [a["name"] for a in result["results"]],
                         "serialized_characters": len(serialized), "estimated_tokens": result["estimated_tokens"]})
    assert len(searches) >= 6, "Save the six documented keyword demonstrations first"
    report = json.loads(config.output_path("data", "reports/catalog-summary.json").read_text(encoding="utf-8"))
    if args.previous_logical_fingerprint:
        assert report["logical_fingerprint"] == args.previous_logical_fingerprint
    result = {"integrity_check": integrity, "foreign_key_issues": foreign_keys, "counts": counts,
              "python": sys.version, "searches": searches,
              "pilot_files": sum(len(a["files"]) for a in manifest["assets"]),
              "pilot_supplied_views": sum(len(a["previews"]) for a in manifest["assets"]),
              "consecutive_catalog_fingerprints_identical": True if args.previous_logical_fingerprint else None,
              "previous_logical_fingerprint": args.previous_logical_fingerprint,
              "logical_fingerprint": report["logical_fingerprint"]}
    save_json(config.output_path("data", "evidence/catalog-checks.json"), result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
