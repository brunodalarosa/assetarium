"""Bounded agent interface. No client-controlled filesystem paths except the setup tools' checked Blender path."""
import base64
import hashlib
from io import BytesIO
import json
import re

from .catalog import detail, encoded, relevant_license_evidence
from .caption_quality import caption_quality, caption_summary
from .config import ConfigError
from .retrieval import SearchEngine, pilot_records, preview_file, resolved_detail, validate_filters

from .search_policy import DEFAULT_MODE, MAX_LIMIT, search_character_cap
from .asset_structure import ASSET_TYPES, structure, supported_stage
from .image_media import FORMATS as IMAGE_FORMATS
from .setup_core import ENGINE_HINTS

ID_PATTERN = r"asset_[0-9a-f]{32}"
COLLECTION_PATTERN = r"col_[0-9a-f]{16}"
FORMATS = ["blend", "dae", "fbx", "glb", "gltf", "obj", "stl", *sorted(IMAGE_FORMATS), "wav"]
SIZE_CLASSES = ["tiny", "small", "medium", "large"]
IMAGE_FACTS = ("width", "height", "alpha", "alpha_coverage", "visible_bounds", "color_count", "size_class", "aspect",
               "pixel_art_candidate", "mode", "format", "frames", "vector")
VIEWS = ["three_quarter", "front", "side", "image"]
MODES = [DEFAULT_MODE, "keyword_description", "keyword", "description", "image", "reference"]
SEARCH_CAP = 6000
DETAIL_CAP = 16000
IMAGE_CAP = 512 * 1024
FILTER_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "asset_type": {"type": "string", "enum": list(ASSET_TYPES)},
    "pack": {"type": "string", "pattern": r"^[A-Za-z0-9_-]{1,128}$"},
    "format": {"type": "string", "enum": FORMATS},
    "max_triangles": {"type": "integer", "minimum": 0, "maximum": 1000000000},
    "rigged": {"type": "boolean"},
    "transparent": {"type": "boolean", "description": "Images only: measured alpha below 255 anywhere."},
    "size_class": {"type": "string", "enum": SIZE_CLASSES,
                   "description": "Images only, by longest edge: tiny <=32, small <=128, medium <=1024, large."},
    "collection": {"type": "string", "pattern": "^" + COLLECTION_PATTERN + "$",
                   "description": "Only members of this collection (from list_collections)."},
    "tag": {"type": "string", "maxLength": 32, "description": "Only assets carrying this owner tag."}}}
