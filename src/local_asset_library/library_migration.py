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


def rekey(work, db, store=None):
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
    counts, store = Counter(), store or work
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
                    from .result_store import first_sight_key
                    keys = {key, first_sight_key(work, record)} if stage == 'inspection' else {key}
                    for value in keys:  # The finished key and the key a fresh duplicate has.
                        remember(store, stage, value, path, record['asset_id'])
    return dict(counts)


def pending(work, stage, legacy=False, ledger_path=None):
    """Pending asset IDs of a dry run, with the old or the new fingerprint definitions (on ``ledger_path`` if given)."""
    import sqlite3
    from . import incremental
    saved = incremental.inspection_input, incremental.caption_input, incremental.stage_content, incremental.ledger
    if ledger_path:
        incremental.ledger = lambda _config: sqlite3.connect(ledger_path)
    if not legacy:
        try:
            return set(incremental.process(work, stage, 1000, dry_run=True)['pending_ids'])
        finally:
            incremental.ledger = saved[3]
    current_caption = incremental.caption_input
    incremental.inspection_input = legacy_inspection_input
    incremental.caption_input = lambda config, record, prompt_version=None, generation=None, recorded=None, views=None: current_caption(
        config, record, prompt_version, generation, recorded, legacy_caption_views(config, record) if views is None else views)
    incremental.stage_content = legacy_stage_content
    try:
        return set(incremental.process(work, stage, 1000, dry_run=True)['pending_ids'])
    finally:
        incremental.inspection_input, incremental.caption_input, incremental.stage_content, incremental.ledger = saved


def legacy_bound(config, found):
    """``config`` reading one old generated folder in place (read only by convention: nothing here writes)."""
    from dataclasses import replace
    from pathlib import Path
    return replace(config, source_root=Path(found['path']), source_key=found['key'], metadata_root=Path(found['metadata']),
                   catalog_generation=None)


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


# ------------------------------------------------------------------ the one-time migration (ASSETRM-0002 phase 3)

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.svg', '.tga', '.bmp', '.gif'}
MODEL_SUFFIXES = {'.fbx', '.gltf', '.glb', '.obj', '.blend', '.stl', '.dae'}


def receipts(config):
    """Saved migration receipts, oldest first."""
    import json
    folder = config.project_root / 'data/library/migration'
    if not folder.is_dir():
        return []
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('20*.json'))]


def migrated(config):
    """Old generated folders a receipt names as verified imports (each folder is imported once)."""
    return {f['metadata'].casefold(): f for r in receipts(config) for f in r.get('folders', []) if f.get('status') == 'verified'}


def imported(config):
    """Old generated folders any receipt names (verified or not): a later run never imports them again."""
    return {f['metadata'].casefold() for r in receipts(config) for f in r.get('folders', [])
            if f.get('status') in {'verified', 'unverified', 'imported'}}


def needed(config):
    """Whether old generated folders still wait for the migration; cheap (no deep search), for the app's notice."""
    from pathlib import Path
    done = imported(config)
    for source in _legacy_registry(config):
        metadata = Path(source['path']) / LEGACY_METADATA_DIR
        if metadata.is_dir() and str(metadata).casefold() not in done:
            return {'needed': True, 'command': command(config)}
    return {'needed': False}


def command(config):
    import os
    wrapper = r'.\scripts\uv.ps1' if os.name == 'nt' else './scripts/uv.sh'
    return f'{wrapper} run --locked python scripts/migrate-library.py'


def legacy_path(config, relative):
    """Before the migration, a published asset's result read from its old generated folder (read only)."""
    import re
    from pathlib import Path
    from .sources import owners
    match = re.search(r'(?:^|/)(asset_[0-9a-f]{32})(?:/|\.|$)', relative)
    key = owners(config).get(match[1]) if match else None
    source = next((s for s in _legacy_registry(config) if s.get('key') == key), None) if key else None
    if not source:
        return None
    target = Path(source['path']) / LEGACY_METADATA_DIR / relative
    return target if target.is_file() else None


