"""Source registration, source-owned metadata and the combined read-only catalog.

Logical data/ paths are retained in records so moving results never changes an
embedding input. Only this resolver translates them to metadata-lal directories.
"""
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from functools import lru_cache
import json
import ntpath
import os
from pathlib import Path
import re
import sqlite3
import uuid

from .config import ConfigError, _inside, _relative
from .publication import atomic_json, read_json, read_only
from .settings import processing_formats, processing_eligible, format_group, PROCESSING_FORMATS

SHARED_DATA = {
    "embeddings/capability.json", "embeddings/model-download.json",
    "captions/model-download.json", "captions/model-preflight.json",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def registry(config):
    if not config.sources_registry:
        return {"schema_version": 1, "revision": "legacy", "sources": [], "detached": []}
    from .publication import request_memo
    return request_memo(("registry", str(config.sources_registry), str(config.models_root)), lambda: _registry(config))


def _registry(config):
    if not config.sources_registry.exists():
        return {"schema_version": 1, "revision": "empty", "sources": [], "detached": []}
    stat = config.sources_registry.stat()
    return _registry_file(config.sources_registry, stat.st_mtime_ns, stat.st_size,
                          config.project_root, config.models_root)


@lru_cache(maxsize=16)
def _registry_file(path, stamp, size, project_root, models_root):
    from .config import Config
    config = Config(project_root, project_root.parent / '.lal-managed-sources', None, models_root)
    value = read_json(path)
    if value.get("schema_version") != 1 or not isinstance(value.get("sources"), list):
        raise ConfigError("Invalid source settings")
    seen, identifiers, roots = set(), set(), []
    for item in value["sources"]:
        key = item.get("key", "")
        if (not key or key in seen or item.get('id') in identifiers or len(Path(key).parts) != 1 or "/" in key or "\\" in key
                or key in {".", "..", "metadata-lal"} or not re.fullmatch(r"[0-9a-f]{32}", item.get("id", ""))
                or type(item.get("enabled")) is not bool):
            raise ConfigError("Invalid or duplicate asset source")
        _relative(key)
        root = validate_directory(config, item["path"], require_exists=False)
        if any(root.is_relative_to(p) or p.is_relative_to(root) for p in roots):
            raise ConfigError("Asset source directories overlap")
        roots.append(root)
        seen.add(key)
        identifiers.add(item['id'])
    return value


def validate_directory(config, value, require_exists=True):
    from .publication import request_memo
    return request_memo(('source-directory', value, require_exists, str(config.project_root), str(config.models_root)),
                        lambda: _validate_directory(config, value, require_exists))


def _validate_directory(config, value, require_exists=True):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ConfigError("Choose an absolute asset directory")
    path = Path(value)
    if ".." in path.parts or any(ntpath.isreserved(p) or p.endswith((".", " ")) for p in path.parts[1:]):
        raise ConfigError("Ambiguous asset directory")
    resolved = path.resolve()
    if resolved != path.absolute():
        raise ConfigError("Asset source directory links are not supported")
    if require_exists and not resolved.is_dir():
        raise ConfigError("Asset source directory is unavailable")
    for other in (config.project_root, config.models_root):
        if other and (resolved.is_relative_to(other) or other.is_relative_to(resolved)):
            raise ConfigError("Asset sources must not overlap LAL or shared models")
    metadata = resolved / "metadata-lal"
    if metadata.is_symlink() or metadata.is_junction() or metadata.resolve() != metadata:
        raise ConfigError("metadata-lal must be a regular directory inside its source")
    return resolved


def get_source(config, key, include_detached=False):
    value = registry(config)
    items = value["sources"] + (value.get("detached", []) if include_detached else [])
    source = next((s for s in items if s["key"] == key), None)
    if source is None:
        raise ConfigError("Asset source is not registered")
    return source


def source_for_path(config, relative):
    key = relative.replace("\\", "/").split("/", 1)[0]
    if config.source_key and key != config.source_key:
        raise ConfigError("Original file belongs to a different asset source")
    return get_source(config, key)


def bound(config, source):
    path = validate_directory(config, source["path"], require_exists=False)
    return replace(config, source_root=path, source_key=source["key"],
                   metadata_root=path / "metadata-lal", catalog_generation=None)


def import_formats(config):
    """Optional source-specific inventory restriction, separate from work settings.

    Processing checkboxes retain existing imports. A deliberate import cleanup
    can additionally restrict a source so later scans do not recreate its imports.
    """
    if config.metadata_root is None:
        return None
    path = config.output_path('data', 'source.json')
    if not path.exists():
        return None
    value = read_json(path)
    if 'import_formats' not in value:
        return None
    from .settings import validate_formats
    return validate_formats(value['import_formats'])


IMPORT_TYPES = ('model_3d', 'image')


def import_types(config):
    """Asset types a source enrolls. Images are an explicit per-source choice."""
    if config.metadata_root is None:
        return ('model_3d',)
    path = config.output_path('data', 'source.json')
    value = read_json(path) if path.exists() else {}
    types = value.get('import_types', ['model_3d'])
    if not isinstance(types, list) or not set(types) <= set(IMPORT_TYPES) or 'model_3d' not in types:
        raise ConfigError('Invalid saved source asset types; choose them again in Settings → Asset sources')
    return tuple(t for t in IMPORT_TYPES if t in types)


def set_import_types(config, key, images):
    """Save whether a source enrolls images; existing results are never deleted."""
    from .gpu_queue import lease
    from .source_operations import active_operation
    if type(images) is not bool:
        raise ConfigError('Images must be a checkbox value')
    source = get_source(config, key)
    scoped = bound(config, source)
    if active_operation(scoped):
        raise ConfigError("Wait for this source's operation to finish before changing its asset types")
    with lease(config, 'source-settings', resource='sources'):
        path = scoped.output_path('data', 'source.json')
        value = read_json(path)
        value['import_types'] = ['model_3d', 'image'] if images else ['model_3d']
        atomic_json(path, value)
    return source


def _source_settings(config):
    if config.metadata_root is None:
        return {}
    path = config.output_path('data', 'source.json')
    return read_json(path) if path.exists() else {}


def validate_exclusion(pattern):
    """A folder-name pattern (``Unity*``) or a folder path from the source root (``Weapons/Unity FBX``)."""
    if not isinstance(pattern, str):
        raise ConfigError('Enter a folder name or a path inside the source')
    value = pattern.strip().replace('\\', '/').strip('/')
    parts = value.split('/')
    if (not value or len(value) > 200 or any(ord(c) < 32 for c in value) or ':' in value
            or any(part in {'', '.', '..'} for part in parts) or value.casefold() == 'metadata-lal'):
        raise ConfigError('Enter a folder name like "Unity*" or a path inside the source like "Models/Unity FBX"')
    return value


def excluded_folders(config):
    """Folders a scan skips entirely (decision 0019): not walked, hashed or imported."""
    value = _source_settings(config).get('excluded_folders', [])
    if not isinstance(value, list) or len(value) > 50:
        raise ConfigError('Invalid saved excluded folders; set them again in Settings → Asset sources')
    return [validate_exclusion(item) for item in value]


def export_decisions(config):
    """Owner answers to duplicate export folder suggestions: group or keep separate (decision 0019)."""
    value = _source_settings(config).get('export_decisions', [])
    if not isinstance(value, list) or any(not isinstance(item, dict) or item.get('decision') not in {'group', 'separate'}
                                          for item in value):
        raise ConfigError('Invalid saved export folder decisions; answer the suggestions again in Settings → Asset sources')
    return value


def _change_source_settings(config, key, change, busy_reason):
    from .gpu_queue import lease
    from .source_operations import active_operation
    source = get_source(config, key)
    scoped = bound(config, source)
    if active_operation(scoped):
        raise ConfigError(busy_reason)
    with lease(config, 'source-settings', resource='sources'):
        path = scoped.output_path('data', 'source.json')
        value = read_json(path)
        change(value)
        atomic_json(path, value)
    return source


def set_excluded_folders(config, key, patterns):
    """Save a source's excluded folders; the caller rescans. Nothing on disk is deleted."""
    if not isinstance(patterns, list) or len(patterns) > 50:
        raise ConfigError('Give up to 50 excluded folders')
    cleaned = list(dict.fromkeys(validate_exclusion(item) for item in patterns))
    return _change_source_settings(config, key, lambda value: value.update(excluded_folders=cleaned),
                                   "Wait for this source's operation to finish before changing its excluded folders")


def decide_export(config, key, suggestion_id, decision):
    """Group a suggested duplicate export folder set, keep it separate, or exclude its extra folders."""
    if decision not in {'group', 'separate', 'exclude'}:
        raise ConfigError('Choose Group, Keep separate or Exclude')
    source = get_source(config, key)
    status = source_status(config, source)
    suggestion = next((s for s in status.get('export_suggestions', []) if s['id'] == suggestion_id), None)
    if suggestion is None:
        raise ConfigError('This suggestion is no longer current; the source was scanned again since it was shown')
    if decision == 'exclude':
        # Keep the reference folder and any folders already grouped with it; exclude the extra copies.
        extra = [(suggestion['anchor'] + '/' + folder).strip('/') for folder in suggestion['folders']
                 if folder != suggestion['reference'] and folder not in suggestion['grouped_folders']]
        return set_excluded_folders(config, key, excluded_folders(bound(config, source)) + extra)
    entry = {k: suggestion[k] for k in ('id', 'anchor', 'folders', 'reference', 'names', 'name_manifest_sha256')}
    entry.update(decision=decision, utc=now())
    def change(value):
        value['export_decisions'] = [d for d in value.get('export_decisions', []) if d.get('id') != suggestion_id] + [entry]
    return _change_source_settings(config, key, change, "Wait for this source's operation to finish before answering")


def texture_folder(config):
    """The owner's texture folder choice for models missing textures (decision 0021), or None."""
    value = _source_settings(config).get('texture_folder')
    if value is None:
        return None
    if (not isinstance(value, dict) or not (value.get('folder') is None or isinstance(value.get('folder'), str))
            or type(value.get('single_copies')) is not bool or (value.get('folder') is None and not value['single_copies'])):
        raise ConfigError('Invalid saved texture folder; choose it again in Settings → Asset sources')
    return value


def set_texture_folder(config, key, folder, single_copies):
    """Save a texture folder choice offered by the current suggestion; the caller rescans. Originals never change."""
    if type(single_copies) is not bool or not (folder is None or isinstance(folder, str)):
        raise ConfigError('Choose a suggested folder and whether to use single copies')
    if folder is None and not single_copies:
        raise ConfigError('Choose a texture folder, single copies, or both')
    source = get_source(config, key)
    offered = (source_status(config, source).get('texture_suggestion') or {}).get('folders', [])
    if folder is not None and folder not in {item['folder'] for item in offered}:
        raise ConfigError('That folder is not one of the current suggestions; the source was scanned again since')
    choice = {'folder': folder, 'single_copies': single_copies, 'utc': now()}
    return _change_source_settings(config, key, lambda value: value.update(texture_folder=choice),
                                   "Wait for this source's operation to finish before choosing textures")


def forget_texture_folder(config, key):
    """Undo the choice: the rescan drops its recipes; recorded results stay."""
    def change(value):
        if value.pop('texture_folder', None) is None:
            raise ConfigError('No texture folder is chosen for this source')
    return _change_source_settings(config, key, change, "Wait for this source's operation to finish before changing textures")


def forget_export(config, key, decision_id):
    """Undo an answer: the folders become separate again and the suggestion returns on the rescan."""
    def change(value):
        before = value.get('export_decisions', [])
        value['export_decisions'] = [d for d in before if d.get('id') != decision_id]
        if len(value['export_decisions']) == len(before):
            raise ConfigError('That answer is no longer saved for this source')
    return _change_source_settings(config, key, change, "Wait for this source's operation to finish before changing answers")


@lru_cache(maxsize=8)
def _owner_map(path, stamp, size):
    return read_json(Path(path)).get("assets", {})


def owners(config):
    from .publication import request_memo
    return request_memo(("owners", str(config.project_root)), lambda: _owners(config))


def _owners(config):
    path = config.project_root / "data/library/asset-sources.json"
    if not path.exists():
        return {}
    stat = path.stat()
    return _owner_map(str(path), stat.st_mtime_ns, stat.st_size)


def generated_path(config, relative):
    if relative in SHARED_DATA:
        return None
    if config.metadata_root:
        root = config.metadata_root
        # The source root and its metadata directory are revalidated for every
        # access, including when an external directory is replaced by a link.
        validate_directory(config, str(config.source_root), require_exists=False)
        if relative in {"catalog.sqlite", "embeddings/index.sqlite", "library/membership.json"}:
            from .publication import generation
            selected = config.catalog_generation or generation(config)
            if selected != "legacy":
                relative = "library/generations/" + selected + "/" + relative
        return _inside(root, relative)
    match = re.search(r"(?:^|/)(asset_[0-9a-f]{32})(?:/|\.|$)", relative)
    if match:
        key = owners(config).get(match[1])
        if key:
            source = get_source(config, key, include_detached=True)
            return _inside(validate_directory(config, source["path"], False) / "metadata-lal", relative)
    return None


def write_changed(path, value, ignore=()):
    """Rewrite only on content change; status mtimes drive UI revisions."""
    if path.exists():
        try:
            old = read_json(path)
        except (OSError, ValueError):
            old = None
        if isinstance(old, dict) and {k: v for k, v in old.items() if k not in ignore} == {
                k: v for k, v in value.items() if k not in ignore}:
            return False
    atomic_json(path, value)
    return True


def save_registry(config, value):
    value["revision"] = uuid.uuid4().hex
    atomic_json(config.sources_registry, value)


def add(config, directory):
    from .gpu_queue import lease
    with lease(config, "source-settings", resource="sources"):
        root = validate_directory(config, directory)
        value = deepcopy(registry(config))
        for source in value["sources"]:
            other = Path(source["path"])
            if root.is_relative_to(other) or other.is_relative_to(root):
                raise ConfigError("That directory overlaps an existing asset source")
        identity_path = root / "metadata-lal/source.json"
        if identity_path.parent.exists() and not identity_path.exists():
            raise ConfigError('metadata-lal already exists without a LAL source identity; it was left unchanged')
        if identity_path.exists():
            identity = read_json(identity_path)
            key, identifier = identity.get("key"), identity.get("id")
            if (not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier or "")
                    or identity.get("schema_version") != 1):
                raise ConfigError("Existing metadata-lal source identity is invalid; preserved for review")
            _relative(key)
            if "/" in key or "\\" in key or any(s["key"] == key or s['id'] == identifier for s in value["sources"]):
                raise ConfigError("Existing source identity conflicts with a registered source")
        else:
            identifier = uuid.uuid4().hex
            key = root.name
            if key == "metadata-lal":
                raise ConfigError("Select an original asset source, not metadata-lal")
            if any(s["key"] == key for s in value["sources"] + value.get("detached", [])):
                key += "-" + identifier[:8]
            atomic_json(identity_path, {"schema_version": 1, "id": identifier, "key": key})
        source = {"id": identifier, "key": key, "name": root.name, "path": str(root), "enabled": True}
        value["sources"].append(source)
        value["detached"] = [s for s in value.get("detached", []) if s["id"] != identifier]
        save_registry(config, value)
    return source


