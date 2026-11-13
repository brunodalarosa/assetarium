"""Blender discovery and isolation, inspection result checks, catalog publication and source evidence."""

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time

from .catalog import detail, encoded, file_hash, save_json
from .config import ConfigError

VERSION = "inspect-render-v1"
# Pinned importer checks: these assets always inspect this format. Changing the set would
# re-inspect them with another source, so it stays as recorded.
PINNED_SOURCES = {("kenney_car-kit", "sedan"): "glb",
                  ("kenney_car-kit", "sedan-sports"): "obj",
                  ("kenney_food-kit", "apple"): "fbx",
                  ("quaternius_ultimate-nature-pack", "BirchTree_1"): "blend"}
BLENDER_FLAGS = ("--background", "--factory-startup", "--disable-autoexec", "--offline-mode")
# The worker scripts call os.path.isreserved, which only Windows provides. Their hashes
# are inspection fingerprints, so instead of editing them (re-queuing every finished
# inspection) Blender's Python gets ntpath's check off Windows: the same path policy.
PORTABILITY = () if os.name == "nt" else (
    "--python-expr", "import ntpath, os.path; os.path.isreserved = ntpath.isreserved")


def blender_command(blender, *args):
    return [str(blender), *BLENDER_FLAGS, *PORTABILITY, *args]


def environment(config):
    env = os.environ.copy()
    isolated = (
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
    )
    if os.name != "nt":
        isolated += (("HOME", "scratch", "blender-user/home"),
                     ("XDG_CONFIG_HOME", "scratch", "blender-user/xdg-config"),
                     ("XDG_DATA_HOME", "scratch", "blender-user/xdg-data"),
                     ("XDG_CACHE_HOME", "cache", "blender-xdg-cache"), ("TMPDIR", "scratch", "blender-tmp"))
    for key, area, relative in isolated:
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


def blender_candidates(config):
    """Existing Blender executables, configured first. Nothing is executed (shared by setup checks)."""
    candidates = [config.blender] if config.blender else []
    if shutil.which("blender"):
        candidates.append(Path(shutil.which("blender")))
    if os.name == "nt":
        foundation = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Blender Foundation"
        if foundation.is_dir():
            candidates.extend(sorted(foundation.glob("Blender */blender.exe"), reverse=True))
    else:
        candidates.extend(Path(p) for p in ("/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender"))
        for parent in (Path("/opt"), Path.home()):
            candidates.extend(sorted(parent.glob("blender*/blender"), reverse=True))
    return [path for path in dict.fromkeys(candidates) if path and path.is_file()]


def discover_blender(config):
    attempts = []
    for path in blender_candidates(config):
        result = run_process([str(path), "--version"], config.project_root, environment(config), 30)
        attempts.append({"path": str(path), **result})
        if result["returncode"] == 0 and not result["timed_out"] and "Blender " in result["output"]:
            probe = {"executable": str(path.resolve()), "version_output": result["output"], "attempts": attempts}
            save_json(config.output_path("data", "inspection/blender-runtime.json"), probe)
            return path.resolve(), probe
    raise ConfigError("No usable installed Blender; see discovery attempts before considering a project-local portable release: " + encoded(attempts))


BLENDER_VERSION = re.compile(r"Blender (\d+)\.(\d+)(?:\.(\d+))?")
_versions, _versions_lock = {}, threading.Lock()


class BlenderVersionError(RuntimeError):
    """The configured Blender's version is unknown: a visible fault, never a guessed key input.

    Not a ValueError, so key computation never turns it into a per-asset precondition fault."""


def blender_versions_path(config):
    return Path(config.project_root) / "data/inspection/blender-versions.json"


def _executable(path):
    """(path as configured, size, mtime): what a remembered Blender is recognized by."""
    info = Path(path).stat()
    return str(Path(path)), info.st_size, info.st_mtime_ns


