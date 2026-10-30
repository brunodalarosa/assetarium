"""The implicit processing queue (decision 0023): Make previews and Generate descriptions wait in line.

An item names an action and a scope (a folder or pack of a library folder, or picked assets). The scope is
resolved when the item starts: "whatever there still lacks previews". Previews always run ahead of
descriptions; otherwise items run in the owner's order. Items run one at a time through the durable source
operations, and each operation starts the next item when it ends, so the queue needs no open window. An
overnight switch holds descriptions until the chosen window. A queue left over after a restart is paused and
never resumes by itself. Blocked work is never queued: its prerequisite and fix are shown instead.
"""
from datetime import datetime, time as clock, timezone
import json
from pathlib import PurePosixPath
import statistics
import uuid

from .config import ConfigError
from .publication import atomic_json, read_json

ACTIONS = ('previews', 'descriptions')
OPERATION = {'previews': 'process', 'descriptions': 'describe'}
QUICK, LONG = 10 * 60, 30 * 60  # Seconds: start on a click; above QUICK an Undo toast; above LONG ask first.
RECENT = 30


def now():
    return datetime.now(timezone.utc).isoformat()


def queue_path(config):
    return config.library_store() / 'queue/queue.json'


def load(config):
    path = queue_path(config)
    value = read_json(path) if path.exists() else {}
    value.setdefault('schema_version', 1)
    value.setdefault('items', [])
    value.setdefault('recent', [])
    value.setdefault('paused', False)
    value.setdefault('overnight', {'enabled': False, 'start': '22:00', 'end': '07:00'})
    return value


def save(config, value):
    path = queue_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, value)


def _locked(config):
    from .gpu_queue import lease
    return lease(config, 'processing-queue', resource='queue')


def scope_label(config, scope):
    from .sources import get_source
    source = get_source(config, scope['key'])
    if scope.get('asset_ids'):
        count = len(scope['asset_ids'])
        return f"{count} picked {'asset' if count == 1 else 'assets'} in {source['name']}"
    return PurePosixPath(scope['path']).name if scope.get('path') else source['name']


def validate_scope(config, scope):
    from .sources import get_source
    if not isinstance(scope, dict) or not isinstance(scope.get('key'), str):
        raise ConfigError('Choose a library folder, pack, folder or assets')
    source = get_source(config, scope['key'])
    path = scope.get('path') or ''
    ids = scope.get('asset_ids') or []
    if not isinstance(path, str) or '..' in PurePosixPath(path).parts or not isinstance(ids, list) or len(ids) > 100000:
        raise ConfigError('Invalid scope')
    return source, {'key': scope['key'], 'path': path.strip('/'), 'asset_ids': [str(i) for i in ids]}


def resolve(config, action, scope):
    """The assets an item would process now, and those it cannot (blocked), from the saved working catalog."""
    from .incremental import working
    from .library_view import _folder, blockers, kind_of, state_of
    from .settings import descriptions_enabled, processing_eligible, processing_formats
    from .sources import bound, description_state, embedding_failures, get_source, read_records
    source = get_source(config, scope['key'])
    scoped = bound(config, source)
    work = working(scoped)
    current = work if work.output_path('data', 'catalog.sqlite').exists() else scoped
    if not current.output_path('data', 'catalog.sqlite').exists():
        return {'ids': [], 'blocked': {}, 'kinds': {}, 'records': []}
    records = read_records(current)
    picked = set(scope.get('asset_ids') or ())
    path = scope.get('path') or ''
    inside = lambda r: (r['asset_id'] in picked) if picked else (not path or _folder(r, source['key']) == path
                                                                  or _folder(r, source['key']).startswith(path + '/'))
    blocked, faults, formats = blockers(config), embedding_failures(current), processing_formats(config)
    ids, stopped, kinds, chosen = [], {}, {}, []
    for record in records:
        if not inside(record) or not processing_eligible(record, formats):
            continue
        if action == 'previews':
            state, reason = state_of(record, blocked, faults)
            if state == 'blocked':
                stopped[reason] = stopped.get(reason, 0) + 1
                continue
            if state != 'no_previews':
                continue
        elif not descriptions_enabled(config) or description_state(record) != 'missing':
            continue
        ids.append(record['asset_id'])
        chosen.append(record)
        kinds[kind_of(record)] = kinds.get(kind_of(record), 0) + 1
    return {'ids': ids, 'blocked': stopped, 'kinds': kinds, 'records': chosen,
            'fixes': {b['reason']: b['fix'] for b in blocked.values()}}


