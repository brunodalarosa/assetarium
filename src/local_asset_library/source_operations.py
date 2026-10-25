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

from .config import ConfigError, load_config, runtime_command, venv_python
from .publication import atomic_json, read_json
from .sources import (registry, get_source, bound, now, source_status, scan_source,
                      aggregate, read_records, write_membership)
from .gpu_queue import lease, process_alive

RUNNING = {"queued", "scanning", "processing", "publishing", "cancelling", "verifying"}
STAGE_LABELS = {'inspection':'Inspecting assets and rendering previews',
                'caption':'Writing descriptions', 'embeddings':'Preparing search data'}
# Descriptions are optional extra data (decision 0008): importing never generates them.
OPERATION_STAGES = {'process': ('inspection', 'embeddings'), 'describe': ('caption', 'embeddings')}
RUNTIMES = {'inspection': 'mcp', 'caption': 'caption', 'embeddings': 'embedding'}
DESCRIPTIONS_OFF = 'Descriptions are turned off. Turn them on in Settings → General to generate descriptions.'
DESCRIPTIONS_STOPPED = 'Descriptions were turned off in Settings → General; finished descriptions are published.'


def stage_progress(operation, stage, fraction=0):
    stages = OPERATION_STAGES.get(operation, OPERATION_STAGES['process'])
    return .05 + .85 * (stages.index(stage) + fraction) / len(stages)


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
    if operation not in {"scan", "process", "describe"}:
        raise ConfigError("Unknown asset source operation")
    if operation == "describe" and not key:
        raise ConfigError("Choose an asset source to generate descriptions for")
    scoped = bound(config, get_source(config, key)) if key else config
    if key:
        from .sources import validate_directory
        validate_directory(config, str(scoped.source_root))
    if operation in {"process", "describe"} and not get_source(config, key)["enabled"]:
        raise ConfigError("Enable this asset source before processing it")
    if operation in {'process', 'describe'}:
        from .settings import processing_formats
        if not processing_formats(config):
            raise ConfigError('Processing is paused. Select formats in Settings → General before processing assets')
    if operation == 'describe':
        from .settings import descriptions_enabled
        if not descriptions_enabled(config):
            raise ConfigError(DESCRIPTIONS_OFF)
    if operation == 'describe' and not (source_status(config, get_source(config, key)).get('descriptions') or {}).get('missing'):
        raise ConfigError('Every asset that can be described already has a description or a recorded failure')
    if operation == 'scan' and not key and not any(s['enabled'] for s in registry(config)['sources']):
        return {'status': 'idle', 'reason': None}  # Nothing to scan (a fresh install); no worker is started.
    python = venv_python(config.project_root)
    # Reserve and spawn under one short lock, independent of a potentially long
    # running processing lease. Duplicate clicks cannot start duplicate work.
    with lease(config, "source-operation-start", resource="sources"):
        if active_operation(scoped):
            return {"status": "busy", "reason": "This operation is already running"}
        token = uuid.uuid4().hex
        state(scoped, token=token, pid=os.getpid(), status="queued", phase="Queued", progress=0,
              operation=operation, key=key, reason=None, current_asset=None)
        command = [str(python), str(config.project_root / "scripts/source-operation.py"), operation, "--token", token]
        if key:
            command.extend(["--source", key])
        log = scoped.output_path("data", "library/operations/" + token + ".log")
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            with log.open("w", encoding="utf-8") as stream:
                # Own session off Windows: Ctrl+C or a closed terminal in a CLI never kills the work.
                process = subprocess.Popen(command, cwd=config.project_root, stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, start_new_session=os.name != "nt")
            # The child waits for this handoff before updating the same state.
            state(scoped, pid=process.pid)
        except OSError as exc:
            if not python.is_file():
                command = r'.\scripts\uv.ps1 sync --locked' if os.name == 'nt' else './scripts/uv.sh sync --locked'
                exc = ConfigError('The base environment (.venv) is missing, so source operations cannot start. '
                                  'Create it from the project folder with: ' + command)
            state(scoped, status="faulty", reason=str(exc))
            raise exc
    if operation == "describe":
        from .notifications import clear_ready
        clear_ready(config, get_source(config, key)["id"])
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


BUDGET_REACHED = ("Storage budget reached. Increase it in Settings → General, then process this source again; "
                  "completed work is preserved")


def storage_base(config, token):
    # Receipts include external metadata as well as the project, deduplicated by
    # file identity. Model/runtime installations and original files are excluded.
    from .source_storage import receipt
    from .settings import storage_budget
    base = receipt(config, "before-" + token)["totals"]["allocated_bytes"]
    if base >= storage_budget(config)['total_allocated_bytes']:
        raise ConfigError(BUDGET_REACHED)
    return base


def check_budget(config, label, base):
    from .source_storage import receipt
    from .settings import storage_budget
    measured = receipt(config, label)["totals"]["allocated_bytes"]
    budgets = storage_budget(config)
    if measured > budgets["total_allocated_bytes"] or measured - base > budgets["peak_additional_allocated_bytes"]:
        raise ConfigError(BUDGET_REACHED)


