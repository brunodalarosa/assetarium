"""Pilot-only exact retrieval. Channel rankings remain separate from RRF output."""
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import time

import numpy as np

from .catalog import detail, digest, encoded, read_database, save_json
from .caption_quality import caption_summary
from .captions import effective_caption, file_hash, validate_overlay
from .config import ConfigError
from .embedding_backend import normalize
from .publication import line_ending_hashes, pinned, pinned_config
from .search_policy import DEFAULT_MODE, MAX_LIMIT, RRF_K, RRF_WEIGHTS, search_character_cap
from .asset_structure import asset_type
from .dependency_resolution import dependency_file

VERSION = "pilot-retrieval-v1"
MODES = {"keyword", "description", "image", "keyword_description", "combined", "reference"}


def pilot_records(config):
    """Shared read-only slim records of the pinned publication (see library_cache)."""
    from .library_cache import library_records
    return library_records(config)


def current_overlay(config, record):
    overlay = record.get("owner_overlay")
    path = config.output_path("data", f"captions/corrections/{record['asset_id']}.json")
    if path.is_file():
        from .library_cache import cached_json
        overlay = cached_json(path)  # Shared and read-only; reparsed when the file changes.
    if overlay:
        validate_overlay(overlay)
    return overlay


def observations(config, record):
    overlay = current_overlay(config, record)
    if overlay:
        return effective_caption(record, overlay)["description"]
    return record.get("description")


def description_input(config, record):
    observation = observations(config, record)
    if record["processing"]["caption"] != "complete" or not observation:
        raise ConfigError("Caption absent/failed; no description embedding")
    # Structured visual observations only; suggestions and measured facts never leak in.
    keys = ("identity", "description", "shape", "colors", "parts", "style", "distinguishing_features", "uncertainties")
    text = encoded({k: observation[k] for k in keys})
    for view in (record.get("caption_provenance") or {}).get("input_views", []):
        if not view["path"].startswith("data/"):
            raise ConfigError("Caption input view must be under project data")
        path = config.output_path("data", view["path"].removeprefix("data/"))
        if file_hash(path) != view["sha256"]:
            raise ConfigError("Caption input view is stale")
    return text, digest({"text": text})


def preview_file(config, preview):
    quality = preview.get("quality", {})
    if quality.get("empty") or quality.get("off_frame"):
        raise ConfigError("Preview has a recorded render fault")
    if preview.get("source_path"):
        path = config.source_file(preview["source_path"])
    elif preview.get("path", "").startswith("data/"):
        path = config.output_path("data", preview["path"][5:])
    else:
        raise ConfigError("Preview is not a source/project individual view")
    if not preview.get("sha256") or file_hash(path) != preview["sha256"]:
        raise ConfigError("Preview missing/stale")
    return path


def image_input(preview):
    # Review/approval/provenance labels do not change the consumed pixels.
    return digest({k:preview[k] for k in ('path','source_path','sha256','view_label','origin') if k in preview})


@pinned_config
def source_check(config, record):
    """Conservative logical-asset exclusion on missing/stale recorded files/dependencies."""
    checked = []
    if record.get('texture_repair'):
        from .texture_repair import validate_recipe
        # Mapping changes are bound to rendered-view fingerprints. Keep the
        # source fingerprint based on verified file bytes for existing clients.
        validate_recipe(config, record)
    if record.get('metadata_fault'):
        raise ConfigError('Catalog metadata faulty: '+record['metadata_fault']['error'])
    if record["availability"] != "available":
        raise ConfigError("Catalog marks asset unavailable")
    for item in record["files"]:
        if item["availability"] != "available":
            raise ConfigError("Catalog marks alternate source unavailable")
        path = config.source_file(item["path"])
        if not item.get("sha256") or file_hash(path) != item["sha256"]:
            raise ConfigError("Source content is stale: " + item["path"])
        checked.append({"path": item["path"], "sha256": item["sha256"]})
    if not checked:
        raise ConfigError("No source files")
    for dependency in record.get("dependencies", []):
        if dependency.get("required_for_render") is False:
            # Verified inactive image datablock: retain its fault without discarding usable geometry/views.
            checked.append({"path": dependency.get("path"), "sha256": dependency.get("sha256"),
                            "status": dependency.get("status"), "required_for_render": False})
            continue
        if dependency.get("status") != "available" or not dependency.get("path"):
            raise ConfigError("Dependency unavailable or unresolved: " + str(dependency.get('reference') or dependency.get('path'))
                              + (" — " + dependency['error'] if dependency.get('error') else ''))
        from .dependency_resolution import dependency_file
        path = dependency_file(config, dependency)
        if not dependency.get("sha256") or file_hash(path) != dependency["sha256"]:
            raise ConfigError("Dependency content is stale: " + dependency["path"])
        checked.append({"path": dependency["path"], "sha256": dependency["sha256"]})
    technical = record.get("technical") or {}
    if technical.get("inspected_path"):
        if file_hash(config.source_file(technical["inspected_path"])) != technical["inspected_sha256"]:
            raise ConfigError("Inspection source is stale")
    if record.get('identity_version') == 'subasset-v1':
        checked.append({'parent': record['parent_asset_id'], 'selector': record['subasset']})
    return digest(checked)