def _batch_rate(config, stage):
    """Seconds per asset from recent batch reports of this stage, across library folders (None without history)."""
    rates = []
    for path in sorted((config.library_store() / 'folders').glob(f'*/library/batches/{stage}-*.json'),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:12]:
        try:
            value = read_json(path)
        except (OSError, ValueError):
            continue
        done = (value.get('complete') or 0) + (value.get('failed') or 0)
        if done and value.get('elapsed_seconds'):
            rates.append(value['elapsed_seconds'] / done)
    return statistics.median(rates) if rates else None


def _render_rate(config):
    from .render_devices import saved
    test = saved(config)
    if not test:
        return None
    best = next((r.get('best') for r in test.get('results', []) if r.get('key') == test.get('chosen')), None)
    return best['seconds_per_asset'] if best else None


def _bytes_per_asset(config):
    """Median store bytes per finished inspection result (a sample of the store; None without history)."""
    sizes = []
    for root in ('results/inspection', 'inspection'):
        for folder in list((config.library_store() / root).glob('*/*' if root == 'inspection' else '*/*'))[:200]:
            if folder.is_dir():
                sizes.append(sum(f.stat().st_size for f in folder.iterdir() if f.is_file()))
    return statistics.median(sizes) if sizes else None


def _store_use(config):
    """Allocated bytes from the newest storage receipt, and the budget (no new measurement here)."""
    from .settings import storage_budget
    receipts = sorted((config.project_root / 'data/storage').glob('*.json'), key=lambda p: p.stat().st_mtime)
    used = None
    for path in reversed(receipts[-5:]):
        try:
            used = read_json(path)['totals']['allocated_bytes']
            break
        except (OSError, ValueError, KeyError):
            continue
    try:
        budget = storage_budget(config)['total_allocated_bytes']
    except (ConfigError, OSError, ValueError):
        budget = None
    return used, budget


def estimate(config, action, found):
    """Counts per kind, a time range and disk, from the speed test and recent runs; or "no measurement yet"."""
    kinds = found['kinds']
    models, images = kinds.get('model_3d', 0), sum(v for k, v in kinds.items() if k != 'model_3d')
    if action == 'previews':
        render = _batch_rate(config, 'inspection') or _render_rate(config)
        search = _batch_rate(config, 'embeddings') or 0.3
        seconds = None if render is None and models else (models * (render or 0) + images * 0.5 + (models + images) * search)
    else:
        rate = _batch_rate(config, 'caption')
        seconds = None if rate is None else (models + images) * rate
    per_asset = _bytes_per_asset(config) if action == 'previews' else 4096
    disk = None if per_asset is None else int(per_asset * (models + images))
    used, budget = _store_use(config)
    return {'assets': models + images, 'kinds': kinds,
            'seconds': None if seconds is None else [round(seconds * 0.7), round(seconds * 1.5)],
            'measured': seconds is not None, 'disk_bytes': disk,
            'budget_reached': bool(budget and used is not None and disk is not None and used + disk > budget),
            'budget_bytes': budget, 'used_bytes': used}


def duration(seconds):
    minutes = max(1, round(seconds / 60))
    return f'{minutes} min' if minutes < 90 else f'{minutes / 60:.1f} h'