def remembered_blenders(config):
    """Every Blender executable this checkout has seen, with the version it reported (decision 0028)."""
    path = blender_versions_path(config)
    try:
        stamp = path.stat()
    except FileNotFoundError:
        return []
    cached = _versions.get(("file", str(path)))
    if cached and cached[0] == (stamp.st_mtime_ns, stamp.st_size):
        return cached[1]
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))["executables"]
        for entry in entries:
            if not (isinstance(entry["path"], str) and isinstance(entry["size"], int) and isinstance(entry["mtime_ns"], int)
                    and BLENDER_VERSION.fullmatch("Blender " + entry["version"])):
                raise ValueError("invalid entry")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BlenderVersionError(f"{path} is unreadable ({exc}); it lists the Blender versions finished 3D "
                                  "inspections were keyed with, so restore it rather than delete it") from exc
    _versions[("file", str(path))] = ((stamp.st_mtime_ns, stamp.st_size), entries)
    return entries


def remember_blender(config, path, version):
    """Record ``version`` for this executable (path, size, mtime); written once per executable."""
    from .publication import atomic_json
    name, size, mtime = _executable(path)
    with _versions_lock:
        entries = remembered_blenders(config)
        if any((e["path"], e["size"], e["mtime_ns"], e["version"]) == (name, size, mtime, version) for e in entries):
            return
        entry = {"path": name, "size": size, "mtime_ns": mtime, "version": version,
                 "seen_utc": datetime.now(timezone.utc).isoformat()}
        atomic_json(blender_versions_path(config), {"schema_version": 1, "executables": entries + [entry]})


def blender_version(config, path=None):
    """The full version the configured Blender (or ``path``) reports, e.g. "5.2.2"; None when there is no file.

    ``blender --version`` runs at most once per executable (path, size, mtime): the answer is remembered
    in data/inspection/blender-versions.json, which also lets old keys survive a move (library_migration).
    """
    path = config.blender if path is None else path
    if not path or not Path(path).is_file():
        return None
    name, size, mtime = _executable(path)
    known = _versions.get((name, size, mtime)) or next(
        (e["version"] for e in remembered_blenders(config) if (e["path"], e["size"], e["mtime_ns"]) == (name, size, mtime)), None)
    if known is None:
        result = run_process([name, "--version"], config.project_root, environment(config), 30)
        found = BLENDER_VERSION.search(result["output"])
        if result["timed_out"] or result["returncode"] or not found:
            raise BlenderVersionError(f"{name} did not report a Blender version (exit code {result['returncode']}"
                                      f"{', timed out' if result['timed_out'] else ''}); check it in Settings")
        known = ".".join(g for g in found.groups() if g)
        remember_blender(config, name, known)
    _versions[(name, size, mtime)] = known
    return known


def blender_major(config, path=None):
    """The major version 3D inspection keys hold (decision 0028, E7): 5.1 and 5.5 render alike."""
    version = blender_version(config, path)
    return int(version.split(".")[0]) if version else None


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
    requested = PINNED_SOURCES.get((asset["pack"], asset["name"]))
    if formats is not None and requested and format_group(requested) not in formats:
        requested = None
    if requested:
        reason = "Pinned importer check for " + requested + "; only this file's facts are measured"
    else:
        ranking = {"glb": 0, "gltf": 1, "obj": 2, "fbx": 3, "blend": 4, "stl": 5}
        available = [f for f in asset["files"] if f["availability"] == "available"]
        if not available:
            raise ConfigError("Asset has no available inspection source")
        requested = min(available, key=lambda f: (ranking.get(f["format"], 99), f["path"]))["format"]
        reason = "Prefer portable GLB with embedded materials; otherwise OBJ with explicit MTL references; alternate features remain unknown"
    source = next((f for f in asset["files"] if f["format"] == requested and f["availability"] == "available"), None)
    if source is None:
        raise ConfigError("Required inspection format is missing: " + requested)
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
            from .result_store import logical
            relative = logical(config, Path(job["output"]) / view["filename"])
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