def index_database(config, readonly=False):
    from .publication import generation
    if not readonly and config.catalog_generation is None and generation(config)!='legacy':
        raise ConfigError('Published indexes are immutable; use the incremental library coordinator')
    path = config.output_path("data", "embeddings/index.sqlite")
    if readonly:
        if not path.is_file():
            raise ConfigError("Pilot embedding index missing")
        return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript("""
      CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL,
        channel TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS vectors (job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),
        asset_id TEXT NOT NULL, channel TEXT NOT NULL, input_fingerprint TEXT NOT NULL,
        contract_fingerprint TEXT NOT NULL, source_fingerprint TEXT NOT NULL,
        modality TEXT NOT NULL, role TEXT NOT NULL, dimensions INTEGER NOT NULL,
        vector BLOB NOT NULL, vector_sha256 TEXT NOT NULL, preview TEXT);
      PRAGMA user_version=1;
    """)
    db.execute("PRAGMA foreign_keys=ON")
    return db


def recorded_contract(config, contract):
    """The contract with its recorded adapter/lock hashes when those files differ only by LF/CRLF.

    Search and indexing compare contracts exactly; a git checkout that swaps line
    endings changes neither inference nor vectors, so it must not force a re-embed.
    """
    if not contract:
        return contract
    try:
        recorded = json.loads(config.output_path("data", "embeddings/capability.json").read_text(encoding="utf-8"))["contract"]
    except (OSError, ValueError, KeyError, TypeError):
        return contract  # The existing capability checks report the fault.
    result = dict(contract)
    # A contract may name its own hashed files (the CPU embedder, decision 0018); CUDA keeps these two.
    files = contract.get("hashed_files") or {"adapter_sha256": "src/local_asset_library/embedding_backend.py",
                                             "runtime_lock_sha256": "runtime/embedding/uv.lock"}
    package = "src/local_asset_library/"
    for key, path in ((key, Path(__file__).with_name(relative[len(package):]) if relative.startswith(package)
                       else config.project_root / relative) for key, relative in files.items()):
        old = recorded.get(key) if isinstance(recorded, dict) else None
        if old and contract.get(key) and contract[key] != old:
            try:
                if old in line_ending_hashes(path):
                    result[key] = old
            except OSError:
                pass
    return result


