"""The one-time move of per-source generated folders into the central library store (decision 0023).

The legacy folder name lives here only; other code imports it to skip or refuse those folders.
"""

LEGACY_METADATA_DIR = "metadata-lal"


# Fingerprints as defined before decision 0023, which hashed source-prefixed paths. The migration recomputes
# them to prove a recorded result is current before filing it under its new input key; nothing else uses them.

def legacy_inspection_input(config, record, resolution=640, content_only=False, formats=None, recorded=None):
    from .asset_structure import asset_type
    from .catalog import digest
    from .captions import file_hash
    from .config import ConfigError
    from .incremental import EQUIVALENT_WORKERS, recorded_fingerprint
    from .inspection import choose_source
    if asset_type(record) == 'image':
        return legacy_image_input(config, record, content_only=content_only, recorded=recorded)
    if asset_type(record) != 'model_3d':
        raise ConfigError('No inspection adapter for this asset type')
    asset = {"asset_id": record["asset_id"], "pack": record["pack_id"], "name": record["display_name"], "files": record["files"]}
    from .settings import inspected_path, processing_formats
    path = inspected_path(record) if record['processing'].get('inspection') != 'pending' else None
    source = next((f for f in asset['files'] if f['path'] == path), None)
    if source:
        reason = record.get('primary_inspection_reason', 'Preserve the previously inspected source; alternates remain uninspected')
    else:
        source, reason = choose_source(asset, processing_formats(config) if formats is None else formats)
    deps = [d for d in record["dependencies"] if d.get("from") == source["path"]]
    deps = [d for d in deps if d.get("required_for_render") is not False]
    content = [{"path": source["path"], "sha256": source.get("sha256")}]
    for item in [source] + deps:
        path = item.get("path")
        try:
            from .dependency_resolution import dependency_file
            actual = file_hash(dependency_file(config, item))
        except (OSError, ValueError, TypeError) as exc:
            actual = {"missing": path, "reason": str(exc)}
        content.append({"path": path, "actual": actual, "expected": item.get("sha256")})
    from .texture_repair import validate_recipe
    repair = validate_recipe(config, record)
    if repair:
        content.append({'texture_repair': repair})
    if content_only:
        return asset, source, reason, digest(content)
    code = config.project_root / "src/local_asset_library"
    files = {"worker": code / "blender_worker.py", "render_math": code / "render_math.py"}
    worker = file_hash(files["worker"])
    settings = {"source": content, "resolution": resolution,
        "worker": EQUIVALENT_WORKERS.get(worker, worker), "render_math": file_hash(files["render_math"]),
        "blender": str(config.blender), "blender_mtime": config.blender.stat().st_mtime_ns if config.blender and config.blender.exists() else None}
    if repair:
        files['repair_worker'] = code / ('blender_shared_dependency_worker.py' if repair.get('kind') == 'shared_dependency_paths'
                                        else 'blender_repair_worker.py')
        settings['repair_worker'] = file_hash(files['repair_worker'])
    return asset, source, reason, recorded_fingerprint(settings, files, recorded, EQUIVALENT_WORKERS)


def legacy_image_input(config, record, content_only=False, recorded=None):
    from .catalog import digest
    from .config import ConfigError
    from .image_inspection import VERSION, code_files, renderer_version
    from .image_media import ACTIVE, POLICIES, PREFERENCE, image_format
    from .incremental import recorded_fingerprint
    from .publication import verified_hash
    from .retrieval import source_check
    current = source_check(config, record)
    available = [f for f in record['files'] if f['availability'] == 'available' and image_format(f['path'])]
    if not available:
        raise ConfigError('No decodable image file is recorded for this asset')
    source = min(available, key=lambda f: (PREFERENCE.index(image_format(f['path'])), f['path']))
    reason = 'Preferred raster export' if source['format'] != 'svg' else 'Self-contained SVG export'
    value = {'adapter': VERSION, 'source': current, 'path': source['path']}
    if content_only:
        return {'asset_id': record['asset_id'], 'files': record['files']}, source, reason, digest(value)
    files = code_files(config)
    value.update(policy=POLICIES[ACTIVE], **{name: verified_hash(path) for name, path in files.items()})
    if source['format'] == 'svg':
        value['renderer'] = renderer_version()
    return {'asset_id': record['asset_id'], 'files': record['files']}, source, reason, recorded_fingerprint(value, files, recorded)


def legacy_caption_views(config, record):
    from .captions import input_state
    return [{"path": p.get("path"), "sha256": p.get("sha256"), "view_label": p.get("view_label"),
             "actual": s.get("current_sha256", s.get("error"))} for s in input_state(config, record) for p in [s["preview"]]]


def legacy_caption_input(config, record, recorded=None):
    from .incremental import caption_input
    return caption_input(config, record, recorded=recorded, views=legacy_caption_views(config, record))


def legacy_stage_content(config, record, stage):
    from .captions import input_state
    from .catalog import digest
    try:
        if stage == 'inspection':
            return legacy_inspection_input(config, record, content_only=True,
                                           formats=('gltf', 'fbx', 'obj', 'blend', 'stl', 'dae'))[3]
        return digest([{'path': s['preview'].get('path'), 'view': s['preview'].get('view_label'),
                        'expected': s['preview'].get('sha256'), 'actual': s.get('current_sha256', s.get('error'))}
                       for s in input_state(config, record)])
    except (OSError, ValueError, KeyError):
        return digest({'files': record.get('files'), 'dependencies': record.get('dependencies')})