def set_enabled(config, key, enabled):
    from .gpu_queue import lease
    if type(enabled) is not bool:
        raise ConfigError("Enabled must be a checkbox value")
    with lease(config, "source-settings", resource="sources"):
        value = deepcopy(registry(config))
        source = next((s for s in value["sources"] if s["key"] == key), None)
        if source is None:
            raise ConfigError("Unknown asset source")
        source["enabled"] = enabled
        save_registry(config, value)
    return source


def remove(config, key):
    from .gpu_queue import lease
    from .source_operations import active_operation
    source = get_source(config, key)
    if active_operation(bound(config, source)):
        raise ConfigError("Cancel this source's operation and wait for it to finish before removing it")
    with lease(config, "source-settings", resource="sources"):
        value = deepcopy(registry(config))
        value["sources"] = [s for s in value["sources"] if s["key"] != key]
        value.setdefault("detached", []).append(source)
        save_registry(config, value)


def read_records(config):
    path = config.output_path("data", "catalog.sqlite")
    if not path.exists():
        return []
    from .catalog import read_database
    with closing(read_database(config)) as db:
        return [json.loads(r[0]) for r in db.execute("SELECT record FROM assets ORDER BY asset_id")]


def import_outcome(record, embedding_failed=None):
    """Classify saved import attempts without retrying retained faults.

    Descriptions are optional extra data (decision 0008): a pending or failed
    caption is neither import work nor an import failure. A failed prerequisite
    blocks its dependent stages. Scanning changed source files resets durable
    stage states to pending. ``embedding_failed`` reports image-vector faults.
    """
    stages = record["processing"]
    from .asset_structure import applicable_stages
    applicable = applicable_stages(record)
    faults = {stage for stage, value in stages.items()
              if stage != "caption" and value in {"failed", "unsupported", "partial"}}
    # Image vectors are complete; only the optional description vector is missing or failed.
    optional_only = stages.get("embeddings") in {"partial", "failed"} and embedding_failed is False
    if optional_only:
        faults.discard("embeddings")
    attempted = any(stages.get(stage) in {"complete", "failed", "partial"}
                    for stage in ("inspection", "previews", "embeddings"))
    pending = set()
    if "inventory" not in faults:
        for stage, prerequisites in (("inspection", ()), ("previews", ("inspection",))):
            if stage not in applicable:
                continue
            if stages.get(stage) != "complete" and stage not in faults and not faults.intersection(prerequisites):
                pending.add(stage)
        if 'embeddings' in applicable and stages.get("embeddings") not in {"complete", "partial"} and not optional_only and "embeddings" not in faults:
            if record.get("previews") or record.get("description") or not faults:
                pending.add("embeddings")
    return {"state": "pending" if pending else "failed" if faults else "complete",
            "attempted": attempted, "pending_stages": sorted(pending), "failed_stages": sorted(faults)}