def index_pilot(config, backend):
    started = time.perf_counter()
    from .membership import records as full_records
    records = full_records(config)  # Processing reads fresh full records.
    contract = recorded_contract(config, backend.contract)
    common = digest(contract)
    capability = json.loads(config.output_path("data", "embeddings/capability.json").read_text(encoding="utf-8"))
    if capability.get("contract_fingerprint") != common or not capability.get("actual_text_and_image_inference"):
        raise ConfigError("Index requires actual text/image capability evidence for this contract")
    outcomes, jobs, vectors = [], [], []
    with closing(index_database(config)) as db:
        old_contract = db.execute("SELECT value FROM meta WHERE key='contract_fingerprint'").fetchone()
        old_jobs = {r[0]: r[1:] for r in db.execute("SELECT job_id,fingerprint,status,evidence FROM jobs")}
        old_vectors = {r[0]: r for r in db.execute("SELECT * FROM vectors")}
        for record in records:
            identifier = record["asset_id"]
            try:
                source_fingerprint = source_check(config, record)
                source_error = None
            except (OSError, ValueError) as exc:
                source_fingerprint, source_error = "unavailable", str(exc)
            items = [("description", None)] + [("image", p) for p in record["previews"]]
            for channel, preview in items:
                ref = None if preview is None else {k: preview[k] for k in ("path", "source_path", "sha256", "view_label", "origin") if k in preview}
                job_id = digest({"asset": identifier, "channel": channel, "preview": ref and {k: v for k, v in ref.items() if k != "sha256"}})
                state = {"contract": common, "source": source_fingerprint, "preview": preview,
                         "caption": record.get("description") if preview is None else None}
                input_fingerprint = digest(state)
                blob = None
                try:
                    if source_error:
                        raise ConfigError(source_error)
                    if channel == "description":
                        value, input_fingerprint = description_input(config, record)
                    else:
                        value = preview_file(config, preview)
                        input_fingerprint = image_input(preview)
                    fingerprint = digest({"contract": common, "source": source_fingerprint, "input": input_fingerprint})
                    old = old_jobs.get(job_id)
                    if old_contract and json.loads(old_contract[0]) == common and old and old[0] == fingerprint:
                        if old[1] == "failed":
                            evidence = json.loads(old[2])
                            status = "failed"
                        else:
                            row = old_vectors[job_id]
                            checked_vector(row, common)
                            vectors.append(row)
                            status, evidence = "complete", {"reused": True}
                    else:
                        vector = backend.text(value, role="document") if channel == "description" else backend.image(value)
                        vector = normalize(vector, contract["dimensions"])
                        # Recheck actual input/source bytes after inference before publishing.
                        if source_check(config, record) != source_fingerprint:
                            raise ConfigError("Source changed during inference")
                        if channel == "description":
                            if description_input(config, record)[1] != input_fingerprint:
                                raise ConfigError("Description changed during inference")
                        else:
                            preview_file(config, preview)
                        blob = vector.astype("<f4").tobytes()
                        vectors.append((job_id, identifier, channel, input_fingerprint, common, source_fingerprint,
                                        "text" if channel == "description" else "image", "document", contract["dimensions"],
                                        blob, hashlib.sha256(blob).hexdigest(), encoded(ref)))
                        status, evidence = "complete", {"reused": False, "metrics": dict(backend.last_metrics)}
                except (OSError, ValueError, RuntimeError, KeyError) as exc:
                    fingerprint = digest({"contract": common, "source": source_fingerprint, "input": input_fingerprint})
                    status, evidence = "failed", {"error": str(exc), "type": type(exc).__name__, "reused": False}
                jobs.append((job_id, identifier, channel, fingerprint, status, encoded(evidence)))
                outcomes.append({"job_id": job_id, "asset_id": identifier, "channel": channel,
                                 "input": ref, "status": status, **evidence})
        # One atomic publication: old/stale vectors never survive failed replacement jobs.
        with db:
            db.execute("DELETE FROM vectors")
            db.execute("DELETE FROM jobs")
            db.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?)", jobs)
            db.executemany("INSERT INTO vectors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", vectors)
            metadata = {"version": VERSION, "contract": contract, "contract_fingerprint": common,
                        "pilot_ids": [r["asset_id"] for r in records]}
            db.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", [(k, encoded(v)) for k, v in metadata.items()])
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ConfigError("Embedding database integrity check failed")
    report = {"contract_fingerprint": common, "pilot_assets": len(records), "vector_count": len(vectors),
              "complete": sum(o["status"] == "complete" for o in outcomes),
              "failed": sum(o["status"] == "failed" for o in outcomes),
              "elapsed_seconds": time.perf_counter() - started, "outcomes": outcomes}
    save_json(config.output_path("data", "embeddings/index-report.json"), report)
    return report


def checked_vector(row, contract_fingerprint):
    if row[4] != contract_fingerprint or row[8] != 768:
        raise ConfigError("Vector query/index contract mismatch")
    blob = row[9]
    if len(blob) != 768 * 4 or hashlib.sha256(blob).hexdigest() != row[10]:
        raise ConfigError("Vector bytes/checksum mismatch")
    value = np.frombuffer(blob, dtype="<f4")
    normalize(value)
    if not np.isclose(np.linalg.norm(value), 1, atol=1e-5):
        raise ConfigError("Stored embedding is not normalized")
    if (row[2], row[6], row[7]) not in {("description", "text", "document"), ("image", "image", "document")}:
        raise ConfigError("Vector modality/role mismatch")
    return value