ASSET_IDS = {"type": "array", "maxItems": 200, "items": {"type": "string", "pattern": "^" + ID_PATTERN + "$"}}
TAG_LIST = {"type": "array", "maxItems": 24, "items": {"type": "string", "maxLength": 32}}
EDIT_ACTIONS = ["create", "rename", "describe", "add", "remove", "set_item"]
SCHEMAS = {
    "search_assets": {"type": "object", "additionalProperties": False, "properties": {
        "query": {"type": "string", "maxLength": 1024},
        "mode": {"type": "string", "enum": MODES, "default": DEFAULT_MODE},
        "filters": FILTER_SCHEMA, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": 5},
        "reference_asset_id": {"type": "string", "pattern": "^" + ID_PATTERN + "$"},
        "reference_view": {"type": "string", "enum": VIEWS, "description": "Default: image for images, three_quarter for models."}}},
    "get_asset": {"type": "object", "required": ["asset_id"], "additionalProperties": False, "properties": {
        "asset_id": {"type": "string", "pattern": "^" + ID_PATTERN + "$"},
        "source_format": {"type": "string", "enum": FORMATS},
        "source_variant": {"type": "string", "maxLength": 128,
                           "description": "Folder label of one of this asset's files, from source_variants (for example \"Unity FBX\"); "
                                          "chooses between files of the same format. Never a path."},
        "include_metadata": {"type": "boolean", "default": False},
        "include_preview": {"type": "boolean", "default": False},
        "preview_view": {"type": "string", "enum": VIEWS, "description": "Default: image for images, three_quarter for models."}}},
    "list_collections": {"type": "object", "additionalProperties": False, "properties": {
        "query": {"type": "string", "maxLength": 200, "description": "Matches collection names/descriptions and the assets inside (names, labels, notes, tags, descriptions)."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20}}},
    "get_collection": {"type": "object", "required": ["collection_id"], "additionalProperties": False, "properties": {
        "collection_id": {"type": "string", "pattern": "^" + COLLECTION_PATTERN + "$"},
        "offset": {"type": "integer", "minimum": 0, "maximum": 2000, "default": 0},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}}},
    "edit_collection": {"type": "object", "required": ["action"], "additionalProperties": False, "properties": {
        "action": {"type": "string", "enum": EDIT_ACTIONS},
        "collection_id": {"type": "string", "pattern": "^" + COLLECTION_PATTERN + "$", "description": "Required except for create."},
        "name": {"type": "string", "maxLength": 80, "description": "create/rename; unique ignoring case."},
        "description": {"type": "string", "maxLength": 2000, "description": "create/describe."},
        "asset_ids": {**ASSET_IDS, "description": "create/add/remove; approved library members only. set_item takes exactly one."},
        "label": {"type": "string", "maxLength": 60, "description": "Per-collection label (where the asset is used); create/add/set_item."},
        "notes": {"type": "string", "maxLength": 4000, "description": "Per-collection implementation notes; create/add/set_item."}}},
    "tag_assets": {"type": "object", "required": ["asset_ids"], "additionalProperties": False, "properties": {
        "asset_ids": ASSET_IDS, "add": {**TAG_LIST, "description": "Owner tags to add (shared app-wide, not per collection)."},
        "remove": {**TAG_LIST, "description": "Owner tags to remove."}}},
    # Setup (decision 0016): writes need a setup session the user opened in the app; Blender is only proposed.
    "get_setup_status": {"type": "object", "additionalProperties": False, "properties": {}},
    "validate_blender": {"type": "object", "required": ["path"], "additionalProperties": False, "properties": {
        "path": {"type": "string", "maxLength": 1024, "description": "Absolute path of a file named blender.exe (Windows) or blender; nothing else is run."}}},
    "apply_setup": {"type": "object", "additionalProperties": False, "properties": {
        "storage_budget_gib": {"type": "integer", "minimum": 1, "maximum": 1048576},
        "processing_formats": {"type": "array", "maxItems": 3, "items": {"type": "string", "enum": ["fbx", "gltf", "obj"]},
                               "description": "Formats to process; .glb counts as gltf; [] pauses processing."},
        "caption_batch_size": {"type": "integer", "minimum": 1, "maximum": 8, "enum": [1, 2, 4, 8]},
        "descriptions_enabled": {"type": "boolean"},
        "description_engine": {"type": "string", "enum": ["builtin", "local-server"],
                               "description": "builtin: NVIDIA CUDA BF16. local-server: an OpenAI-compatible vision model server already running on this computer (llama.cpp, Ollama, LM Studio)."},
        "description_server": {"type": "object", "additionalProperties": False, "properties": {
            "url": {"type": "string", "maxLength": 256, "description": "Loopback only, e.g. http://127.0.0.1:8080/v1."},
            "model": {"type": "string", "maxLength": 256}}},
        "search_device": {"type": "string", "enum": ["cuda", "cpu"],
                          "description": "Where semantic and image search run: cuda (NVIDIA GPU with BF16) or cpu (any x86-64 CPU; slower first index)."},
        "engine_hint": {"type": "string", "enum": [hint["id"] for hint in ENGINE_HINTS]}}},
    "propose_setup": {"type": "object", "required": ["blender_path"], "additionalProperties": False, "properties": {
        "blender_path": {"type": "string", "maxLength": 1024, "description": "A path validate_blender passed; the user applies it in the app."}}},
    "finish_setup": {"type": "object", "additionalProperties": False, "properties": {}}}
WRITE_TOOLS = {"edit_collection", "tag_assets", "apply_setup", "propose_setup", "finish_setup"}
SETUP_TOOLS = {"get_setup_status", "validate_blender", "apply_setup", "propose_setup", "finish_setup"}
COLLECTION_MEANING = ("A collection is a named, owner-organized bundle of asset IDs, not an asset. Members keep their files "
                      "where they are; labels and notes belong to the collection. Use get_asset on a member for its files.")


def default_view(record):
    return 'image' if record.get('asset_type') == 'image' else 'three_quarter'


class TransientFault(ConfigError):
    """Availability faults (busy GPU queue, stopped worker) are not retained per query."""


