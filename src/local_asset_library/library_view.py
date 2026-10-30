"""The Asset sources tab: library folders → bundles → packs → folders, with work states (decision 0023).

Read only. Built from each folder's working catalog and inventory (never a scan), cached by their identity.
Each asset has one work state (no previews yet, queued, running, ready, blocked, failed, missing, excluded)
plus overlays (warning, description, collections, new). Blocked work names its fix and is never offered as a
processing action; recorded failures stay apart from pending work.
"""
from contextlib import closing
from functools import lru_cache
import json
from pathlib import Path, PurePosixPath

from .config import ConfigError

STATES = ('no_previews', 'queued', 'running', 'ready', 'blocked', 'failed', 'missing', 'excluded')
TYPES = (('model_3d', '3D models'), ('image', 'Images'), ('material_texture', 'Material textures'))


def blockers(config):
    """Prerequisites a stage needs and lacks, each with its fix: Blender for 3D previews, the search runtime."""
    from .config import with_saved_blender
    from .engines import runtime_ready, weights_ready, command, search_device, SEARCH_DEVICES
    found = {}
    blender = with_saved_blender(config).blender
    if not blender or not Path(blender).exists():
        found['previews'] = {'reason': 'Blender is not set up', 'fix': 'Set up Blender in Settings → General → Setup',
                             'stages': ['inspection', 'previews'], 'types': ['model_3d']}
    try:
        project = SEARCH_DEVICES[search_device(config)]['project']
        runtime, weights = runtime_ready(config, 'embedding'), weights_ready(config, 'embedding')
    except (OSError, ValueError, KeyError) as exc:
        runtime, weights, project = {'ready': False}, {'ready': False, 'reason': str(exc)}, 'runtime/embedding'
    if not runtime['ready']:
        found['search'] = {'reason': 'The search runtime is not installed', 'stages': ['embeddings'], 'types': ['model_3d', 'image'],
                           'fix': 'Install it: ' + command(config, 'embedding', 'sync --locked --project ' + project)}
    elif not weights['ready']:
        found['search'] = {'reason': 'The search model is not downloaded', 'stages': ['embeddings'], 'types': ['model_3d', 'image'],
                           'fix': weights.get('reason') or 'Download it with scripts/prepare_embedding_model.py'}
    return found


def kind_of(record):
    if record.get('asset_type') == 'image':
        value = ((record.get('type_metadata') or {}).get('image_kind') or {}).get('value')
        return 'material_texture' if value == 'material_texture' else 'image'
    return record.get('asset_type', 'model_3d')


def state_of(record, blocked, vector_faults=None, queued=(), running=()):
    """(work state, reason) for one record."""
    from .sources import import_outcome
    outcome = import_outcome(record, None if vector_faults is None else record['asset_id'] in vector_faults)
    if outcome['failed_stages']:
        fault = next(iter((record.get('stage_faults') or {}).values()), {})
        return 'failed', str(fault.get('error') or fault.get('reason') or 'Recorded failure: ' + ', '.join(outcome['failed_stages']))
    if record['asset_id'] in running:
        return 'running', None
    if outcome['state'] == 'pending':
        # Blocked: the next stage this asset needs cannot run here (it would fail every time).
        following = next(s for s in ('inspection', 'previews', 'embeddings') if s in outcome['pending_stages'])
        for blocker in blocked.values():
            if following in blocker['stages'] and kind_of(record) in blocker['types']:
                return 'blocked', blocker['reason']
        if record['asset_id'] in queued:
            return 'queued', None
        return 'no_previews', 'Search data pending' if following == 'embeddings' else None
    return 'ready', None


def overlays(config, record, descriptions_on, collections):
    from .sources import description_state
    found = {}
    review = (record.get('caption_provenance') or {}).get('findings') or []
    if any(f.get('severity') == 'warning' for f in review if isinstance(f, dict)):
        found['warning'] = True  # Review notes are not shown as warnings.
    if descriptions_on:
        found['description'] = description_state(record)
    if collections.get(record['asset_id']):
        found['collections'] = collections[record['asset_id']]
    return found