def description_state(record):
    """complete, failed, missing (inputs ready to describe) or unavailable (no usable renders yet)."""
    stages = record["processing"]
    caption = stages.get("caption")
    from .asset_structure import description_supported
    if caption == "complete":
        return "complete"
    if caption in {"failed", "partial"} or caption == 'unsupported' and description_supported(record):
        return "failed"
    if not description_supported(record):
        return 'unavailable'
    if stages.get("inventory") in {"failed", "unsupported"} or stages.get("inspection") != "complete":
        return "unavailable"
    if stages.get("previews") == "complete":
        return "missing"
    # A partial preview run can still supply all caption inputs.
    labels = [p.get("view_label") for p in record.get("previews", []) if p.get("origin") == "rendered"]
    if stages.get("previews") == "partial" and record.get("technical") and {"front", "side", "three_quarter"}.issubset(labels)             and len(labels) == len(set(labels)):
        return "missing"
    return "unavailable"


def embedding_failures(config):
    """Assets with failed image-vector attempts; description vectors are optional."""
    path = config.output_path("data", "embeddings/index.sqlite")
    if not path.exists():
        return None
    with closing(read_only(path)) as db:
        return {row[0] for row in db.execute("SELECT DISTINCT asset_id FROM jobs WHERE status='failed' AND channel='image'")}


