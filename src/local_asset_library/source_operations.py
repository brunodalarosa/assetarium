"""Durable, cancellable source operations. Cancellation never kills a worker; only its owning app going away does."""
from contextlib import closing, contextmanager
from dataclasses import replace
import json
import logging
import os
import sqlite3
import signal
import subprocess
import threading
import time
import uuid

from .config import ConfigError, runtime_command, venv_python, with_saved_blender
from .publication import atomic_json, read_json, read_only
from .sources import (registry, get_source, bound, now, source_status, scan_source,
                      aggregate, read_records, write_membership)
from .gpu_queue import lease, process_alive

RUNNING = {"queued", "scanning", "processing", "publishing", "cancelling", "verifying"}
STAGE_LABELS = {'inspection':'Inspecting assets and rendering previews',
                'caption':'Writing descriptions', 'embeddings':'Preparing search data'}
# Descriptions are optional extra data (decision 0033): importing never generates them.
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
    if 'phase' in updates and 'metrics' not in updates:
        updates['metrics'] = None
    if 'stage' in updates and updates['stage'] != value.get('stage') and 'completed' not in updates:
        updates.update(completed=None, total=None)
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


def start(config, operation, key=None, asset_ids=None, queue_item=None, owner=None, quiet=False, mode=None):
    """Start a durable operation; ``asset_ids`` narrows process/describe to a queue item's resolved scope.

    ``mode`` (describe, named assets only): ``retry`` generates their recorded failures once more on the owner's
    request; ``edited`` writes no text and only rebuilds search vectors after an owner edit, then publishes.

    ``quiet`` marks the app's launch check of every folder (decision 0027): the app shows it as a hint, not a scan.

    ``owner`` is the open app's process ID: the operation stops with that app (``watch_owner``).
    """
    if operation not in {"scan", "process", "describe", "render-test", "search-check"}:
        raise ConfigError("Unknown asset source operation")
    if operation == "search-check":
        from .engines import search_runtime_fault
        if key or (fault := search_runtime_fault(config)):
            raise ConfigError(fault if not key else "The search check is not tied to a library folder")
    if operation == "render-test" and (key or not (blender := with_saved_blender(config).blender) or not blender.exists()):
        raise ConfigError("Set up Blender first (Settings → General → Setup), then test render speed")
    if operation == "describe" and not key:
        raise ConfigError("Choose an asset source to generate descriptions for")
    scoped = bound(config, get_source(config, key)) if key else config
    if key:
        from .sources import validate_directory
        validate_directory(config, str(scoped.source_root))
    if operation in {"process", "describe"} and not get_source(config, key)["enabled"]:
        raise ConfigError("Enable this asset source before processing it")
    if operation in {'process', 'describe'}:
        from .settings import used_formats
        if not used_formats(config):
            raise ConfigError('Processing is paused. Select formats in Settings → General before processing assets')
    if mode not in {None, 'retry', 'edited'} or (mode and (operation != 'describe' or not asset_ids)):
        raise ConfigError('Try again and search updates name the assets of a description run')
    if operation == 'describe' and mode != 'edited':
        from .settings import descriptions_enabled
        if not descriptions_enabled(config):
            raise ConfigError(DESCRIPTIONS_OFF)
    if operation == 'describe' and asset_ids is None and not (source_status(config, get_source(config, key)).get('descriptions') or {}).get('missing'):
        raise ConfigError('Every asset that can be described already has a description or a recorded failure')
    if operation == 'scan' and not key and not any(s['enabled'] for s in registry(config)['sources']):
        return {'status': 'idle', 'reason': None}  # Nothing to scan (a fresh install); no worker is started.
    python = venv_python(config.project_root)
    # Reserve and spawn under one short lock, independent of a potentially long
    # running processing lease. Duplicate clicks cannot start duplicate work.
    with lease(config, "source-operation-start", resource="sources"):
        if active_operation(scoped):
            return {"status": "busy", "reason": "Another operation is running; try again when it finishes"
                    if operation == "render-test" else "This operation is already running"}
        token = uuid.uuid4().hex
        state(scoped, token=token, pid=os.getpid(), status="queued", phase="Queued", progress=0,
              operation=operation, key=key, reason=None, current_asset=None, completed=None, total=None, stage=None,
              asset_ids=sorted(asset_ids) if asset_ids is not None else None, queue_item=queue_item, owner=owner,
              quiet=bool(quiet and operation == 'scan' and not key), changes=None, mode=mode)
        command = [str(python), str(config.project_root / "scripts/source-operation.py"), operation, "--token", token]
        if key:
            command.extend(["--source", key])
        if owner:
            command.extend(["--owner", str(owner)])
        log = scoped.output_path("data", "library/operations/" + token + ".log")
        log.parent.mkdir(parents=True, exist_ok=True)
        try:
            with log.open("w", encoding="utf-8") as stream:
                # Own session off Windows: Ctrl+C or a closed terminal in a CLI never kills the work.
                process = subprocess.Popen(command, cwd=config.project_root, stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, start_new_session=os.name != "nt")
            # The child waits for this handoff before updating the same state.
            state(scoped, pid=process.pid)
            from .logs import kv
            logging.getLogger(__name__).info('Operation started · %s', kv(operation=operation, folder=key, pid=process.pid,
                                                                           token=token[:8], output=log))
        except OSError as exc:
            if not python.is_file():
                command = r'.\scripts\uv.ps1 sync --locked' if os.name == 'nt' else './scripts/uv.sh sync --locked'
                exc = ConfigError('The base environment (.venv) is missing, so source operations cannot start. '
                                  'Create it from the project folder with: ' + command)
            state(scoped, status="faulty", reason=str(exc))
            raise exc
    if operation == "describe" and mode is None:
        from .notifications import clear_ready
        clear_ready(config, get_source(config, key)["id"])
    return {"status": "started", "token": token}


