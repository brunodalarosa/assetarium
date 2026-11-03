"""The Asset sources tab: library folders → bundles → packs → folders, with work states (decision 0023).

Read only. Built from each folder's working catalog and inventory (never a scan), cached by their identity.
Each asset has one work state (no previews yet, queued, running, ready, blocked, failed, missing, excluded)
plus overlays (warning, description, collections, new). Blocked work names its fix and is never offered as a
processing action; recorded failures stay apart from pending work.
"""
from contextlib import closing
import json
from pathlib import Path, PurePosixPath

from .config import ConfigError

STATES = ('no_previews', 'queued', 'running', 'ready', 'blocked', 'failed', 'missing', 'excluded', 'skipped')
TYPES = (('model_3d', '3D models'), ('image', 'Images'), ('material_texture', 'Material textures'))


def blockers(config):
    """Prerequisites a stage needs and lacks, each with its fix: Blender for 3D previews, the search runtime."""
    from .config import with_saved_blender
    from .engines import runtime_ready, weights_command, weights_ready, command, search_device, SEARCH_DEVICES
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
    elif weights.get('state') == 'present':
        found['search'] = {'reason': 'The search model is here but not verified yet', 'stages': ['embeddings'], 'types': ['model_3d', 'image'],
                           'fix': 'Verify it (reads the files, downloads nothing): ' + weights_command(config, 'embedding', weights, project)}
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


def _folder(record, key):
    path = record['files'][0]['path'] if record.get('files') else ''
    parent = PurePosixPath(path.removeprefix(key + '/')).parent.as_posix()
    return '' if parent == '.' else parent


def _current(config, source):
    """The folder's working catalog when it has one, else its published one; None before a first scan."""
    from .incremental import working
    from .sources import bound
    scoped = bound(config, source)
    work = working(scoped)
    current = work if work.output_path('data', 'catalog.sqlite').exists() else scoped
    return current if current.output_path('data', 'catalog.sqlite').exists() else None


def _new_ids(config, source):
    """Assets first seen after the owner's last visit to this folder (none before a first visit)."""
    from .library_store import answers, connect, database_path
    visit = next((a['value'] for a in answers(config, source['id'], 'visit')), '')
    if not visit or not database_path(config).exists():
        return []
    with closing(connect(config)) as db:
        return [r[0] for r in db.execute('SELECT asset_id FROM assets WHERE folder_id=? AND first_seen > ?', (source['id'], visit))]