def importing_failures(config):
    """Original paths for failed assets in registered sources, even if disabled."""
    paths, assets, unavailable = set(), 0, []
    for source in registry(config)["sources"]:
        scoped = bound(config, source)
        try:
            work = replace(scoped, catalog_generation="work")
            current = work if work.output_path("data", "catalog.sqlite").exists() else scoped
            records = read_records(current)
            vector_faults = embedding_failures(current)
            for record in records:
                failed_vector = None if vector_faults is None else record["asset_id"] in vector_faults
                if not import_outcome(record, failed_vector)["failed_stages"]:
                    continue
                assets += 1
                for file in record["files"]:
                    relative = _relative(file["path"])
                    if relative.parts[0] != source["key"]:
                        raise ConfigError("Asset path does not belong to its source")
                    paths.add(str(Path(source["path"]).joinpath(*relative.parts[1:])))
        except (OSError, ValueError, sqlite3.Error) as exc:
            unavailable.append({"source": source["name"], "reason": str(exc)})
    return {"status": "ready", "paths": sorted(paths, key=lambda path: (path.casefold(), path)),
            "assets": assets, "unavailable": unavailable}


def source_status(config, source):
    scoped = bound(config, source)
    path = scoped.output_path("data", "library/source-status.json")
    status = read_json(path) if path.exists() else {
        "needs_processing": True, "pending": 0, "reason": "Scan this source to discover its assets", "scanned": False}
    work = replace(scoped, catalog_generation='work')
    current = work if work.output_path('data', 'catalog.sqlite').exists() else scoped
    formats = tuple(processing_formats(config))
    paths = [current.output_path('data', 'catalog.sqlite'), scoped.output_path('data', 'catalog.sqlite'),
             current.output_path('data', 'embeddings/index.sqlite')]
    signature = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else (str(p), None, None) for p in paths)
    if paths[0].exists():
        try:
            status = dict(status, **_format_status(scoped, formats, signature))
        except (sqlite3.Error, OSError, ValueError) as exc:
            # One unreadable database marks only this source; its files and results stay where they are.
            status = dict(status, scan_fault=f"This source's saved processing data could not be read ({exc}). "
                                             "Its files and results are kept.")
    from .settings import descriptions_enabled
    status = dict(status, processing_paused=not formats, processing_formats=list(formats),
                  descriptions_enabled=descriptions_enabled(config))
    if not formats:
        status.update(needs_processing=False, pending=0, pending_ids=[], reason='Processing paused: no formats selected')
    from .source_operations import operation_status
    fault_path = config.project_root / 'data/library/source-faults' / (source['id'] + '.json')
    if fault_path.exists():
        status = dict(status, **read_json(fault_path), needs_processing=True)
    answered = {d['id'] for d in export_decisions(scoped)}  # Hidden at once; the rescan the answer starts confirms it.
    status['export_suggestions'] = [s for s in status.get('export_suggestions', []) if s['id'] not in answered]
    return {**source, **status, 'import_formats': import_formats(scoped), 'import_types': list(import_types(scoped)),
            'exclusions': excluded_folders(scoped), 'export_decisions': export_decisions(scoped),
            'texture_folder': texture_folder(scoped),
            "operation": operation_status(scoped)}


