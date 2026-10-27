"""Explicit membership, stage ledger, bounded processing and immutable publication."""
from collections import Counter, defaultdict
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from itertools import product
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import threading
import time
import uuid

from .catalog import (build_inventory, detail, digest, encoded, read_database, save_json,
                      snapshot, walk_source, write_database, SOURCE_ID, SCANNER_VERSION)
from .config import ConfigError
from .membership import records, membership
from .publication import atomic_json, generation, line_ending_hashes, read_only
from .captions import file_hash, image_inputs, input_state
from .caption_quality import caption_summary
from .inspection import choose_source, discover_blender, validate_result

STAGES = ("inspection", "caption", "embeddings")
COVERAGE_STAGES = ('inventory','inspection','previews','caption','embeddings')
CAPTION_PROMPT_VERSION = 'v4'
IMAGE_CAPTION_PROMPT_VERSION = 'image-v1'
PROMPT_VERSIONS = {'v1', 'v2', 'v3', 'v4', IMAGE_CAPTION_PROMPT_VERSION}
WORK = "work"
_blender_runtime = {}
# Parallel inspections render outside it; catalog reads/writes around them take turns.
_catalog = threading.RLock()
GPU_WAIT = 30  # Seconds GPU renders wait for another GPU job, like the other GPU stages.
# blender_worker.py edits whose CPU renders are proven identical (scripts/check-render-stability.py), mapped
# to the hash finished inspections recorded, so an equivalent edit never re-queues them (decision 0022).
EQUIVALENT_WORKERS = {
    '69520d2225259116d055fb94d8c4948b5bb8e020773b3e9889885632dee6f690':  # Render device from the job (LF)
        'ba0252a27ec2cff5957dace405ad91d6a9d83cd868da797700433d9aa5ecc014',
    'b9ac48c40e1c3d527f061438a98164ae3adc184c89832c52bc49ba66eadc5ab1':  # The same with CRLF endings
        'aada0bbcd3ddc236f0a004e219cb31e2d5f5bd5ea9d988341a57529c476da0de',
}


def working(config):
    return replace(config, catalog_generation=WORK)


def policy(config):
    from .library_policy import contract
    value = contract(config)
    from .settings import storage_budget, settings_path
    if 'budget' in value or settings_path(config).exists():
        value['budget'] = storage_budget(config, value.get('budget'))
    if config.sources_registry:
        from .sources import registry
        value = dict(value, packs=[config.source_key] if config.source_key else
                     [s['key'] for s in registry(config)['sources']], approved=True)
        value.pop('maximum_assets', None)
        if not value['packs']:
            return value
    packs = value.get("packs")
    if (value.get("schema_version") != 1 or value.get("approved") is not True
            or not isinstance(packs, list) or not packs or len(set(packs)) != len(packs)
            or any(not isinstance(p, str) or not p or "/" in p or "\\" in p or p in {".", ".."} for p in packs)):
        raise ConfigError("Library expansion needs an explicit valid approved pack contract")
    return value


