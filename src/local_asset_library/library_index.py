"""Durable vector jobs; active catalog/index publication stays separate."""
from contextlib import closing
import hashlib
import json
import os
import time
import uuid

from .catalog import digest, encoded, save_json
from .config import ConfigError
from .publication import atomic_json
from .membership import records
from .asset_structure import asset_type
from .retrieval import (index_database, checked_vector, source_check, description_input, preview_file, image_input, normalize,
                        recorded_contract, VERSION)


def index_library(config, backend=None, limit=1000, dry_run=False, description_only=False,
                  cancelled=None, progress=None):
    from .incremental import update_record
    from .settings import processing_formats, processing_eligible
    inventory = records(config)
    inventory_by_id = {r['asset_id']: r for r in inventory}
    formats = processing_formats(config)
    selected = [record for record in inventory if processing_eligible(record, formats)]
    with closing(index_database(config, readonly=dry_run)) as db:
        metadata = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM meta")}
        capability = json.loads(config.output_path("data", "embeddings/capability.json").read_text(encoding="utf-8"))
        # A dry run counts against the verified receipt's contract, the one the next run will use: a first run has
        # no index contract yet, and after a device switch the old one is stale. A backend is checked against it.
        contract = recorded_contract(config, backend.contract) if backend else (capability.get("contract") or metadata.get("contract"))
        if not contract:
            raise ConfigError("Verified embedding contract missing")
        common = digest(contract)
        if capability.get("contract_fingerprint") != common or not capability.get("actual_text_and_image_inference"):
            raise ConfigError("Actual inference capability receipt does not match contract")
        old_jobs = {r[0]: r[1:] for r in db.execute("SELECT job_id,fingerprint,status,evidence FROM jobs")}
        old_vectors = {r[0]: r for r in db.execute("SELECT * FROM vectors")}
        expected, outcomes, visited = set(), [], set()
        pending, processed, deferred = 0, 0, 0
        started = time.monotonic()
        if not dry_run:
            atomic_json(config.output_path('data','library/processing-status.json'),{'status':'running','stage':'embeddings','completed':0,'selected':limit,'pid':os.getpid()})
        for position, record in enumerate(selected):
            identifier = record["asset_id"]
            if not dry_run and cancelled and cancelled():
                break
            if not dry_run and progress:
                progress(identifier, position, len(selected))
            # A 2D image is embedded from its recorded model input only; its original,
            # display raster and thumbnail are presentation, not extra vectors.
            views = ([p for p in record['previews'] if p.get('role') == 'model_input']
                     if asset_type(record) == 'image' else record['previews'])
            if asset_type(record) == 'image' and not views:
                # No direct-media input exists yet. Do not manufacture either a
                # vector failure or a successful empty image index.
                continue
            counts = {"complete": 0, "failed": 0, "pending": 0, "deferred": 0}
            channels = [("description", None)] + [("image", p) for p in views]
            for channel, preview in channels:
                ref = None if preview is None else {k: preview[k] for k in ("path", "source_path", "sha256", "view_label", "origin") if k in preview}
                job = digest({"asset": identifier, "channel": channel, "preview": ref and {k: v for k, v in ref.items() if k != "sha256"}})
                expected.add(job)
                if description_only and channel == 'image':
                    old = old_jobs.get(job)
                    counts[old[1] if old and old[1] in {'complete', 'failed'} else 'pending'] += 1
                    continue
                # A description awaiting generation has no vector input yet.
                # Keep it eligible after captioning without creating a failed job
                # or including it in runnable pending work (which would loop).
                if (channel == 'description' and record.get('description') is None
                        and record['processing'].get('caption') == 'pending'
                        and not record.get('caption_provenance') and job not in old_jobs):
                    deferred += 1
                    counts['deferred'] += 1
                    outcomes.append({'asset_id': identifier, 'channel': channel, 'status': 'deferred',
                                     'reused': False, 'reason': 'Description generation pending'})
                    continue
                value, error, source_fp = None, None, "unavailable"
                input_fp = digest({"preview": ref, "description": record.get("description")})
                try:
                    source_fp = source_check(config, record)
                    value, input_fp = description_input(config, record) if channel == "description" else (preview_file(config, preview), image_input(preview))
                except (ValueError, OSError, KeyError) as exc:
                    error = str(exc)
                fp = digest({"contract": common, "source": source_fp, "input": input_fp})
                old, row = old_jobs.get(job), old_vectors.get(job)
                reuse = bool(old and old[0] == fp and old[1] in {"complete", "failed"})
                if not reuse and old and old[1]=='failed':
                    previous_input=digest({'contract':metadata.get('contract_fingerprint'),'source':source_fp,'input':input_fp})
                    reuse=old[0]==previous_input
                if not reuse and row and not error and row[4] == common and channel == "description":
                    legacy = digest({"text": value, "caption": (record.get("caption_provenance") or {}).get("fingerprint"), "input_views": (record.get("caption_provenance") or {}).get("input_views")})
                    reuse = row[3] in {legacy,input_fp}
                    if reuse:
                        row = (*row[:3], input_fp, row[4],source_fp,*row[6:])
                if not reuse and row and not error and row[4]==common and channel=='image':
                    reuse=row[3] in {digest(preview),input_fp}
                    if reuse:
                        row=(*row[:3],input_fp,row[4],source_fp,*row[6:])
                if reuse:
                    status, evidence = old[1], json.loads(old[2])
                    if status == "complete":
                        try:
                            checked_vector(row, common)
                        except (ValueError, KeyError, TypeError) as exc:
                            status, evidence, row = "failed", {"error": str(exc), "corrupt_output": True}, None
                else:
                    pending += 1
                    if processed >= limit or dry_run:
                        counts["pending"] += 1
                        continue
                    processed += 1
                    status, evidence, row = "failed", {"error": error}, None
                    if not error:
                        if backend is None:
                            raise ConfigError("Pending vectors require explicitly loaded backend")
                        with db:
                            db.execute("DELETE FROM vectors WHERE job_id=?", (job,))
                            db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?)", (job, identifier, channel, fp, "running", encoded({"resumable": True})))
                        try:
                            vector = normalize(backend.text(value, role="document") if channel == "description" else backend.image(value), contract["dimensions"])
                            if source_check(config, record) != source_fp:
                                raise ConfigError("Source changed during inference")
                            if channel == "description" and description_input(config, record)[1] != input_fp:
                                raise ConfigError("Description changed during inference")
                            if channel == "image":
                                preview_file(config, preview)
                            blob = vector.astype("<f4").tobytes()
                            row = (job, identifier, channel, input_fp, common, source_fp, "text" if channel == "description" else "image", "document", contract["dimensions"], blob, hashlib.sha256(blob).hexdigest(), encoded(ref))
                            status, evidence = "complete", {"metrics": dict(backend.last_metrics)}
                        except (OSError, ValueError, RuntimeError, KeyError) as exc:
                            status, evidence = "failed", {"error": str(exc), "type": type(exc).__name__}
                counts[status] += 1
                if not dry_run and (not reuse or old[0] != fp or status != old[1]):
                    with db:
                        db.execute("DELETE FROM vectors WHERE job_id=?", (job,))
                        db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?)", (job, identifier, channel, fp, status, encoded(evidence)))
                        if status == "complete":
                            db.execute("INSERT INTO vectors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", row)
                outcomes.append({"asset_id": identifier, "channel": channel, "status": status, "reused": reuse, **evidence})
                if not dry_run and processed and processed%10==0:
                    atomic_json(config.output_path('data','library/processing-status.json'),{'status':'running','stage':'embeddings','completed':processed,'selected':limit,'pid':os.getpid()})
            if not dry_run:
                record["processing"]["embeddings"] = ("pending" if counts["pending"] else
                    "partial" if counts["complete"] and (counts["failed"] or counts["deferred"]) else
                    "failed" if counts["failed"] else "pending" if counts['deferred'] else "complete")
                update_record(config, record)
                visited.add(identifier)
                if progress:
                    progress(None, position + 1, len(selected))
        if not dry_run:
            with db:
                current_ids = {r['asset_id'] for r in inventory}
                for job, identifier in db.execute("SELECT job_id,asset_id FROM jobs").fetchall():
                    if identifier in visited and job not in expected:
                        existing = inventory_by_id.get(identifier)
                        prior = db.execute('SELECT channel,status FROM jobs WHERE job_id=?', (job,)).fetchone()
                        if existing and asset_type(existing) == 'image' and prior == ('description', 'failed'):
                            continue  # Optional failure history is not cleared by stage applicability.
                    if identifier not in current_ids or (identifier in visited and job not in expected):
                        db.execute("DELETE FROM vectors WHERE job_id=?", (job,))
                        db.execute("DELETE FROM jobs WHERE job_id=?", (job,))
                values = {"version": VERSION, "contract": contract, "contract_fingerprint": common, "pilot_ids": [r["asset_id"] for r in inventory], "input_policy": "effective-description-content-v1",'image_input_policy':'verified-view-content-v1'}
                db.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", [(k, encoded(v)) for k, v in values.items() if metadata.get(k) != v])
        report = {"stage": "embeddings", "pending": pending, "processed": processed, "deferred_descriptions": deferred, "dry_run": dry_run, "outcomes": outcomes, "elapsed_seconds": time.monotonic() - started, "vectors": db.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]}
        if backend is not None and hasattr(backend,'resources'):
            report['resources']=backend.resources()
        if not dry_run:
            save_json(config.output_path("data", f"library/batches/embeddings-{uuid.uuid4().hex}.json"), report)
            atomic_json(config.output_path('data','library/processing-status.json'),{'status':'batch_complete','stage':'embeddings','completed':processed,'pending_before_batch':pending,'vectors':report['vectors']})
        return report
