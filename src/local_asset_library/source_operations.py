"""Durable, cancellable source operations. Cancellation never kills a worker."""
from contextlib import closing, contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid

from .config import ConfigError, load_config
from .publication import atomic_json, read_json
from .sources import (registry, get_source, bound, now, source_status, scan_source,
                      aggregate, read_records, write_membership)
from .gpu_queue import lease, process_alive

RUNNING = {"queued", "scanning", "processing", "publishing", "cancelling", "verifying"}
STAGE_LABELS = {'inspection':'Inspecting assets and rendering previews',
                'caption':'Writing descriptions', 'embeddings':'Preparing search data'}


def operation_status(config):
    path = config.output_path("data", "library/source-operation.json")
    if not path.exists():
        return {"status": "idle", "progress": 0}
    value = read_json(path)
    if value.get("status") in RUNNING and value.get("pid") and not process_alive(value["pid"]):
        return dict(value, status="interrupted", reason="Operation stopped; completed asset checkpoints are preserved")
    if value.get("status") in RUNNING and cancelled(config, value.get("token")):
        return dict(value, status="cancelling", phase=(finishing(value.get('stage'))
                    if value.get('current_asset') else "Stopping safely; completed assets are saved"))
    return value


def finishing(stage):
    # Descriptions are generated in batches; cancelling waits for the whole batch.
    return "Finishing the current batch before stopping" if stage == 'caption' else "Finishing the current asset before stopping"


def stage_fault_path(scoped, token):
    return scoped.output_path("data", "library/operations/" + token + "-stage-fault.json")


def active_operation(config):
    return operation_status(config).get("status") in RUNNING


def state(config, **updates):
    path = config.output_path("data", "library/source-operation.json")
    value = read_json(path) if path.exists() else {}
    if ('progress' in updates and updates.get('token', value.get('token')) == value.get('token')
            and updates.get('status') in RUNNING):
        updates['progress'] = max(value.get('progress', 0), updates['progress'])
    value.update(updates, updated_utc=now())
    atomic_json(path, value)
    return value


def cancelled(config, token):
    path = config.output_path("data", "library/source-cancel.json")
    return path.exists() and read_json(path).get("token") == token


def cancel(config):
    current = operation_status(config)
    if current.get("status") not in RUNNING:
        return {"status": "idle"}
    atomic_json(config.output_path("data", "library/source-cancel.json"), {"token": current["token"], "requested_utc": now()})
    return {"status": "cancelling", "reason": "Stopping after the current asset; saved work will be preserved"}


@contextmanager
def operation_lease(config, scoped, token):
    """Wait between operations while allowing queued work to be cancelled."""
    acquired = None
    while not cancelled(scoped, token):
        candidate = lease(config, 'source-operation', timeout=.2, resource='operations')
        try:
            candidate.__enter__()
            acquired = candidate
            break
        except ConfigError as exc:
            if 'queue busy' not in str(exc):
                raise
            state(scoped,status='queued',phase='Waiting for another source operation')
            time.sleep(.25)
    if acquired is None:
        state(scoped,status='cancelled',phase='Cancelled before processing started')
        yield False
        return
    try:
        yield True
    finally:
        acquired.__exit__(None,None,None)