def _folder(record, key):
    path = record['files'][0]['path'] if record.get('files') else ''
    parent = PurePosixPath(path.removeprefix(key + '/')).parent.as_posix()
    return '' if parent == '.' else parent


@lru_cache(maxsize=16)
def _tree(stamp, key, records_json, inventory_json, structure_json, names_json, first_seen_json, visit, blocked_json):
    records, inventory = json.loads(records_json), json.loads(inventory_json)
    detected, names, first_seen = json.loads(structure_json), json.loads(names_json), json.loads(first_seen_json)
    blocked = json.loads(blocked_json)
    nodes = {'': {'path': '', 'children': set(), 'assets': 0, 'previews': 0, 'new': 0, 'pending': 0, 'blocked': 0, 'failed': 0}}

    def node(path):
        if path not in nodes:
            nodes[path] = {'path': path, 'children': set(), 'assets': 0, 'previews': 0, 'new': 0, 'pending': 0, 'blocked': 0, 'failed': 0}
            parent = PurePosixPath(path).parent.as_posix()
            node('' if parent == '.' else parent)['children'].add(path)
        return nodes[path]
    for row in inventory:  # Folders only; files are listed in the grid.
        parent = PurePosixPath(row.removeprefix(key + '/')).parent.as_posix()
        node('' if parent == '.' else parent)
    for record in records:
        folder = _folder(record, key)
        state, _ = state_of(record, blocked)
        chain = PurePosixPath(folder).parts if folder else ()
        for depth in range(len(chain) + 1):
            entry = node('/'.join(chain[:depth]))
            entry['assets'] += 1
            entry['previews'] += state in {'ready'} or (state != 'failed' and bool(record.get('previews')))
            entry['pending'] += state == 'no_previews'
            entry['blocked'] += state == 'blocked'
            entry['failed'] += state == 'failed'
            entry['new'] += bool(visit and first_seen.get(record['asset_id'], '') > visit)
    packs, bundles = detected['packs'], set(detected['bundles'])
    result = []
    for path, entry in sorted(nodes.items()):
        pack = packs.get(path)
        kind = 'library' if path == '' else 'pack' if pack else 'bundle' if path in bundles else 'folder'
        result.append({**entry, 'children': sorted(entry['children']), 'kind': kind,
                       'name': names.get(path) or (PurePosixPath(path).name if path else None),
                       'coverage': round(entry['previews'] / entry['assets'], 3) if entry['assets'] else None,
                       'pack': {'id': pack['id'], 'cover': pack.get('cover'), 'basis': pack['basis'],
                                'markers': pack['markers']} if pack else None})
    return result


def folder_tree(config, source):
    """One library folder's nodes (folders only) with counts, coverage and +N new; cheap and cached."""
    from .catalog import read_database
    from .incremental import working
    from .library_store import answers, connect, database_path
    from .packs import names_of, structure
    from .sources import bound, read_records
    if not Path(source['path']).is_dir():
        return {'offline': True, 'nodes': []}
    scoped = bound(config, source)
    work = working(scoped)
    current = work if work.output_path('data', 'catalog.sqlite').exists() else scoped
    path = current.output_path('data', 'catalog.sqlite')
    if not path.exists():
        return {'offline': False, 'nodes': [], 'scanned': False}
    records = read_records(current)
    with closing(read_database(current)) as db:
        inventory = sorted(json.loads(r[0])['path'] for r in db.execute('SELECT record FROM inventory'))
    with closing(connect(config)) as db:
        first_seen = dict(db.execute("SELECT asset_id, first_seen FROM assets WHERE folder_id=?", (source['id'],)).fetchall()) \
            if database_path(config).exists() else {}
    visit = next((a['value'] for a in answers(config, source['id'], 'visit')), '')
    detected = structure(config, source, records)
    stat = path.stat()
    blocked = blockers(config)
    slim = [{k: r.get(k) for k in ('asset_id', 'files', 'processing', 'previews', 'technical', 'asset_type', 'type_metadata',
                                   'stage_faults', 'description')} for r in records]
    for item in slim:
        item['files'] = item['files'][:1]
        item['previews'] = bool(item['previews'])
        item['technical'] = bool(item['technical'])
        item['description'] = bool(item['description'])
    nodes = _tree((str(path), stat.st_mtime_ns, stat.st_size), source['key'], json.dumps(slim), json.dumps(inventory),
                  json.dumps(detected), json.dumps(names_of(config, source)), json.dumps(first_seen), visit, json.dumps(blocked))
    return {'offline': False, 'scanned': True, 'nodes': nodes}


