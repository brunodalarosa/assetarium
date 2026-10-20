"""Bounded pilot jobs, catalog publication, and source immutability evidence."""

from contextlib import closing
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time

from .catalog import detail, digest, encoded, file_hash, read_database, save_json
from .config import ConfigError

VERSION = "inspect-render-v1"
REPRESENTATIVES = {("kenney_car-kit", "sedan"): "glb",
                   ("kenney_car-kit", "sedan-sports"): "obj",
                   ("kenney_food-kit", "apple"): "fbx",
                   ("quaternius_ultimate-nature-pack", "BirchTree_1"): "blend"}
SUPPORTED = {"glb", "gltf", "obj", "fbx", "blend", "stl"}


def environment(config):
    env = os.environ.copy()
    for key, area, relative in (
        ("BLENDER_USER_RESOURCES", "scratch", "blender-user/resources"),
        ("BLENDER_USER_CONFIG", "scratch", "blender-user/config"),
        ("BLENDER_USER_SCRIPTS", "scratch", "blender-user/scripts"),
        ("BLENDER_USER_DATAFILES", "scratch", "blender-user/datafiles"),
        ("BLENDER_USER_EXTENSIONS", "scratch", "blender-user/extensions"),
        ("APPDATA", "scratch", "blender-user/appdata"),
        ("LOCALAPPDATA", "scratch", "blender-user/localappdata"),
        ("TEMP", "scratch", "blender-tmp"), ("TMP", "scratch", "blender-tmp"),
        ("CUDA_CACHE_PATH", "cache", "blender-cuda"),
        ("PYTHONPYCACHEPREFIX", "cache", "blender-pycache"),
    ):
        path = config.output_path(area, relative)
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    env.pop("PYTHONPATH", None)
    return env


def run_process(command, cwd, env, timeout):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    started = time.perf_counter()
    with subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, creationflags=flags) as process:
        try:
            output, _ = process.communicate(timeout=timeout)
            return {"returncode": process.returncode, "timed_out": False,
                    "output": output.decode("utf-8", errors="replace"),
                    "elapsed_seconds": round(time.perf_counter() - started, 3)}
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate()
            return {"returncode": process.returncode, "timed_out": True,
                    "output": output.decode("utf-8", errors="replace"),
                    "elapsed_seconds": round(time.perf_counter() - started, 3)}


def discover_blender(config):
    candidates = [config.blender] if config.blender else []
    if shutil.which("blender"):
        candidates.append(Path(shutil.which("blender")))
    foundation = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Blender Foundation"
    if foundation.is_dir():
        candidates.extend(sorted(foundation.glob("Blender */blender.exe"), reverse=True))
    attempts = []
    for path in dict.fromkeys(candidates):
        if path and path.is_file():
            result = run_process([str(path), "--version"], config.project_root, environment(config), 30)
            attempts.append({"path": str(path), **result})
            if result["returncode"] == 0 and not result["timed_out"] and "Blender " in result["output"]:
                probe = {"executable": str(path.resolve()), "version_output": result["output"], "attempts": attempts}
                save_json(config.output_path("data", "inspection/blender-runtime.json"), probe)
                return path.resolve(), probe
    raise ConfigError("No usable installed Blender; see discovery attempts before considering a project-local portable release: " + encoded(attempts))


