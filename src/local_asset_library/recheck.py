"""Owner-requested recheck of recorded failures that came from the file and dependency check (decision 0020).

Recorded failures are never retried on their own. A recheck lists, per source, the failed stage jobs
whose recorded reason was the pre-stage file/dependency check (``retrieval.source_check``) and runs
that check again, read only. Releasing them needs an explicit owner action and the preview it saw:
each released job keeps its earlier evidence and becomes pending, so the next Process assets tries
it once. Failures from Blender, rendering or models are never released here.
"""
import json
from contextlib import closing
from datetime import datetime, timezone

from .catalog import digest
from .config import ConfigError

CHECK_REASONS = ("Dependency unavailable or unresolved", "Dependency content is stale", "Source content is stale",
                 "Catalog marks alternate source unavailable")
STAGES = ("inspection", "caption")


def _candidates(config, source):
    from .incremental import ledger, working
    from .retrieval import source_check
    from .sources import bound, read_records
    work = working(bound(config, source))
    records = {r["asset_id"]: r for r in read_records(work)}
    ready, still = [], []
    with closing(ledger(work)) as db:
        rows = db.execute("SELECT asset_id,stage,fingerprint,evidence FROM jobs WHERE status='failed'").fetchall()
    for identifier, stage, fingerprint, evidence in sorted(rows):
        record = records.get(identifier)
        reason = str(json.loads(evidence).get("error", ""))
        if stage not in STAGES or record is None or record["processing"].get(stage) != "failed" \
                or not reason.startswith(CHECK_REASONS):
            continue
        try:
            source_check(work, record)
        except (OSError, ValueError) as exc:
            still.append({"asset_id": identifier, "stage": stage, "name": record["display_name"], "reason": str(exc)})
            continue
        ready.append({"asset_id": identifier, "stage": stage, "name": record["display_name"], "fingerprint": fingerprint,
                      "recorded_reason": reason})
    return work, ready, still


def preview(config, key):
    """What a recheck would release now; reads only."""
    from .sources import get_source
    source = get_source(config, key)
    _, ready, still = _candidates(config, source)
    identity = digest(sorted((item["asset_id"], item["stage"], item["fingerprint"]) for item in ready))
    return {"status": "ready", "source": source["key"], "preview_id": identity, "retry": len(ready),
            "still_failing": len(still), "examples": [item["name"] for item in ready[:5]],
            "still_failing_examples": [{"name": item["name"], "reason": item["reason"]} for item in still[:5]]}


def release(config, key, preview_id):
    """Release exactly the previewed failures, once; refused when anything changed since the preview."""
    from .gpu_queue import lease
    from .incremental import checkpoint, ledger, update_record
    from .sources import get_source
    source = get_source(config, key)
    try:
        held = lease(config, "recheck", timeout=1, resource="operations")
        held.__enter__()
    except ConfigError:
        raise ConfigError("Wait for the running source operation to finish, then recheck again") from None
    try:
        work, ready, _ = _candidates(config, source)
        if not ready:
            raise ConfigError("Nothing to retry: no recorded failure from the file check passes it now")
        if digest(sorted((item["asset_id"], item["stage"], item["fingerprint"]) for item in ready)) != preview_id:
            raise ConfigError("The failures changed since this recheck; recheck again before retrying")
        stamp = datetime.now(timezone.utc).isoformat()
        from .sources import read_records
        records = {r["asset_id"]: r for r in read_records(work)}
        with closing(ledger(work)) as db:
            for item in ready:
                old = db.execute("SELECT evidence FROM jobs WHERE asset_id=? AND stage=?", (item["asset_id"], item["stage"])).fetchone()
                checkpoint(db, item["asset_id"], item["stage"], item["fingerprint"], "released",
                           {"released_utc": stamp, "released_by": "owner", "reason": "File check passes under decision 0020",
                            "previous": json.loads(old[0]) if old else None})
                record = records[item["asset_id"]]
                record["processing"][item["stage"]] = "pending"
                fault = record.setdefault("stage_faults", {}).pop(item["stage"], None)
                if fault is not None:
                    record.setdefault("released_faults", {})[item["stage"]] = {**fault, "released_utc": stamp}
                update_record(work, record)
    finally:
        held.__exit__(None, None, None)
    return {"status": "released", "source": source["key"], "retried": len(ready),
            "reason": f"{len(ready):,} {'asset is' if len(ready) == 1 else 'assets are'} ready to process again; "
                      "Process assets tries each once. Other recorded failures are unchanged."}
