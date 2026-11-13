"""Key definitions that changed, kept only to recognize results recorded under them (decision 0028).

Nothing here writes the ledger or the result store: an old key that matches stays the recorded key, so finished
work is never re-queued and never re-keyed. ``scripts/check-rekey.py`` proves it on copies of a real library.
"""


def legacy_blender(path, mtime_ns):
    """The Blender part of 3D inspection keys before they held the major version: install path and mtime."""
    return {"blender": str(path), "blender_mtime": mtime_ns}


def recognized(config, settings, files, recorded, equivalents):
    """Whether ``recorded`` is ``settings`` keyed the old way with a Blender of the same major version.

    Candidates are every Blender this checkout has seen with that major version (so a moved or reinstalled
    Blender keeps old keys), plus today's configured one exactly as the old definition read it.
    """
    from .incremental import recorded_fingerprint
    from .inspection import remembered_blenders
    major = settings["blender_major"]
    base = {k: v for k, v in settings.items() if k != "blender_major"}
    blender = config.blender
    candidates = [(blender, blender.stat().st_mtime_ns if blender and blender.exists() else None)]
    candidates += [(e["path"], e["mtime_ns"]) for e in remembered_blenders(config)
                   if int(e["version"].split(".")[0]) == major]
    for path, mtime in dict.fromkeys((str(p), m) for p, m in candidates):
        if recorded_fingerprint({**base, **legacy_blender(path, mtime)}, files, recorded, equivalents) == recorded:
            return True
    return False


def legacy_inspection_input(config, record, resolution=640, formats=None, recorded=None):
    """incremental.inspection_input for 3D assets as it was before the major-version key (its key part, verbatim).

    Only the proof uses it, as the old code's answer; recognition above needs just the Blender part.
    """
    import posixpath
    from .asset_structure import asset_type
    from .captions import file_hash
    from .config import ConfigError
    from .incremental import EQUIVALENT_WORKERS, recorded_fingerprint
    from .inspection import choose_source
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
    from .result_store import location_free, relative_to
    base, prefix = posixpath.dirname(source["path"]), source["path"].split("/", 1)[0] if config.source_key else None
    content = [{"format": source["format"], "sha256": source.get("sha256")}]
    for item in [source] + deps:
        path = item.get("path")
        relative = relative_to(base, path) if path else None
        try:
            from .dependency_resolution import dependency_file
            actual = file_hash(dependency_file(config, item))
        except (OSError, ValueError, TypeError):
            actual = {"missing": relative}
        content.append({"path": relative, "actual": actual, "expected": item.get("sha256")})
    from .texture_repair import validate_recipe
    repair = validate_recipe(config, record)
    if repair:
        from .dependency_resolution import portable
        content.append({'texture_repair': location_free(portable(repair, base), base, prefix)})
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