def unreadable_status(config, source, exc):
    """A source whose status could not be read at all: shown with its fault, never hiding the others."""
    from .source_operations import operation_status
    try:
        operation = operation_status(bound(config, source))
    except Exception:  # The fault below already explains this source.
        operation = {'status': 'idle', 'progress': 0}
    return {**source, 'scanned': True, 'needs_processing': False, 'pending': 0, 'failed': 0,
            'scan_fault': f"This source's status could not be read ({type(exc).__name__}: {exc}). Its files and results are kept.",
            'import_formats': [], 'import_types': [], 'exclusions': [], 'export_decisions': [], 'export_suggestions': [],
            'texture_folder': None, 'operation': operation}


def source_statuses(config):
    """Every registered source's status; one that cannot be read shows its fault instead of failing the list."""
    statuses = []
    for source in registry(config)['sources']:
        try:
            statuses.append(source_status(config, source))
        except Exception as exc:
            statuses.append(unreadable_status(config, source, exc))
    return statuses


def processing_summary(current, published, formats, vector_faults=None):
    from .catalog import encoded
    counts = dict.fromkeys(PROCESSING_FORMATS, 0)
    pending, failed, skipped = [], [], 0
    descriptions = dict.fromkeys(('complete', 'missing', 'failed', 'unavailable'), 0)
    for record in current:
        for group in {format_group(f['format']) for f in record['files']}:
            counts[group] = counts.get(group, 0) + 1
        identifier = record['asset_id']
        outcome = import_outcome(record, None if vector_faults is None else identifier in vector_faults)
        if outcome['failed_stages']:
            failed.append(identifier)
        if not processing_eligible(record, formats):
            skipped += 1
            continue
        descriptions[description_state(record)] += 1
        old = published.get(identifier)
        if outcome['state'] == 'pending' or old is None or encoded(old) != encoded(record):
            pending.append(identifier)
    reason = ('Processing paused: no formats selected' if not formats else
              'Assets need processing or publication' if pending else
              'Import finished with recorded failures' if failed else
              'No assets match the selected processing formats' if current and skipped == len(current) else
              'Selected formats are up to date and published')
    counts = {key: counts[key] for key in (*PROCESSING_FORMATS, *sorted(set(counts) - set(PROCESSING_FORMATS)))}
    return {'format_counts': counts, 'pending_ids': sorted(pending), 'pending': len(pending), 'reason': reason,
            'needs_processing': bool(pending), 'failed': len(failed), 'skipped_formats': skipped,
            'eligible_assets': len(current) - skipped, 'descriptions': descriptions}