def app_processes():
    """Running Assetarium desktop apps or MCP servers (they must be closed during the migration)."""
    import os
    import subprocess
    from pathlib import Path
    names = ('asset-desktop.pyw', 'asset-mcp.py', 'asset-worker.py')
    if os.name == 'nt':
        done = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                               'Get-CimInstance Win32_Process | ForEach-Object { $_.CommandLine }'],
                              capture_output=True, text=True, timeout=120)
        lines = done.stdout.splitlines()
    else:
        lines = []
        for entry in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                lines.append(entry.read_bytes().replace(b'\0', b' ').decode(errors='replace'))
            except OSError:
                pass
    return [line.strip() for line in lines if any(name in line for name in names)]


def _counts(found):
    """What every-type enrollment (decision 0023) adds to an old source: images it left out, other formats."""
    import os
    from pathlib import Path, PurePosixPath
    from .settings import format_group
    settings = found.get('settings') or {}
    images_off = 'image' not in settings.get('import_types', ['model_3d'])
    allowed = settings.get('import_formats')
    images, other, by_folder = 0, 0, {}
    root = Path(found['path'])
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.casefold() != LEGACY_METADATA_DIR and not (Path(directory) / d).is_symlink()
                         and not (Path(directory) / d).is_junction())
        folder = Path(directory).relative_to(root).as_posix()
        for name in files:
            suffix = PurePosixPath(name).suffix.lower()
            images += images_off and suffix in IMAGE_SUFFIXES
            if allowed is not None and suffix in MODEL_SUFFIXES:
                kept = format_group(suffix[1:]) in allowed
                other += not kept
                entry = by_folder.setdefault(folder, [0, 0])
                entry[0 if kept else 1] += 1
    # A folder (with its subfolders) holding only formats the source did not import becomes an exclusion.
    proposals = []
    ancestors = {'/'.join(f.split('/')[:depth]) for f in by_folder if f != '.' for depth in range(1, f.count('/') + 2)}
    for folder in sorted(ancestors, key=lambda f: (f.count('/'), f)):  # The shallowest folder that qualifies.
        inside = [v for f, v in by_folder.items() if f == folder or f.startswith(folder + '/')]
        if (folder != '.' and sum(v[1] for v in inside) and not sum(v[0] for v in inside)
                and not any(folder.startswith(p + '/') for p in proposals)):
            proposals.append(folder)
    return {'images_previously_off': images, 'import_formats': allowed, 'other_format_models': other,
            'proposed_exclusions': proposals}


def _ledger_counts(found):
    import sqlite3
    from contextlib import closing
    from pathlib import Path
    path = Path(found['metadata']) / 'library/jobs.sqlite'
    if not path.is_file():
        return {}
    try:
        with closing(sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True)) as db:
            return {f'{stage}:{status}': count for stage, status, count in
                    db.execute('SELECT stage, status, count(*) FROM jobs GROUP BY stage, status')}
    except sqlite3.Error as exc:  # Reported in the plan; apply keeps the fault to this folder.
        return {'fault': f'Unreadable stage ledger: {exc}'}


def _asset_count(config, found):
    from .incremental import working
    from .sources import read_records
    try:
        return len(read_records(working(legacy_bound(config, found))) or read_records(legacy_bound(config, found)))
    except Exception:  # A plan reports what it can; apply reads again and keeps faults per folder.
        return None