def folder_tree(config, source, blocked=None):
    """One library folder's nodes (folders only) with counts, coverage and +N new, from its view (never whole records)."""
    from .folder_view import Reading, connect, state_sql
    from .packs import names_of, structure
    if not Path(source['path']).is_dir():
        return {'offline': True, 'nodes': []}
    current = _current(config, source)
    if current is None:
        return {'offline': False, 'nodes': [], 'scanned': False}
    try:
        view = connect(current)
    except Reading:
        return {'offline': False, 'scanned': True, 'reading': True, 'nodes': []}
    state, params, _, _ = state_sql(blockers(config) if blocked is None else blocked)
    with closing(view):
        groups = view.execute(f'SELECT asset_folders.folder, {state}, has_preview, COUNT(*) FROM assets '
                              'JOIN asset_folders USING(asset_id) WHERE asset_folders.visible GROUP BY 1, 2, 3', params).fetchall()
        # Files in formats that are off: counted per folder for one quiet line, never listed or offered as work.
        hidden = view.execute('SELECT asset_folders.folder, COUNT(*) FROM assets JOIN asset_folders USING(asset_id) '
                              'WHERE NOT asset_folders.visible GROUP BY 1').fetchall()
        fresh = view.execute('SELECT asset_folders.folder, COUNT(*) FROM assets JOIN asset_folders USING(asset_id) '
                             'WHERE asset_folders.visible AND asset_id IN (SELECT value FROM json_each(?)) GROUP BY 1',
                             (json.dumps(_new_ids(config, source)),)).fetchall()
        folders = [r[0] for r in view.execute('SELECT path FROM folders')]
        detected = structure(config, source, view)
    nodes = {'': {'path': '', 'children': set(), 'assets': 0, 'previews': 0, 'new': 0, 'pending': 0, 'blocked': 0, 'failed': 0, 'skipped': 0,
                  'hidden': 0}}

    def node(path):
        if path not in nodes:
            nodes[path] = {'path': path, 'children': set(), 'assets': 0, 'previews': 0, 'new': 0, 'pending': 0, 'blocked': 0, 'failed': 0,
                           'skipped': 0, 'hidden': 0}
            parent = PurePosixPath(path).parent.as_posix()
            node('' if parent == '.' else parent)['children'].add(path)
        return nodes[path]

    def chain(folder):
        parts = PurePosixPath(folder).parts if folder else ()
        return [node('/'.join(parts[:depth])) for depth in range(len(parts) + 1)]
    for folder in folders:  # Folders only; files are listed in the grid.
        node(folder)
    for folder, state, preview, count in groups:
        for entry in [node(folder)]:
            entry['assets'] += count
            entry['previews'] += count * (state == 'ready' or (state != 'failed' and bool(preview)))
            entry['pending'] += count * (state == 'no_previews')
            entry['blocked'] += count * (state == 'blocked')
            entry['failed'] += count * (state == 'failed')
            entry['skipped'] += count * (state == 'skipped')
    for folder, count in fresh:
        for entry in [node(folder)]:
            entry['new'] += count
    for folder, count in hidden:
        for entry in [node(folder)]:
            entry['hidden'] += count
    packs, bundles, names = detected['packs'], set(detected['bundles']), names_of(config, source)
    result = []
    for path, entry in sorted(nodes.items()):
        pack = packs.get(path)
        kind = 'library' if path == '' else 'pack' if pack else 'bundle' if path in bundles else 'folder'
        result.append({**entry, 'children': sorted(entry['children']), 'kind': kind,
                       'name': names.get(path) or (PurePosixPath(path).name if path else None),
                       # Coverage of what Assetarium processes: skipped assets can never get previews.
                       'coverage': round(entry['previews'] / (entry['assets'] - entry['skipped']), 3)
                       if entry['assets'] > entry['skipped'] else None,
                       'pack': {'id': pack['id'], 'cover': pack.get('cover'), 'basis': pack['basis'],
                                'markers': pack['markers']} if pack else None})
    return {'offline': False, 'scanned': True, 'nodes': result}


def tree(config):
    """Every library folder with its tree, what needs the owner, and the migration notice."""
    from .library_migration import needed
    from .library_store import missing_count
    from .sources import registry, source_status
    folders, blocked = [], blockers(config)
    for source in registry(config)['sources']:
        try:
            status = source_status(config, source)
            entry = folder_tree(config, source, blocked)
        except Exception as exc:  # One unreadable folder shows its fault; the others still list.
            status, entry = {'scan_fault': f'{type(exc).__name__}: {exc}'}, {'offline': not Path(source['path']).is_dir(), 'nodes': []}
        attention = [reason for reason, active in (
            ('Offline', entry['offline']), ('Files missing', bool(status.get('missing'))),
            ('Duplicate export folders to answer', bool(status.get('export_suggestions'))),
            ('A texture folder to choose', bool((status.get('texture_suggestion') or {}).get('folders')) and not status.get('texture_folder')),
            ('Could not be read', bool(status.get('scan_fault')))) if active]
        folders.append({**source, **entry, 'attention': attention, 'missing': missing_count(config, source['id']),
                        'excluded_folders': status.get('excluded_folders', []), 'exclusions': status.get('exclusions', []),
                        'export_suggestions': status.get('export_suggestions', []), 'export_decisions': status.get('export_decisions', []),
                        'texture_suggestion': status.get('texture_suggestion'), 'texture_folder': status.get('texture_folder'),
                        'scan_fault': status.get('scan_fault'), 'operation': status.get('operation'),
                        'scanned_utc': status.get('scanned_utc')})
    migration = needed(config)
    return {'status': 'ready', 'folders': folders, 'migration': migration, 'blockers': list(blocked.values()),
            'types': [{'id': i, 'label': label} for i, label in TYPES],
            'attention': bool(migration.get('needed') or any(f['attention'] for f in folders))}