def source_variants(record, problems=None):
    """The asset's files by folder label (decision 0019), so an agent can ask for one by name; empty when single.

    Unusable alternate files (decision 0020) are listed with ``usable: false`` and their reason.
    """
    from .catalog import file_variants
    labels, problems = file_variants(record), problems or {}
    if not labels:
        return {}
    return {"source_variants": [{"variant": labels[f["path"]], "format": f["format"], "usable": f["path"] not in problems,
                                 **({"reason": problems[f["path"]]} if f["path"] in problems else {})}
                                for f in record["files"] if f["path"] in labels]}


def check_string(key, value, prop, multiline=False):
    allowed = "\n\t" if multiline else ""
    if type(value) is not str or len(value) > prop.get("maxLength", 1024) or any(ord(c) < 32 and c not in allowed for c in value):
        raise ConfigError("Invalid string: " + key)
    if "enum" in prop and value not in prop["enum"]:
        raise ConfigError("Unsupported value: " + key)
    if "pattern" in prop and not re.fullmatch(prop["pattern"], value):
        raise ConfigError("Invalid ID: " + key)


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
        if kind == "integer" and (type(value) is not int or not prop["minimum"] <= value <= prop["maximum"]
                                  or value not in prop.get("enum", [value])):
            raise ConfigError("Invalid integer: " + key)
        if kind == "array":
            if type(value) is not list or len(value) > prop["maxItems"]:
                raise ConfigError("Invalid list: " + key)
            for item in value:
                check_string(key, item, prop["items"])
        if kind == "string":
            # Notes may hold line breaks; other strings stay single-line.
            check_string(key, value, prop, multiline=key == "notes" or (name == "edit_collection" and key == "description"))
        if kind == "object" and key == "description_server":
            if type(value) is not dict or set(value) - set(prop["properties"]):
                raise ConfigError("description_server takes url and model only")
            for part, text in value.items():
                check_string(key + "." + part, text, prop["properties"][part])
        elif kind == "object":
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