def start(config, operation, key=None):
    if operation not in {"scan", "process"}:
        raise ConfigError("Unknown asset source operation")
    scoped = bound(config, get_source(config, key)) if key else config
    if key:
        from .sources import validate_directory
        validate_directory(config, str(scoped.source_root))
    if operation == "process" and not get_source(config, key)["enabled"]:
        raise ConfigError("Enable this asset source before processing it")
    if operation == 'process':
        from .settings import processing_formats
        if not processing_formats(config):
            raise ConfigError('Processing is paused. Select formats in Settings → General before processing assets')
    # Reserve and spawn under one short lock, independent of a potentially long
    # running processing lease. Duplicate clicks cannot start duplicate work.
    with lease(config, "source-operation-start", resource="sources"):
        if active_operation(scoped):
            return {"status": "busy", "reason": "This operation is already running"}
        token = uuid.uuid4().hex
        state(scoped, token=token, pid=os.getpid(), status="queued", phase="Queued", progress=0,
              operation=operation, key=key, reason=None, current_asset=None)
        command = [str(config.project_root / ".venv/Scripts/python.exe"),
                   str(config.project_root / "scripts/source-operation.py"), operation, "--token", token]
        if key:
            command.extend(["--source", key])
        log = scoped.output_path("data", "library/operations/" + token + ".log")
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            with log.open("w", encoding="utf-8") as stream:
                process = subprocess.Popen(command, cwd=config.project_root, stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            # The child waits for this handoff before updating the same state.
            state(scoped, pid=process.pid)
        except OSError as exc:
            state(scoped, status="faulty", reason=str(exc))
            raise
    return {"status": "started", "token": token}


def scan_all(config, token, key=None):
    scoped = bound(config, get_source(config, key)) if key else config
    sources = [get_source(config, key)] if key else [s for s in registry(config)["sources"] if s["enabled"]]
    faults = []
    for i, source in enumerate(sources):
        if cancelled(scoped, token):
            state(scoped, status="cancelled", phase="Scan cancelled")
            return
        state(scoped, status="scanning", phase="Scanning " + source["name"], progress=i / max(1, len(sources)))
        try:
            scan_source(config, source)
        except (OSError, ValueError, sqlite3.Error) as exc:
            fault = {"key": source["key"], "reason": str(exc), "status": "faulty", "utc": now()}
            faults.append(fault)
            # A missing/unwritable source must never be recreated just to save
            # its error. Keep availability diagnostics centrally and continue.
            diagnostic = {'scan_fault':str(exc), 'reason':'Source scan failed; previous results and evidence retained',
                          'fault_utc':now()}
            fault_root = config.project_root / 'data/library/source-faults'
            atomic_json(fault_root / 'history' / (source['id'] + '-' + uuid.uuid4().hex + '.json'),diagnostic)
            atomic_json(fault_root / (source['id'] + '.json'),diagnostic)
    aggregate(config)
    state(scoped, status="complete_with_faults" if faults else "complete", phase="Scan complete", progress=1, faults=faults)


def ensure_index(config, scoped):
    from .incremental import working
    from .retrieval import index_database
    from .catalog import encoded
    path = working(scoped).output_path("data", "embeddings/index.sqlite")
    if path.exists():
        return
    # Copy only the verified model contract, never another source's vectors.
    base = config.output_path("data", "embeddings/index.sqlite")
    metadata = {}
    if base.exists():
        with closing(sqlite3.connect(base.as_uri() + "?mode=ro", uri=True)) as db:
            metadata = dict(db.execute("SELECT key,value FROM meta"))
    if not metadata.get('contract'):
        capability = config.project_root / 'data/library/embedding-contract.json'
        if capability.exists():
            metadata.update(read_json(capability))
    metadata["pilot_ids"] = encoded([r["asset_id"] for r in read_records(working(scoped))])
    with closing(index_database(working(scoped))) as db, db:
        db.executemany("INSERT INTO meta VALUES (?,?)", list(metadata.items()))


def publish_source(scoped):
    """Publish checkpoints, including usable partial results, as one generation."""
    from .incremental import working, copy_database, database_content
    from .publication import generation
    work = working(scoped)
    current = read_records(work)
    ids = {r["asset_id"] for r in current}
    index = work.output_path("data", "embeddings/index.sqlite")
    from .catalog import encoded
    with closing(sqlite3.connect(index)) as db, db:
        for table in ("vectors", "jobs"):
            for job, identifier in db.execute("SELECT job_id,asset_id FROM " + table).fetchall():
                if identifier not in ids:
                    db.execute("DELETE FROM " + table + " WHERE job_id=?", (job,))
        db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", ("pilot_ids", encoded(sorted(ids))))
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ConfigError("Source index integrity check failed")
    if scoped.output_path("data", "library/active.json").exists():
        if (database_content(scoped.output_path("data", "catalog.sqlite"), "catalog") ==
                database_content(work.output_path("data", "catalog.sqlite"), "catalog") and
                database_content(scoped.output_path("data", "embeddings/index.sqlite"), "index") == database_content(index, "index")):
            return generation(scoped)
    target = replace(scoped, catalog_generation="v_" + uuid.uuid4().hex)
    copy_database(work.output_path("data", "catalog.sqlite"), target.output_path("data", "catalog.sqlite"))
    copy_database(index, target.output_path("data", "embeddings/index.sqlite"))
    write_membership(target, current)
    atomic_json(scoped.output_path("data", "library/active.json"), {"generation": target.catalog_generation})
    return target.catalog_generation


def process_source(config, source, token):
    scoped = bound(config, source)
    from .settings import processing_formats
    if not processing_formats(config):
        state(scoped, status='complete', phase='Processing paused: no formats selected', progress=1, current_asset=None)
        return
    state(scoped, status="scanning", phase="Checking source", progress=.01)
    scan_source(config, source)
    ensure_index(config, scoped)
    state(scoped, status='processing', phase='Preparing processing', progress=.02)
    # Receipts include external metadata as well as the project, deduplicated by
    # file identity. Model/runtime installations and original files are excluded.
    from .source_storage import receipt
    before = receipt(config, "before-" + token)
    from .settings import storage_budget
    budgets = storage_budget(config)
    base = before["totals"]["allocated_bytes"]
    if base >= budgets['total_allocated_bytes']:
        raise ConfigError('Storage budget reached. Increase it in Settings → General, then process this source again; completed work is preserved')
    stages = [("inspection", ".venv-mcp"), ("caption", ".venv-caption"), ("embeddings", ".venv-embedding")]
    for i, (stage, environment) in enumerate(stages):
        if cancelled(scoped, token):
            state(scoped, status="cancelled", phase="Cancelled; completed assets saved", current_asset=None)
            return
        state(scoped, status="processing", phase=STAGE_LABELS[stage], stage=stage, progress=.05 + .27 * i)
        runtime = {'inspection':'mcp','caption':'caption','embeddings':'embedding'}[stage]
        command = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                   str(config.project_root/'scripts'/(runtime+'-runtime.ps1')),
                   'run','--locked','--no-sync','--offline','--project',str(config.project_root/'runtime'/runtime),
                   'python',str(config.project_root / "scripts/source-operation.py"), "stage", "--source", source["key"],
                   "--stage", stage, "--token", token]
        env = os.environ.copy()
        env.update(PYTHONPATH=str(config.project_root / "src"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                   HF_HUB_DISABLE_TELEMETRY="1")
        completed = subprocess.run(command, cwd=config.project_root, env=env,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if completed.returncode:
            fault = stage_fault_path(scoped, token)
            raise ConfigError(read_json(fault)["reason"] if fault.exists() else
                              "Source processing worker failed; see its saved operation log")
        measured = receipt(config, stage + "-" + token)
        budgets = storage_budget(config)
        if (measured["totals"]["allocated_bytes"] > budgets["total_allocated_bytes"] or
                measured["totals"]["allocated_bytes"] - base > budgets["peak_additional_allocated_bytes"]):
            raise ConfigError("Storage budget reached. Increase it in Settings → General, then process this source again; completed work is preserved")
    if cancelled(scoped, token):
        state(scoped, status="cancelled", phase="Cancelled; completed assets saved", current_asset=None)
        return
    state(scoped, status="publishing", phase="Publishing source", progress=.90, current_asset=None)
    publish_source(scoped)
    state(scoped, status="publishing", phase="Updating searches", progress=.95)
    aggregate(config)
    state(scoped, status="verifying", phase="Scanning to verify publication", progress=.98)
    status = scan_source(config, source)
    measured = receipt(config, "published-" + token)
    budgets = storage_budget(config)
    if (measured["totals"]["allocated_bytes"] > budgets["total_allocated_bytes"] or
            measured["totals"]["allocated_bytes"] - base > budgets["peak_additional_allocated_bytes"]):
        raise ConfigError("Storage budget reached. Increase it in Settings → General, then process this source again; completed work is preserved")
    state(scoped, status="complete_with_faults" if status["failed"] or status["needs_processing"] else "complete",
          phase="Finished with recorded issues" if status["failed"] or status["needs_processing"] else "Up to date and published",
          progress=1, current_asset=None)


def worker_stage(config, source, stage, token):
    from .incremental import process
    from .library_index import index_library
    from .incremental import working
    scoped = bound(config, source)
    from .settings import processing_formats
    backend = None
    stage_index = {"inspection": 0, "caption": 1, "embeddings": 2}[stage]
    def on_progress(identifier, completed, total):
        state(scoped, status="cancelling" if cancelled(scoped, token) else "processing",
              phase=(finishing(stage) if cancelled(scoped, token) else STAGE_LABELS[stage]),
              stage=stage, completed=completed, total=total, current_asset=identifier,
              progress=.05 + .27 * (stage_index + completed / max(1, total)))
    for _ in range(10000):
        if cancelled(scoped, token):
            return
        if not processing_formats(config):
            return
        preview = process(scoped, stage, limit=1000, dry_run=True)
        if not preview.get("pending"):
            return
        with lease(config, "batch-source-" + stage, timeout=30) if stage != "inspection" else _nullcontext():
            if stage != "inspection" and backend is None:
                if stage == "caption":
                    from .caption_backend import QwenBackend
                    backend = QwenBackend(scoped, json.loads((config.project_root / "docs/caption-model.json").read_text()))
                else:
                    from .embedding_backend import EmbeddingBackend
                    backend = EmbeddingBackend(scoped)
            from .caption_batching import GpuMemoryError
            try:
                result = process(scoped, stage, limit=1000, backend=backend,
                                 cancelled=lambda: cancelled(scoped, token), progress=on_progress)
            except GpuMemoryError as exc:
                # A machine limit, not an asset fault: the coordinator shows this reason.
                atomic_json(stage_fault_path(scoped, token), {"reason": str(exc), "utc": now()})
                raise
        if cancelled(scoped, token):
            return
        if not result.get("outcomes") and not result.get("processed"):
            raise ConfigError("No processing progress; source work preserved for review")
    raise ConfigError("Source processing exceeded its bounded batches")


from contextlib import nullcontext as _nullcontext