def load_pilot(config):
    path = config.output_path("data", "pilot/selection-manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if len(manifest.get("assets", [])) != 40 or len({a["asset_id"] for a in manifest["assets"]}) != 40:
        raise ConfigError("Expected the existing 40-distinct-asset pilot")
    with closing(read_database(config)) as db:
        fingerprint = json.loads(db.execute("SELECT value FROM metadata WHERE key='source_fingerprint'").fetchone()[0])
    if manifest["source_fingerprint"] != fingerprint:
        raise ConfigError("Pilot and catalog source fingerprints differ")
    for asset in manifest["assets"]:
        if not re.fullmatch(r"asset_[0-9a-f]{32}", asset["asset_id"]):
            raise ConfigError("Invalid pilot asset ID")
        record = detail(config, asset["asset_id"])
        if (asset["pack"], asset["identity"]) != (record["pack_id"], record["source_relative_identity"]):
            raise ConfigError("Pilot identity does not match catalog")
    return manifest


def source_evidence(config, assets, additional=()):
    paths = set(additional)
    expected = {}
    items = {}
    for asset in assets:
        for row in asset["files"] + asset["dependencies"]:
            if row.get("path") and row.get("availability", row.get("status")) == "available":
                paths.add(row["path"])
                items[row['path']] = row
                if row.get("sha256"):
                    expected[row["path"]] = row["sha256"]
    result = []
    for path in sorted(paths):
        from .dependency_resolution import dependency_file
        actual = dependency_file(config, items.get(path, {'path': path}))
        stat = actual.stat()
        with actual.open('rb') as stream:
            actual_hash = file_hash(stream)
        result.append({"path": path, "sha256": actual_hash, "size": stat.st_size,
                       "mtime_ns": stat.st_mtime_ns, "matches_catalog": expected.get(path, actual_hash) == actual_hash})
    return result


def choose_source(asset, formats=None):
    if formats is not None:
        from .settings import format_group
        asset = dict(asset, files=[f for f in asset['files'] if format_group(f['format']) in formats])
    requested = REPRESENTATIVES.get((asset["pack"], asset["name"]))
    if formats is not None and requested and format_group(requested) not in formats:
        requested = None
    if requested:
        reason = "Explicit pilot representative to validate the " + requested + " importer; only this file's facts are measured"
    else:
        ranking = {"glb": 0, "gltf": 1, "obj": 2, "fbx": 3, "blend": 4, "stl": 5}
        available = [f for f in asset["files"] if f["availability"] == "available"]
        if not available:
            raise ConfigError("Asset has no available inspection source")
        requested = min(available, key=lambda f: (ranking.get(f["format"], 99), f["path"]))["format"]
        reason = "Prefer portable GLB with embedded materials; otherwise OBJ with explicit MTL references; alternate features remain unknown"
    source = next((f for f in asset["files"] if f["format"] == requested and f["availability"] == "available"), None)
    if source is None:
        raise ConfigError("Required inspection format missing from pilot: " + requested)
    return source, reason


def validate_result(config, job, result):
    if (result.get("asset_id"), result.get("source_path"), result.get("format")) != (job["asset_id"], job["source_path"], job["format"]):
        raise ConfigError("Worker returned the wrong source identity")
    if result.get("status") == "complete":
        if not result.get("technical") or result["technical"].get("autoexec_enabled") is not False:
            raise ConfigError("Worker metadata missing or autoexec was enabled")
        required = {"object_count", "mesh_object_count", "evaluated_instance_totals", "world_bounds", "units", "materials", "armatures", "animation_clips"}
        if not required.issubset(result["technical"]):
            raise ConfigError("Worker technical metadata is incomplete")
        views = {view["view_label"] for view in result.get("previews", [])}
        if not {"front", "side", "three_quarter"}.issubset(views):
            raise ConfigError("Required preview views missing")
        for view in result["previews"]:
            if view["quality"]["empty"] or view["quality"]["off_frame"]:
                raise ConfigError("Worker claimed successful invalid preview")
            relative = (Path(job["output"]) / view["filename"]).relative_to(config.metadata_root or config.project_root / "data").as_posix()
            path = config.output_path("data", relative)
            if not path.is_file():
                raise ConfigError("Preview file missing")
            with path.open("rb") as stream:
                if file_hash(stream) != view["sha256"]:
                    raise ConfigError("Preview hash mismatch")
    for row in result.get("sources", []):
        from .dependency_resolution import dependency_file
        dependency = next((d for d in job.get('dependency_files', []) if d['path'] == row['path']), row)
        path = dependency_file(config, dependency)
        if not row.get("unchanged"):
            raise ConfigError("Worker reports source mutation")
        with path.open('rb') as stream:
            if file_hash(stream) != row["before"] or row.get("after") != row["before"]:
                raise ConfigError("Worker source/dependency hash no longer matches")


def publish(config, asset, source, reason, result, fingerprint, output_relative):
    from .publication import generation
    if config.catalog_generation is None and generation(config)!='legacy':
        raise ConfigError('Published inspection data is immutable; stage an incremental library update')
    record = detail(config, asset["asset_id"])
    old_reviews = {p["sha256"]: p.get("visual_review", "pending") for p in record["previews"] if p.get("origin") == "rendered"}
    record["primary_inspection_path"] = source["path"]
    record["primary_inspection_reason"] = reason
    record["technical"] = result.get("technical")
    if record["technical"]:
        for texture in record["technical"]["textures"]:
            if texture["status"] == "embedded":
                texture["embedding_evidence_limit"] = "Packed Blender image datablock after import; not proof of embedding in the original source format"
        record["technical"].update(extraction_method=VERSION, blender_version=result["blender_version"],
                                    inspected_path=source["path"], inspected_sha256=source["sha256"],
                                    inspected_format=source["format"], alternate_formats="uninspected")
    # Keep supplied baseline pictures and owner overlay; replace only this stage's generated views.
    record["previews"] = [p for p in record["previews"] if p.get("origin") != "rendered"]
    for preview in result.get("previews", []):
        record["previews"].append({"origin": "rendered", "path": "data/" + output_relative + "/" + preview["filename"],
                                   "view_label": preview["view_label"], "sha256": preview["sha256"],
                                   "coordinate_convention": result["render_settings"]["coordinate_convention"],
                                   "render_settings": result["render_settings"], "renderer_version": VERSION,
                                   "quality": preview["quality"], "visual_review": old_reviews.get(preview["sha256"], "pending")})
    record["processing"]["inspection"] = "complete" if result.get("technical") else result["status"]
    record["processing"]["previews"] = result["status"]
    record["inspection_run"] = {"status": result["status"], "errors": result.get("errors", []),
                                "elapsed_seconds": result.get("elapsed_seconds"), "fingerprint": fingerprint,
                                "result_path": "data/" + output_relative + "/result.json"}
    technical = result.get("technical") or {}
    record["inspection_run"]["source_faults"] = [
        {"kind": "overlapping_duplicate_faces", "status": "faulty", "object": mesh["object"],
         "count": mesh["duplicate_position_faces"], "repair": "not_performed",
         "render_adjustment": "shadow rays disabled in derived scene"}
        for mesh in technical.get("meshes", []) if mesh.get("duplicate_position_faces")
    ] + [{"kind": "missing_texture_reference", "status": "faulty", "name": texture["name"],
          "required_for_render": texture["required_for_render"], "repair": "not_performed"}
         for texture in technical.get("textures", []) if texture["status"] == "missing"]
    record["provenance"]["inspection"] = {"version": VERSION, "input_fingerprint": fingerprint,
                                           "updated_utc": datetime.now(timezone.utc).isoformat()}
    for image in (result.get("technical") or {}).get("textures", []):
        if image.get("path"):
            record["dependencies"] = [d for d in record["dependencies"] if not (d.get("inspection_version") == VERSION and d.get("from") == source["path"] and d.get("path") == image["path"])]
            record["dependencies"].append({"path": image["path"], "role": "texture", "sha256": image["sha256"],
                                            "status": image["status"], "from": source["path"],
                                            "required_for_render": image["required_for_render"],
                                            "evidence": "Blender inspected image datablock", "inspection_version": VERSION})
            if image.get('dependency_resolution'):
                record['dependencies'][-1]['dependency_resolution'] = image['dependency_resolution']
    with closing(sqlite3.connect(config.output_path("data", "catalog.sqlite"))) as db, db:
        db.execute("UPDATE assets SET record=? WHERE asset_id=?", (encoded(record), asset["asset_id"]))


def reuse_result(record, fingerprint, retry_faults=False):
    run = record.get("inspection_run", {})
    faulty = run.get("status") in {"failed", "unsupported"} or bool(run.get("source_faults"))
    return run.get("fingerprint") == fingerprint and not (faulty and retry_faults)


def inspect_pilot(config, phase="representatives", resolution=640, timeout=180, retry_faults=False):
    if phase not in {"representatives", "pilot"} or resolution not in {320, 640, 960} or not 10 <= timeout <= 600:
        raise ConfigError("Invalid phase/resolution/timeout")
    manifest = load_pilot(config)
    if phase == "pilot":
        review_path = config.output_path("data", "inspection/review/representatives-review.json")
        if not review_path.is_file():
            raise ConfigError("Review the four representative cases with image tools and save technical review evidence before the full pilot")
        review = json.loads(review_path.read_text(encoding="utf-8"))
        reviewed = {r["asset_id"]: r for r in review.get("assets", [])}
        if review.get("status") != "technical_pass":
            raise ConfigError("Representative technical image review has not passed")
        for asset in manifest["assets"]:
            if (asset["pack"], asset["name"]) in REPRESENTATIVES:
                current = detail(config, asset["asset_id"])
                entry = reviewed.get(asset["asset_id"], {})
                if entry.get("inspection_fingerprint") != current.get("inspection_run", {}).get("fingerprint"):
                    raise ConfigError("Representative review does not match current rendered inputs")
    selected = [a for a in manifest["assets"] if phase == "pilot" or (a["pack"], a["name"]) in REPRESENTATIVES]
    blender, runtime = discover_blender(config)
    env = environment(config)
    worker = Path(__file__).with_name("blender_worker.py")
    mathematics = Path(__file__).with_name("render_math.py")
    script_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (worker, mathematics)}
    before = source_evidence(config, manifest["assets"])
    if not all(row["matches_catalog"] for row in before):
        raise ConfigError("Pilot source/dependency files differ from catalog; inspection not started")
    save_json(config.output_path("data", f"evidence/step3-{phase}-before.json"), before)
    outcomes = []
    started = time.perf_counter()
    for index, asset in enumerate(selected, 1):
        print(f"Inspecting {index}/{len(selected)}: {asset['pack']} / {asset['name']}", flush=True)
        source, reason = choose_source(asset)
        fingerprint = digest({"version": VERSION, "source": source, "dependencies": asset["dependencies"],
                              "blender": runtime["version_output"], "scripts": script_hashes, "resolution": resolution})
        if phase == "pilot" and (asset["pack"], asset["name"]) in REPRESENTATIVES:
            if reviewed[asset["asset_id"]]["inspection_fingerprint"] != fingerprint:
                raise ConfigError("Renderer settings/code changed since representative image review; rerun and review representatives first")
        relative = f"inspection/{asset['asset_id']}/{source['format']}/{fingerprint[:16]}"
        output = config.output_path("data", relative)
        job = {"schema_version": 1, "project_root": str(config.project_root), "source_root": str(config.source_root),
               "asset_id": asset["asset_id"], "source_path": source["path"], "format": source["format"],
               "source_sha256": source["sha256"], "output": str(output), "resolution": resolution}
        task = config.output_path("data", relative + "/job.json")
        result_path = config.output_path("data", relative + "/result.json")
        record = detail(config, asset["asset_id"])
        cached = False
        try:
            if reuse_result(record, fingerprint, retry_faults) and result_path.is_file():
                result = json.loads(result_path.read_text(encoding="utf-8"))
                validate_result(config, job, result)
                cached = result["status"] in {"complete", "failed", "unsupported"}
            if not cached:
                save_json(task, job)
                command = [str(blender), "--background", "--factory-startup", "--disable-autoexec", "--offline-mode",
                           "--python-exit-code", "5", "--python", str(worker), "--", str(task)]
                process = run_process(command, config.project_root, env, timeout)
                log = config.output_path("data", relative + "/blender.log")
                log.write_text(process["output"], encoding="utf-8")
                if process["timed_out"]:
                    raise TimeoutError(f"Blender job exceeded {timeout} seconds")
                if process["returncode"] != 0:
                    raise RuntimeError(f"Blender exited {process['returncode']}; see {log}")
                if not result_path.is_file():
                    raise RuntimeError("Blender produced no result record")
                result = json.loads(result_path.read_text(encoding="utf-8"))
                validate_result(config, job, result)
        except (OSError, ValueError, RuntimeError, ConfigError) as exc:
            result = {"status": "failed", "asset_id": asset["asset_id"], "source_path": source["path"],
                      "format": source["format"], "technical": None, "previews": [], "errors": [str(exc)]}
            save_json(result_path, result)
        publish(config, asset, source, reason, result, fingerprint, relative)
        outcomes.append({"asset_id": asset["asset_id"], "name": asset["name"], "pack": asset["pack"],
                         "source_faults": detail(config, asset["asset_id"])["inspection_run"]["source_faults"],
                         "format": source["format"], "status": result["status"], "cached": cached,
                         "views": len(result.get("previews", [])), "errors": result.get("errors", []),
                         "warnings": result.get("warnings", []),
                         "elapsed_seconds": result.get("elapsed_seconds"), "result_path": "data/" + relative + "/result.json"})
    extra = {image["path"] for asset in selected for image in (detail(config, asset["asset_id"]).get("technical") or {}).get("textures", []) if image.get("status") == "available"}
    after = source_evidence(config, manifest["assets"], extra)
    before_map = {r["path"]: r for r in before}
    mutations = [r["path"] for r in after if r["path"] in before_map and r != before_map[r["path"]]]
    save_json(config.output_path("data", f"evidence/step3-{phase}-after.json"), after)
    report = {"version": VERSION, "phase": phase, "runtime": runtime["executable"],
              "elapsed_seconds": round(time.perf_counter() - started, 3), "resolution": resolution,
              "outcomes": outcomes, "complete": sum(o["status"] == "complete" for o in outcomes),
              "failed": sum(o["status"] != "complete" for o in outcomes), "source_mutations": mutations,
              "faulty": sum(o["status"] != "complete" or bool(o["source_faults"]) for o in outcomes),
              "source_files_verified": len(after), "visual_review": "pending", "caption_generation": "not_started"}
    save_json(config.output_path("data", f"inspection/{phase}-report.json"), report)
    with closing(sqlite3.connect(config.output_path("data", "catalog.sqlite"))) as db, db:
        for key, value in {"inspection_version": VERSION, "inspection_phase": phase,
                           "logical_fingerprint_scope": "step2 inventory snapshot; later inspection fields have per-stage fingerprints"}.items():
            db.execute("INSERT OR REPLACE INTO metadata VALUES (?,?)", (key, encoded(value)))
    if mutations:
        raise ConfigError("Source mutation detected; see step 3 evidence")
    if phase == "pilot":
        save_json(config.output_path("data", "inspection/processed-manifest.json"), {
            "selection_version": manifest["selection_version"], "source_fingerprint": manifest["source_fingerprint"],
            "assets": [{"asset_id": asset["asset_id"], "primary_inspection_path": detail(config, asset["asset_id"])["primary_inspection_path"],
                        "primary_inspection_reason": detail(config, asset["asset_id"])["primary_inspection_reason"],
                        "result_path": outcome["result_path"], "status": outcome["status"],
                        "source_faults": detail(config, asset["asset_id"])["inspection_run"]["source_faults"]}
                       for asset, outcome in zip(selected, outcomes)]})
    return report


def review_sheet(config, phase):
    if phase not in {"representatives", "pilot"}:
        raise ConfigError("Invalid review phase")
    blender, _ = discover_blender(config)
    script = config.project_root / "scripts/blender_review_sheet.py"
    process = run_process([str(blender), "--background", "--factory-startup", "--disable-autoexec", "--offline-mode",
                           "--python-exit-code", "5", "--python", str(script), "--", phase],
                          config.project_root, environment(config), 60)
    log = config.output_path("data", f"inspection/review/{phase}-sheet.log")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(process["output"], encoding="utf-8")
    if process["returncode"] != 0 or process["timed_out"]:
        raise ConfigError("Review-sheet creation failed; see " + str(log))
    return {"sheet": str(config.output_path("data", f"inspection/review/{phase}.png")),
            "grid_map": str(config.output_path("data", f"inspection/review/{phase}-grid-map.json"))}