def bounded_detail(payload):
    """Optional evidence must not discard a verified, complete source package."""
    while True:
        try:
            return bounded(payload, DETAIL_CAP)
        except ConfigError:
            metadata = payload.get('metadata', {})
            optional = set(metadata) - {'formats', 'processing'}
            if not optional:
                raise  # Never trim source paths, dependencies, or source faults.
            key = max(optional, key=lambda name: (len(encoded(metadata[name])), name))
            metadata.pop(key)
            delivery = payload.setdefault('metadata_delivery', {
                'status': 'partial', 'omitted_fields': [],
                'reason': 'Optional metadata exceeds the response limit; full evidence remains in the local catalog. Source and dependencies are complete.'})
            delivery['omitted_fields'].append(key)


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
        handler = {"search_assets": self.search, "get_asset": self.get, "list_collections": self.list_collections,
                   "get_collection": self.get_collection, "edit_collection": self.edit_collection,
                   "tag_assets": self.tag_assets}[name]
        return handler(args)

    def list_collections(self, args):
        from .asset_collections import summaries
        found = summaries(self.config, args.get("query", ""))["collections"]
        limit = args.get("limit", 20)
        items = [{"collection_id": c["collection_id"], "name": c["name"], "description": c["description"][:300],
                  "asset_count": c["asset_count"], "updated_at": c["updated_at"], **({"match": c["match"]} if "match" in c else {})}
                 for c in found[:limit]]
        payload = {"status": "collections" if items else "no_match", "kind": "collection_list", "query": args.get("query", ""),
                   "total_matching": len(found), "collections": items, "meaning": COLLECTION_MEANING}
        return bounded(payload, SEARCH_CAP, "collections"), None, {}

    def get_collection(self, args):
        from .asset_collections import detail
        value = detail(self.config, args["collection_id"])
        offset, limit = args.get("offset", 0), args.get("limit", 50)
        items = [{"asset_id": e["asset_id"], "name": e["name"], "asset_type": e["asset_type"], "source": e["source_name"],
                  "label": e["label"], "notes": e["notes"], "tags": e["tags"], "availability": e["availability"],
                  **({"reason": e["reason"]} if e.get("reason") else {})} for e in value["items"][offset:offset + limit]]
        payload = {"status": "collection", "kind": "collection", "collection_id": value["collection_id"], "name": value["name"],
                   "description": value["description"], "updated_at": value["updated_at"], "asset_count": value["asset_count"],
                   "offset": offset, "items": items, "meaning": COLLECTION_MEANING}
        while True:
            end = offset + len(payload["items"])
            payload["next_offset"] = end if end < value["asset_count"] else None
            bounded(payload, DETAIL_CAP, "items")
            if payload["next_offset"] == (offset + len(payload["items"]) if offset + len(payload["items"]) < value["asset_count"] else None):
                return payload, None, {}

    def edit_collection(self, args):
        from . import asset_collections as collections
        action, identifier = args["action"], args.get("collection_id")
        if (action == "create") == (identifier is not None):
            raise ConfigError("create takes no collection_id; every other action requires one")
        members = args.get("asset_ids", [])
        if (action in {"create", "rename"} and not args.get("name") or action == "describe" and "description" not in args
                or action in {"add", "remove", "set_item"} and not members):
            raise ConfigError(action + " requires " + {"create": "name", "rename": "name", "describe": "description"}.get(action, "asset_ids"))
        if action == "create":
            result = collections.create(self.config, args["name"], args.get("description", ""), members,
                                        label=args.get("label", ""), notes=args.get("notes", ""), actor="agent")
        elif action in {"rename", "describe"}:
            result = collections.update(self.config, identifier, name=args.get("name") if action == "rename" else None,
                                        description=args.get("description") if action == "describe" else None, actor="agent")
        elif action == "add":
            result = collections.add(self.config, identifier, members, label=args.get("label", ""), notes=args.get("notes", ""), actor="agent")
        elif action == "remove":
            result = collections.remove(self.config, identifier, members, actor="agent")
            result = dict(result, removed=len(result["removed"]))
        else:
            if len(members) != 1 or ("label" not in args and "notes" not in args):
                raise ConfigError("set_item takes exactly one asset ID and a label and/or notes")
            result = collections.set_item(self.config, identifier, members[0], args.get("label"), args.get("notes"), actor="agent")
        return bounded(dict(result, action=action), SEARCH_CAP), None, {}

    def tag_assets(self, args):
        from .asset_collections import library
        from .asset_tags import change
        if not args.get("add") and not args.get("remove"):
            raise ConfigError("Give tags to add and/or remove")
        members = library(self.config)
        missing = [i for i in args["asset_ids"] if i not in members]
        if missing:
            raise ConfigError("Asset ID unavailable in configured approved membership: " + ", ".join(missing[:3]))
        return bounded(change(self.config, args["asset_ids"], args.get("add", []), args.get("remove", [])), SEARCH_CAP), None, {}

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
            view = args.get("reference_view", default_view(record))
            # A 2D image query uses the same derived model input as its index vector.
            preview, _ = self.preview(record, 'model_input' if record.get('asset_type') == 'image' and view == 'image' else view)
            reference = preview.get("path") or "source/" + preview["source_path"]
        try:
            # Keyword search never touches the embedding runtime or its contract.
            response, evidence = SearchEngine(self.config, self.backend if mode != "keyword" else None).search(
                args.get("query", ""), mode=mode, reference=reference,
                filters=args.get("filters"), limit=args.get("limit", 5))
        except Exception as exc:
            if not isinstance(exc, TransientFault):
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
        result = resolved_detail(self.config, record["asset_id"], args.get("source_format"), args.get("source_variant"))
        deps = result["dependencies"]
        if len(deps) > 64:
            raise ConfigError("Dependency count exceeds 64; cannot return an incomplete usable package")
        from .packs import fields
        payload = {"asset_id": record["asset_id"], "name": record["display_name"], "pack": record["pack_id"],
                   **fields(self.config, record),  # The detected pack inside the library folder (decision 0023).
                   'asset_type': record.get('asset_type', 'model_3d'), 'parent_asset_id': record.get('parent_asset_id'),
                   "availability": "available", "status": "available", "usable": True,
                   "selected_source": result["selected_source"], "dependencies": deps,
                   **source_variants(record, result["unusable_files"]),
                   "dependency_completeness": "Known references verified; uninspected binary/alternate dependencies remain unknown",
                   "source_faults": (record.get("inspection_run") or {}).get("source_faults", []),
                   **caption_summary(self.config, record),
                   "limitations": result["limitations"], "preview": {"status": "not_requested"}}
        if result.get('texture_overrides'):
            payload['texture_overrides'] = result['texture_overrides']
        from .asset_collections import load as load_collections
        from .asset_tags import tags_for
        payload['tags'] = tags_for(self.config, record['asset_id'])
        payload['collections'] = [{'collection_id': c['id'], 'name': c['name'], 'label': item['label']}
                                  for c in load_collections(self.config)['collections']
                                  for item in c['items'] if item['asset_id'] == record['asset_id']][:20]
        from .publication import generation
        payload['generation'] = generation(self.config)
        if args.get("include_metadata", False):
            technical = record.get("technical") or {}
            keys = ("inspected_path", "inspected_sha256", "inspected_format") + (
                IMAGE_FACTS if record.get('asset_type') == 'image' else ("evaluated_instance_totals", "unit_settings"))
            payload["metadata"] = {"formats": sorted({f["format"] for f in record["files"]}),
                "technical": {k: technical.get(k) for k in keys},
                "description": record.get("description"), "suggested_uses": record.get("suggested_uses"),
                "processing": record["processing"], "license_evidence": relevant_license_evidence(record),
                'stage_faults':record.get('stage_faults',{}), 'inspection_run':record.get('inspection_run'),
                "caption_quality": caption_quality(self.config, record),
                "caption_fault_evidence": (record.get("caption_provenance") or {}).get("visual_faults", []),
                'asset_structure': structure(record), 'type_metadata': record.get('type_metadata', {'version': 1}),
                'relationships': record.get('relationships', [])}
        image = None
        faults = []
        if args.get("include_preview", False):
            payload["preview"], image, faults = self.preview_content(record, args.get("preview_view", default_view(record)))
        return bounded_detail(payload), image, {"excluded": faults}

    def preview_content(self, record, view, size=512, optimize=True):
        """Requested view as derived PNG, or its pending/excluded/faulty state; no substitute view."""
        try:
            has_view = any(p.get('view_label') == view for p in record['previews'])
            if not has_view and not supported_stage(record, 'previews'):
                return ({'status': 'unsupported', 'reason': 'This asset has no implemented preview adapter.'}, None, [])
            pending_preview = (not has_view and record['processing'].get('previews') in {'pending', 'unknown'}
                and record['processing'].get('inspection') not in {'failed', 'unsupported'}
                and not (record.get('inspection_run') or {}).get('source_faults')
                and not (record.get('inspection_run') or {}).get('errors')
                and not any(k in record.get('stage_faults', {}) for k in ('inspection', 'previews')))
            if pending_preview:
                from .settings import processing_eligible, processing_formats
                eligible = processing_eligible(record, processing_formats(self.config))
                return (({'status': 'pending', 'reason': 'Preview has not been generated.'} if eligible else
                         {'status': 'excluded', 'reason': 'Preview has not been generated because this source format is not selected in Settings → General.'}),
                        None, [])
            preview, path = self.preview(record, view)
            from PIL import Image, ImageOps
            if path.stat().st_size > 16 * 1024 * 1024:
                raise ConfigError("Preview source exceeds 16 MiB decode cap")
            with Image.open(path) as source:
                if source.width * source.height > 16000000:
                    raise ConfigError("Preview exceeds pixel cap")
                source.load()
                output = ImageOps.exif_transpose(source).convert("RGBA")
                native = list(output.size)
                scaling = {}
                if record.get('asset_type') == 'image' and max(output.size) < size // 2:
                    # Small art is enlarged with hard pixel edges so a client can see it; alpha is kept.
                    factor = (size // 2) // max(output.size)
                    output = output.resize((output.width * factor, output.height * factor), Image.Resampling.NEAREST)
                    scaling = {'scale': factor, 'resample': 'nearest'}
                output.thumbnail((size, size), Image.Resampling.LANCZOS)
                stream = BytesIO()
                output.save(stream, format="PNG", optimize=optimize)
            blob = stream.getvalue()
            if len(blob) > IMAGE_CAP:
                raise ConfigError("Derived PNG exceeds 512 KiB cap")
            content = {"status": "image_content", "view": preview["view_label"], "mime_type": "image/png",
                       "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "source_sha256": preview["sha256"],
                       "dimensions": list(output.size), "delivery": "MCP ImageContent base64; client/model inspection must be verified separately"}
            if record.get('asset_type') == 'image':
                content.update(native_dimensions=native, transparency='preserved as PNG alpha', **scaling,
                               pixels='original source pixels' if preview.get('role') == 'original' else
                               'rasterized from the SVG source by ' + (preview.get('derivation') or {}).get('renderer', 'the recorded renderer'))
            return content, base64.b64encode(blob).decode("ascii"), []
        except (OSError, ValueError) as exc:
            return ({"status": "faulty", "reason": str(exc)[:400]}, None,
                    [{"asset_id": record["asset_id"], "channel": "preview", "reason": str(exc)}])