def describe_estimate(value):
    kinds = value['kinds']
    words = {'model_3d': ('model', 'models'), 'image': ('image', 'images'), 'material_texture': ('material texture', 'material textures')}
    counts = ', '.join(f"{n:,} {words.get(k, (k, k))[n != 1]}" for k, n in sorted(kinds.items()))
    low, high = (duration(s) for s in value['seconds']) if value['seconds'] else (None, None)
    time = ((f'about {high}' if low == high else f'about {low}–{high}') if value['seconds']
            else 'no measurement yet (run the render speed test in Settings → General for an estimate)')
    disk = f", about {value['disk_bytes'] / 2**20:,.0f} MiB in the library store" if value['disk_bytes'] else ''
    budget = ' This would reach your storage budget; the run stops there and keeps finished work.' if value['budget_reached'] else ''
    return f'{counts}: {time}{disk}.{budget}'


def add(config, action, scope, confirmed=False):
    """Queue an action. Under 10 minutes it starts on the click; 10–30 minutes start with Undo; longer asks first."""
    if action not in ACTIONS:
        raise ConfigError('Choose Make previews or Generate descriptions')
    if action == 'descriptions':
        from .settings import descriptions_enabled
        from .source_operations import DESCRIPTIONS_OFF
        if not descriptions_enabled(config):
            raise ConfigError(DESCRIPTIONS_OFF)
    source, scope = validate_scope(config, scope)
    if not source['enabled']:
        raise ConfigError('Enable this library folder in search before processing it')
    found = resolve(config, action, scope)
    label = scope_label(config, scope)
    if not found['ids']:
        if found['blocked']:
            reason, count = next(iter(found['blocked'].items()))
            raise ConfigError(f"{count:,} {'asset waits' if count == 1 else 'assets wait'} for a fix: {reason}. {found['fixes'].get(reason, '')}".strip())
        raise ConfigError(f"Nothing in {label} needs {'previews' if action == 'previews' else 'descriptions'}")
    value = estimate(config, action, found)
    verb = 'Make previews' if action == 'previews' else 'Generate descriptions'
    long = value['seconds'] is not None and value['seconds'][1] > LONG
    if (long or value['budget_reached']) and not confirmed:
        return {'status': 'confirm', 'estimate': value, 'title': f'{verb} for {label}?',
                'body': describe_estimate(value) + ' It runs in the background; you can keep working, cancel it, or hold descriptions overnight.',
                'confirm_label': f"{verb} ({value['assets']:,} {'asset' if value['assets'] == 1 else 'assets'})"}
    item = {'id': uuid.uuid4().hex, 'action': action, 'scope': scope, 'label': label, 'added_utc': now(), 'status': 'waiting',
            'estimate': value}
    with _locked(config):
        queue = load(config)
        queue['items'].append(item)
        if queue['paused'] and not any(i['status'] == 'running' for i in queue['items']):
            queue['paused'] = False  # Asking for work is the owner's go-ahead.
        save(config, queue)
    started = advance(config)
    running = started and started.get('id') == item['id']
    undo = value['seconds'] is not None and QUICK < value['seconds'][1] <= LONG
    text = describe_estimate(value)
    return {'status': 'started' if running else 'queued', 'item': item, 'undo': undo,
            'title': (f"Started · {duration(value['seconds'][1])}" if value['seconds'] and running else 'Started' if running else 'Waiting in line'),
            'body': f'{verb} for {label}. {text}'}


def _order(items, overnight_hold):
    """Previews always go ahead of descriptions; otherwise the owner's order. Held descriptions wait."""
    waiting = [i for i in items if i['status'] == 'waiting']
    previews = [i for i in waiting if i['action'] == 'previews']
    descriptions = [] if overnight_hold else [i for i in waiting if i['action'] == 'descriptions']
    return previews + descriptions


def in_window(window, moment=None):
    moment = (moment or datetime.now()).time()
    start, end = (clock.fromisoformat(window['start']), clock.fromisoformat(window['end']))
    return start <= moment < end if start < end else moment >= start or moment < end