@lru_cache(maxsize=64)
def _format_status(scoped, formats, signature):
    # Polling settings uses saved inventory only. Cache by database identity and
    # settings, without rescanning originals or rewriting source metadata.
    work = replace(scoped, catalog_generation='work')
    current = work if work.output_path('data', 'catalog.sqlite').exists() else scoped
    return processing_summary(read_records(current), {r['asset_id']: r for r in read_records(scoped)},
                              formats, embedding_failures(current))


def visible(config, records):
    if not config.sources_registry or config.source_key:
        return records
    allowed = {}
    for source in registry(config)["sources"]:
        if not source["enabled"]:
            continue
        fault_path = config.project_root / 'data/library/source-faults' / (source['id'] + '.json')
        if fault_path.exists():
            allowed[source['key']] = set()
            continue
        status_path = bound(config, source).output_path("data", "library/source-status.json")
        from .library_cache import cached_json
        status = cached_json(status_path) if status_path.exists() else {}
        # A missing/changed file is excluded as soon as a scan discovers it,
        # while its prior published results remain available for later repair.
        allowed[source["key"]] = None if not status.get("scanned") else set(status.get("searchable_ids", []))
    return [r for r in records if r["pack_id"] in allowed and
            (allowed[r["pack_id"]] is None or r["asset_id"] in allowed[r["pack_id"]])]


def revision(config):
    if not config.sources_registry:
        return "legacy"
    from .catalog import digest
    value = registry(config)
    states = []
    for source in value["sources"]:
        path = bound(config, source).output_path("data", "library/source-status.json")
        fault_path = config.project_root / 'data/library/source-faults' / (source['id'] + '.json')
        states.append((source["key"], path.stat().st_mtime_ns if path.exists() else None,
                       fault_path.stat().st_mtime_ns if fault_path.exists() else None))
    return digest([value["revision"], states, processing_formats(config)])[:16]


def write_catalog(config, rows, records):
    """Write a fresh database; never mutate a published generation."""
    from .catalog import write_database, digest, encoded
    metadata = {"schema_version": 1, "source_id": "playful-lowpoly-v1",
                "source_root": str(config.source_root), "source_fingerprint": digest(rows),
                "logical_fingerprint": digest(records), "scan_utc": now()}
    if config.source_key:
        metadata['source_key'] = config.source_key
    blank = [dict(r, technical=None, description=None, embeddings=[], owner_overlay={}) for r in records]
    write_database(config, rows, blank, metadata)
    with closing(sqlite3.connect(config.output_path("data", "catalog.sqlite"))) as db, db:
        db.executemany("UPDATE assets SET record=? WHERE asset_id=?", [(encoded(r), r["asset_id"]) for r in records])


def write_membership(config, records):
    from .catalog import digest
    ids = sorted(r["asset_id"] for r in records)
    atomic_json(config.output_path("data", "library/membership.json"), {
        "schema_version": 1, "asset_ids": ids, "fingerprint": digest(ids), "scope": "library",
        "packs": sorted({r["pack_id"] for r in records}), "approval": "Configured asset sources; manual processing"})