def plan(config, library_folders=(), search=()):
    """The dry run: what applying would import, re-key, relink and newly enroll. Writes only the plan file."""
    from collections import Counter
    from pathlib import Path
    from .publication import atomic_json
    from .sources import now
    named = [Path(p).resolve() for p in library_folders]
    found = discover(config, [*named, *[Path(p) for p in search]])
    done = imported(config)
    ids = Counter(f.get('id') for f in found if not f.get('fault'))
    registry = {s['id']: s for s in _legacy_registry(config) if s.get('id')}
    folders, groups = [], {}
    for entry in found:
        item = {k: entry.get(k) for k in ('path', 'metadata', 'id', 'key', 'fault')}
        if str(entry['metadata']).casefold() in done:
            item['status'] = 'already imported'
        elif entry.get('fault'):
            item['status'] = 'fault'
        elif ids[entry['id']] > 1:
            item.update(status='conflict', fault='Two old generated folders share this identity; neither is imported')
        else:
            item['status'] = 'ready'
            old = registry.get(entry['id'])
            item.update(registered=bool(old and old['registered']), detached=bool(old and not old['registered']),
                        enabled=old.get('enabled', True) if old else True, name=old.get('name', entry['key']) if old else entry['key'])
            if old and Path(old['path']) != Path(entry['path']):
                item['relinked_from'] = old['path']  # A moved source (another drive): the registry is corrected.
            owner = next((n for n in named if Path(entry['path']).is_relative_to(n)), None)
            item['library_folder'] = str(owner or entry['path'])
            groups.setdefault(item['library_folder'], []).append(entry['key'])
            item.update(ledger=_ledger_counts(entry), enroll=_counts(entry), assets=_asset_count(config, entry))
        folders.append(item)
    found_ids = {f.get('id') for f in found}
    unmatched = [{'key': s['key'], 'path': s['path'], 'reason': 'Not found; pass the folder that now contains it with --search'}
                 for s in registry.values() if s['id'] not in found_ids]
    value = {'schema_version': 1, 'utc': now(), 'library_folders': [str(n) for n in named], 'search': [str(p) for p in search],
             'folders': folders, 'groups': groups, 'unmatched_registry': unmatched, 'app_processes': app_processes(),
             'command': command(config)}
    path = config.project_root / f"data/library/migration/plan-{_stamp(value['utc'])}.json"
    atomic_json(path, value)
    return value, path


def _stamp(utc):
    return utc.replace(':', '').replace('-', '').replace('.', '')[:22]


def _copy_tree(source, target, link_results):
    """Copy (never move) a tree; immutable result files are hard-linked when on the same volume. Refuses links."""
    import os
    import shutil
    from pathlib import Path
    copied = linked = 0
    for directory, dirs, files in os.walk(source, followlinks=False):
        for name in dirs:
            if (Path(directory) / name).is_symlink() or (Path(directory) / name).is_junction():
                raise ValueError(f'Links are not migrated: {Path(directory) / name}')
        relative = Path(directory).relative_to(source)
        (target / relative).mkdir(parents=True, exist_ok=True)
        for name in files:
            origin, destination = Path(directory) / name, target / relative / name
            if origin.is_symlink():
                raise ValueError(f'Links are not migrated: {origin}')
            if destination.exists():
                if destination.stat().st_size == origin.stat().st_size and destination.read_bytes() == origin.read_bytes():
                    continue
                raise ValueError(f'A different file already exists in the store: {destination}')
            if link_results:
                try:
                    os.link(origin, destination)  # Results are never edited in place, only replaced.
                    linked += 1
                    continue
                except OSError:
                    pass  # Another volume: copy instead.
            shutil.copy2(origin, destination)
            copied += 1
    return {'copied': copied, 'linked': linked}