def indexed_vectors(config, db, fingerprint):
    """Rows and their validated float32 matrix, built once per index file and contract.

    Every stored vector is checked (checksum, norm, modality, contract) when the
    view is built; corruption raises on every search and is never cached.
    """
    from .library_cache import memo
    path = config.output_path("data", "embeddings/index.sqlite")
    stat = path.stat()
    def build():
        # Vector bytes are only needed for validation; the matrix holds the values.
        rows = db.execute("SELECT * FROM vectors ORDER BY job_id").fetchall()
        matrix = np.stack([checked_vector(row, fingerprint) for row in rows]) if rows else np.zeros((0, 768), np.float32)
        return [row[:9] + (None, None, row[11]) for row in rows], matrix
    return memo("vectors", (str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, fingerprint), build, size=2)


def validate_filters(filters):
    if set(filters) - {"pack", "format", "max_triangles", "rigged", "asset_type", "transparent", "size_class", "collection", "tag"}:
        raise ConfigError("Unknown/unverified filter")
    if "collection" in filters and (not isinstance(filters["collection"], str) or not re.fullmatch(r"col_[0-9a-f]{16}", filters["collection"])):
        raise ConfigError("Collection filter must be a collection ID")
    if "tag" in filters:
        from .asset_tags import clean
        clean(filters["tag"])
    if "transparent" in filters and type(filters["transparent"]) is not bool:
        raise ConfigError("Transparency filter must be boolean")
    if "size_class" in filters and filters["size_class"] not in ("tiny", "small", "medium", "large"):
        raise ConfigError("Unknown image size class")
    from .asset_structure import ASSET_TYPES
    if 'asset_type' in filters and filters['asset_type'] not in ASSET_TYPES:
        raise ConfigError('Unknown asset type filter')
    if "max_triangles" in filters and (type(filters["max_triangles"]) is not int or filters["max_triangles"] < 0):
        raise ConfigError("Triangle filter must be a nonnegative integer")
    if "rigged" in filters and type(filters["rigged"]) is not bool:
        raise ConfigError("Rigged filter must be boolean")
    for key in ("pack", "format"):
        if key in filters and (not isinstance(filters[key], str) or not filters[key]):
            raise ConfigError("Invalid metadata filter")


def scope(config, filters):
    """Owner organization filters (collection members, tagged assets) as an ID set; None when unscoped."""
    allowed = None
    if "collection" in filters:
        from .asset_collections import member_ids
        allowed = set(member_ids(config, filters["collection"]))
    if "tag" in filters:
        from .asset_tags import tagged
        tagged_ids = tagged(config, filters["tag"])
        allowed = tagged_ids if allowed is None else allowed & tagged_ids
    return allowed


def matches(record, filters, allowed=None):
    if allowed is not None and record["asset_id"] not in allowed:
        return False
    from .asset_structure import asset_type
    if 'asset_type' in filters and filters['asset_type'] != asset_type(record):
        return False
    if filters.get("pack", record["pack_id"]) != record["pack_id"]:
        return False
    if "format" in filters and not any(f["format"] == filters["format"] for f in record["files"]):
        return False
    if "transparent" in filters or "size_class" in filters:
        # Measured image facts only; unprocessed or non-image assets never match.
        technical = record.get("technical") or {}
        if asset_type(record) != "image" or record["processing"].get("inspection") != "complete" or technical.get("kind") != "image":
            return False
        if "transparent" in filters and (technical.get("alpha") in (None, "none")) == filters["transparent"]:
            return False
        if "size_class" in filters and technical.get("size_class") != filters["size_class"]:
            return False
    if "max_triangles" in filters or "rigged" in filters:
        technical = record.get("technical")
        if not technical or record["processing"]["inspection"] != "complete":
            return False
        inspected=next((f for f in record['files'] if f['path']==technical.get('inspected_path')),None)
        if not inspected or not technical.get('inspected_sha256') or inspected.get('sha256')!=technical['inspected_sha256']:
            return False
        if "format" in filters and filters["format"] != technical.get('inspected_format'):
            return False  # Do not apply one export's measured facts to uninspected alternates.
        if "max_triangles" in filters:
            count = (technical.get("evaluated_instance_totals") or {}).get("triangles")
            if type(count) is not int or count<0 or count > filters["max_triangles"]:
                return False
        if 'rigged' in filters:
            if not isinstance(technical.get('armatures'),list) or bool(technical['armatures'])!=filters['rigged']:
                return False
    return True