def tree(config):
    """Every library folder with its tree, what needs the owner, and the migration notice."""
    from .library_migration import needed
    from .library_store import missing_assets
    from .sources import registry, source_status
    folders = []
    for source in registry(config)['sources']:
        try:
            status = source_status(config, source)
            entry = folder_tree(config, source)
        except Exception as exc:  # One unreadable folder shows its fault; the others still list.
            status, entry = {'scan_fault': f'{type(exc).__name__}: {exc}'}, {'offline': not Path(source['path']).is_dir(), 'nodes': []}
        attention = [reason for reason, active in (
            ('Offline', entry['offline']), ('Files missing', bool(status.get('missing'))),
            ('Duplicate export folders to answer', bool(status.get('export_suggestions'))),
            ('A texture folder to choose', bool((status.get('texture_suggestion') or {}).get('folders')) and not status.get('texture_folder')),
            ('Could not be read', bool(status.get('scan_fault')))) if active]
        folders.append({**source, **entry, 'attention': attention, 'missing': len(missing_assets(config, source['id'])),
                        'excluded_folders': status.get('excluded_folders', []), 'exclusions': status.get('exclusions', []),
                        'export_suggestions': status.get('export_suggestions', []), 'export_decisions': status.get('export_decisions', []),
                        'texture_suggestion': status.get('texture_suggestion'), 'texture_folder': status.get('texture_folder'),
                        'scan_fault': status.get('scan_fault'), 'operation': status.get('operation'),
                        'scanned_utc': status.get('scanned_utc')})
    migration = needed(config)
    return {'status': 'ready', 'folders': folders, 'migration': migration, 'blockers': list(blockers(config).values()),
            'types': [{'id': i, 'label': label} for i, label in TYPES],
            'attention': bool(migration.get('needed') or any(f['attention'] for f in folders))}


