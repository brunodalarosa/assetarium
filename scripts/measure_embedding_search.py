"""Fresh-process startup measurements, paired with a warm query in each process."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time

from local_asset_library.catalog import save_json, encoded
from local_asset_library.config import load_project_config

root = Path(__file__).resolve().parents[1]
config = load_project_config(root)
parser = argparse.ArgumentParser()
parser.add_argument("--child", choices=["keyword", "description", "image", "combined", "reference"])
args = parser.parse_args()
if args.child:
    from local_asset_library.retrieval import SearchEngine
    started = time.perf_counter()
    backend = None
    if args.child != "keyword":
        from local_asset_library.embedding_backend import EmbeddingBackend
        backend = EmbeddingBackend(config)
    engine = SearchEngine(config, backend)
    ref = "data/inspection/asset_24e2752dbb26ecd19677091f78243709/fbx/a30ceb622a88a274/three_quarter.png"
    query = "apple" if args.child == "keyword" else "a red apple with a green leaf"
    runs = []
    for state in ("model_cold_first_query", "warm_repeat"):
        response, evidence = engine.search("" if args.child == "reference" else query,
                     args.child, ref if args.child == "reference" else None)
        evidence["timing_state"] = state
        save_json(config.output_path("data", f"embeddings/cold/{args.child}-{state}.json"), evidence)
        runs.append({"state": state, "search_seconds": evidence["elapsed_seconds"],
                     "characters": len(encoded(response)), "estimated_tokens": response["estimated_tokens"],
                     "first_name": response["results"][0]["name"] if response["results"] else None})
    print(json.dumps({"mode": args.child, "load_seconds": backend.load_seconds if backend else 0,
                      "runs": runs, "child_elapsed_seconds": time.perf_counter() - started}))
else:
    measurements = []
    for mode in ("keyword", "description", "image", "combined", "reference"):
        started = time.perf_counter()
        run = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--child", mode],
              cwd=root, env=os.environ.copy(), capture_output=True, text=True, encoding="utf-8",
              timeout=120, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if run.returncode:
            raise RuntimeError(f"Cold {mode} failed: {run.stderr}")
        value = json.loads(run.stdout.strip().splitlines()[-1])
        value["process_wall_seconds_including_two_queries"] = time.perf_counter() - started
        value["stdout_non_result_lines"] = run.stdout.strip().splitlines()[:-1]
        value["stderr"] = run.stderr
        measurements.append(value)
        print(json.dumps({"mode": mode, "load_seconds": value["load_seconds"], "runs": value["runs"]}), flush=True)
    save_json(config.output_path("data", "embeddings/cold-warm-timings.json"),
              {"measurements": measurements, "definitions":
               {"cold": "Fresh Python process, no resident model; weights hashed and loaded, then first query. OS disk cache not purged.",
                "warm": "Second query using the same model/process; file hashes still checked.",
                "process_wall": "Includes process startup, model load, both queries and evidence serialization; not a single-query latency."}})