def _wanted_path(config):
    return config.output_path("data", "library/scans-wanted.json")


def want_scan(config, key):
    """Remember a scan that could not start because its folder was busy; it starts when that operation ends."""
    with lease(config, "scans-wanted", resource="sources"):
        target = _wanted_path(config)
        keys = read_json(target).get("keys", []) if target.exists() else []
        atomic_json(target, {"keys": sorted(set(keys) | {key})})


def start_wanted(config):
    """Start the remembered scans (every operation calls this as it ends); one still busy stays remembered."""
    target = _wanted_path(config)
    if not target.exists():
        return []
    with lease(config, "scans-wanted", resource="sources"):
        keys = read_json(target).get("keys", [])
        atomic_json(target, {"keys": []})
    left, started = [], []
    for key in keys:
        try:
            (started if start(config, "scan", key).get("status") == "started" else left).append(key)
        except ConfigError:
            continue  # The folder was removed or cannot be read; its own status says why.
    if left:
        for key in left:
            want_scan(config, key)
    return started


def watch_owner(config, scoped, owner, poll=1.0, end=None):
    """Work the app started never outlives it: once that app is gone, closed or crashed, this operation and its
    child processes stop at once. A crash is logged with its reason and its queue items go to Recent."""
    def run():
        while process_alive(owner):
            time.sleep(poll)
        from .logs import kv
        from .processing_queue import owner_gone
        try:
            closed = owner_gone(config, owner)
        except Exception:
            closed = False
        reason = ('Stopped when you closed Assetarium' if closed
                  else 'Assetarium closed unexpectedly; this run stopped with it. Finished assets are saved.')
        state(scoped, status='cancelled' if closed else 'faulty', phase='Stopped', reason=reason)
        logging.getLogger(__name__).log(logging.INFO if closed else logging.ERROR, 'Operation stopped with its app · %s',
                                        kv(app=owner, reason=reason))
        (end or end_tree)()
    thread = threading.Thread(target=run, name='owner-watch', daemon=True)
    thread.start()
    return thread


def end_tree():
    """End this operation process and every process it started (renders, description and search runtimes)."""
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(os.getpid())], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.killpg(os.getpgrp(), signal.SIGKILL)  # Started in its own session: the group is this operation.
    finally:
        os._exit(1)


