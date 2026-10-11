"""One CLI entry point for configuration and the step 2 catalog."""

import argparse
import json
from pathlib import Path
import sqlite3

import numpy as np

from .config import ConfigError, load_config
from .catalog import compact_search_result, detail, pilot, query, scan, verify_source
from .inspection import inspect_pilot, review_sheet


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Read-only source inventory and local asset search")
    parser.add_argument("--config", type=Path, default=root / "config.example.toml")
    parser.add_argument("command", choices=["check-config", "doctor", "scan", "search", "get", "pilot", "verify-source", "inspect", "review-sheet", "embed-index", "detail"])
    parser.add_argument("value", nargs="?")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--selection", type=Path, default=root / "docs/pilot-selection.json")
    parser.add_argument("--phase", choices=["representatives", "pilot"], default="representatives")
    parser.add_argument("--resolution", type=int, default=640)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retry-faults", action="store_true", help="Explicitly retry unchanged faulty inspection results")
    parser.add_argument("--mode", choices=["keyword", "description", "image", "keyword_description", "combined", "reference"], help="Pilot retrieval channel; omit to preserve full-catalog keyword baseline")
    parser.add_argument("--reference", help="Reference image under data/, scratch/, or source/")
    parser.add_argument("--pack")
    parser.add_argument("--format", dest="source_format")
    parser.add_argument("--max-triangles", type=int)
    parser.add_argument("--rigged", choices=["yes", "no"])
    parser.add_argument("--min-similarity", type=float, help="Explicit evaluation cosine floor, not a confidence threshold")
    parser.add_argument("--rankings-output", help="Save complete channel rankings under data/; excluded from compact default response")
    args = parser.parse_args()
    try:
        config = load_config(args.config, root)
        if args.command in {"embed-index", "detail"} or (args.command == "search" and args.mode):
            from .retrieval import SearchEngine, index_pilot, resolved_detail
            if args.command == "detail":
                result = resolved_detail(config, args.value or "", args.source_format)
            elif args.command == "embed-index":
                from .embedding_backend import EmbeddingBackend
                report = index_pilot(config, EmbeddingBackend(config))
                result = {k: v for k, v in report.items() if k != "outcomes"}
            else:
                backend = None
                if args.mode != "keyword":
                    from .embedding_backend import EmbeddingBackend
                    backend = EmbeddingBackend(config)
                filters = {k: v for k, v in {"pack": args.pack, "format": args.source_format,
                           "max_triangles": args.max_triangles,
                           "rigged": None if args.rigged is None else args.rigged == "yes"}.items() if v is not None}
                result, evidence = SearchEngine(config, backend).search(args.value or "", args.mode,
                                  args.reference, filters, args.limit, args.min_similarity)
                from .catalog import save_json
                save_json(config.output_path("data", args.rankings_output or "embeddings/last-search.json"), evidence)
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            return 0
        if args.command == "search" and (args.reference or args.pack or args.source_format or args.max_triangles is not None or args.rigged or args.min_similarity is not None or args.rankings_output):
            raise ConfigError("Pilot options require an explicit --mode")
        if args.command == "review-sheet":
            print(json.dumps(review_sheet(config, args.phase)))
            return 0
        if args.command == "inspect":
            result = inspect_pilot(config, args.phase, args.resolution, args.timeout, args.retry_faults)
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            return 0 if not result["failed"] else 1
        if args.command in {"scan", "search", "get", "pilot", "verify-source"}:
            if args.command == "scan":
                result = scan(config)
            elif args.command == "verify-source":
                result = verify_source(config)
            elif args.command == "pilot":
                result = pilot(config, args.selection)
            elif args.command == "get":
                result = detail(config, args.value or "")
            else:
                if not args.value:
                    raise ConfigError("Search requires a quoted keyword query")
                result = compact_search_result(args.value, query(config, args.value, args.limit))
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            return 0
        result = {"source_root": str(config.source_root), "source_read_only": True,
                  "project_root": str(root), "storage_valid": True}
        if args.command == "doctor":
            with sqlite3.connect(":memory:") as connection:
                connection.execute("CREATE VIRTUAL TABLE probe USING fts5(text)")
                connection.execute("INSERT INTO probe VALUES ('scaffold')")
                assert connection.execute("SELECT count(*) FROM probe WHERE probe MATCH 'scaffold'").fetchone()[0] == 1
            vector = np.array([3.0, 4.0], dtype=np.float32)
            result.update(sqlite=sqlite3.sqlite_version, fts5=True, numpy=np.__version__,
                          numpy_finite_normalized=bool(np.isfinite(vector / np.linalg.norm(vector)).all()),
                          blender_executable_exists=bool(config.blender and config.blender.is_file()))
        print(json.dumps(result, indent=2))
        return 0
    except (ConfigError, sqlite3.Error, OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