def scan_source(config, source):
    from .catalog import build_inventory, digest, encoded
    from .incremental import working
    scoped = bound(config, source)
    work = working(scoped)
    previous = read_records(work) or read_records(scoped)
    old = {r["asset_id"]: r for r in previous}
    suggestions = []
    rows, fresh, _, _ = build_inventory(scoped, suggestions)
    from .catalog import snapshot, walk_source
    if snapshot(rows) != snapshot(walk_source(scoped)):
        raise ConfigError('Files changed during the scan; prior catalog retained. Scan again when file changes finish.')
    # Isolate file failures to their assets; other assets in the source continue.
    rejected = [r for r in rows if r.get("status") == "rejected"]
    merged, changed = [], set()
    published = None
    for record in fresh:
        prior = old.get(record["asset_id"])
        if prior is None:
            # An asset that returns unchanged (for example after its type was switched
            # off and on again) resumes from its published record instead of starting over.
            if published is None:
                published = {r["asset_id"]: r for r in read_records(scoped)}
            candidate = published.get(record["asset_id"])
            if candidate and candidate["files"] == record["files"]:
                prior = candidate
        if prior:
            same = prior["files"] == record["files"] and [d for d in prior["dependencies"] if not d.get("inspection_version")] == record["dependencies"]
            kept = deepcopy(prior)
            for key in ("files", "availability", "variants", "dependency_inspection"):
                kept[key] = record[key]
            from .dependency_overrides import synchronize_recipe
            synchronize_recipe(kept, record)
            # Preserve relevant supplied and collection evidence without carrying
            # sibling-subpack licenses into every model in a nested source.
            from .catalog import relevant_license_evidence
            kept['license_evidence'] = relevant_license_evidence(dict(record, license_evidence=list({
                (e.get('path'), e.get('sha256')): e
                for e in prior.get('license_evidence', []) + record.get('license_evidence', [])}.values())))
            if not same or import_formats(scoped) is not None:
                kept['grouping'] = record['grouping']
            if not same:
                changed.add(record["asset_id"])
                kept["dependencies"] = record["dependencies"]
                kept["processing"] = dict(record["processing"])
            record = kept
        else:
            changed.add(record["asset_id"])
        failures = [r for r in rejected if r['path'] in {f['path'] for f in record['files']}]
        if failures:
            record['processing']['inventory'] = 'failed'
            record.setdefault('stage_faults',{})['inventory'] = {
                'status':'faulty','reason':'Source files could not be read','files':failures}
        merged.append(record)
    # Owner texture folder recipes (decision 0021): a recipe change is a changed input for those models.
    from .texture_folders import apply as apply_texture_folder
    before = {r['asset_id']: r.get('texture_repair') for r in merged}
    texture_suggestion = apply_texture_folder(merged, rows, texture_folder(scoped))
    changed.update(r['asset_id'] for r in merged if r.get('texture_repair') != before[r['asset_id']])
    inventory_hash = digest(rows)
    status_path = scoped.output_path("data", "library/source-status.json")
    prior_status = read_json(status_path) if status_path.exists() else {}
    if (inventory_hash != prior_status.get("inventory_hash") or old != {r['asset_id']: r for r in merged}
            or not work.output_path("data", "catalog.sqlite").exists()):
        candidate = replace(scoped, catalog_generation="scan_" + uuid.uuid4().hex)
        write_catalog(candidate, rows, merged)
        target = work.output_path("data", "catalog.sqlite")
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(candidate.output_path("data", "catalog.sqlite"), target)
        write_membership(work, merged)
    published = {r["asset_id"]: r for r in read_records(scoped)}
    incomplete, failed, unpublished, imports = [], [], [], {}
    vector_faults = embedding_failures(work)
    searchable = []
    for record in merged:
        identifier = record["asset_id"]
        outcome = import_outcome(record, None if vector_faults is None else identifier in vector_faults)
        # Keep the current input identity with the saved outcome. Old failures
        # cannot suppress a new attempt after a source/dependency change.
        imports[identifier] = {**outcome, "input_fingerprint": digest({"files": record["files"],
            "dependencies": [d for d in record["dependencies"] if not d.get("inspection_version")]})}
        if outcome["state"] == "pending":
            incomplete.append(identifier)
        if outcome["failed_stages"]:
            failed.append(identifier)
        old_pub = published.get(identifier)
        if old_pub is None or encoded(old_pub) != encoded(record):
            unpublished.append(identifier)
        if old_pub and identifier not in changed and old_pub["files"] == record["files"]:
            searchable.append(identifier)
    pending_ids = sorted(set(incomplete + unpublished))
    write_changed(scoped.output_path("data", "library/import-status.json"),
                  {"schema_version": 1, "inventory_hash": inventory_hash, "assets": imports})
    status = {"scanned": True, "scanned_utc": now(), "inventory_hash": inventory_hash,
              "assets": len(merged), "pending": len(pending_ids), "failed": len(failed),
              "pending_ids": pending_ids, "searchable_ids": sorted(searchable),
              "needs_processing": bool(pending_ids), "removed": len(set(old) - {r["asset_id"] for r in merged}),
              # Decision 0019: owner-excluded folders and unanswered duplicate export folder suggestions.
              "excluded_folders": [{"path": r["path"].split("/", 1)[1], "files": r["excluded_files"]}
                                   for r in rows if r.get("status") == "excluded_folder"],
              "export_suggestions": suggestions, "texture_suggestion": texture_suggestion,
              "reason": ("Assets need processing or publication" if pending_ids else
                         "Import finished with recorded failures" if failed else "Up to date and published")}
    formats = processing_formats(config)
    status.update(processing_summary(merged, published, formats, vector_faults), processing_paused=not formats,
                  processing_formats=formats)
    # An unchanged scan keeps its earlier receipt time and leaves views untouched.
    write_changed(status_path, status, ignore=("scanned_utc",))
    fault_path = config.project_root / 'data/library/source-faults' / (source['id'] + '.json')
    if fault_path.exists():
        fault_path.unlink()  # A successful explicit/startup scan resolves this application availability diagnostic.
    # File identity ownership includes removed assets so their evidence remains resolvable.
    own_path = config.project_root / "data/library/asset-sources.json"
    mapping = dict(owners(config))
    mapping.update({r["asset_id"]: source["key"] for r in previous + merged})
    write_changed(own_path, {"schema_version": 1, "assets": mapping})
    return status


