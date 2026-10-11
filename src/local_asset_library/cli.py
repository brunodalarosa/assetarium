"""One CLI entry point for configuration and the step 2 catalog."""

import argparse
import json
from pathlib import Path
import sqlite3

import numpy as np

from .config import ConfigError, load_config
from .catalog import compact_search_result, detail, pilot, query, scan, verify_source


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Read-only source inventory and local asset search")
    parser.add_argument("--config", type=Path, default=root / "config.example.toml")
    parser.add_argument("command", choices=["check-config", "doctor", "scan", "search", "get", "pilot", "verify-source"])
    parser.add_argument("value", nargs="?")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--selection", type=Path, default=root / "docs/pilot-selection.json")
    args = parser.parse_args()
    try:
        config = load_config(args.config, root)
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
    except (ConfigError, sqlite3.Error, OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