def _finish_running(config, queue):
    """Move a running item whose operation ended to Recent, with its outcome."""
    from .source_operations import operation_status, RUNNING
    from .sources import bound, get_source
    changed = False
    for item in [i for i in queue['items'] if i['status'] in {'running', 'cancelling'}]:
        try:
            status = operation_status(bound(config, get_source(config, item['scope']['key'])))
        except ConfigError:
            status = {'status': 'faulty', 'reason': 'The library folder was removed'}
        if status.get('token') == item.get('token') and status.get('status') in RUNNING:
            continue
        outcome = status.get('status') if status.get('token') == item.get('token') else 'interrupted'
        queue['items'].remove(item)
        queue['recent'] = ([{**item, 'status': outcome, 'finished_utc': now(), 'phase': status.get('phase'),
                             'reason': status.get('reason'), 'faults': status.get('faults')}] + queue['recent'])[:RECENT]
        changed = True
    return changed


def advance(config):
    """Start the next item when nothing runs (never while paused). Returns the item that runs now, or None."""
    from .source_operations import start
    with _locked(config):
        queue = load(config)
        _finish_running(config, queue)
        running = next((i for i in queue['items'] if i['status'] in {'running', 'cancelling'}), None)
        if running or queue['paused']:
            save(config, queue)
            return running
        hold = queue['overnight']['enabled'] and not in_window(queue['overnight'])
        for item in _order(queue['items'], hold):
            found = resolve(config, item['action'], item['scope'])  # The scope is resolved when the item starts.
            if not found['ids']:
                queue['items'].remove(item)
                queue['recent'] = ([{**item, 'status': 'nothing_to_do', 'finished_utc': now(),
                                     'reason': 'Everything here was already done or is blocked'}] + queue['recent'])[:RECENT]
                continue
            try:
                result = start(config, OPERATION[item['action']], item['scope']['key'], asset_ids=found['ids'], queue_item=item['id'])
            except ConfigError as exc:
                queue['items'].remove(item)
                queue['recent'] = ([{**item, 'status': 'faulty', 'finished_utc': now(), 'reason': str(exc)}] + queue['recent'])[:RECENT]
                continue
            if result.get('status') != 'started':
                break  # Another operation runs on this folder; the item waits for it.
            item.update(status='running', token=result['token'], started_utc=now(), resolved=len(found['ids']))
            break
        save(config, queue)
        return next((i for i in queue['items'] if i['status'] == 'running'), None)


def control(config, action, identifier=None, value=None):
    """Up next: remove, move, pause, resume, overnight. Removing the running item cancels it cleanly."""
    from .source_operations import cancel
    from .sources import bound, get_source
    with _locked(config):
        queue = load(config)
        item = next((i for i in queue['items'] if i['id'] == identifier), None)
        if action in {'remove', 'move'} and item is None:
            raise ConfigError('That item is no longer in the queue')
        if action == 'remove':
            if item['status'] == 'running':
                cancel(bound(config, get_source(config, item['scope']['key'])))
                item['status'] = 'cancelling'
            else:
                queue['items'].remove(item)
        elif action == 'move':
            if type(value) is not int:
                raise ConfigError('Give a position')
            queue['items'].remove(item)
            queue['items'].insert(max(0, min(len(queue['items']), value)), item)
        elif action in {'pause', 'resume'}:
            queue['paused'] = action == 'pause'
        elif action == 'overnight':
            window = dict(queue['overnight'], **(value or {}))
            if type(window.get('enabled')) is not bool:
                raise ConfigError('Overnight must be on or off')
            for key in ('start', 'end'):
                clock.fromisoformat(window[key])
            queue['overnight'] = {k: window[k] for k in ('enabled', 'start', 'end')}
        else:
            raise ConfigError('Unknown queue action')
        save(config, queue)
    if action in {'resume', 'remove', 'overnight', 'move'}:
        advance(config)
    return state(config)