def folder_items(config, key, path='', offset=0, page_size=60, filters=None, show_files=True):
    """A folder's (or pack's) assets with state and overlays, then its other files, faded; paged."""
    from .asset_collections import load
    from .catalog import read_database
    from .incremental import working
    from .library_store import missing_assets
    from .packs import pack_of, structure
    from .settings import descriptions_enabled
    from .sources import bound, embedding_failures, get_source, read_records
    if type(offset) is not int or offset < 0 or type(page_size) is not int or not 1 <= page_size <= 200:
        raise ConfigError('Invalid page')
    filters = filters or {}
    source = get_source(config, key)
    scoped = bound(config, source)
    work = working(scoped)
    current = work if work.output_path('data', 'catalog.sqlite').exists() else scoped
    records = read_records(current) if current.output_path('data', 'catalog.sqlite').exists() else []
    inside = lambda folder: not path or folder == path or folder.startswith(path.rstrip('/') + '/')
    blocked, faults = blockers(config), embedding_failures(current)
    detected = structure(config, source, records)
    collections = {}
    for collection in load(config).get('collections', []):
        for item in collection.get('items', []):
            collections[item['asset_id']] = collections.get(item['asset_id'], 0) + 1
    descriptions = descriptions_enabled(config)
    from .library_store import answers, connect, database_path
    visit = next((a['value'] for a in answers(config, source['id'], 'visit')), '')
    first_seen = {}
    if visit and database_path(config).exists():
        with closing(connect(config)) as db:
            first_seen = dict(db.execute('SELECT asset_id, first_seen FROM assets WHERE folder_id=?', (source['id'],)).fetchall())
    items = []
    for record in sorted(records, key=lambda r: (_folder(r, key).casefold(), r['display_name'].casefold(), r['asset_id'])):
        if not inside(_folder(record, key)):
            continue
        kind = kind_of(record)
        if filters.get('types') and kind not in filters['types']:
            continue
        state, reason = state_of(record, blocked, faults)
        items.append({'asset_id': record['asset_id'], 'name': record['display_name'], 'kind': kind, 'state': state,
                      'reason': reason, 'folder': _folder(record, key), 'pack': pack_of(config, source, record, detected),
                      'formats': sorted({f['format'] for f in record['files']}), 'has_preview': bool(record.get('previews')),
                      'path': record['files'][0]['path'] if record['files'] else None,
                      'overlays': overlays(config, record, descriptions, collections),
                      'new': bool(visit and first_seen.get(record['asset_id'], '') > visit)})
    for asset in missing_assets(config, source['id']):
        saved = asset.get('record') or {}
        folder = _folder(saved, key) if saved.get('files') else PurePosixPath(asset['locator']).parent.as_posix().replace('.', '')
        if inside(folder):
            items.append({'asset_id': asset['asset_id'], 'name': saved.get('display_name') or PurePosixPath(asset['locator']).stem,
                          'kind': kind_of(saved) if saved else 'model_3d', 'state': 'missing', 'folder': folder,
                          'reason': 'Not found since ' + asset['last_seen'][:10], 'overlays': {}, 'formats': [], 'has_preview': False,
                          'path': None, 'pack': None})
    wanted = set(filters.get('states') or ())
    if wanted:
        items = [i for i in items if i['state'] in wanted or ('new' in wanted and i.get('new'))]
    files = []
    if show_files:
        owned = {f['path'] for r in records for f in r['files']}
        with closing(read_database(current)) as db:
            for (payload,) in db.execute('SELECT record FROM inventory'):
                row = json.loads(payload)
                folder = PurePosixPath(row['path'].removeprefix(key + '/')).parent.as_posix()
                folder = '' if folder == '.' else folder
                if row['path'] in owned or not inside(folder) or row.get('status') == 'excluded_folder':
                    continue
                files.append({'path': row['path'], 'name': PurePosixPath(row['path']).name, 'folder': folder,
                              'role': row.get('role'), 'excluded': row.get('status') in {'excluded_folder', 'excluded_directory_link'}})
        files.sort(key=lambda f: (f['folder'].casefold(), f['name'].casefold()))
    everything = items + [{'file': True, **f} for f in files]
    counts = {state: sum(i['state'] == state for i in items) for state in STATES}
    return {'status': 'ready', 'key': key, 'path': path, 'items': everything[offset:offset + page_size], 'total': len(everything),
            'assets': len(items), 'files': len(files), 'counts': counts, 'offset': offset, 'page_size': page_size}


def locate(config, asset_id):
    """Where an asset lives (its library folder and folder), for Show in pack."""
    from .incremental import working
    from .sources import bound, read_records, registry
    for source in registry(config)['sources']:
        scoped = bound(config, source)
        current = working(scoped) if working(scoped).output_path('data', 'catalog.sqlite').exists() else scoped
        if not current.output_path('data', 'catalog.sqlite').exists():
            continue
        record = next((r for r in read_records(current) if r['asset_id'] == asset_id), None)
        if record:
            return {'status': 'located', 'key': source['key'], 'path': _folder(record, source['key']), 'asset_id': asset_id}
    raise ConfigError('This asset is not in a library folder any more')


def record_visit(config, key):
    """The owner looked at this folder: its "+N new" counts from now (decision 0023 open point: resets on visit)."""
    from .library_store import now, save_answer
    from .sources import get_source
    source = get_source(config, key)
    save_answer(config, source['id'], '', 'visit', now())
    return {'status': 'saved'}