ITEM = 'asset_id, name, kind, state, reason, folder, formats, has_preview, path, description, warning'


def folder_items(config, key, path='', offset=0, page_size=60, filters=None, show_files=True):
    """A folder's (or pack's) asset cards with state and overlays, then its other files, faded; paged in SQL from its view.

    Variants of one group are one card (its representative, or the first member a filter keeps) with ``variants``
    listing every member; ``assets`` counts assets, ``cards`` and ``total`` count what pages through.
    """
    from .asset_collections import load
    from .folder_view import Reading, connect, inside_sql, asset_scope_sql, state_sql
    from .library_store import missing_list
    from .packs import names_of, pack_of, structure
    from .settings import descriptions_enabled
    from .sources import get_source
    if type(offset) is not int or offset < 0 or type(page_size) is not int or not 1 <= page_size <= 200:
        raise ConfigError('Invalid page')
    filters = filters or {}
    source = get_source(config, key)
    current = _current(config, source)
    inside = lambda folder: not path or folder == path or folder.startswith(path.rstrip('/') + '/')
    wanted = set(filters.get('states') or ())
    missing = []
    for asset in missing_list(config, source['id']):
        saved = asset.get('record') or {}
        folder = _folder(saved, key) if saved.get('files') else PurePosixPath(asset['locator']).parent.as_posix().replace('.', '')
        if inside(folder) and (not wanted or 'missing' in wanted):
            missing.append({'asset_id': asset['asset_id'], 'name': saved.get('display_name') or PurePosixPath(asset['locator']).stem,
                            'kind': kind_of(saved) if saved else 'model_3d', 'state': 'missing', 'folder': folder,
                            'reason': 'Not found since ' + asset['last_seen'][:10], 'overlays': {}, 'formats': [], 'has_preview': False,
                            'path': None, 'pack': None})
    counts = dict.fromkeys(STATES, 0)
    if current is None:
        counts['missing'] = len(missing)
        return {'status': 'ready', 'key': key, 'path': path, 'items': missing[offset:offset + page_size], 'total': len(missing), 'cards': len(missing),
                'assets': len(missing), 'files': 0, 'counts': counts, 'offset': offset, 'page_size': page_size}
    try:
        view = connect(current)
    except Reading as exc:
        return {'status': 'reading', 'reason': str(exc), 'key': key, 'path': path}
    new = _new_ids(config, source)
    state, state_params, reason, reason_params = state_sql(blockers(config))
    where, params = asset_scope_sql(path)
    where += ' AND NOT hidden'  # Formats that are off do not exist for Assetarium (decision 0026).
    if filters.get('types'):
        where += f" AND kind IN ({','.join('?' * len(filters['types']))})"
        params += list(filters['types'])
    if wanted:
        where += f" AND ({state} IN ({','.join('?' * len(wanted))})" + (
            ' OR asset_id IN (SELECT value FROM json_each(?)))' if 'new' in wanted else ')')
        params += state_params + sorted(wanted) + ([json.dumps(new)] if 'new' in wanted else [])
    with closing(view):
        counts.update(view.execute(f'SELECT {state}, COUNT(*) FROM assets WHERE {where} GROUP BY 1', state_params + params).fetchall())
        listed = view.execute(f'SELECT COUNT(DISTINCT card) FROM assets WHERE {where}', params).fetchone()[0]
        assets = sum(counts.values()) + len(missing)
        counts['missing'] += len(missing)
        cards = listed + len(missing)
        files_where, files_params = inside_sql(path)
        files = view.execute(f'SELECT COUNT(*) FROM files WHERE {files_where}', files_params).fetchone()[0] if show_files else 0
        # One row per card: its representative when the filters keep it, otherwise the first member they keep.
        rows = view.execute(f'SELECT {ITEM}, group_key FROM (SELECT {ITEM}, group_key, folder_key, '
                            'ROW_NUMBER() OVER (PARTITION BY card ORDER BY representative DESC, name_key, asset_id) AS position, '
                            'MIN(name_key) OVER (PARTITION BY card) AS card_name, card '
                            f'FROM (SELECT *, {state} AS state, {reason} AS reason FROM assets WHERE {where})) '
                            'WHERE position = 1 ORDER BY folder_key, card_name, card LIMIT ? OFFSET ?',
                            state_params + reason_params + params + [page_size, offset]).fetchall() if offset < listed else []
        members = {}
        grouped = sorted({row[-1] for row in rows if row[-1]})
        if grouped:  # Every member of the shown groups (at most variant_groups.CAP each), unfiltered: the picker shows them all.
            for row in view.execute(f'SELECT {ITEM}, group_key, variant, representative FROM (SELECT *, {state} AS state, {reason} AS reason '
                                    'FROM assets WHERE group_key IN (SELECT value FROM json_each(?))) ORDER BY group_key, representative DESC, name_key',
                                    state_params + reason_params + [json.dumps(grouped)]):
                members.setdefault(row[-3], []).append(row)
        detected = structure(config, source, view)
        descriptions, names, new = descriptions_enabled(config), names_of(config, source), set(new)
        collections = {}
        for collection in load(config).get('collections', []):
            for item in collection.get('items', []):
                collections[item['asset_id']] = collections.get(item['asset_id'], 0) + 1
        def item(row):
            asset_id, name, kind, item_state, item_reason, folder, formats, preview, first, description, warning = row[:11]
            found = {'warning': True} if warning else {}  # Review notes are not shown as warnings.
            if descriptions:
                found['description'] = description
            if collections.get(asset_id):
                found['collections'] = collections[asset_id]
            local_where, local_params = inside_sql(path)
            local_files = view.execute(f'SELECT path, format FROM locations WHERE asset_id=? AND visible AND {local_where} ORDER BY path',
                                       [asset_id] + local_params).fetchall()
            local_formats = sorted({f[1] for f in local_files})
            selected_format = local_formats[0] if path and len(local_formats) == 1 else None
            first = local_files[0][0] if local_files else first
            return {'asset_id': asset_id, 'name': name, 'kind': kind, 'asset_type': 'image' if kind in {'image', 'material_texture'} else 'model_3d',
                    'state': item_state, 'reason': item_reason, 'source_format': selected_format,
                    'folder': folder, 'pack': pack_of(config, source, {'files': [{'path': first}]}, detected, names) if first else None,
                    'formats': local_formats, 'has_preview': bool(preview), 'path': first, 'overlays': found,
                    'new': asset_id in new}
        page = []
        for row in rows:
            card = item(row)
            if row[-1] in members:
                card['group'] = row[-1]
                card['variants'] = [dict(item(m), variant=m[-2], representative=bool(m[-1])) for m in members[row[-1]]]
            page.append(card)
        start = max(0, offset - listed)
        page += missing[start:start + page_size - len(page)]
        if files and len(page) < page_size:
            page += [{'file': True, 'path': p, 'name': n, 'folder': f, 'role': r, 'excluded': bool(x)} for p, n, f, r, x in view.execute(
                f'SELECT path, name, folder, role, excluded FROM files WHERE {files_where} ORDER BY folder_key, name_key, path LIMIT ? OFFSET ?',
                files_params + [page_size - len(page), max(0, offset - cards)])]
    return {'status': 'ready', 'key': key, 'path': path, 'items': page, 'total': cards + files, 'cards': cards,
            'assets': assets, 'files': files, 'counts': counts, 'offset': offset, 'page_size': page_size}


def locate(config, asset_id):
    """Where an asset lives (its library folder and folder), for Show in pack."""
    from .folder_view import connect
    from .sources import registry
    for source in registry(config)['sources']:
        current = _current(config, source)
        if current is None:
            continue
        with closing(connect(current, fresh=True)) as view:
            row = view.execute('SELECT folder FROM assets WHERE asset_id=?', (asset_id,)).fetchone()
        if row:
            return {'status': 'located', 'key': source['key'], 'path': row[0], 'asset_id': asset_id}
    raise ConfigError('This asset is not in a library folder any more')


def record_visit(config, key):
    """The owner looked at this folder: its "+N new" counts from now (decision 0023 open point: resets on visit)."""
    from .library_store import now, save_answer
    from .sources import get_source
    source = get_source(config, key)
    save_answer(config, source['id'], '', 'visit', now())
    return {'status': 'saved'}
