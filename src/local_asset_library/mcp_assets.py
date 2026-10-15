"""Bounded read-only agent interface. No client-controlled filesystem paths."""
import base64
import hashlib
from io import BytesIO
import json
import re

from .catalog import detail, encoded
from .caption_quality import caption_quality, caption_summary
from .config import ConfigError
from .retrieval import SearchEngine, pilot_records, preview_file, resolved_detail, validate_filters

from .search_policy import DEFAULT_MODE, MAX_LIMIT, search_character_cap

ID_PATTERN = r"asset_[0-9a-f]{32}"
FORMATS = ["blend", "dae", "fbx", "glb", "gltf", "obj", "stl"]
VIEWS = ["three_quarter", "front", "side"]
MODES = [DEFAULT_MODE, "keyword_description", "keyword", "description", "image", "reference"]
SEARCH_CAP = 6000
DETAIL_CAP = 16000
IMAGE_CAP = 512 * 1024
FILTER_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "pack": {"type": "string", "pattern": r"^[A-Za-z0-9_-]{1,128}$"},
    "format": {"type": "string", "enum": FORMATS},
    "max_triangles": {"type": "integer", "minimum": 0, "maximum": 1000000000},
    "rigged": {"type": "boolean"}}}
SCHEMAS = {
    "search_assets": {"type": "object", "additionalProperties": False, "properties": {
        "query": {"type": "string", "maxLength": 1024},
        "mode": {"type": "string", "enum": MODES, "default": DEFAULT_MODE},
        "filters": FILTER_SCHEMA, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": 5},
        "reference_asset_id": {"type": "string", "pattern": "^" + ID_PATTERN + "$"},
        "reference_view": {"type": "string", "enum": VIEWS, "default": "three_quarter"}}},
    "get_asset": {"type": "object", "required": ["asset_id"], "additionalProperties": False, "properties": {
        "asset_id": {"type": "string", "pattern": "^" + ID_PATTERN + "$"},
        "source_format": {"type": "string", "enum": FORMATS},
        "include_metadata": {"type": "boolean", "default": False},
        "include_preview": {"type": "boolean", "default": False},
        "preview_view": {"type": "string", "enum": VIEWS, "default": "three_quarter"}}}}


def validate(name, arguments):
    """Strict validation also applies inside the private worker, without coercion."""
    if name not in SCHEMAS or type(arguments) is not dict:
        raise ConfigError("Unknown tool or non-object arguments")
    schema = SCHEMAS[name]
    if set(arguments) - set(schema["properties"]) or set(schema.get("required", [])) - set(arguments):
        raise ConfigError("Unknown/missing arguments; filesystem paths are not accepted")
    for key, value in arguments.items():
        prop = schema["properties"][key]
        kind = prop["type"]
        if kind == "boolean" and type(value) is not bool:
            raise ConfigError("Boolean required: " + key)
        if kind == "integer" and (type(value) is not int or not prop["minimum"] <= value <= prop["maximum"]):
            raise ConfigError("Invalid integer: " + key)
        if kind == "string":
            if type(value) is not str or len(value) > prop.get("maxLength", 1024) or any(ord(c) < 32 for c in value):
                raise ConfigError("Invalid string: " + key)
            if "enum" in prop and value not in prop["enum"]:
                raise ConfigError("Unsupported value: " + key)
            if "pattern" in prop and not re.fullmatch(prop["pattern"], value):
                raise ConfigError("Invalid ID: " + key)
        if kind == "object":
            if type(value) is not dict:
                raise ConfigError("Filters must be an object")
            validate_filters(value)
            if "pack" in value and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value["pack"]):
                raise ConfigError("Invalid pack filter")
            if "format" in value and value["format"] not in FORMATS:
                raise ConfigError("Unsupported format filter")
            if value.get("max_triangles", 0) > 1000000000:
                raise ConfigError("Triangle filter exceeds cap")
    if name == "search_assets":
        mode = arguments.get("mode", DEFAULT_MODE)
        text = arguments.get("query", "")
        if mode == "reference":
            if text or "reference_asset_id" not in arguments:
                raise ConfigError("Reference search requires an asset ID and no text")
        elif not text.strip() or "reference_asset_id" in arguments or "reference_view" in arguments:
            raise ConfigError("Text search requires query and no reference arguments")
        if mode == "keyword" and len(text) > 256:
            raise ConfigError("Keyword query exceeds 256 characters")