def _readonly_copy(path, target):
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def apply(config, value, confirm):
    """Import every ``ready`` folder of a plan into the store, then verify. ``confirm(text)`` asks the owner."""
    import shutil
    import sqlite3
    from contextlib import closing
    from dataclasses import replace
    from pathlib import Path
    from . import library_store
    from .config import ConfigError
    from .incremental import ledger, working
    from .publication import atomic_json, read_json
    from .sources import now, read_records
    running = app_processes()
    if running:
        raise ConfigError('Close the Assetarium app and MCP servers first: ' + '; '.join(running)[:400])
    done = imported(config)
    ready = [f for f in value['folders'] if f['status'] == 'ready' and str(f['metadata']).casefold() not in done]
    if not ready:
        raise ConfigError('Nothing to import: every folder is imported already, faulty or in conflict')
    if not confirm(f"Import {len(ready)} old generated folder(s) into {config.library_store()}? "
                   "Nothing is moved; the old folders stay until you remove them with --remove-old."):
        raise ConfigError('Cancelled; nothing was changed')
    from .source_storage import receipt
    before = receipt(config, 'migration-before')['totals']
    store = config.library_store()
    store.mkdir(parents=True, exist_ok=True)
    results, groups = [], {}
    # Every folder is registered first, so a texture one model borrows from another folder still resolves.
    with closing(library_store.connect(config)) as db, db:
        for item in ready:
            library_store.save_folder(db, {'id': item['id'], 'key': item['key'], 'name': item.get('name') or item['key'],
                                           'path': item['path'], 'enabled': item.get('enabled', True)},
                                      state='removed' if item.get('detached') else 'active')
    from .sources import _registry_file
    _registry_file.cache_clear()
    for item in ready:
        found = {k: item[k] for k in ('path', 'metadata', 'id', 'key')}
        legacy = legacy_bound(config, found)
        entry = {**{k: item.get(k) for k in ('path', 'metadata', 'id', 'key', 'library_folder', 'relinked_from')}, 'status': 'imported'}
        try:
            metadata = Path(item['metadata'])
            absorbed = store / 'absorbed' / item['id']
            absorbed.mkdir(parents=True, exist_ok=True)
            shutil.copy2(metadata / 'source.json', absorbed / 'source.json')
            copy = absorbed / 'jobs.sqlite'  # The old ledger, kept as evidence; pending is measured on a copy of it.
            _readonly_copy(metadata / 'library/jobs.sqlite', copy)
            measured = absorbed / 'jobs-measured.sqlite'
            shutil.copy2(copy, measured)
            entry['before'] = {stage: sorted(pending(working(legacy), stage, legacy=True, ledger_path=measured))
                               for stage in ('inspection', 'caption')}
            measured.unlink()
            entry['published_ids'] = sorted(r['asset_id'] for r in read_records(legacy))
            records = read_records(working(legacy)) or read_records(legacy)
            entry['known_ids'] = sorted(r['asset_id'] for r in records)
            # Results are shared by the whole store; working data and evidence go under the folder's own directory.
            partition = store / 'folders' / item['id']
            entry['copy'] = {}
            for area in ('inspection', 'captions'):
                if (metadata / area).is_dir():
                    entry['copy'][area] = _copy_tree(metadata / area, store / area, link_results=True)
            for child in metadata.iterdir():
                if child.name in {'inspection', 'captions'}:
                    continue
                if child.is_dir():
                    entry['copy'][child.name] = _copy_tree(child, partition / child.name, link_results=False)
                else:
                    partition.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(child, partition / child.name)
            (partition / 'library/jobs.sqlite').unlink(missing_ok=True)  # The store's ledger replaces it.
            # Every type is enrolled now (decision 0023); a format restriction becomes the proposed exclusions.
            settings = read_json(partition / 'source.json')
            excluded = list(dict.fromkeys(settings.get('excluded_folders', []) + item['enroll']['proposed_exclusions']))
            settings = {k: v for k, v in settings.items() if k not in {'import_types', 'import_formats'}}
            if excluded:
                settings['excluded_folders'] = excluded[:50]
            atomic_json(partition / 'source.json', settings)
            # Re-key a copy of the old ledger, then merge it into the store's ledger.
            rekeyed = absorbed / 'jobs-rekeyed.sqlite'
            shutil.copy2(copy, rekeyed)
            with closing(sqlite3.connect(rekeyed)) as db:
                entry['rekeyed'] = rekey(working(legacy), db, config)
                rows = db.execute('SELECT * FROM jobs').fetchall()
                history = db.execute('SELECT asset_id, stage, fingerprint, status, evidence, updated FROM history ORDER BY sequence').fetchall()
            rekeyed.unlink()
            with closing(ledger(replace(config, source_key=item['key']))) as db, db:
                db.executemany('INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?)', rows)
                db.executemany('INSERT INTO history(asset_id,stage,fingerprint,status,evidence,updated) VALUES (?,?,?,?,?,?)', history)
            # The folder and its assets, with their existing IDs.
            source = {'id': item['id'], 'key': item['key'], 'name': item.get('name') or item['key'], 'path': item['path'],
                      'enabled': item.get('enabled', True)}
            with closing(library_store.connect(config)) as db, db:
                stamp = now()
                db.executemany("INSERT OR IGNORE INTO assets VALUES (?,?,?,?,'present',?,?,NULL)",
                               [(r['asset_id'], item['id'], r['source_relative_identity'], library_store.content_of(r), stamp, stamp)
                                for r in records])
            groups.setdefault(item['library_folder'], []).append(source)
        except Exception as exc:  # A fault stops only its own folder, with evidence; the others continue.
            entry.update(status='faulty', fault=f'{type(exc).__name__}: {exc}')
            with closing(library_store.connect(config)) as db, db:
                db.execute('DELETE FROM folders WHERE id=?', (item['id'],))  # Not imported: a later run takes it.
        results.append(entry)
    # A folder named with --library-folder takes in the old sources inside it; recognition keeps every ID.
    from . import sources as library
    for root, members in groups.items():
        if len(members) == 1 and Path(members[0]['path']) == Path(root):
            continue
        library._registry_file.cache_clear()
        for member in members:  # A detached old source inside it joins too.
            with closing(library_store.connect(config)) as db, db:
                library_store.save_folder(db, member, state='active')
        library._registry_file.cache_clear()
        added = library.add(config, root)
        for entry in results:
            if entry.get('library_folder') == root and entry['status'] == 'imported':
                entry['joined'] = added['key']
    return verify(config, {'schema_version': 1, 'utc': now(), 'plan_utc': value.get('utc'), 'folders': results,
                           'storage_before': before})


