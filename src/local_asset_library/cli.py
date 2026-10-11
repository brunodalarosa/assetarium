"""One CLI entry point; stage 1 checks do not create a catalog."""

import argparse
import json
from pathlib import Path
import sqlite3

import numpy as np

from .config import ConfigError, load_config


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Local Asset Library scaffold checks")
    parser.add_argument("--config", type=Path, default=root / "config.example.toml")
    parser.add_argument("command", choices=["check-config", "doctor"])
    args = parser.parse_args()
    try:
        config = load_config(args.config, root)
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
    except (ConfigError, sqlite3.Error) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