def run_stages(config, source, scoped, token, operation, base):
    """Run each stage in its own locked runtime; returns False when cancelled."""
    for stage in OPERATION_STAGES[operation]:
        if cancelled(scoped, token):
            return False
        state(scoped, status="processing", phase=STAGE_LABELS[stage], stage=stage, progress=stage_progress(operation, stage))
        runtime = RUNTIMES[stage]
        command = [*runtime_command(config.project_root, runtime),
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
        check_budget(config, stage + "-" + token, base)
    return not cancelled(scoped, token)


def publish_and_verify(config, source, scoped, phase):
    state(scoped, status="publishing", phase=phase, progress=.90, current_asset=None)
    publish_source(scoped)
    state(scoped, status="publishing", phase="Updating searches", progress=.95)
    aggregate(config)
    state(scoped, status="verifying", phase="Scanning to verify publication", progress=.98)
    return scan_source(config, source)


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
    base = storage_base(config, token)
    if not run_stages(config, source, scoped, token, 'process', base):
        state(scoped, status="cancelled", phase="Cancelled; completed assets saved", current_asset=None)
        return
    status = publish_and_verify(config, source, scoped, "Publishing source")
    check_budget(config, "published-" + token, base)
    state(scoped, status="complete_with_faults" if status["failed"] or status["needs_processing"] else "complete",
          phase="Finished with recorded issues" if status["failed"] or status["needs_processing"] else "Up to date and published",
          progress=1, current_asset=None)
    from .notifications import notify_ready
    notify_ready(config, source, (status.get("descriptions") or {}).get("missing", 0))


def description_counts(scoped):
    from collections import Counter
    from .incremental import working
    from .settings import processing_formats, processing_eligible
    from .sources import description_state
    formats = processing_formats(scoped)
    return Counter(description_state(r) for r in read_records(working(scoped)) if processing_eligible(r, formats))


DESCRIBE_END = {'complete': ('complete', 'Descriptions generated and published'),
                'complete_with_failures': ('complete_with_faults', 'Descriptions generated; some failed and were recorded'),
                'cancelled': ('cancelled', 'Cancelled; finished descriptions are published'),
                'stopped': ('faulty', 'Stopped; finished descriptions are published')}


def describe_source(config, source, token):
    """Generate missing descriptions and their vectors, then publish what finished.

    Descriptions are optional extra data (decision 0008). Recorded description
    failures are kept, not retried. A cancel or stop still publishes completed
    descriptions, and every run ends with one report notification.
    """
    from .notifications import notify_report
    scoped = bound(config, source)
    started = time.monotonic()
    state(scoped, status="scanning", phase="Checking source", progress=.01)
    scan_source(config, source)
    ensure_index(config, scoped)
    before = description_counts(scoped)
    state(scoped, status='processing', phase='Preparing descriptions', progress=.02)
    outcome, reason = None, None
    try:
        base = storage_base(config, token)
        if not run_stages(config, source, scoped, token, 'describe', base):
            outcome = 'cancelled'
    except ConfigError as exc:
        # Machine limits (GPU memory, storage budget) stop the run; assets stay pending.
        outcome, reason = 'stopped', str(exc)
    publish_and_verify(config, source, scoped, "Publishing descriptions")
    after = description_counts(scoped)
    failed = max(0, after['failed'] - before['failed'])
    outcome = outcome or ('complete_with_failures' if failed else 'complete')
    notify_report(config, source, token, outcome, written=max(0, after['complete'] - before['complete']),
                  failed=failed, remaining=after['missing'], reason=reason,
                  elapsed_seconds=round(time.monotonic() - started))
    status, phase = DESCRIBE_END[outcome]
    state(scoped, status=status, phase=phase, progress=1, current_asset=None, reason=reason)


def worker_stage(config, source, stage, token):
    from .incremental import process
    from .library_index import index_library
    from .incremental import working
    scoped = bound(config, source)
    from .settings import processing_formats
    backend = None
    operation = operation_status(scoped).get("operation", "process")
    # Description runs only describe assets whose renders are ready, so unfinished
    # imports never gain recorded description faults.
    only = None
    if stage == "caption":
        from .sources import description_state
        only = {r["asset_id"] for r in read_records(working(scoped)) if description_state(r) == "missing"}
    def on_progress(identifier, completed, total):
        state(scoped, status="cancelling" if cancelled(scoped, token) else "processing",
              phase=(finishing(stage) if cancelled(scoped, token) else STAGE_LABELS[stage]),
              stage=stage, completed=completed, total=total, current_asset=identifier,
              progress=stage_progress(operation, stage, completed / max(1, total)))
    for _ in range(10000):
        if cancelled(scoped, token):
            return
        if not processing_formats(config):
            return
        from .settings import descriptions_enabled
        if stage == "caption" and not descriptions_enabled(config):
            # Turned off while running: stop after the finished batch; its descriptions are kept.
            atomic_json(stage_fault_path(scoped, token), {"reason": DESCRIPTIONS_STOPPED, "utc": now()})
            raise ConfigError(DESCRIPTIONS_STOPPED)
        preview = process(scoped, stage, limit=1000, dry_run=True, asset_ids=only)
        if not preview.get("pending"):
            return
        from . import engines
        from .description_engines import EngineStop
        with lease(config, "batch-source-" + stage, timeout=30) if stage != "inspection" else _nullcontext():
            try:
                if stage != "inspection" and backend is None:
                    backend = engines.description_engine(scoped) if stage == "caption" else engines.embedder(scoped)
                result = process(scoped, stage, limit=1000, backend=backend, asset_ids=only,
                                 cancelled=lambda: cancelled(scoped, token), progress=on_progress)
            except EngineStop as exc:
                # A machine limit, not an asset fault: the coordinator shows this reason.
                atomic_json(stage_fault_path(scoped, token), {"reason": str(exc), "utc": now()})
                raise
        if cancelled(scoped, token):
            return
        if not result.get("outcomes") and not result.get("processed"):
            raise ConfigError("No processing progress; source work preserved for review")
    raise ConfigError("Source processing exceeded its bounded batches")


from contextlib import nullcontext as _nullcontext
