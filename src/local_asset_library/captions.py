"""Step 4: image-only captions; measured facts and owner edits stay separate."""

from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import sqlite3
import time

from .catalog import detail, digest, encoded, file_hash as stream_hash, save_json
from .config import ConfigError
from .inspection import load_pilot

VERSION = "caption-adapter-v1"
FIELDS = {"identity", "description", "shape", "colors", "parts", "style",
          "distinguishing_features", "uncertainties", "suggested_uses"}
OBSERVATIONS = FIELDS - {"suggested_uses"}
# A ship's rigging is its visible ropes; only the character-rig meanings are technical claims.
TECHNICAL = re.compile(r"\b(triangle count|polygon count|vertex count|\d+\s+(?:triangles|polygons|vertices)|rigged|unrigged|armature|(?:skeletal|character|bone) rig(?:ging)?|animation clips?|UV maps?|file format|dependency completeness|meters tall|metres tall)\b", re.I)
USES = re.compile(r"\b(suitable for|ideal for|can be used|could be used|would work|gameplay|Play Shapes|designed for)\b", re.I)
USE_NOTE = "Use wording in visual observations; suggested uses belong in their own list. The description stays usable."
CALIBRATION_INDICES = (0, 4, 5, 6, 10, 13, 16, 22, 28, 37)


def file_hash(path):
    from .publication import verified_hash
    return verified_hash(path)