def verify(config, value):
    """Rescan (no models), check every published ID is present and nothing newly pending; save the receipt."""
    from .incremental import working
    from .publication import atomic_json
    from .source_storage import receipt
    from .sources import _registry_file, bound, read_records, registry, scan_source
    _registry_file.cache_clear()
    present, faults, after = set(), {}, {'inspection': set(), 'caption': set()}
    for source in registry(config)['sources'] + registry(config)['detached']:
        try:
            if source in registry(config)['sources']:
                scan_source(config, source)
            work = working(bound(config, source))
            present |= {r['asset_id'] for r in read_records(work)}
            for stage in after:
                after[stage] |= pending(work, stage)
        except Exception as exc:
            faults[source['key']] = f'{type(exc).__name__}: {exc}'
    for entry in value['folders']:
        if entry['status'] != 'imported':
            continue
        before, known = entry.pop('before'), set(entry.pop('known_ids'))
        lost = sorted(set(entry.pop('published_ids')) - present)
        newly = {stage: sorted((after[stage] & known) - set(before[stage])) for stage in before}
        entry['check'] = {'missing_published_ids': lost, 'newly_pending': newly,
                          'pending_before': {s: len(v) for s, v in before.items()},
                          'pending_after': {s: len(after[s] & known) for s in before}}
        entry['status'] = 'verified' if not lost and not any(newly.values()) else 'unverified'
    value['scan_faults'] = faults
    value['storage_after'] = receipt(config, 'migration-after')['totals']
    path = config.project_root / f"data/library/migration/{_stamp(value['utc'])}.json"
    atomic_json(path, value)
    return value, path


def remove_old(config, confirm):
    """Owner-only: remove old generated folders whose import a receipt verified, one confirmation each."""
    import os
    import shutil
    from pathlib import Path
    from .config import ConfigError
    done = list(migrated(config).values())
    if not done:
        raise ConfigError('No verified import yet; run the migration and check its receipt first')
    removed = []
    for entry in done:
        metadata = Path(entry['metadata'])
        if not metadata.is_dir():
            continue
        if metadata.name.casefold() != LEGACY_METADATA_DIR or metadata.is_symlink() or metadata.is_junction():
            raise ConfigError(f'Refusing an unexpected folder: {metadata}')
        size, links = 0, []
        for directory, dirs, files in os.walk(metadata, followlinks=False):
            links += [str(Path(directory) / d) for d in dirs if (Path(directory) / d).is_symlink() or (Path(directory) / d).is_junction()]
            size += sum((Path(directory) / f).lstat().st_size for f in files)
        if links:
            raise ConfigError(f'{metadata} contains links; check them and remove it by hand: ' + ', '.join(links[:3]))
        if confirm(f'Remove {metadata} ({size / 2**20:.1f} MiB)?'):
            shutil.rmtree(metadata)
            removed.append({'metadata': str(metadata), 'bytes': size})
    return removed