def aggregate(config):
    """Publish a derived combined catalog; source snapshots remain authoritative."""
    from .catalog import encoded, digest
    from .retrieval import index_database
    from .publication import generation
    records, inventories, jobs, vectors, meta = [], [], [], [], {}
    signature = []
    for source in registry(config)["sources"]:
        if (config.project_root / 'data/library/source-faults' / (source['id'] + '.json')).exists():
            continue
        scoped = bound(config, source)
        if not scoped.output_path("data", "library/active.json").exists():
            continue
        signature.append((source["id"], generation(scoped)))
        records.extend(read_records(scoped))
        with closing(sqlite3.connect(scoped.output_path("data", "catalog.sqlite"))) as db:
            inventories.extend(json.loads(r[0]) for r in db.execute("SELECT record FROM inventory"))
        path = scoped.output_path("data", "embeddings/index.sqlite")
        if path.exists():
            with closing(read_only(path)) as db:
                source_meta = {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM meta")}
                if meta and source_meta.get("contract_fingerprint") != meta.get("contract_fingerprint"):
                    raise ConfigError("Source vector models differ; source retained without combined publication")
                meta = source_meta or meta
                jobs.extend(db.execute("SELECT * FROM jobs").fetchall())
                vectors.extend(db.execute("SELECT * FROM vectors").fetchall())
    fingerprint = digest(sorted(signature))
    legacy_fingerprint = digest(signature)
    projection_path = config.project_root / 'data/library/combined-publications' / (fingerprint + '.json')
    active_path = config.project_root / "data/library/active.json"
    if active_path.exists() and read_json(active_path).get("sources_fingerprint") in {fingerprint, legacy_fingerprint}:
        publication = dict(read_json(active_path), sources_fingerprint=fingerprint)
        if not projection_path.exists():
            atomic_json(projection_path, publication)
        if read_json(active_path).get('sources_fingerprint') != fingerprint:
            atomic_json(active_path,publication)
        return {"no_change": True, "generation": generation(config)}
    if projection_path.exists():
        previous = read_json(projection_path)
        previous_config = replace(config, catalog_generation=previous['generation'])
        for relative in ('catalog.sqlite','embeddings/index.sqlite','library/membership.json'):
            if not previous_config.output_path('data',relative).is_file():
                raise ConfigError('A saved combined publication is incomplete; retained for review')
        atomic_json(active_path,previous)
        _retain(config)
        return {'generation':previous['generation'],'reused':True,'membership':len(records)}
    contract_path = config.project_root / 'data/library/embedding-contract.json'
    if not meta:
        old_index = config.output_path('data','embeddings/index.sqlite')
        if old_index.exists():
            with closing(read_only(old_index)) as db:
                meta = {k: json.loads(v) for k,v in db.execute('SELECT key,value FROM meta')}
        elif contract_path.exists():
            meta = {k: json.loads(v) for k,v in read_json(contract_path).items()}
    if meta.get('contract'):
        atomic_json(contract_path, {k: encoded(v) for k,v in meta.items() if k != 'pilot_ids'})
    target = replace(config, catalog_generation="v_" + uuid.uuid4().hex)
    write_catalog(target, inventories, records)
    write_membership(target, records)
    with closing(index_database(target)) as db, db:
        meta["pilot_ids"] = sorted(r["asset_id"] for r in records)
        db.executemany("INSERT INTO meta VALUES (?,?)", [(k, encoded(v)) for k, v in meta.items()])
        db.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?)", jobs)
        db.executemany("INSERT INTO vectors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", vectors)
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ConfigError("Combined index integrity check failed")
    publication = {"generation": target.catalog_generation, "sources_fingerprint": fingerprint}
    atomic_json(projection_path,publication)
    atomic_json(active_path,publication)
    _retain(config)
    return {"generation": target.catalog_generation, "membership": len(records)}


def _retain(config):
    """Retire superseded generations (decision 0006); never fails the publication."""
    from .retention import retire_generations, write_receipt
    try:
        retire_generations(config)
    except Exception as exc:
        write_receipt(config, 'generation-retention', [{'root': str(config.project_root), 'targets': [], 'bytes': 0,
                      'faults': [{'status': 'faulty', 'reason': str(exc) or type(exc).__name__}]}])