def validate_caption(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("Caption must have exactly the required fields")
    identity = value["identity"]
    if not isinstance(identity, dict) or set(identity) != {"label", "certainty"}:
        raise ValueError("Identity requires label and certainty")
    if identity["certainty"] not in {"probable", "uncertain", "unknown"}:
        raise ValueError("Identity certainty must be probable, uncertain or unknown")
    def string(item, bound):
        return isinstance(item, str) and bool(item.strip()) and len(item) <= bound
    if not string(identity["label"], 160) or not string(value["description"], 1800):
        raise ValueError("Invalid identity or description")
    if "unknown" in identity["label"].casefold() and identity["certainty"] == "probable":
        raise ValueError("Unknown identity cannot have probable certainty; use uncertain or unknown and record why")
    if not 10 <= len(value["description"].split()) <= 170:
        raise ValueError("Description must have 10-170 words; use concise visual observations without padding")
    for key in FIELDS - {"identity", "description"}:
        items = value[key]
        if not isinstance(items, list) or len(items) > 16 or not all(string(v, 300) for v in items):
            raise ValueError(f"Invalid string list: {key}")
    # The prompt asks for visible components only; a pebble or grass clump honestly has none.
    if any(not value[key] for key in ("shape", "colors", "style")):
        raise ValueError("Core visual attributes must not be empty")
    if identity["certainty"] != "probable" and not value["uncertainties"]:
        raise ValueError("Uncertain identity requires an explicit uncertainty")
    if TECHNICAL.search(encoded({k: value[k] for k in OBSERVATIONS})):
        raise ValueError("Measured technical claim in visual observations")
    return deepcopy(value)


def use_notes(value):
    """Use wording in observations is a review note, never a fault (AGENTS.md caption severity)."""
    notes = []
    for key in sorted(OBSERVATIONS & set(value)):
        item = value[key]
        texts = [item["label"]] if key == "identity" else [item] if isinstance(item, str) else item
        for text in texts:
            for match in USES.finditer(text):
                excerpt = text[max(0, match.start() - 80):match.end() + 80].strip()
                notes.append({"severity": "review_note", "evidence": f'{key}: "{excerpt}"',
                              "reason": f'{USE_NOTE} Matched "{match[0]}".'})
    return notes[:16]


def parse_caption(text):
    # One complete JSON object, optionally fenced; no substring extraction.
    clean = text.strip()
    if clean.startswith("```json\n") and clean.endswith("\n```"):
        clean = clean[8:-4]
    elif clean.startswith("```\n") and clean.endswith("\n```"):
        clean = clean[4:-4]
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    return validate_caption(json.loads(clean, object_pairs_hook=unique_pairs))


def caption_views(record):
    """Rendered 3D views, or a 2D image's derived model input."""
    return [p for p in record["previews"] if p.get("origin") == "rendered" or p.get("role") == "model_input"]


def image_view_label(preview):
    color = (preview.get("derivation") or {}).get("background")
    return ("2D image" + (f"; transparent pixels are shown on a flat rgb({color[0]},{color[1]},{color[2]}) "
                          "backdrop that is not part of the image" if color else ""))


def image_inputs(config, record):
    if record["processing"]["inspection"] != "complete" or not record.get("technical"):
        raise ConfigError("No successful inspector result")
    if record.get("asset_type") == "image":
        selected = [p for p in record["previews"] if p.get("role") == "model_input"]
        if len(selected) != 1 or not selected[0]["path"].startswith("data/"):
            raise ConfigError("Require exactly one derived model-input image")
        path = config.output_path("data", selected[0]["path"][5:])
        if not path.is_file() or file_hash(path) != selected[0]["sha256"]:
            raise ConfigError("Input image missing or hash mismatch")
        return [{"path": selected[0]["path"], "view_label": image_view_label(selected[0]),
                 "sha256": selected[0]["sha256"], "coordinate_convention": "2d-image"}]
    selected = [p for p in record["previews"] if p.get("origin") == "rendered"]
    labels = [p["view_label"] for p in selected]
    if not {"front", "side", "three_quarter"}.issubset(labels) or len(labels) != len(set(labels)):
        raise ConfigError("Require distinct actual front, side and three-quarter views")
    result = []
    for preview in selected:
        if not preview["path"].startswith("data/"):
            raise ConfigError("Image must be a generated project view")
        path = config.output_path("data", preview["path"][5:])
        if preview.get("quality", {}).get("empty") or preview.get("quality", {}).get("off_frame"):
            raise ConfigError("Inspector marked input image empty or off-frame")
        if not path.is_file() or file_hash(path) != preview["sha256"]:
            raise ConfigError("Input image missing or hash mismatch")
        result.append({"path": preview["path"], "view_label": preview["view_label"],
                       "sha256": preview["sha256"], "coordinate_convention": preview["coordinate_convention"]})
    return result


def input_state(config, record):
    """Include current bytes/missing state so unchanged failures stay retained."""
    state = []
    for preview in caption_views(record):
        row = {"preview": preview}
        try:
            if not preview["path"].startswith("data/"):
                raise ConfigError("Not a project view")
            path = config.output_path("data", preview["path"][5:])
            row["current_sha256"] = file_hash(path)
        except (OSError, ValueError) as exc:
            row["error"] = str(exc)
        state.append(row)
    return state


def reuse_caption(record, fingerprint, retry_faults=False):
    previous = record.get("caption_provenance") or {}
    return (previous.get("fingerprint") == fingerprint
            and record["processing"]["caption"] in {"complete", "failed", "unsupported"}
            and not (retry_faults and record["processing"]["caption"] != "complete"))


def caption_fingerprint(config, record, backend, prompt):
    return digest({"model": backend.contract, "prompt": prompt,
                   "input_state": input_state(config, record),
                   "inspection_fingerprint": record.get("inspection_run", {}).get("fingerprint"),
                   "settings": backend.settings, "adapter": file_hash(Path(__file__)),
                   "backend": file_hash(config.project_root / "src/local_asset_library/caption_backend.py")})


def verify_calibration(config, backend, prompt, prompt_path, manifest):
    path = config.output_path("data", "captions/calibration-review.json")
    receipt = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if receipt.get("status") != "technically_reviewed" or receipt.get("approved_prompt_sha256") != file_hash(prompt_path):
        raise ConfigError("Pilot needs current calibration image/text review receipt")
    expected_ids = {manifest["assets"][i]["asset_id"] for i in CALIBRATION_INDICES}
    rows = receipt.get("receipts", [])
    if {r["asset_id"] for r in rows} != expected_ids or len(rows) != len(expected_ids):
        raise ConfigError("Calibration receipt must cover the selected ten assets")
    for row in rows:
        record = detail(config, row["asset_id"])
        if row["caption_fingerprint"] != caption_fingerprint(config, record, backend, prompt):
            raise ConfigError("Calibration model, code, settings or images changed; recalibrate and review")
        if image_inputs(config, record) != row["input_views"]:
            raise ConfigError("Calibration input images changed")


def infer_caption(backend, inputs, prompt, max_attempts=2):
    if max_attempts not in {1, 2}:
        raise ValueError("One or two attempts allowed")
    attempts = []
    current = prompt
    for index in range(max_attempts):
        started = time.perf_counter()
        try:
            raw, metrics = backend.generate(inputs, current, max_new_tokens=1100 + 400 * index)
        except Exception as exc:
            # Unsupported images, OOM, timeout and unchanged runtime faults are not retried.
            attempts.append({"status": "inference_failed", "error": f"{type(exc).__name__}: {exc}",
                             "elapsed_seconds": time.perf_counter() - started})
            return {"status": "failed", "description": None, "suggested_uses": [], "attempts": attempts}
        try:
            caption = parse_caption(raw)
        except (ValueError, TypeError) as exc:
            attempts.append({"status": "invalid_output", "error": str(exc), "raw": raw,
                             "metrics": metrics, "prompt_sha256": digest(current),
                             "max_new_tokens": 1100 + 400 * index})
            # A changed corrective instruction and token limit, never an identical retry.
            current = prompt + "\nYour previous response failed validation: " + str(exc) + ". Inspect the same images again and return one complete JSON object with all fields."
            continue
        attempts.append({"status": "complete", "raw": raw, "metrics": metrics,
                         "prompt_sha256": digest(current), "max_new_tokens": 1100 + 400 * index})
        uses = caption.pop("suggested_uses")
        return {"status": "complete", "description": caption, "suggested_uses": uses, "attempts": attempts}
    return {"status": "failed", "description": None, "suggested_uses": [], "attempts": attempts}


def infer_captions(backend, inputs_list, prompt, max_new_tokens=1100, batch_size=None):
    """One batched generation; single attempt per asset, same outcome shape as infer_caption.

    ``backend`` is a DescriptionEngine (``description_engines``). EngineStop propagates:
    running out of memory or losing the engine is a machine limit, not an asset outcome.
    A bare QwenBackend from the historical evidence scripts is still accepted and batched
    through caption_batching, keeping caption_backend.py and its fingerprints unchanged.
    """
    from .caption_batching import GpuMemoryError, generate_batch, memory_message
    from .description_engines import MemoryLimitError
    started = time.perf_counter()
    outcomes = []
    own = getattr(backend, 'generate_batch', None)
    try:
        results = own(inputs_list, prompt, max_new_tokens) if own else generate_batch(backend, inputs_list, prompt, max_new_tokens)
    except (GpuMemoryError, MemoryLimitError):
        # Name the configured setting, not a smaller final batch.
        raise MemoryLimitError(memory_message(batch_size or len(inputs_list))) from None
    for result in results:
        if isinstance(result, BaseException):
            outcomes.append({"status": "failed", "description": None, "suggested_uses": [],
                             "attempts": [{"status": "inference_failed", "error": f"{type(result).__name__}: {result}",
                                           "elapsed_seconds": time.perf_counter() - started}]})
            continue
        raw, metrics = result
        attempt = {"raw": raw, "metrics": metrics, "prompt_sha256": digest(prompt), "max_new_tokens": max_new_tokens}
        try:
            caption = parse_caption(raw)
        except (ValueError, TypeError) as exc:
            outcomes.append({"status": "failed", "description": None, "suggested_uses": [],
                             "attempts": [{"status": "invalid_output", "error": str(exc), **attempt}]})
            continue
        uses = caption.pop("suggested_uses")
        outcomes.append({"status": "complete", "description": caption, "suggested_uses": uses,
                         "attempts": [{"status": "complete", **attempt}]})
    return outcomes


def validate_overlay(value):
    if not isinstance(value, dict) or set(value) != {"schema_version", "description", "suggested_uses", "caption_review", "artistic_suitability", "notes"}:
        raise ValueError("Invalid owner correction overlay fields")
    if value["schema_version"] != 1 or not isinstance(value["description"], dict) or not set(value["description"]).issubset(OBSERVATIONS):
        raise ValueError("Overlay can change visual fields only")
    if value["suggested_uses"] is not None and (not isinstance(value["suggested_uses"], list) or not all(isinstance(x, str) for x in value["suggested_uses"])):
        raise ValueError("Invalid corrected uses")
    if any(value[k] not in {"pending", "approved", "rejected"} for k in ("caption_review", "artistic_suitability")):
        raise ValueError("Invalid owner review state")
    if not isinstance(value["notes"], str):
        raise ValueError("Owner notes must be text")
    return value


def effective_caption(record, overlay):
    validate_overlay(overlay)
    description = deepcopy(record.get("description"))
    if description is None:
        if overlay["description"]:
            raise ValueError("A failed AI caption cannot acquire a manufactured success through overlay")
    else:
        description.update(deepcopy(overlay["description"]))
        validate_caption({**description, "suggested_uses": overlay["suggested_uses"] if overlay["suggested_uses"] is not None else record.get("suggested_uses", [])})
    return {"description": description,
            "suggested_uses": deepcopy(overlay["suggested_uses"] if overlay["suggested_uses"] is not None else record.get("suggested_uses", []))}


def overlay_for(config, record):
    path = config.output_path("data", f"captions/corrections/{record['asset_id']}.json")
    if not path.exists():
        initial = {"schema_version": 1, "description": {}, "suggested_uses": None,
                   "caption_review": "pending", "artistic_suitability": "pending", "notes": ""}
        # Preserve already present catalog corrections if a prior owner overlay exists.
        initial.update(record.get("owner_overlay") or {})
        save_json(path, initial)
    return validate_overlay(json.loads(path.read_text(encoding="utf-8"))), path


def merge_record(record, outcome, provenance, overlay):
    result = deepcopy(record)
    result["description"] = deepcopy(outcome["description"])
    result["suggested_uses"] = deepcopy(outcome["suggested_uses"])
    result["caption_provenance"] = deepcopy(provenance)
    result["owner_overlay"] = deepcopy(overlay)
    result["effective_caption"] = effective_caption(result, overlay)
    result["processing"]["caption"] = outcome["status"]
    # In particular: technical, inspection faults, license, grouping and vectors are untouched.
    return result


def publish(config, identifier, outcome, provenance):
    from .publication import generation
    if config.catalog_generation is None and generation(config)!='legacy':
        raise ConfigError('Published captions are immutable; review/update working membership and publish a new generation')
    record = detail(config, identifier)
    overlay, path = overlay_for(config, record)
    from .result_store import logical
    overlay_reference = ('data/' + logical(config, path) if config.metadata_root
                         else path.relative_to(config.project_root).as_posix())
    provenance = {**provenance, "owner_overlay_path": overlay_reference,
                  "owner_overlay_sha256": file_hash(path), "owner_caption_review": overlay["caption_review"],
                  "owner_artistic_suitability": overlay["artistic_suitability"]}
    result = merge_record(record, outcome, provenance, overlay)
    with closing(sqlite3.connect(config.output_path("data", "catalog.sqlite"))) as db, db:
        db.execute("UPDATE assets SET record=? WHERE asset_id=?", (encoded(result), identifier))
    return result


def run_batch(config, backend, phase, prompt_version, retry_faults=False):
    if phase not in {"calibration", "pilot"} or prompt_version not in {"v1", "v2"}:
        raise ConfigError("Invalid caption phase/prompt")
    manifest = load_pilot(config)
    assets = manifest["assets"]
    if phase == "calibration":
        assets = [assets[i] for i in CALIBRATION_INDICES]
    prompt_path = config.project_root / f"prompts/caption-{prompt_version}.txt"
    prompt = prompt_path.read_text(encoding="utf-8")
    if phase == "pilot":
        verify_calibration(config, backend, prompt, prompt_path, manifest)
    started = time.perf_counter()
    outcomes = []
    for asset in assets:
        record = detail(config, asset["asset_id"])
        print(f"Caption {phase}: {asset['name']}", flush=True)
        inputs = []
        provenance = {"adapter_version": VERSION, "model": backend.contract,
                      "prompt_version": prompt_version, "prompt_sha256": file_hash(prompt_path),
                      "settings": backend.settings, "utc": datetime.now(timezone.utc).isoformat(),
                      "input_views": inputs, "ai_review": "pending", "owner_caption_review": "pending",
                      "owner_artistic_suitability": "pending"}
        fingerprint = caption_fingerprint(config, record, backend, prompt)
        provenance["fingerprint"] = fingerprint
        try:
            old = record.get("caption_provenance") or {}
            if reuse_caption(record, fingerprint, retry_faults):
                overlay, _ = overlay_for(config, record)
                outcome = {"status": record["processing"]["caption"], "description": record["description"],
                           "suggested_uses": record.get("suggested_uses", []), "attempts": old.get("attempts", [])}
                publish(config, asset["asset_id"], outcome, old)
                outcomes.append({"asset_id": asset["asset_id"], "name": asset["name"], "cached": True, **outcome})
                continue
            inputs = image_inputs(config, record)
            provenance["input_views"] = inputs
            outcome = infer_caption(backend, inputs, prompt)
            # Detect changed image bytes even if the model returned usable text.
            image_inputs(config, record)
        except (OSError, ValueError) as exc:
            outcome = {"status": "failed", "description": None, "suggested_uses": [],
                       "attempts": [{"status": "input_failed", "error": str(exc)}]}
        provenance["attempts"] = outcome["attempts"]
        provenance["elapsed_seconds"] = sum(a.get("metrics", {}).get("elapsed_seconds", a.get("elapsed_seconds", 0)) for a in outcome["attempts"])
        relative = f"captions/{phase}-{prompt_version}/{asset['asset_id']}.json"
        provenance["result_path"] = "data/" + relative
        save_json(config.output_path("data", relative), {"asset_id": asset["asset_id"], **outcome, "provenance": provenance})
        try:
            publish(config, asset["asset_id"], outcome, provenance)
        except ValueError as exc:
            outcome["publication_error"] = str(exc)
            outcome["status"] = "failed"
            # Keep the malformed owner file and previous corrections untouched.
            # Record publication failure while retaining usable raw output on disk.
            retained = detail(config, asset["asset_id"])
            retained["processing"]["caption"] = "failed"
            retained["description"] = None
            retained["effective_caption"] = None
            retained["caption_provenance"] = {**provenance, "publication_error": str(exc)}
            with closing(sqlite3.connect(config.output_path("data", "catalog.sqlite"))) as db, db:
                db.execute("UPDATE assets SET record=? WHERE asset_id=?", (encoded(retained), asset["asset_id"]))
        outcomes.append({"asset_id": asset["asset_id"], "name": asset["name"], "cached": False, **outcome})
    report = {"phase": phase, "prompt_version": prompt_version, "elapsed_seconds": time.perf_counter() - started,
              "complete": sum(o["status"] == "complete" for o in outcomes),
              "failed": sum(o["status"] != "complete" for o in outcomes), "outcomes": outcomes,
              "owner_caption_review": "pending", "owner_artistic_suitability": "pending"}
    save_json(config.output_path("data", f"captions/{phase}-{prompt_version}-report.json"), report)
    review_artifact(config, assets, f"{phase}-{prompt_version}")
    return report


def review_artifact(config, assets, name):
    rows = []
    for asset in assets:
        record = detail(config, asset["asset_id"])
        correction_error = ""
        try:
            overlay, overlay_path = overlay_for(config, record)
            effective = effective_caption(record, overlay)
        except ValueError as exc:
            correction_error = f"Owner overlay error; file retained: {exc}"
            overlay = {"caption_review": "pending", "artistic_suitability": "pending"}
            overlay_path = config.output_path("data", f"captions/corrections/{record['asset_id']}.json")
            effective = {"description": record.get("description"), "suggested_uses": record.get("suggested_uses", [])}
        provenance = record.get("caption_provenance") or {}
        images = []
        for p in provenance.get("input_views", []):
            config.output_path("data", p["path"][5:])
            images.append(f'<figure><a href="../../{html.escape(p["path"][5:], quote=True)}"><img src="../../{html.escape(p["path"][5:], quote=True)}"></a><figcaption>{html.escape(p["view_label"])}</figcaption></figure>')
        rows.append(f'<article><h2>{html.escape(record["pack_id"])} / {html.escape(record["display_name"])}</h2>'
                    f'<p>{html.escape(record["asset_id"])} — {html.escape(record["processing"]["caption"])} {html.escape(correction_error)}</p>'
                    f'<div class="views">{"".join(images)}</div>'
                    f'<h3>Visual observations (owner review: {overlay["caption_review"]})</h3>'
                    f'<p>{html.escape((effective["description"] or {}).get("description", "Caption failed; see evidence."))}</p>'
                    f'<pre>{html.escape(json.dumps(effective["description"], indent=2))}</pre>'
                    f'<h3>Suggested uses — interpretation</h3><p>{html.escape(json.dumps(effective["suggested_uses"]))}</p>'
                    f'<p>Artistic suitability: {overlay["artistic_suitability"]}. AI review: {html.escape(provenance.get("ai_review", "pending"))}.</p>'
                    f'<a href="../corrections/{overlay_path.name}">Editable owner correction overlay</a>'
                    f'<details><summary>Provenance, inspector facts and retained faults</summary><pre>{html.escape(json.dumps({"caption_provenance": provenance, "technical": record["technical"], "inspection_run": record.get("inspection_run")}, indent=2))}</pre></details></article>')
    page = '<!doctype html><meta charset="utf-8"><title>Pilot caption review</title><style>body{font:16px system-ui;margin:2rem;background:#eee;color:#222;max-width:1500px}article{background:white;padding:1rem;margin:2rem 0} .views{display:flex;flex-wrap:wrap}figure{margin:4px}img{width:300px;max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}h2{font-size:20px}</style><h1>Local vision caption review</h1><p>Actual input views. AI inspection is technical evidence; Bruno\'s caption and artistic approval remain pending. Suggestions are interpretations. Measured facts come exclusively from the inspector. Edit overlays, then run caption-review to refresh.</p>' + "".join(rows)
    target = config.output_path("data", f"captions/review/{name}.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    return target