def bounded(payload, cap, removable=None):
    payload.update(character_cap=cap, serialized_characters=0, estimated_tokens=0,
                   token_estimate_method="ceil(characters/4); heuristic, not client/model tokens")
    while True:
        for _ in range(12):
            size = len(encoded(payload))
            payload.update(serialized_characters=size, estimated_tokens=(size + 3) // 4)
        if len(encoded(payload)) <= cap:
            return payload
        if removable and payload.get(removable):
            payload[removable].pop()
            payload["truncated"] = True
        else:
            raise ConfigError("Response exceeds deterministic cap; no incomplete usable package returned")


def error_payload(exc, identifier=None):
    reason = str(exc) or type(exc).__name__
    identifier = identifier if isinstance(identifier,str) and re.fullmatch(ID_PATTERN,identifier) else None
    state = "stale" if "stale" in reason.lower() or "fingerprint mismatch" in reason.lower() else (
        "unavailable" if "missing" in reason.lower() or "unavailable" in reason.lower() else "unknown")
    return bounded({"status": "faulty", "availability": state, "asset_id": identifier,
                    "usable": False, "reason": reason[:800],
                    "policy": "Partial successes preserved; no automatic repair/retry or fallback."}, SEARCH_CAP)


class AssetService:
    def __init__(self, config, backend_factory=None, backend=None):
        self.config = config
        self.backend_factory = backend_factory
        self.backend = backend
        self.backend_fault = None
        self.query_faults = {}

    def record(self, identifier):
        if not re.fullmatch(ID_PATTERN, identifier):
            raise ConfigError("Malformed asset ID")
        from .membership import membership
        if identifier not in set(membership(self.config)['asset_ids']):
            raise ConfigError("Asset ID unavailable in configured approved membership")
        record = detail(self.config, identifier)
        if self.config.sources_registry:
            from .sources import visible
            if not visible(self.config, [record]):
                raise ConfigError('Asset source is disabled, removed, or awaiting processing/publication')
        return record

    def preview(self, record, view):
        item = next((p for p in record["previews"] if p.get("view_label") == view), None)
        if item is None:
            raise ConfigError("Requested preview view unavailable; no substitute")
        return item, preview_file(self.config, item)

    from .publication import pinned

    @pinned
    def execute(self, name, args):
        from .publication import generation
        from .sources import revision
        version = (generation(self.config), revision(self.config))
        if getattr(self, '_publication_version', None) != version:
            self.query_faults.clear()
            self._publication_version = version
        validate(name, args)
        return self.search(args) if name == "search_assets" else self.get(args)

    def search(self, args):
        mode = args.get("mode", DEFAULT_MODE)
        key = encoded(args)
        if key in self.query_faults:
            raise ConfigError("Unchanged faulty query retained: " + self.query_faults[key])
        has_sources = bool(pilot_records(self.config)) if self.config.sources_registry else True
        if mode != "keyword" and has_sources and self.backend is None:
            if self.backend_fault:
                raise ConfigError("Embedding runtime faulty; explicit repair/retry required: " + self.backend_fault)
            try:
                if not self.backend_factory:
                    raise ConfigError("Embedding worker unavailable")
                self.backend = self.backend_factory(self.config)
            except Exception as exc:
                self.backend_fault = str(exc)
                raise
        reference = None
        if mode == "reference":
            record = self.record(args["reference_asset_id"])
            resolved_detail(self.config, record["asset_id"])
            preview, _ = self.preview(record, args.get("reference_view", "three_quarter"))
            reference = preview.get("path") or "source/" + preview["source_path"]
        try:
            response, evidence = SearchEngine(self.config, self.backend).search(
                args.get("query", ""), mode=mode, reference=reference,
                filters=args.get("filters"), limit=args.get("limit", 5))
        except Exception as exc:
            self.query_faults[key] = str(exc)
            raise
        # Replace internal path with an ID reference, never pretend that it is a viewed image.
        response["query"] = args.get("query", "") if mode != "reference" else args["reference_asset_id"]
        faults = list(evidence["excluded"])
        for item in response["results"]:
            record = self.record(item["asset_id"])
            item["preview"] = {"asset_id": item["asset_id"], "request": "get_asset(include_preview=true)"} if item["preview"] else None
            for preview in record["previews"]:
                try:
                    preview_file(self.config, preview)
                except (OSError, ValueError) as exc:
                    faults.append({"asset_id": item["asset_id"], "channel": "preview", "reason": str(exc)})
        response["faults"] = [{"asset_id": f["asset_id"], "status": "faulty", "channel": f["channel"], "reason": f["reason"][:120]} for f in faults[:3]]
        response["fault_count"] = len(faults)
        response["fault_evidence"] = "Recorded separately in this server's local call audit"
        from .publication import generation
        response['generation'] = generation(self.config)
        return bounded(response, search_character_cap(args.get("limit", 5)), "results"), None, {"excluded": faults, "elapsed_seconds": evidence["elapsed_seconds"]}

    def get(self, args):
        record = self.record(args["asset_id"])
        result = resolved_detail(self.config, record["asset_id"], args.get("source_format"))
        deps = result["dependencies"]
        if len(deps) > 64:
            raise ConfigError("Dependency count exceeds 64; cannot return an incomplete usable package")
        payload = {"asset_id": record["asset_id"], "name": record["display_name"], "pack": record["pack_id"],
                   "availability": "available", "status": "available", "usable": True,
                   "selected_source": result["selected_source"], "dependencies": deps,
                   "dependency_completeness": "Known references verified; uninspected binary/alternate dependencies remain unknown",
                   "source_faults": (record.get("inspection_run") or {}).get("source_faults", []),
                   **caption_summary(self.config, record),
                   "limitations": result["limitations"], "preview": {"status": "not_requested"}}
        if result.get('texture_overrides'):
            payload['texture_overrides'] = result['texture_overrides']
        from .publication import generation
        payload['generation'] = generation(self.config)
        if args.get("include_metadata", False):
            technical = record.get("technical") or {}
            payload["metadata"] = {"formats": sorted({f["format"] for f in record["files"]}),
                "technical": {k: technical.get(k) for k in ("inspected_path", "inspected_sha256", "inspected_format", "evaluated_instance_totals", "unit_settings")},
                "description": record.get("description"), "suggested_uses": record.get("suggested_uses"),
                "processing": record["processing"], "license_evidence": record.get("license_evidence"),
                'stage_faults':record.get('stage_faults',{}), 'inspection_run':record.get('inspection_run'),
                "caption_quality": caption_quality(self.config, record),
                "caption_fault_evidence": (record.get("caption_provenance") or {}).get("visual_faults", [])}
        image = None
        faults = []
        if args.get("include_preview", False):
            try:
                preview, path = self.preview(record, args.get("preview_view", "three_quarter"))
                from PIL import Image, ImageOps
                if path.stat().st_size > 16 * 1024 * 1024:
                    raise ConfigError("Preview source exceeds 16 MiB decode cap")
                with Image.open(path) as source:
                    if source.width * source.height > 16000000:
                        raise ConfigError("Preview exceeds pixel cap")
                    source.load()
                    output = ImageOps.exif_transpose(source).convert("RGBA")
                    output.thumbnail((512, 512), Image.Resampling.LANCZOS)
                    stream = BytesIO()
                    output.save(stream, format="PNG", optimize=True)
                blob = stream.getvalue()
                if len(blob) > IMAGE_CAP:
                    raise ConfigError("Derived PNG exceeds 512 KiB cap")
                image = base64.b64encode(blob).decode("ascii")
                payload["preview"] = {"status": "image_content", "view": preview["view_label"], "mime_type": "image/png",
                    "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "source_sha256": preview["sha256"],
                    "dimensions": list(output.size), "delivery": "MCP ImageContent base64; client/model inspection must be verified separately"}
            except (OSError, ValueError) as exc:
                payload["preview"] = {"status": "faulty", "reason": str(exc)[:400]}
                faults.append({"asset_id": record["asset_id"], "channel": "preview", "reason": str(exc)})
        return bounded(payload, DETAIL_CAP), image, {"excluded": faults}