def scan_all(config, token, key=None):
    scoped = bound(config, get_source(config, key)) if key else config
    sources = [get_source(config, key)] if key else [s for s in registry(config)["sources"] if s["enabled"]]
    faults, changes = [], {'new': 0, 'changed': 0, 'removed': 0}
    for i, source in enumerate(sources):
        if cancelled(scoped, token):
            state(scoped, status="cancelled", phase="Scan cancelled")
            return
        state(scoped, status="scanning", phase="Scanning " + source["name"], progress=i / max(1, len(sources)))
        try:
            found = scan_source(config, source, progress=scan_reporter(scoped, source['name'])).get('changes') or {}
            for name in changes:
                changes[name] += found.get(name, 0)
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
    state(scoped, phase='Publishing library', metrics=dict(phase='Publishing library', completed=len(sources), total=None, unit='library folders'))
    aggregate(config)
    state(scoped, status="complete_with_faults" if faults else "complete", phase="Scan complete", progress=1, faults=faults, metrics=None,
          changes=changes)


def scan_reporter(config, source_name=None):
    """Persist measured scan progress at most twice per second, plus phase boundaries."""
    previous = [None, 0.0, None]
    def report(metrics):
        if source_name:
            metrics = dict(metrics, source_name=source_name)
        phase, tick = metrics['phase'], time.monotonic()
        finished = metrics.get('total') is not None and metrics['completed'] == metrics['total']
        if phase != previous[0] or tick - previous[1] >= .5 or (finished and metrics != previous[2]):
            state(config, phase=phase, metrics=metrics)
            previous[:] = [phase, tick, dict(metrics)]
    return report


def ensure_index(config, scoped):
    from .incremental import working
    from .retrieval import index_database, INDEX_IDS_KEY, current_meta
    from .catalog import encoded
    path = working(scoped).output_path("data", "embeddings/index.sqlite")
    if path.exists():
        return
    # Copy only the verified model contract, never another source's vectors.
    base = config.output_path("data", "embeddings/index.sqlite")
    metadata = {}
    if base.exists():
        with closing(read_only(base)) as db:
            metadata = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM meta")}
    if not metadata.get('contract'):
        capability = config.project_root / 'data/library/embedding-contract.json'
        if capability.exists():
            metadata.update({k: json.loads(v) for k, v in read_json(capability).items()})
    metadata = current_meta(metadata)
    metadata[INDEX_IDS_KEY] = [r["asset_id"] for r in read_records(working(scoped))]
    with closing(index_database(working(scoped))) as db, db:
        db.executemany("INSERT INTO meta VALUES (?,?)", [(k, encoded(v)) for k, v in metadata.items()])


def publish_source(scoped):
    """Publish checkpoints, including usable partial results, as one generation."""
    from .incremental import working, copy_database, database_content
    from .publication import generation
    work = working(scoped)
    current = read_records(work)
    ids = {r["asset_id"] for r in current}
    index = work.output_path("data", "embeddings/index.sqlite")
    from .catalog import encoded
    from .retrieval import INDEX_IDS_KEY, LEGACY_NAMES, VERSION
    with closing(sqlite3.connect(index)) as db, db:
        for table in ("vectors", "jobs"):
            for job, identifier in db.execute("SELECT job_id,asset_id FROM " + table).fetchall():
                if identifier not in ids:
                    db.execute("DELETE FROM " + table + " WHERE job_id=?", (job,))
        db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (INDEX_IDS_KEY, encoded(sorted(ids))))
        db.execute("DELETE FROM meta WHERE key=?", (LEGACY_NAMES["ids"],))
        db.execute("UPDATE meta SET value=? WHERE key='version' AND value=?", (encoded(VERSION), encoded(LEGACY_NAMES["version"])))
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


def stage_runtime(config, stage):
    """(environment wrapper, runtime project) for a stage, following the engine and search device settings.

    A local model server needs no Torch, so its descriptions run in the app environment (decision 0018);
    CPU search uses the CPU-only lock installed into the same search environment.
    """
    from . import engines
    runtime = RUNTIMES[stage]
    if stage == 'caption' and engines.active(config)['engine'] == engines.SERVER:
        return 'mcp', 'mcp'
    if stage == 'embeddings' and engines.search_device(config) == 'cpu':
        return runtime, 'embedding-cpu'
    return runtime, runtime