def after_restart(config):
    """At app start: a leftover queue is shown paused, with Resume; it never resumes by itself."""
    with _locked(config):
        queue = load(config)
        _finish_running(config, queue)
        if any(i['status'] == 'waiting' for i in queue['items']) and not any(i['status'] == 'running' for i in queue['items']):
            queue['paused'] = True
        save(config, queue)


def _log_lines(config, item):
    """Errors and warnings of a running item's operation log (copyable), newest last."""
    from .sources import bound, get_source
    try:
        log = bound(config, get_source(config, item['scope']['key'])).output_path('data', f"library/operations/{item['token']}.log")
        lines = log.read_text(encoding='utf-8', errors='replace').splitlines()[-400:]
    except (ConfigError, OSError, KeyError):
        return []
    keep = [line for line in lines if any(w in line.lower() for w in ('error', 'warning', 'failed', 'fault', 'traceback'))]
    return [{'text': line[:600], 'level': 'error' if any(w in line.lower() for w in ('error', 'failed', 'traceback')) else 'warning'}
            for line in keep[-40:]] + [{'text': line[:600], 'level': 'info'} for line in lines[-8:] if line not in keep]


def failures(config):
    """Recorded failures by stage and reason, per library folder (never mixed with pending work)."""
    from .incremental import working
    from .sources import bound, read_records, registry, import_outcome
    groups = {}
    for source in registry(config)['sources']:
        scoped = bound(config, source)
        current = working(scoped) if working(scoped).output_path('data', 'catalog.sqlite').exists() else scoped
        if not current.output_path('data', 'catalog.sqlite').exists():
            continue
        for record in read_records(current):
            outcome = import_outcome(record)
            for stage in outcome['failed_stages']:
                fault = (record.get('stage_faults') or {}).get(stage) or (record.get('stage_faults') or {}).get('previews') or {}
                reason = str(fault.get('error') or fault.get('reason') or 'Recorded failure')[:300]
                key = (source['key'], stage, reason)
                entry = groups.setdefault(key, {'key': source['key'], 'folder': source['name'], 'stage': stage, 'reason': reason, 'assets': []})
                entry['assets'].append({'asset_id': record['asset_id'], 'name': record['display_name'],
                                        'path': record['files'][0]['path'] if record['files'] else None})
    return sorted(groups.values(), key=lambda g: (-len(g['assets']), g['folder'], g['stage']))


def blocked_groups(config):
    """Blocked work by reason with its fix and how many assets it would unblock."""
    from .library_view import blockers, folder_tree
    from .sources import registry
    found = blockers(config)
    if not found:
        return []
    counts = {}
    for source in registry(config)['sources']:
        try:
            nodes = folder_tree(config, source).get('nodes', [])
        except Exception:  # A folder that cannot be read is shown on the Asset sources tab.
            continue
        root = next((n for n in nodes if n['path'] == ''), None)
        if root:
            counts[source['key']] = root.get('blocked', 0)
    total = sum(counts.values())
    return [{**b, 'assets': total, 'folders': {k: v for k, v in counts.items() if v}} for b in found.values()]


def state(config):
    """Everything the Asset processing tab shows: Running, Up next, Blocked, Recorded failures, Recent."""
    from .source_operations import operation_status
    from .sources import bound, get_source
    with _locked(config):
        queue = load(config)
        if _finish_running(config, queue):
            save(config, queue)
    running = next((i for i in queue['items'] if i['status'] in {'running', 'cancelling'}), None)
    if running:
        try:
            running = {**running, 'operation': operation_status(bound(config, get_source(config, running['scope']['key']))),
                       'log': _log_lines(config, running)}
        except ConfigError:
            pass
    hold = queue['overnight']['enabled'] and not in_window(queue['overnight'])
    order = _order(queue['items'], False)
    return {'status': 'ready', 'paused': queue['paused'], 'overnight': {**queue['overnight'], 'holding': hold},
            'running': running, 'up_next': [{**i, 'held': hold and i['action'] == 'descriptions'} for i in order],
            'blocked': blocked_groups(config), 'failures': failures(config), 'recent': queue['recent']}