def keyword_ranking(config, text, allowed):
    terms = re.findall(r"[^\W_]+", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text), flags=re.UNICODE)
    if not terms:
        return []
    match = " AND ".join('"' + t.replace('"', '""') + '"' for t in terms)
    with closing(read_database(config)) as db:
        rows = db.execute("SELECT asset_id,bm25(asset_fts) FROM asset_fts WHERE asset_fts MATCH ? ORDER BY bm25(asset_fts),asset_id", (match,)).fetchall()
    return [{"asset_id": identifier, "score": float(score)} for identifier, score in rows if identifier in allowed]


def aggregate_views(rows, scores):
    best = {}
    for row, score in zip(rows, scores):
        candidate = {"asset_id": row[1], "score": float(score), "input": json.loads(row[11])}
        if row[1] not in best or score > best[row[1]]["score"]:
            best[row[1]] = candidate
    return sorted(best.values(), key=lambda r: (-r["score"], r["asset_id"]))


def fuse(rankings, weights=None):
    scores = {}
    for channel, ranking in rankings.items():
        for rank, candidate in enumerate(ranking, 1):
            identifier = candidate["asset_id"]
            scores[identifier] = scores.get(identifier, 0) + (weights or {}).get(channel, 1) / (RRF_K + rank)
    return [{"asset_id": identifier, "score": score} for identifier, score in sorted(scores.items(), key=lambda r: (-r[1], r[0]))]