def copy_database(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(read_only(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def initialize(config):
    work = working(config)
    path = work.output_path("data", "catalog.sqlite")
    if not path.exists():
        copy_database(config.output_path("data", "catalog.sqlite"), path)
        index = config.output_path("data", "embeddings/index.sqlite")
        if index.exists():
            copy_database(index, work.output_path("data", "embeddings/index.sqlite"))
    return work


def ledger(config):
    path = config.output_path("data", "library/jobs.sqlite")
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS jobs(asset_id TEXT, stage TEXT, fingerprint TEXT,
          status TEXT, evidence TEXT, updated TEXT, PRIMARY KEY(asset_id,stage));
        CREATE TABLE IF NOT EXISTS history(sequence INTEGER PRIMARY KEY, asset_id TEXT,
          stage TEXT, fingerprint TEXT, status TEXT, evidence TEXT, updated TEXT);
    """)
    return db


def checkpoint(db, identifier, stage, fingerprint, status, evidence):
    row = (identifier, stage, fingerprint, status, encoded(evidence), datetime.now(timezone.utc).isoformat())
    with db:
        db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?)", row)
        db.execute("INSERT INTO history(asset_id,stage,fingerprint,status,evidence,updated) VALUES (?,?,?,?,?,?)", row)


def inspection_input(config, record, resolution=640, content_only=False, formats=None, recorded=None):
    from .asset_structure import asset_type
    if asset_type(record) == 'image':
        from .image_inspection import inspection_input as image_input
        return image_input(config, record, content_only=content_only, recorded=recorded)
    if asset_type(record) != 'model_3d':
        raise ConfigError('No inspection adapter for this asset type')
    asset = {"asset_id": record["asset_id"], "pack": record["pack_id"], "name": record["display_name"], "files": record["files"]}
    from .settings import inspected_path, processing_formats
    path = inspected_path(record) if record['processing'].get('inspection') != 'pending' else None
    source = next((f for f in asset['files'] if f['path'] == path), None)
    if source:
        reason = record.get('primary_inspection_reason', 'Preserve the previously inspected source; alternates remain uninspected')
    else:
        source, reason = choose_source(asset, processing_formats(config) if formats is None else formats)
    deps = [d for d in record["dependencies"] if d.get("from") == source["path"]]
    # Inactive datablocks remain evidence but do not change rendered pixels.
    deps = [d for d in deps if d.get("required_for_render") is not False]
    content = [{"path": source["path"], "sha256": source.get("sha256")}]
    for item in [source] + deps:
        path = item.get("path")
        try:
            from .dependency_resolution import dependency_file
            actual = file_hash(dependency_file(config, item))
        except (OSError, ValueError, TypeError) as exc:
            actual = {"missing": path, "reason": str(exc)}
        content.append({"path": path, "actual": actual, "expected": item.get("sha256")})
    from .texture_repair import validate_recipe
    repair = validate_recipe(config, record)
    if repair:
        content.append({'texture_repair': repair})
    if content_only:
        return asset,source,reason,digest(content)
    code = config.project_root / "src/local_asset_library"
    files = {"worker": code / "blender_worker.py", "render_math": code / "render_math.py"}
    worker = file_hash(files["worker"])
    settings = {"source": content, "resolution": resolution,
        "worker": EQUIVALENT_WORKERS.get(worker, worker), "render_math": file_hash(files["render_math"]),
        "blender": str(config.blender), "blender_mtime": config.blender.stat().st_mtime_ns if config.blender and config.blender.exists() else None}
    if repair:
        files['repair_worker'] = code / ('blender_shared_dependency_worker.py' if repair.get('kind') == 'shared_dependency_paths'
                                        else 'blender_repair_worker.py')
        settings['repair_worker'] = file_hash(files['repair_worker'])
    return asset, source, reason, recorded_fingerprint(settings, files, recorded, EQUIVALENT_WORKERS)


def recorded_fingerprint(value, files, recorded=None, equivalents=None):
    """digest(value), or ``recorded`` when it differs only by LF/CRLF endings of ``files``.

    ``value[key]`` is the hash of ``files[key]``. Python and uv read these files as
    text, so a git checkout that swaps line endings must not re-queue finished work.
    ``equivalents`` maps a file hash to the proven-equivalent hash recorded instead.
    """
    current = digest(value)
    equivalents = equivalents or {}
    if recorded and recorded != current:
        for hashes in product(*([equivalents.get(h, h) for h in line_ending_hashes(path)] for path in files.values())):
            if digest({**value, **dict(zip(files, hashes))}) == recorded:
                return recorded
    return current


def prompt_hash(config, version, recorded=None):
    """Current prompt bytes, or the recorded hash when only line endings differ.

    The model reads the prompt as text, so a git checkout that swaps LF/CRLF
    never changes inference and must not re-queue finished descriptions.
    """
    path = config.project_root / f"prompts/caption-{version}.txt"
    current = file_hash(path)
    if recorded and recorded != current:
        text = path.read_bytes().replace(b"\r\n", b"\n")
        if recorded in {hashlib.sha256(text).hexdigest(), hashlib.sha256(text.replace(b"\n", b"\r\n")).hexdigest()}:
            return recorded
    return current


def default_prompt_version(record):
    from .asset_structure import asset_type
    return IMAGE_CAPTION_PROMPT_VERSION if asset_type(record) == 'image' else CAPTION_PROMPT_VERSION


def caption_input(config, record, prompt_version=None, generation=None, recorded=None):
    # Model/runtime contracts and prompt affect inference. Severity/owner review do not.
    # Completed captions retain their generation prompt and mode for cache validation;
    # adopting a new default is not a request to regenerate existing results.
    # The built-in engine's fingerprint inputs are frozen evidence (decision 0007), so this
    # function knows them; other engines contribute their identity and adapter (decision 0015).
    from .caption_batching import MODE, POLICY
    from . import engine_server
    provenance = (record.get('caption_provenance') or {}) if record['processing'].get('caption') == 'complete' else {}
    if prompt_version is None:
        prompt_version = provenance.get('prompt_version') or default_prompt_version(record)
    if prompt_version not in PROMPT_VERSIONS:
        raise ConfigError('Unsupported caption prompt version')
    identity = provenance.get('engine')
    if generation is None:
        if provenance:
            generation = provenance.get('generation_mode', 'sequential')
        else:  # New work follows the configured engine; finished work keeps its own.
            from .engines import generation as configured
            generation, identity = configured(config)
    if generation not in {'sequential', MODE, engine_server.MODE}:
        raise ConfigError('Unsupported caption generation mode')
    if generation == engine_server.MODE:
        if not isinstance(identity, dict):
            from .engines import generation as configured
            identity = configured(config)[1] or {}
        files = {"engine": Path(engine_server.__file__)}
        value = {"views": [{"path": p.get("path"), "sha256": p.get("sha256"),
            "view_label": p.get("view_label"), "actual": s.get("current_sha256", s.get("error"))}
            for s in input_state(config, record) for p in [s["preview"]]],
            "engine": identity, "adapter": file_hash(files["engine"]),
            "prompt": prompt_hash(config, prompt_version, provenance.get('prompt_sha256')
                                  if provenance.get('prompt_version') == prompt_version else None),
            "generation_policy": engine_server.POLICY}
        return recorded_fingerprint(value, files, recorded)
    files = {"backend": config.project_root / "src/local_asset_library/caption_backend.py",
             "runtime": config.project_root / "runtime/caption/uv.lock"}
    value = {"views": [{"path": p.get("path"), "sha256": p.get("sha256"),
        "view_label": p.get("view_label"), "actual": s.get("current_sha256", s.get("error"))}
        for s in input_state(config, record) for p in [s["preview"]]],
        "model": {k: v for k,v in json.loads((config.project_root / "docs/caption-model.json").read_text(encoding="utf-8")).items()
                  if k in {'model_id', 'revision'}},
        "prompt": prompt_hash(config, prompt_version, provenance.get('prompt_sha256')
                              if provenance.get('prompt_version') == prompt_version else None),
        "backend": file_hash(files["backend"]),
        "runtime": file_hash(files["runtime"]),
        "generation_policy": "single-attempt-no-fault-retry-v1"}
    if generation == MODE:  # Sequential fingerprints stay byte-identical to earlier results.
        files["batching"] = config.project_root / "src/local_asset_library/caption_batching.py"
        value.update(generation_policy=POLICY, batching=file_hash(files["batching"]))
    return recorded_fingerprint(value, files, recorded)


def stage_content(config,record,stage):
    try:
        if stage=='inspection':
            # Retained fault identity does not change when checkboxes change.
            return inspection_input(config,record,content_only=True,
                                    formats=('gltf', 'fbx', 'obj', 'blend', 'stl', 'dae'))[3]
        return digest([{'path':s['preview'].get('path'),'view':s['preview'].get('view_label'),
            'expected':s['preview'].get('sha256'),'actual':s.get('current_sha256',s.get('error'))}
            for s in input_state(config,record)])
    except (OSError,ValueError,KeyError):
        return digest({'files':record.get('files'),'dependencies':record.get('dependencies')})


def seed(config):
    """Adopt validated existing results without recaptioning due to orchestration edits."""
    with closing(ledger(config)) as db, closing(read_database(config)) as catalog:
        for (payload,) in catalog.execute("SELECT record FROM assets"):
            record = json.loads(payload)
            identifier = record["asset_id"]
            for stage, old in (("inspection", record.get("inspection_run")), ("caption", record.get("caption_provenance"))):
                if not old or db.execute("SELECT 1 FROM jobs WHERE asset_id=? AND stage=?", (identifier, stage)).fetchone():
                    continue
                state = record["processing"][stage]
                fp = inspection_input(config, record)[3] if stage == "inspection" else caption_input(config, record)
                evidence = {"adopted": True, "original": deepcopy(old),'fault_content':stage_content(config,record,stage)}
                try:
                    if stage == "inspection" and state == "complete":
                        from .asset_structure import asset_type
                        if asset_type(record) == 'image':
                            from .image_inspection import validate_result as validate_image
                            validate_image(config, record)
                        else:
                            path = config.output_path("data", old["result_path"].removeprefix("data/"))
                            result = json.loads(path.read_text(encoding="utf-8"))
                            source = next(f for f in record["files"] if f["path"] == result["source_path"])
                            validate_result(config, {"asset_id": identifier, "source_path": source["path"],
                                "format": source["format"], "output": str(path.parent)}, result)
                    if stage == "caption" and state == "complete":
                        image_inputs(config, record)
                except (OSError, ValueError, KeyError) as exc:
                    state = "failed"
                    evidence["error"] = str(exc)
                checkpoint(db, identifier, stage, fp, state, evidence)


def update_record(config, record):
    with closing(sqlite3.connect(config.output_path("data", "catalog.sqlite"))) as db, db:
        payload = encoded(record)
        db.execute("UPDATE assets SET record=? WHERE asset_id=? AND record<>?", (payload, record["asset_id"], payload))


def refresh(config, dry_run=False):
    approved = policy(config)
    current = working(config) if working(config).output_path("data", "catalog.sqlite").exists() else config
    with closing(read_database(current)) as db:
        old = {r[0]: json.loads(r[1]) for r in db.execute("SELECT asset_id,record FROM assets")}
    rows, fresh, ambiguities, archives = build_inventory(config)
    baseline = snapshot(rows)
    if baseline != snapshot(walk_source(config)):
        raise ConfigError("Source changed during refresh; no publication")
    selected = [r for r in fresh if r["pack_id"] in approved["packs"]]
    if len(selected) > approved.get('maximum_assets', len(selected)):
        raise ConfigError('Membership exceeds explicitly approved expansion bound; obtain a new scope approval')
    added = [r["asset_id"] for r in selected if r["asset_id"] not in old]
    removed = sorted(set(old) - {r["asset_id"] for r in fresh})
    changed = []
    merged = []
    for record in fresh:
        previous = old.get(record["asset_id"])
        if previous:
            same = previous["files"] == record["files"] and [d for d in previous["dependencies"] if not d.get("inspection_version")] == record["dependencies"]
            kept = deepcopy(previous)
            for key in ("files", "availability", "display_name", "license_evidence", "grouping", "variants", "dependency_inspection"):
                kept[key] = record[key]
            from .dependency_overrides import synchronize_recipe
            synchronize_recipe(kept, record)
            kept["dependencies"] = record["dependencies"] + [d for d in previous["dependencies"] if d.get("inspection_version") and any(f["path"] == d.get("from") and f["sha256"] == next((o["sha256"] for o in previous["files"] if o["path"] == f["path"]), None) for f in record["files"])]
            kept["previews"] = record["previews"] + [p for p in previous["previews"] if p.get("origin") == "rendered"]
            if not same:
                changed.append(record["asset_id"])
            record = kept
        merged.append(record)
    report = {"membership": len(selected), "packs": approved["packs"], "added": added,
        "deleted": removed, "changed": changed, "dry_run": dry_run,
        "identity_rule": "IDs bind pack and relative identity. Rename is deletion plus addition; never transfer owner approval automatically.",
        "stage_pending": {s: sum(r["processing"][s] == "pending" for r in merged if r["pack_id"] in approved["packs"]) for s in STAGES}}
    if dry_run:
        return report
    work = initialize(config)
    seed(work)
    if not added and not removed and not changed:
        try:
            if set(membership(work)['asset_ids']) == {r['asset_id'] for r in selected}:
                report['no_change'] = True
                atomic_json(config.output_path('data','library/last-refresh.json'),report)
                return report
        except (OSError, ValueError):
            pass
    # Build a new DB beside working data, then replace; never truncate usable old results.
    candidate = replace(config, catalog_generation="scan_" + uuid.uuid4().hex)
    meta = {"schema_version": 1, "source_id": SOURCE_ID, "source_root": str(config.source_root),
            "scanner_version": SCANNER_VERSION, "source_fingerprint": digest(baseline),
            "logical_fingerprint": digest(merged), "scan_utc": datetime.now(timezone.utc).isoformat()}
    blank = [deepcopy(r) for r in merged]
    for r in blank:
        r.update(technical=None, description=None, embeddings=[], owner_overlay={})
    write_database(candidate, rows, blank, meta)
    with closing(sqlite3.connect(candidate.output_path("data", "catalog.sqlite"))) as db, db:
        db.executemany("UPDATE assets SET record=? WHERE asset_id=?", [(encoded(r), r["asset_id"]) for r in merged])
    os.replace(candidate.output_path("data", "catalog.sqlite"), work.output_path("data", "catalog.sqlite"))
    ids = sorted(r["asset_id"] for r in merged if r["pack_id"] in approved["packs"])
    atomic_json(work.output_path("data", "library/membership.json"), {"schema_version": 1, "asset_ids": ids,
        "fingerprint": digest(ids), "scope": "library", "packs": approved["packs"], "approval": approved["approval"]})
    atomic_json(config.output_path("data", "library/last-refresh.json"), report)
    return report


def run_inspection(config, record, fingerprint, resolution=640, timeout=180, formats=None):
    from .asset_structure import asset_type
    if asset_type(record) == 'image':
        from .image_inspection import run
        with _catalog:
            return run(config, record, fingerprint)
    from .inspection import publish
    with _catalog:
        asset, source, reason, _ = inspection_input(config, record, resolution, formats=formats)
        key = (str(config.blender), config.blender.stat().st_mtime_ns if config.blender and config.blender.exists() else None)
        if key not in _blender_runtime:
            _blender_runtime[key] = discover_blender(config)
        blender, runtime = _blender_runtime[key]
    relative = f"inspection/{record['asset_id']}/{source['format']}/{fingerprint[:16]}"
    output = config.output_path("data", relative)
    job = {"schema_version": 1, "project_root": str(config.project_root), "source_root": str(config.source_root),
        "asset_id": record["asset_id"], "source_path": source["path"], "format": source["format"],
        "source_sha256": source["sha256"], "output": str(output), "resolution": resolution}
    if config.source_key:
        job.update(source_prefix=config.source_key, metadata_root=str(config.metadata_root))
    from . import render_pool
    device = render_pool.job_device(config)
    if device:
        job['render_device'] = device
    worker = 'blender_worker.py'
    if record.get('texture_repair'):
        from .texture_repair import validate_recipe
        job['texture_repair'] = validate_recipe(config, record)
        worker = 'blender_repair_worker.py'
        if job['texture_repair'].get('kind') == 'shared_dependency_paths':
            from .dependency_resolution import worker_files
            job['dependency_files'] = worker_files(config, job['texture_repair'])
            worker = 'blender_shared_dependency_worker.py'
    task = output / "job.json"
    result_path = output / "result.json"
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except ValueError:
            # Cut off by an interrupted run: an unfinished render, not an asset fault. Keep the partial file.
            result_path.replace(output / f"result.interrupted-{uuid.uuid4().hex[:8]}.json")
            result = None
        if result is not None:
            validate_result(config, job, result)
    if not result_path.exists():
        save_json(task, job)
        process = render_pool.run(config, blender, config.project_root / 'src/local_asset_library' / worker, task, timeout)
        (output / "blender.log").write_text(process["output"], encoding="utf-8")
        if process["timed_out"] or process["returncode"] != 0 or not result_path.exists():
            raise RuntimeError(f"Inspection timeout/exit {process['returncode']}; see {output / 'blender.log'}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        unavailable = [e for e in result.get("errors", []) if e.startswith("Render device unavailable: ")]
        if unavailable:
            # A machine fault, not this asset's: keep the evidence aside and leave the asset pending.
            result_path.replace(output / f"result.device-unavailable-{uuid.uuid4().hex[:8]}.json")
            raise render_pool.DeviceUnavailable(unavailable[0] + ". Choose Automatic or CPU in Settings → General")
        validate_result(config, job, result)
    with _catalog:
        publish(config, asset, source, reason, result, fingerprint, relative)
    return {"status": result["status"], "result_path": str(result_path), "seconds": result.get("elapsed_seconds"), "errors": result.get("errors", [])}


def returned(value):
    if isinstance(value, BaseException):
        raise value
    return value


def run_captions(config, batch, backend, batch_size=None):
    """Generate one batch of (record, fingerprint, inputs); return each outcome or its exception.

    Every asset is re-checked, saved and published on its own. EngineStop (out of memory,
    engine unavailable) propagates before anything is recorded, so the batch stays pending.
    """
    from .captions import infer_captions, publish
    from .caption_batching import MODE
    # A model batch never mixes prompts: 3D views and 2D images use separate versioned prompts.
    groups = {}
    for index, (record, _, _) in enumerate(batch):
        groups.setdefault(default_prompt_version(record), []).append(index)
    outcomes, members = [None] * len(batch), {}
    for version, indices in groups.items():
        prompt = (config.project_root / f'prompts/caption-{version}.txt').read_text(encoding="utf-8")
        for index, outcome in zip(indices, infer_captions(backend, [batch[i][2] for i in indices], prompt, batch_size=batch_size)):
            outcomes[index], members[index] = outcome, (version, len(indices), indices.index(index))
    results = []
    for index, ((record, fingerprint, inputs), outcome) in enumerate(zip(batch, outcomes)):
        version, assets, position = members[index]
        prompt_path = config.project_root / f'prompts/caption-{version}.txt'
        try:
            image_inputs(config, record)
            relative = f"captions/library/{record['asset_id']}/{fingerprint}.json"
            provenance = {"fingerprint": fingerprint, "model": backend.contract, "settings": backend.settings,
                "prompt_version": version, "prompt_sha256": file_hash(prompt_path), "input_views": inputs,
                "generation_mode": getattr(backend, 'generation_mode', MODE),
                **({"engine": backend.identity} if getattr(backend, 'identity', None) else {}),
                "batch": {"size": batch_size or len(batch), "assets": assets, "position": position},
                "attempts": outcome["attempts"], "ai_review": "pending", "owner_caption_review": "pending",
                "owner_artistic_suitability": "pending", "result_path": "data/" + relative}
            save_json(config.output_path("data", relative), {"asset_id": record["asset_id"], **outcome, "provenance": provenance})
            publish(config, record["asset_id"], outcome, provenance)
            results.append({"status": outcome["status"], "result_path": "data/" + relative, "attempts": outcome["attempts"]})
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            results.append(exc)
    return results


def run_caption(config, record, fingerprint, backend):
    return returned(run_captions(config, [(record, fingerprint, image_inputs(config, record))], backend)[0])


def restore_reused(record, stage, apply=True):
    """A reused complete result whose stage a rescan reset (for example after grouping export folders) is complete again.

    Only when the record still carries that result: a complete inspection run with its previews, or its description.
    With ``apply=False`` it only reports whether it would (dry runs write nothing).
    """
    states = record['processing'] if apply else dict(record['processing'])
    if stage == 'inspection':
        if ((record.get('inspection_run') or {}).get('status') == 'complete' and record.get('technical') and record.get('previews')
                and (states.get('inspection'), states.get('previews')) != ('complete', 'complete')):
            states.update(inspection='complete', previews='complete')
            return True
    elif stage == 'caption' and record.get('description') and record.get('caption_provenance') and states.get('caption') != 'complete':
        states['caption'] = 'complete'
        return True
    return False


def process(config, stage, limit=40, backend=None, dry_run=False, resolution=640,
            cancelled=None, progress=None, asset_ids=None, status=None):
    if stage not in STAGES or type(limit) is not int or not 1 <= limit <= 1000:
        raise ConfigError("Invalid bounded stage/limit")
    work = working(config)
    selected = records(work)
    from .settings import processing_formats, processing_eligible
    formats = processing_formats(config)
    # asset_ids narrows the caption/inspection selection; vectors cover the whole source.
    selected = [record for record in selected if processing_eligible(record, formats)
                and (asset_ids is None or stage == "embeddings" or record["asset_id"] in asset_ids)]
    from .asset_structure import supported_stage
    selected = [record for record in selected if supported_stage(record, stage)]
    if stage == "embeddings":
        from .library_index import index_library
        return index_library(work, backend, limit, dry_run, cancelled=cancelled, progress=progress)
    from .settings import descriptions_enabled
    if stage == "caption" and not descriptions_enabled(config):
        # Turned off in Settings: no new descriptions; existing ones stay valid and searchable.
        return {"stage": stage, "pending": 0, "selected": 0, "retained": {}, "dry_run": dry_run, "outcomes": [],
                "pending_ids": [], "descriptions_disabled": True,
                "reason": "Descriptions are turned off in Settings → General"}
    pending, retained, restored = [], Counter(), 0
    with closing(ledger(config)) as db:
        for record in selected:
            old = db.execute("SELECT fingerprint,status,evidence FROM jobs WHERE asset_id=? AND stage=?", (record["asset_id"], stage)).fetchone()
            recorded = old[0] if old else None
            try:
                fp = (inspection_input(work, record, resolution, formats=formats, recorded=recorded)[3] if stage == "inspection"
                      else caption_input(work, record, recorded=recorded))
            except (OSError, ValueError) as exc:
                fp = digest({"asset": record["asset_id"], "stage": stage, "precondition": str(exc), "files": record["files"]})
            if old and old[0]==fp and old[1] in {'failed','unsupported'} and not dry_run:
                evidence=json.loads(old[2])
                if 'fault_content' not in evidence:
                    evidence['fault_content']=stage_content(work,record,stage)
                    checkpoint(db,record['asset_id'],stage,fp,old[1],evidence)
                    old=(old[0],old[1],encoded(evidence))
            if old and old[1] in {'failed','unsupported'} and json.loads(old[2]).get('fault_content')==stage_content(work,record,stage):
                retained[old[1]]+=1
                continue  # Changing settings alone is not authorization to retry a source/input fault.
            if (stage == 'inspection' and old and old[1] == 'complete' and record.get('asset_type') == 'image'
                    and record['processing'].get('inspection') == 'pending' and not record.get('technical')):
                old = None  # A re-enrolled image without its result is inspected again (cheap), not a fault.
            if old and old[0] == fp and old[1] in {"complete", "failed", "unsupported"}:
                if old[1] == 'complete':
                    try:
                        if stage == 'caption':
                            image_inputs(work, record)
                        else:
                            from .asset_structure import asset_type
                            if asset_type(record) == 'image':
                                from .image_inspection import validate_result as validate_image
                                validate_image(work, record)
                            run = record.get('inspection_run') or {}
                            if run.get('result_path'):
                                path = work.output_path('data',run['result_path'].removeprefix('data/'))
                                result = json.loads(path.read_text(encoding='utf-8'))
                                validate_result(work, {'asset_id': record['asset_id'], 'source_path': result['source_path'],
                                    'format': result['format'], 'output': str(path.parent)}, result)
                    except (OSError, ValueError, KeyError) as exc:
                        if not dry_run:
                            checkpoint(db, record['asset_id'], stage, fp, 'failed', {'error':str(exc),'corrupt_output':True,'retry':'explicit authorization required','fault_content':stage_content(work,record,stage)})
                            record.setdefault('stage_faults',{})[stage] = {'status':'failed','error':str(exc),'corrupt_output':True}
                            record['processing']['previews' if stage=='inspection' else stage] = 'failed'
                            update_record(work,record)
                        retained['failed'] += 1
                        continue
                    if restore_reused(record, stage, apply=not dry_run):
                        restored += 1
                        if not dry_run:
                            update_record(work, record)
                retained[old[1]] += 1
                continue
            if stage == 'caption':
                fp = caption_input(work, record, prompt_version=default_prompt_version(record))
            pending.append((record, fp))
        report = {"stage": stage, "pending": len(pending), "selected": min(limit, len(pending)), "retained": dict(retained),
                  "restored": restored, "dry_run": dry_run, "outcomes": []}
        report['pending_ids'] = [r['asset_id'] for r, _ in pending]
        if dry_run:
            return report
        started = time.monotonic()
        chosen = pending[:limit]
        status_path = config.output_path('data','library/processing-status.json')
        atomic_json(status_path,{'status':'running','stage':stage,'selected':len(chosen),'completed':0,'pid':os.getpid()})
        from .engines import batch_size
        size = batch_size(config) if stage == 'caption' else 1

        def settle(record, fp, run):
            with _catalog:
                record_outcome(record, fp, run)

        def record_outcome(record, fp, run):
            identifier = record["asset_id"]
            try:
                outcome = run()
                updated = detail(work, identifier)
                final_fp = inspection_input(work, updated, resolution)[3] if stage == "inspection" else caption_input(work, updated)
            except (OSError, ValueError, RuntimeError, KeyError, TimeoutError) as exc:
                outcome = {"status": "failed", "error": str(exc), "type": type(exc).__name__}
                updated = detail(work, identifier)
                updated["processing"][stage] = "failed"
                if stage == 'inspection':
                    try:
                        _, source, reason, _ = inspection_input(work, record, resolution, formats=formats)
                        updated.update(primary_inspection_path=source['path'], primary_inspection_reason=reason)
                    except (OSError, ValueError, KeyError):
                        pass  # Keep the original failure if no source could be selected.
                updated.setdefault("stage_faults", {})[stage] = outcome
                update_record(work, updated)
                final_fp = fp
            if outcome['status'] == 'complete' and stage in updated.get('stage_faults', {}):
                updated['stage_faults'].pop(stage)
                update_record(work, updated)  # Prior failures remain in the append-only stage history.
            outcome['fault_content']=stage_content(work,updated,stage)
            checkpoint(db, identifier, stage, final_fp, outcome["status"], outcome)
            report["outcomes"].append({"asset_id": identifier, **outcome})
            atomic_json(status_path,{'status':'running','stage':stage,'selected':len(chosen),'completed':len(report['outcomes']),'pid':os.getpid(),'last_asset':identifier,'last_status':outcome['status']})

        from .retrieval import source_check
        from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
        from contextlib import ExitStack
        inflight, executor, parallel = [], None, 1

        def collect(everything=False):
            # Settle finished parallel renders on this thread; keep at most one job per render process.
            while inflight and (everything or len(inflight) >= parallel):
                done, _ = wait([future for _, _, future in inflight], return_when=FIRST_COMPLETED)
                for item in [item for item in inflight if item[2] in done]:
                    inflight.remove(item)
                    settle(item[0], item[1], item[2].result)
                    if progress:
                        progress(None, len(report['outcomes']), len(chosen))

        with ExitStack() as stack:
            if stage == "inspection":
                from . import render_devices, render_pool
                from .asset_structure import asset_type
                if any(asset_type(record) == 'model_3d' for record, _ in chosen):
                    render_devices.ensure(work, progress=status, cancelled=cancelled)
                plan = render_pool.plan(work)
                report['render'] = {key: plan[key] for key in ('processes', 'threads', 'reason', 'device_label')}
                if plan['device']:
                    tested = render_devices.saved(work)
                    if tested and plan['device_key'] not in {render_devices.key(d) for d in tested['devices']}:
                        raise render_pool.DeviceUnavailable(f"The chosen render device ({plan['device_label']}) was not found. "
                                                            "Choose Automatic or CPU in Settings → General")
                    from .gpu_queue import lease
                    try:
                        stack.enter_context(lease(config, 'batch-source-inspection', timeout=GPU_WAIT))
                    except ConfigError as exc:
                        raise render_pool.DeviceUnavailable('The GPU is busy with another job (descriptions or search). '
                            'Process assets again when it finishes, or choose CPU in Settings → General') from exc
                stack.enter_context(render_pool.opened(work, plan['processes'], plan['threads'], plan['device']))
                if plan['processes'] > 1:
                    parallel = plan['processes']
                    executor = stack.enter_context(ThreadPoolExecutor(plan['processes'], thread_name_prefix='render'))
            for start in range(0, len(chosen), size):
                if cancelled and cancelled():
                    report['cancelled'] = True
                    break
                group = chosen[start:start + size]
                if progress:
                    progress(group[0][0]["asset_id"], len(report['outcomes']), len(chosen))
                ready = []
                for record, fp in group:
                    checkpoint(db, record["asset_id"], stage, fp, "running", {"resumable": True})
                    print(f"{stage}: {record['pack_id']} / {record['display_name']}", flush=True)
                    try:
                        checked = deepcopy(record)
                        if stage == "inspection":
                            checked["technical"] = None
                        source_check(work, checked)
                        inputs = image_inputs(work, record) if stage == "caption" else None
                    except (OSError, ValueError, RuntimeError, KeyError, TimeoutError) as exc:
                        settle(record, fp, lambda exc=exc: returned(exc))
                        continue
                    if stage == "inspection" and executor:
                        inflight.append((record, fp, executor.submit(run_inspection, work, record, fp, resolution, formats=formats)))
                        collect()
                    elif stage == "inspection":
                        settle(record, fp, lambda: run_inspection(work, record, fp, resolution, formats=formats))
                    else:
                        ready.append((record, fp, inputs))
                if ready:
                    from .description_engines import EngineStop
                    try:
                        results = run_captions(work, ready, backend, batch_size=size)
                    except EngineStop as exc:
                        # Ledger rows stay "running", which the next pass treats as pending.
                        report.update(stopped=str(exc), elapsed_seconds=time.monotonic() - started)
                        save_json(config.output_path("data", f"library/batches/{stage}-{uuid.uuid4().hex}.json"), report)
                        atomic_json(status_path,{'status':'stopped','stage':stage,'completed':len(report['outcomes']),'reason':str(exc)})
                        raise
                    for (record, fp, _), result in zip(ready, results):
                        settle(record, fp, lambda result=result: returned(result))
                if progress:
                    progress(None, len(report['outcomes']), len(chosen))
            if executor:
                collect(everything=True)
        report["elapsed_seconds"] = time.monotonic() - started
        report['complete']=sum(o['status']=='complete' for o in report['outcomes'])
        report['failed']=sum(o['status']=='failed' for o in report['outcomes'])
        report['unsupported']=sum(o['status']=='unsupported' for o in report['outcomes'])
        if backend is not None and hasattr(backend,'resources'):
            report['resources']=backend.resources()
        save_json(config.output_path("data", f"library/batches/{stage}-{uuid.uuid4().hex}.json"), report)
        atomic_json(config.output_path('data','library/processing-status.json'),{'status':'batch_complete','stage':stage,'completed':len(report['outcomes']),'elapsed_seconds':report['elapsed_seconds']})
        return report


def coverage(config):
    from .retrieval import pilot_records
    selected = pilot_records(config)
    from .asset_structure import asset_type
    types = defaultdict(lambda: {'assets': 0, 'stages': {s: Counter() for s in COVERAGE_STAGES}})
    packs = defaultdict(lambda: {"assets": 0, "stages": {s: Counter() for s in COVERAGE_STAGES}, "captions": Counter(), "owner_review": Counter(),
        'usable_partial_results':0,'source_faults':0,'stage_faults':0,'caption_ai_review':Counter()})
    for record in selected:
        typed = types[asset_type(record)]
        typed['assets'] += 1
        for stage in COVERAGE_STAGES:
            typed['stages'][stage][record['processing'].get(stage, 'pending')] += 1
        pack = packs[record["pack_id"]]
        pack["assets"] += 1
        pack['usable_partial_results'] += bool(record.get('technical') or record.get('description') or record.get('previews'))
        pack['source_faults'] += bool((record.get('inspection_run') or {}).get('source_faults'))
        pack['stage_faults'] += bool(record.get('stage_faults'))
        pack['caption_ai_review'][(record.get('caption_provenance') or {}).get('ai_review','pending')] += 1
        for stage in COVERAGE_STAGES:
            pack["stages"][stage][record["processing"].get(stage, "pending")] += 1
        caption_state=record['processing'].get('caption','pending')
        pack["captions"]['not_processed' if caption_state in {'pending','running'} else caption_summary(config, record)["caption_status"]] += 1
        from .retrieval import current_overlay
        try:
            pack["owner_review"][(current_overlay(config, record) or {}).get("caption_review", "pending")] += 1
        except (ValueError, OSError):
            pack["owner_review"]["faulty_overlay"] += 1
    return {"membership": len(selected), "generation": generation(config), "packs": dict(packs), 'asset_types': dict(types)}


def publish(config):
    work = working(config)
    scope = membership(work)
    index = work.output_path("data", "embeddings/index.sqlite")
    with closing(read_only(index)) as db:
        meta = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM meta")}
        if set(meta.get("pilot_ids", [])) != set(scope["asset_ids"]):
            raise ConfigError("Cannot publish mismatched catalog/index membership")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ConfigError("Cannot publish corrupt index")
        vectors = db.execute('SELECT * FROM vectors').fetchall()
    # Refuse to publish a stale pair, including an owner correction made during indexing.
    from .retrieval import source_check, description_input, preview_file, image_input, checked_vector
    from .publication import snapshot as publication_snapshot
    with publication_snapshot(work):
        current = {r['asset_id']:r for r in records(work)}
        from .asset_structure import validate_collection
        validate_collection(list(current.values()))
        sources = {}
        for row in vectors:
            checked_vector(row, meta['contract_fingerprint'])
            record = current.get(row[1])
            if record is None:
                raise ConfigError('Vector outside current configured membership')
            if row[1] not in sources:
                sources[row[1]]=source_check(work,record)
            if row[5]!=sources[row[1]]:
                raise ConfigError('Stale source/index pair; process changed inputs before publication')
            if row[2]=='description':
                if description_input(work,record)[1]!=row[3]:
                    raise ConfigError('Effective description changed; process its vector before publication')
            else:
                ref=json.loads(row[11])
                preview=next((p for p in record['previews'] if p.get('path')==ref.get('path') and p.get('source_path')==ref.get('source_path')),None)
                if preview is None or image_input(preview)!=row[3]:
                    raise ConfigError('Preview/index pair changed; process its vector before publication')
                preview_file(work,preview)
    if generation(config) != 'legacy':
        if (database_content(config.output_path('data','catalog.sqlite'), 'catalog') == database_content(work.output_path('data','catalog.sqlite'), 'catalog')
                and database_content(config.output_path('data','embeddings/index.sqlite'), 'index') == database_content(index, 'index')
                and membership(config)['fingerprint'] == scope['fingerprint']):
            import stat
            for relative in ('catalog.sqlite','embeddings/index.sqlite','library/membership.json'):
                config.output_path('data',relative).chmod(stat.S_IREAD)
            return {'generation':generation(config),'membership':len(scope['asset_ids']),'no_change':True,'coverage':coverage(work)}
    name = "v_" + uuid.uuid4().hex
    target = replace(config, catalog_generation=name)
    copy_database(work.output_path("data", "catalog.sqlite"), target.output_path("data", "catalog.sqlite"))
    copy_database(index, target.output_path("data", "embeddings/index.sqlite"))
    atomic_json(target.output_path("data", "library/membership.json"), scope)
    import stat
    for relative in ('catalog.sqlite','embeddings/index.sqlite','library/membership.json'):
        target.output_path('data',relative).chmod(stat.S_IREAD)
    receipt = {"generation": name, "membership": len(scope["asset_ids"]), "coverage": coverage(work),
        "catalog_sha256": file_hash(target.output_path("data", "catalog.sqlite")),
        "index_sha256": file_hash(target.output_path("data", "embeddings/index.sqlite")),
        "utc": datetime.now(timezone.utc).isoformat()}
    save_json(config.output_path("data", f"library/publications/{name}.json"), receipt)
    atomic_json(config.output_path("data", "library/active.json"), {"generation": name, "membership_fingerprint": scope["fingerprint"]})
    return receipt


def database_content(path, kind):
    tables = ('metadata','assets','inventory','files') if kind=='catalog' else ('meta','jobs','vectors')
    content = {}
    with closing(read_only(path)) as db:
        for table in tables:
            values = db.execute('SELECT * FROM '+table+' ORDER BY 1').fetchall()
            content[table] = [[hashlib.sha256(value).hexdigest() if isinstance(value,bytes) else value for value in row] for row in values]
    return digest(content)