def run_stages(config, source, scoped, token, operation, base):
    """Run each stage in its own locked runtime; returns False when cancelled."""
    for stage in OPERATION_STAGES[operation]:
        if stage == 'caption' and operation_status(scoped).get('mode') == 'edited':
            continue  # The owner wrote the text; only search follows it.
        if cancelled(scoped, token):
            return False
        state(scoped, status="processing", phase=STAGE_LABELS[stage], stage=stage, progress=stage_progress(operation, stage))
        runtime, project = stage_runtime(config, stage)
        command = [*runtime_command(config.project_root, runtime),
                   'run','--locked','--no-sync','--offline','--project',str(config.project_root/'runtime'/project),
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
    return scan_source(config, source, progress=scan_reporter(scoped))


def process_source(config, source, token):
    scoped = bound(config, source)
    from .settings import used_formats
    if not used_formats(config):
        state(scoped, status='complete', phase='Processing paused: no formats selected', progress=1, current_asset=None)
        return
    state(scoped, status="scanning", phase="Checking source", progress=.01)
    scan_source(config, source, progress=scan_reporter(scoped))
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


def search_check(config, token):
    """Run Run check (decision 0031) in the search runtime: two built-in sample images, never library assets."""
    from .search_check import IMAGES
    runtime, project = stage_runtime(config, "embeddings")
    state(config, status="processing", phase="Loading the search model for the one-time search check", progress=.1)
    command = [*runtime_command(config.project_root, runtime), "run", "--locked", "--no-sync", "--offline", "--project",
               str(config.project_root / "runtime" / project), "python", "-m", "local_asset_library.search_check"]
    env = os.environ.copy()
    env.update(PYTHONPATH=str(config.project_root / "src"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    completed = subprocess.run(command, cwd=config.project_root, env=env, capture_output=True, text=True, errors="replace",
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if completed.returncode:
        lines = [line for line in (completed.stderr or completed.stdout).splitlines() if line.strip()]
        reason = "The search check did not pass: " + (lines[-1][:400] if lines else f"exit code {completed.returncode}")
        state(config, status="faulty", phase="Search check failed", reason=reason, progress=1)
        raise ConfigError(reason)
    state(config, status="complete", phase=f"Search check passed on {len(list(IMAGES.glob('*.png')))} built-in images", progress=1)


def render_test(config, token):
    """The owner-started render speed test (decision 0034); waits for processing like other operations."""
    from .render_devices import label, run
    steps = [0]

    def progress(phase):
        steps[0] += 1
        state(config, status="processing", phase=phase, progress=min(.95, .05 + .08 * steps[0]))
    state(config, status="processing", phase="Listing render devices", progress=.02)
    result = run(config, progress, cancelled=lambda: cancelled(config, token))
    if result["cancelled"]:
        state(config, status="cancelled", phase="Speed test cancelled; the previous result is kept", progress=1)
        return
    best = next((r for r in result["results"] if r["key"] == result["chosen"]), None)
    phase = ("Speed test finished: " + best["label"] + f", {best['best']['processes']} at a time"
             if best else "Speed test finished without a working device")
    from . import engines
    if engines.search_device(config) == "cpu":
        searched = search_test(config, token)
        if cancelled(config, token):
            state(config, status="cancelled", phase="Search speed test cancelled; the previous search result is kept", progress=1)
            return
        phase += "; search data " + searched
    state(config, status="complete", progress=1, phase=phase)


def search_test(config, token):
    """The search part of the speed test, in the CPU search runtime; a missing runtime or model skips it."""
    from .search_speed import saved
    state(config, status="processing", phase="Testing search speed", progress=.9)
    runtime, project = stage_runtime(config, "embeddings")
    command = [*runtime_command(config.project_root, runtime), 'run', '--locked', '--no-sync', '--offline', '--project',
               str(config.project_root / 'runtime' / project), 'python', str(config.project_root / "scripts/source-operation.py"),
               "search-test", "--token", token]
    env = os.environ.copy()
    env.update(PYTHONPATH=str(config.project_root / "src"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    completed = subprocess.run(command, cwd=config.project_root, env=env,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    test = saved(config)
    if completed.returncode or not test:
        return "not tested (the CPU search runtime or its model is not ready)"
    return f"{test['chosen']} CPU threads"


def description_counts(scoped):
    from collections import Counter
    from .incremental import working
    from .settings import processing_eligible, used_formats
    from .sources import description_state
    formats = used_formats(scoped)
    return Counter(description_state(r) for r in read_records(working(scoped)) if processing_eligible(r, formats))


def failed_again(scoped, asset_ids):
    """The named assets whose description is still a recorded failure (after a finished Try again run)."""
    from .incremental import working
    from .sources import description_state
    named = set(asset_ids)
    return {r['asset_id'] for r in read_records(working(scoped)) if r['asset_id'] in named and description_state(r) == 'failed'}


DESCRIBE_END = {'complete': ('complete', 'Descriptions generated and published'),
                'complete_with_failures': ('complete_with_faults', 'Descriptions generated; some failed and were recorded'),
                'cancelled': ('cancelled', 'Cancelled; finished descriptions are published'),
                'stopped': ('faulty', 'Stopped; finished descriptions are published')}
EDITED_END = {'complete': ('complete', 'Search updated for the edited description'),
              'cancelled': ('cancelled', 'Cancelled; the edit is saved and search still uses the earlier text'),
              'stopped': ('faulty', 'Stopped; the edit is saved and search still uses the earlier text')}


def describe_source(config, source, token):
    """Generate missing descriptions and their vectors, then publish what finished.

    Descriptions are optional extra data (decision 0033). Recorded description
    failures are kept, not retried. A cancel or stop still publishes completed
    descriptions, and every run ends with one report notification.
    """
    from .notifications import notify_report
    scoped = bound(config, source)
    started = time.monotonic()
    state(scoped, status="scanning", phase="Checking source", progress=.01)
    scan_source(config, source, progress=scan_reporter(scoped))
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
    if operation_status(scoped).get('mode') == 'edited':
        # The inspector shows the edit and its search update; a report notice would only repeat it.
        status, phase = EDITED_END.get(outcome or 'complete', EDITED_END['stopped'])
        state(scoped, status=status, phase=phase, progress=1, current_asset=None, reason=reason)
        return
    after = description_counts(scoped)
    failed = max(0, after['failed'] - before['failed'])
    if outcome is None and operation_status(scoped).get('mode') == 'retry':
        # A Try again that fails once more was already counted as failed before the run: count it again here.
        failed += len(failed_again(scoped, operation_status(scoped).get('asset_ids') or []))
    outcome = outcome or ('complete_with_failures' if failed else 'complete')
    notify_report(config, source, token, outcome, written=max(0, after['complete'] - before['complete']),
                  failed=failed, remaining=after['missing'], reason=reason,
                  elapsed_seconds=round(time.monotonic() - started))
    status, phase = DESCRIBE_END[outcome]
    state(scoped, status=status, phase=phase, progress=1, current_asset=None, reason=reason)


def ensure_search_check(config, scoped, token, backend=None):
    """A missing search check never stops processing (decision 0031): the search stage runs it first, on the
    built-in sample images, and keeps the loaded model. A failed check stops the stage with its reason; assets stay
    pending and finished stages are kept.
    """
    from . import engines
    from .search_check import record
    if engines.capability_ready(config, engines.search_device(config))["ready"]:
        return backend
    state(scoped, status="processing", phase="Running the one-time search check", stage="embeddings")
    try:
        if backend is None:
            from .search_speed import ensure
            backend = engines.embedder(scoped)
            ensure(scoped, backend, progress=lambda phase: state(scoped, status="processing", phase=phase, stage="embeddings"),
                   cancelled=lambda: cancelled(scoped, token))  # CPU threads, as when the stage loads the model itself.
        record(config, backend)
    except (ConfigError, OSError, RuntimeError) as exc:
        reason = f"The search check did not pass, so search data was not built: {exc}"
        atomic_json(stage_fault_path(scoped, token), {"reason": reason, "utc": now()})
        raise ConfigError(reason) from exc
    return backend


def worker_stage(config, source, stage, token):
    from .incremental import process
    from .incremental import working
    scoped = bound(config, source)
    from .settings import used_formats
    backend = None
    operation = operation_status(scoped).get("operation", "process")
    # Description runs only describe assets whose renders are ready, so unfinished
    # imports never gain recorded description faults.
    # A queue item's scope, resolved when it started (decision 0032); None is the whole folder.
    scope = operation_status(scoped).get("asset_ids")
    only = set(scope) if scope is not None else None
    retry = set()
    if stage == "caption":
        from .sources import description_state
        # Try again (the owner named the assets) generates a recorded failure once more, once.
        wanted = {"missing", "failed"} if operation_status(scoped).get("mode") == "retry" else {"missing"}
        states = {r["asset_id"]: description_state(r) for r in read_records(working(scoped))}
        missing = {i for i, value in states.items() if value in wanted}
        only = missing if only is None else missing & only
        if "failed" in wanted:
            retry = {i for i in only if states[i] == "failed"}
    def on_progress(identifier, completed, total):
        state(scoped, status="cancelling" if cancelled(scoped, token) else "processing",
              phase=(finishing(stage) if cancelled(scoped, token) else STAGE_LABELS[stage]),
              stage=stage, completed=completed, total=total, current_asset=identifier,
              progress=stage_progress(operation, stage, completed / max(1, total)))
    for _ in range(10000):
        if cancelled(scoped, token):
            return
        if not used_formats(config):
            return
        from .settings import descriptions_enabled
        if stage == "caption" and not descriptions_enabled(config):
            # Turned off while running: stop after the finished batch; its descriptions are kept.
            atomic_json(stage_fault_path(scoped, token), {"reason": DESCRIPTIONS_STOPPED, "utc": now()})
            raise ConfigError(DESCRIPTIONS_STOPPED)
        try:
            preview = process(scoped, stage, limit=1000, dry_run=True, asset_ids=only, retry=retry)
        except (ConfigError, OSError, ValueError):
            if stage != "embeddings":
                raise
            backend = ensure_search_check(config, scoped, token, backend)  # The missing receipt is why; then measure again.
            preview = process(scoped, stage, limit=1000, dry_run=True, asset_ids=only)
        if stage == "embeddings" and preview.get("pending"):
            backend = ensure_search_check(config, scoped, token, backend)  # Only when there is search data to build.
        if not preview.get("pending") and not preview.get("restored"):
            return  # Reused results whose stage a rescan reset still need the real pass to mark them complete.
        from . import engines
        from .description_engines import EngineStop
        with lease(config, "batch-source-" + stage, timeout=30) if stage != "inspection" else _nullcontext():
            try:
                if stage != "inspection" and backend is None and preview.get("pending"):  # Reuse alone needs no model.
                    backend = engines.description_engine(scoped) if stage == "caption" else engines.embedder(scoped)
                    if stage == "embeddings":
                        from .search_speed import ensure
                        ensure(scoped, backend, progress=lambda phase: state(scoped, status="processing", phase=phase,
                               stage=stage), cancelled=lambda: cancelled(scoped, token))
                result = process(scoped, stage, limit=1000, backend=backend, asset_ids=only, retry=retry,
                                 cancelled=lambda: cancelled(scoped, token), progress=on_progress,
                                 status=lambda phase: state(scoped, status="processing", phase=phase, stage=stage))
                retry = set()  # One new attempt: a second failure is recorded and kept.
            except EngineStop as exc:
                # A machine limit, not an asset fault: the coordinator shows this reason.
                atomic_json(stage_fault_path(scoped, token), {"reason": str(exc), "utc": now()})
                raise
        if cancelled(scoped, token):
            return
        if not result.get("outcomes") and not result.get("processed") and not result.get("restored"):
            raise ConfigError("No processing progress; source work preserved for review")
    raise ConfigError("Source processing exceeded its bounded batches")


from contextlib import nullcontext as _nullcontext