def rekey(work, db):
    """File every finished result of one folder under its new input key; never re-queue (decision 0023).

    For each ledger row the old fingerprint is recomputed from the record. Only a row it still matches is current:
    its fingerprint becomes the new key, its fault identity follows, and a finished result joins the store's
    index. A row that no longer matches is stale and keeps its old fingerprint, so it stays pending as before.
    """
    import json
    from collections import Counter
    from .catalog import encoded
    from .incremental import caption_input, inspection_input, stage_content
    from .membership import records
    from .result_store import KEY_STAGES, remember
    counts = Counter()
    rows = {(r[0], r[1]): r[2:] for r in db.execute('SELECT asset_id, stage, fingerprint, status, evidence FROM jobs')}
    for record in records(work):
        for stage in KEY_STAGES:
            row = rows.get((record['asset_id'], stage))
            if not row or row[1] == 'running':
                continue
            old, status, evidence = row[0], row[1], json.loads(row[2] or '{}')
            try:
                legacy = (legacy_inspection_input(work, record, recorded=old)[3] if stage == 'inspection'
                          else legacy_caption_input(work, record, recorded=old))
                key = inspection_input(work, record, recorded=None)[3] if stage == 'inspection' else caption_input(work, record)
            except (OSError, ValueError, KeyError):
                counts[stage + ':unreadable'] += 1
                continue
            if legacy != old:
                counts[stage + ':stale'] += 1
                continue
            if evidence.get('fault_content') == legacy_stage_content(work, record, stage):
                evidence['fault_content'] = stage_content(work, record, stage)
            with db:
                db.execute('UPDATE jobs SET fingerprint=?, evidence=? WHERE asset_id=? AND stage=?',
                           (key, encoded(evidence), record['asset_id'], stage))
            counts[stage + ':' + status] += 1
            if status == 'complete':
                path = ((record.get('inspection_run') or {}).get('result_path', '').removesuffix('/result.json') if stage == 'inspection'
                        else (record.get('caption_provenance') or {}).get('result_path'))
                if path and (stage == 'caption' or record.get('asset_type') != 'image'):
                    remember(work, stage, key, path, record['asset_id'])
    return dict(counts)


def pending(work, stage, legacy=False):
    """Pending asset IDs of a dry run, with the old or the new fingerprint definitions."""
    from . import incremental
    if not legacy:
        return set(incremental.process(work, stage, 1000, dry_run=True)['pending_ids'])
    saved = incremental.inspection_input, incremental.caption_input, incremental.stage_content
    current_caption = incremental.caption_input
    incremental.inspection_input = legacy_inspection_input
    incremental.caption_input = lambda config, record, prompt_version=None, generation=None, recorded=None, views=None: current_caption(
        config, record, prompt_version, generation, recorded, legacy_caption_views(config, record) if views is None else views)
    incremental.stage_content = legacy_stage_content
    try:
        return set(incremental.process(work, stage, 1000, dry_run=True)['pending_ids'])
    finally:
        incremental.inspection_input, incremental.caption_input, incremental.stage_content = saved


def _legacy_registry(config):
    """The pre-store source registry (``data/library/sources.json``), read only."""
    path = config.project_root / 'data/library/sources.json'
    if not path.is_file():
        return []
    import json
    value = json.loads(path.read_text(encoding='utf-8'))
    return [dict(s, registered=True) for s in value.get('sources', [])] + [dict(s, registered=False) for s in value.get('detached', [])]


def discover(config, search=()):
    """Every old generated folder under registered and detached sources and ``search``, at any depth.

    Links are never followed. Each entry names the folder that holds it, with its saved ``id`` and ``key``,
    or a ``fault`` when its identity cannot be read. The same folder found twice is listed once.
    """
    import json
    import os
    import re
    from pathlib import Path
    roots = [Path(s['path']) for s in _legacy_registry(config)] + [Path(p) for p in search]
    found, seen = [], set()
    for root in roots:
        if not root.is_dir() or root.is_symlink() or root.is_junction():
            continue
        for directory, dirs, _ in os.walk(root, followlinks=False):
            for name in list(dirs):
                path = Path(directory) / name
                if path.is_symlink() or path.is_junction():
                    dirs.remove(name)
                elif name.casefold() == LEGACY_METADATA_DIR:
                    dirs.remove(name)  # Generated data never holds another source.
                    if str(path).casefold() in seen:
                        continue
                    seen.add(str(path).casefold())
                    entry = {'path': str(path.parent), 'metadata': str(path)}
                    try:
                        identity = json.loads((path / 'source.json').read_text(encoding='utf-8'))
                        if (identity.get('schema_version') != 1 or not re.fullmatch(r'[0-9a-f]{32}', identity.get('id') or '')
                                or not isinstance(identity.get('key'), str) or not identity['key']):
                            raise ValueError('source.json is not a schema 1 source identity')
                        entry.update(id=identity['id'], key=identity['key'], settings=identity)
                    except (OSError, ValueError) as exc:
                        entry['fault'] = f'Unreadable source identity: {exc}'
                    found.append(entry)
    return sorted(found, key=lambda e: e['path'].casefold())