class SearchEngine:
    def __init__(self, config, backend=None, contract=None):
        self.config, self.backend = config, backend
        self.contract = recorded_contract(config, contract if contract is not None else (backend.contract if backend else None))

    @pinned
    def search(self, text="", mode=DEFAULT_MODE, reference=None, filters=None, limit=5, min_similarity=None,
               exclude_image_hashes=None):
        started = time.perf_counter()
        filters = filters or {}
        exclude_image_hashes = set(exclude_image_hashes or ())
        if exclude_image_hashes and mode != "reference":
            raise ConfigError("Image exclusions are only accepted for reference evaluation")
        validate_filters(filters)
        if mode not in MODES or type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
            raise ConfigError("Invalid search mode/limit")
        if not isinstance(text, str) or len(text) > 1024 or (mode != "reference" and not text.strip()):
            raise ConfigError("Search requires text of at most 1024 characters")
        if mode == "keyword" and len(text) > 256:
            raise ConfigError("Keyword query must be at most 256 characters")
        if mode == "reference" and (not reference or text):
            raise ConfigError("Reference mode requires an image and no text")
        if reference and mode != "reference":
            raise ConfigError("Reference image is only accepted in reference mode")
        if min_similarity is not None and (not math.isfinite(min_similarity) or not -1 <= min_similarity <= 1):
            raise ConfigError("Evaluation cosine floor must be finite in [-1,1]")
        records, source_fingerprints, excluded = {}, {}, []
        allowed = scope(self.config, filters)
        for record in pilot_records(self.config):
            if not matches(record, filters, allowed):
                continue
            try:
                source_fingerprints[record["asset_id"]] = source_check(self.config, record)
                records[record["asset_id"]] = record
            except (OSError, ValueError) as exc:
                excluded.append({"asset_id": record["asset_id"], "channel": "all", "reason": str(exc)})
        rankings = {}
        if mode in {"keyword", "combined", "keyword_description"}:
            rankings["keyword"] = keyword_ranking(self.config, text, records)
        if mode != "keyword" and records:
            if self.backend is None or self.contract is None:
                raise ConfigError("Semantic search requires the verified embedding runtime")
            fingerprint = digest(self.contract)
            with closing(index_database(self.config, readonly=True)) as db:
                metadata = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM meta")}
                if metadata.get("version") != VERSION or metadata.get("contract_fingerprint") != fingerprint or metadata.get("contract") != self.contract:
                    raise ConfigError("Query/index embedding contract mismatch; reindex explicitly")
                from .membership import membership
                expected_ids = (set(membership(self.config)['asset_ids']) if self.config.sources_registry and not self.config.source_key
                                else {r['asset_id'] for r in pilot_records(self.config)})
                if set(metadata["pilot_ids"]) != expected_ids:
                    raise ConfigError("Pilot query/index scope mismatch")
                channels = (["description", "image"] if mode == "combined" else
                            ["description"] if mode == "keyword_description" else
                            ["image" if mode == "reference" else mode])
                rows, matrix = indexed_vectors(self.config, db, fingerprint)
            if mode == "reference":
                capability = json.loads(self.config.output_path("data", "embeddings/capability.json").read_text(encoding="utf-8"))
                if capability.get("contract_fingerprint") != fingerprint or not capability.get("reference_image_query_support"):
                    raise ConfigError("Reference query requires verified image-query capability for this contract")
                # Local existing image, bounded by source/project guards; no URL loading.
                path = reference_file(self.config, reference)
                query_vector = normalize(self.backend.image(path))
            else:
                query_vector = normalize(self.backend.text(text, role="query"))
            for channel in channels:
                selected, values = [], []
                for position, row in enumerate(rows):
                    if row[2] != channel or row[1] not in records:
                        continue
                    try:
                        record = records[row[1]]
                        if row[5] != source_fingerprints[row[1]]:
                            raise ConfigError("Source/index fingerprint mismatch")
                        if channel == "description":
                            text_value, current = description_input(self.config, record)
                            legacy = digest({"text": text_value, "caption": (record.get("caption_provenance") or {}).get("fingerprint"), "input_views": (record.get("caption_provenance") or {}).get("input_views")})
                            if row[3] != current and (metadata.get("input_policy") or row[3] != legacy):
                                raise ConfigError("Description/index input fingerprint mismatch")
                        else:
                            ref = json.loads(row[11])
                            if ref["sha256"] in exclude_image_hashes:
                                excluded.append({"asset_id": row[1], "channel": channel,
                                                 "reason": "Reference evaluation parent image excluded", "sha256": ref["sha256"]})
                                continue
                            preview = next((p for p in record["previews"] if p.get("path") == ref.get("path") and p.get("source_path") == ref.get("source_path")), None)
                            if preview is None or (image_input(preview) != row[3] and (metadata.get('image_input_policy') or digest(preview)!=row[3])):
                                raise ConfigError("Preview/index input fingerprint mismatch")
                            preview_file(self.config, preview)
                        selected.append(row)
                        values.append(position)
                    except (OSError, ValueError) as exc:
                        # Descriptions are optional (decision 0008): a stale or invalid one
                        # only leaves its channel; the asset still ranks by image and keyword.
                        if channel != "description":
                            excluded.append({"asset_id": row[1], "channel": channel, "reason": str(exc)})
                scores = matrix[values] @ query_vector if values else []
                ranking = aggregate_views(selected, scores)
                # Preserve *unthresholded* channel rankings for later evaluation.
                rankings[channel] = ranking
        eligible = {channel: [r for r in ranking if channel == "keyword" or min_similarity is None or r["score"] >= min_similarity]
                    for channel, ranking in rankings.items()}
        ranked = fuse(eligible, RRF_WEIGHTS[mode]) if mode in {"combined", "keyword_description"} else next(iter(eligible.values()), [])
        results = []
        for candidate in ranked[:limit]:
            record = records[candidate["asset_id"]]
            matching = [c for c, ranking in eligible.items() if any(r["asset_id"] == record["asset_id"] for r in ranking)]
            try:
                obs = observations(self.config, record) or {}
                excerpt = obs.get("description", "")[:180]
                owner_review = (current_overlay(self.config, record) or {}).get("caption_review", "pending")
            except (OSError, ValueError):
                excerpt = "Caption correction is faulty; inspect detail."
                owner_review = "faulty"
            preview = None
            for view in record["previews"]:
                try:
                    preview_file(self.config, view)
                    preview = view.get("path") or view.get("source_path")
                    break
                except (OSError, ValueError):
                    continue
            results.append({"asset_id": record["asset_id"], "name": record["display_name"], "pack": record["pack_id"],
                            "asset_type": asset_type(record),
                            "excerpt": excerpt, "formats": sorted({f["format"] for f in record["files"]}),
                            "preview": preview, "availability": "available", "matching_channels": matching,
                            "score": candidate["score"], "match_status": "keyword_match" if "keyword" in matching else "weak_unvalidated",
                            **caption_summary(self.config, record),
                            "source_faulty": bool((record.get("inspection_run") or {}).get("source_faults") or (record.get('inspection_run') or {}).get('errors')
                                or any(s in record.get('stage_faults',{}) for s in ('inventory','inspection','previews'))),
                            'processing':record['processing'],
                            "caption_owner_review": owner_review})
        response = {"query": text if mode != "reference" else str(reference), "mode": mode, "filters": filters,
                    "results": results, "status": "candidates" if results else "no_match",
                    "score_meaning": "RRF rank score" if mode in {"combined", "keyword_description"} else ("FTS5 BM25" if mode == "keyword" else "cosine similarity; not a probability"),
                    "evaluation_cosine_floor": min_similarity,
                    "match_policy": "Semantic candidates are weak/unvalidated; an optional evaluation cosine floor is not a universal confidence threshold.",
                    "character_cap": search_character_cap(limit), "truncated": False, "serialized_characters": 0, "estimated_tokens": 0,
                    "token_estimate_method": "ceil(characters/4); heuristic, not model tokens"}
        while True:
            for _ in range(8):
                size = len(encoded(response))
                response.update(serialized_characters=size, estimated_tokens=(size + 3) // 4)
            if len(encoded(response)) <= response["character_cap"]:
                break
            if not response["results"]:
                raise ConfigError("Response exceeds deterministic cap")
            response["results"].pop()
            response["truncated"] = True
        evidence = {"response": response, "channel_rankings": rankings, "eligible_channel_rankings": eligible,
                    "excluded": excluded, "elapsed_seconds": time.perf_counter() - started,
                    "contract_fingerprint": digest(self.contract) if self.contract else None,
                    "query_metrics": dict(self.backend.last_metrics) if mode != "keyword" and self.backend else None}
        return response, evidence


def reference_file(config, value):
    value = str(value).replace("\\", "/")
    if value.startswith("data/"):
        path = config.output_path("data", value[5:])
    elif value.startswith("scratch/"):
        path = config.output_path("scratch", value[8:])
    elif value.startswith("source/"):
        path = config.source_file(value[7:])
    else:
        raise ConfigError("Reference must use data/, scratch/, or source/ relative path")
    if not path.is_file():
        raise ConfigError("Reference image is missing")
    return path


def resolved_detail(config, identifier, source_format=None):
    record = detail(config, identifier)
    source_check(config, record)
    files = [f for f in record["files"] if source_format is None or f["format"] == source_format]
    if not files:
        raise ConfigError("Requested source format is not available")
    selected = next((f for f in files if f["path"] == record.get("primary_inspection_path")), files[0])
    dependencies = []
    # Preserve all known logical-asset dependency paths, each with its referring source.
    for item in record.get("dependencies", []):
        try:
            from .dependency_resolution import dependency_file
            path = str(dependency_file(config, item))
            dependencies.append({**item, "resolved_path": path})
        except (ConfigError, OSError) as exc:
            if item.get("required_for_render") is not False:
                raise
            dependencies.append({**item, "resolved_path": None, "fault": str(exc)})
    overrides = [{**{k:b[k] for k in ('image','original_path','path','sha256','role','preserve_supplied_alpha',
                                    'dependency_resolution','from') if k in b},
                  'resolved_path': str(dependency_file(config, b)),
                  'material_users': next((t['render_users'] for t in (record.get('technical') or {}).get('textures', [])
                                          if t['name'] == b['image']), [])}
                 for b in (record.get('texture_repair') or {}).get('bindings', [])]
    return {"asset_id": identifier, "selected_source": {**selected, "resolved_path": str(config.source_file(selected["path"]))},
            'texture_overrides': overrides,
            "dependencies": dependencies, "record": record,
            "limitations": ["All known logical-asset dependencies listed with referring-source evidence; binary/alternate dependency inspection may remain incomplete.",
                            "Visual descriptions are provisional; suggested uses remain a separate field."] +
                           (["Preview uses library texture overrides. Apply the supplied overrides when importing the unchanged original source."] if overrides else []) +
                           (["This is the parent source package. Sub-asset extraction and playback are not implemented."] if record.get('parent_asset_id') else []) +
                           (["Audio bytes are verified; decoding, playback and audio inference are not implemented."] if asset_type(record) == 'audio' else [])}
