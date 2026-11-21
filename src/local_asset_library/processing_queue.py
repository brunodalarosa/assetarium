"""The implicit processing queue (decision 0032): Make previews and Generate descriptions wait in line.

An item names an action and a scope (a folder or pack of a library folder, or picked assets). The scope is
resolved when the item starts: "whatever there still lacks previews". Previews always run ahead of
descriptions; otherwise items run in the owner's order. Items run one at a time through the durable source
operations, and every operation (scans included) starts the next item when it ends, so an item that waited
for a busy folder never stalls. While the app is open it owns the queue: closing it stops the running item at
once and keeps every item for Continue next time; work it started never outlives it, and after a crash nothing
is recovered (the items go to Recent with the reason). Nothing resumes by itself. Blocked work is never queued: its prerequisite and fix are shown instead.
"""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from itertools import islice
import json
from pathlib import PurePosixPath
import statistics
import uuid

from .config import ConfigError
from .publication import atomic_json, read_json
from .store_versions import read_versioned

ACTIONS = ('previews', 'descriptions')
OPERATION = {'previews': 'process', 'descriptions': 'describe'}
# A descriptions item generates missing ones; for named assets it can also try a recorded failure again (an explicit
# owner request, never bulk) or bring search up to date after the owner edited a description (no model writes text).
MODES = {'generate': 'missing', 'retry': 'failed', 'edited': 'complete'}
MODE_TITLE = {'retry': 'Try description again', 'edited': 'Update search for an edited description'}
QUICK, LONG = 10 * 60, 30 * 60  # Seconds: start on a click; above QUICK an Undo toast; above LONG ask first.
UNMEASURED = 100  # Assets: with no time or storage measurement yet, more than this asks first (it may be the longest job).
RECENT = 30


def now():
    return datetime.now(timezone.utc).isoformat()


def queue_path(config):
    return config.library_store() / 'queue/queue.json'


def load(config):
    path = queue_path(config)
    value = read_versioned(path, 'The processing queue', 1) if path.exists() else {}
    value.setdefault('schema_version', 1)
    value.setdefault('items', [])
    value.setdefault('recent', [])
    value.setdefault('paused', False)
    value.setdefault('search_pending', {})  # Asset ID → {key, utc}: an owner edit search does not read yet.
    value.pop('overnight', None)  # The overnight hold was removed; a queue saved with it loads unchanged otherwise.
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
    mode = scope.get('mode') or 'generate'
    if not isinstance(path, str) or '..' in PurePosixPath(path).parts or not isinstance(ids, list) or len(ids) > 100000:
        raise ConfigError('Invalid scope')
    if mode not in MODES or (mode != 'generate' and len(ids) != 1):
        raise ConfigError('Try again and search updates name one asset')
    return source, {'key': scope['key'], 'path': path.strip('/'), 'asset_ids': [str(i) for i in ids],
                    **({'mode': mode} if mode != 'generate' else {})}


def resolve(config, action, scope):
    """The assets an item would process now, and those it cannot (blocked), from the folder's up-to-date view."""
    from .folder_view import connect, asset_scope_sql, state_sql
    from .library_view import _current, blockers
    from .settings import descriptions_enabled
    from .sources import get_source
    source = get_source(config, scope['key'])
    current = _current(config, source)
    blocked = blockers(config)
    fixes = {b['reason']: b['fix'] for b in blocked.values()}
    mode = scope.get('mode') or 'generate'
    if current is None or (action != 'previews' and mode != 'edited' and not descriptions_enabled(config)):
        return {'ids': [], 'blocked': {}, 'kinds': {}, 'fixes': fixes}
    picked = scope.get('asset_ids')
    where, params = ('asset_id IN (SELECT value FROM json_each(?))', [json.dumps(picked)]) if picked else asset_scope_sql(scope.get('path') or '')
    state, state_params, reason, reason_params = state_sql(blocked)
    ids, stopped, kinds = [], {}, {}
    with closing(connect(current, fresh=True)) as view:
        rows = view.execute(f'SELECT asset_id, kind, {state}, {reason}, description FROM assets WHERE eligible AND NOT hidden AND {where} '
                            'ORDER BY asset_id', state_params + reason_params + params)
        for asset_id, kind, item_state, item_reason, description in rows:
            if action == 'previews':
                if item_state == 'blocked':
                    stopped[item_reason] = stopped.get(item_reason, 0) + 1
                    continue
                if item_state != 'no_previews':
                    continue
            elif description != MODES[mode]:
                continue
            ids.append(asset_id)
            kinds[kind] = kinds.get(kind, 0) + 1
    return {'ids': ids, 'blocked': stopped, 'kinds': kinds, 'fixes': fixes}


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
        for folder in islice((config.library_store() / root).glob('*/*'), 200):
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
    if value['budget_bytes'] and value['used_bytes'] is None:
        budget = " Storage use isn't measured yet, so the storage budget can't be checked first."
    return f'{counts}: {time}{disk}.{budget}'


def unmeasured(value):
    """No time or storage measurement yet for a job this big: ask first rather than guess it is short."""
    return value['assets'] > UNMEASURED and (value['seconds'] is None or bool(value['budget_bytes'] and value['used_bytes'] is None))


def add(config, action, scope, confirmed=False, by='owner'):
    """Queue an action. Under 10 minutes it starts on the click; 10–30 minutes start with Undo; longer asks first.

    ``by='agent'`` (decision 0029): the job is the current agent session's, journaled for its Undo all; it never
    resumes the owner's paused queue and is refused while agents are paused.
    """
    from .agent_sessions import PAUSED_REASON, current, note, paused
    if by == 'agent' and paused(config):
        raise ConfigError(PAUSED_REASON)
    if action not in ACTIONS:
        raise ConfigError('Choose Make previews or Generate descriptions')
    if action == 'previews' and (scope or {}).get('mode'):
        raise ConfigError('Try again and search updates are for descriptions')
    if action == 'descriptions' and (scope or {}).get('mode') != 'edited':
        from .settings import descriptions_enabled
        from .source_operations import DESCRIPTIONS_OFF
        if not descriptions_enabled(config):
            raise ConfigError(DESCRIPTIONS_OFF)
    source, scope = validate_scope(config, scope)
    if not source['enabled']:
        raise ConfigError('Enable this library folder in search before processing it')
    mode = scope.get('mode')
    with _locked(config):
        twin = next((i for i in load(config)['items'] if i['status'] == 'waiting' and i['action'] == action and i['scope'] == scope), None)
    if mode and twin:
        # The same request already waits; it reads the description when it starts, so one is enough.
        return {'status': 'queued', 'item': twin, 'undo': False, 'title': 'Waiting in line', 'body': MODE_TITLE[mode] + '.'}
    found = resolve(config, action, scope)
    if found.get('blocked'):
        with _locked(config):
            _hit_blocked(config, found['blocked'])
    label = scope_label(config, scope)
    if mode and not found['ids']:
        raise ConfigError('This description has no recorded failure to try again' if mode == 'retry'
                          else 'This asset has no generated description to update search for')
    if not found['ids']:
        if found['blocked']:
            reason, count = next(iter(found['blocked'].items()))
            raise ConfigError(f"{count:,} {'asset waits' if count == 1 else 'assets wait'} for a fix: {reason}. {found['fixes'].get(reason, '')}".strip())
        raise ConfigError(f"Nothing in {label} needs {'previews' if action == 'previews' else 'descriptions'}")
    value = estimate(config, action, found)
    verb = 'Make previews' if action == 'previews' else MODE_TITLE.get(mode, 'Generate descriptions')
    long = value['seconds'] is not None and value['seconds'][1] > LONG
    if (long or value['budget_reached'] or unmeasured(value)) and not confirmed:
        return {'status': 'confirm', 'estimate': value, 'title': f'{verb} for {label}?',
                'body': describe_estimate(value) + ' It runs in the background; you can keep working or cancel it.',
                'confirm_label': f"{verb} ({value['assets']:,} {'asset' if value['assets'] == 1 else 'assets'})"}
    session = current() if by == 'agent' else None
    item = {'id': uuid.uuid4().hex, 'action': action, 'scope': scope, 'label': label, 'added_utc': now(), 'status': 'waiting',
            'estimate': value, **({'title': MODE_TITLE[mode]} if mode else {}),
            **({'by': 'agent', 'agent': session['agent'] if session else ''} if by == 'agent' else {})}
    with _locked(config):
        queue = load(config)
        queue['items'].append(item)
        if by != 'agent' and queue['paused'] and not any(i['status'] == 'running' for i in queue['items']):
            queue['paused'] = False  # Asking for work is the owner's go-ahead; an agent's request never is.
        save(config, queue)
    if by == 'agent':
        note(config, 'job', item=item['id'], label=f'{verb} for {label}')
    started = advance(config)
    running = started and started.get('id') == item['id']
    undo = value['seconds'] is not None and QUICK < value['seconds'][1] <= LONG
    text = describe_estimate(value)
    return {'status': 'started' if running else 'queued', 'item': item, 'undo': undo,
            'title': (f"Started · {duration(value['seconds'][1])}" if value['seconds'] and running else 'Started' if running else 'Waiting in line'),
            'body': f'{verb} for {label}. {text}'}


def _order(items, held=False):
    """Previews always go ahead of descriptions; otherwise the owner's order. ``held``: agents are paused, so their
    jobs wait and the owner's go first."""
    waiting = [i for i in items if i['status'] == 'waiting' and not (held and i.get('by') == 'agent')]
    return [i for i in waiting if i['action'] == 'previews'] + [i for i in waiting if i['action'] == 'descriptions']


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
        if status.get('token') == item.get('token') and status.get('asset_ids'):
            _tried(config, item['scope']['key'], status['asset_ids'])
        if outcome == 'complete' and item['scope'].get('mode') == 'edited':
            for asset_id in item['scope']['asset_ids']:  # Search reads the edit now, unless it was saved after the start.
                if queue['search_pending'].get(asset_id, {}).get('utc', '') <= item.get('started_utc', ''):
                    queue['search_pending'].pop(asset_id, None)
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
        from .agent_sessions import paused
        for item in _order(queue['items'], held=paused(config)):
            found = resolve(config, item['action'], item['scope'])  # The scope is resolved when the item starts.
            if found.get('blocked'):
                _hit_blocked(config, found['blocked'])
            if not found['ids']:
                queue['items'].remove(item)
                queue['recent'] = ([{**item, 'status': 'nothing_to_do', 'finished_utc': now(),
                                     'reason': 'Everything here was already done or is blocked'}] + queue['recent'])[:RECENT]
                continue
            try:
                result = start(config, OPERATION[item['action']], item['scope']['key'], asset_ids=found['ids'], queue_item=item['id'],
                               owner=_owner(queue), **({'mode': item['scope']['mode']} if item['scope'].get('mode') else {}))
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
    """Up next: remove, move, pause, resume. Removing the running item cancels it cleanly."""
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
            elif item['status'] == 'cancelling':
                pass  # Already stopping; it leaves through Recent when its operation ends.
            else:
                queue['items'].remove(item)
        elif action == 'move':
            if type(value) is not int:
                raise ConfigError('Give a position')
            queue['items'].remove(item)
            queue['items'].insert(max(0, min(len(queue['items']), value)), item)
        elif action in {'pause', 'resume'}:
            queue['paused'] = action == 'pause'
            if action == 'resume':
                for waiting in queue['items']:
                    waiting.pop('stopped_on_close', None)
        else:
            raise ConfigError('Unknown queue action')
        save(config, queue)
    if action in {'resume', 'remove', 'move'}:
        advance(config)
    return state(config)


def withdraw(config, identifier):
    """Undo all of an agent session: a job of it that still waits leaves the queue. Returns why not otherwise;
    processing time already spent cannot be undone and its results are kept."""
    with _locked(config):
        queue = load(config)
        item = next((i for i in queue['items'] if i['id'] == identifier), None)
        if item is not None and item['status'] == 'waiting':
            queue['items'].remove(item)
            save(config, queue)
            return None
    return ('It is running now; stop it in Asset processing (finished results are kept)' if item is not None
            else 'It already ran or was removed; its results are kept')


def _owner(queue):
    """The open app's process ID, handed to the work it starts so that work stops with it; None from a terminal."""
    from .gpu_queue import process_alive
    owner = queue.get('owner') or {}
    return owner['pid'] if owner.get('pid') and not owner.get('closing') and process_alive(owner['pid']) else None


def _stopped_unexpectedly(queue, log=None):
    """After a crash nothing is recovered: every item goes to Recent with the reason and the log that holds it."""
    reason = 'Assetarium closed unexpectedly; this work stopped with it'
    queue['recent'] = ([{**i, 'status': 'stopped', 'finished_utc': now(), 'reason': reason, **({'log': log} if log else {})}
                        for i in queue['items']] + queue['recent'])[:RECENT]
    queue['items'], queue['paused'] = [], False


def claim(config, pid, log=None):
    """At app start the app owns the queue. ``log`` is its session log's file name, shown after a crash.

    Items the last app stopped when it closed wait paused behind Continue; if that app crashed instead, they go to
    Recent. Work left waiting from a terminal is paused too: nothing resumes by itself.
    """
    from .gpu_queue import process_alive
    with _locked(config):
        queue = load(config)
        _finish_running(config, queue)
        last = queue.get('owner') or {}
        if last.get('pid') and last['pid'] != pid and not last.get('closing') and not process_alive(last['pid']):
            _stopped_unexpectedly(queue, last.get('log'))
        if any(i['status'] == 'waiting' for i in queue['items']) and not any(i['status'] in {'running', 'cancelling'} for i in queue['items']):
            queue['paused'] = True
        queue['owner'] = {'pid': pid, 'closing': False, **({'log': log} if log else {})}
        save(config, queue)


def release(config, pid):
    """The app closes: its running item stops at once and every item waits for Continue next time."""
    from .source_operations import cancel
    from .sources import bound, get_source
    with _locked(config):
        queue = load(config)
        owner = queue.get('owner') or {}
        if owner.get('pid') != pid:
            return 0
        for item in queue['items']:
            if item['status'] in {'running', 'cancelling'}:
                try:
                    cancel(bound(config, get_source(config, item['scope']['key'])))
                except ConfigError:
                    pass  # The folder was removed; its operation ends with the app all the same.
                for key in ('token', 'started_utc', 'resolved'):
                    item.pop(key, None)
                item['status'] = 'waiting'  # Its scope resolves again on Continue, so finished assets are skipped.
            item['stopped_on_close'] = True
        queue['paused'] = queue['paused'] or bool(queue['items'])
        queue['owner'] = dict(owner, closing=True)
        save(config, queue)
        return len(queue['items'])


def owner_gone(config, pid):
    """A worker's app is gone. True when it closed on purpose; after a crash its items go to Recent."""
    with _locked(config):
        queue = load(config)
        owner = queue.get('owner') or {}
        if owner.get('pid') != pid or owner.get('closing'):
            return True
        _stopped_unexpectedly(queue, owner.get('log'))
        save(config, queue)
        return False


def running_item(config):
    """The item running now (with its operation's progress), so closing the app can ask first."""
    from .source_operations import operation_status
    from .sources import bound, get_source
    with _locked(config):
        queue = load(config)
        if _finish_running(config, queue):
            save(config, queue)
    item = next((i for i in queue['items'] if i['status'] in {'running', 'cancelling'}), None)
    if item is None:
        return None
    try:
        operation = operation_status(bound(config, get_source(config, item['scope']['key'])))
    except ConfigError:
        operation = {}
    return {**item, 'operation': operation, 'waiting': sum(i['status'] == 'waiting' for i in queue['items'])}


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
    from .folder_view import Reading, connect
    from .library_view import _current
    from .sources import registry
    groups = {}
    for source in registry(config)['sources']:
        current = _current(config, source)
        if current is None:
            continue
        try:
            view = connect(current)
        except Reading:
            continue  # Listed once the folder's view is built; the Asset sources tab shows it is being read.
        with closing(view):
            rows = view.execute('SELECT asset_id, name, path, failed_stages FROM assets WHERE failed_stages IS NOT NULL ORDER BY asset_id').fetchall()
        for asset_id, name, path, stages in rows:
            for stage, reason in json.loads(stages).items():
                key = (source['key'], stage, reason)
                entry = groups.setdefault(key, {'key': source['key'], 'folder': source['name'], 'stage': stage, 'reason': reason, 'assets': []})
                entry['assets'].append({'asset_id': asset_id, 'name': name, 'path': path})
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
            nodes = folder_tree(config, source, found).get('nodes', [])
        except Exception:  # A folder that cannot be read is shown on the Asset sources tab.
            continue
        root = next((n for n in nodes if n['path'] == ''), None)
        if root:
            counts[source['key']] = root.get('blocked', 0)
    total = sum(counts.values())
    return [{**b, 'assets': total, 'folders': {k: v for k, v in counts.items() if v}} for b in found.values()]


# Needs your attention (design principle P7): blocked work, recorded failures and stopped runs whose reason has a fix
# the owner can apply. Dismissing hides a notice and never touches a fault record; it returns ("again") when the
# same fault is triggered again. A stopped run's reason maps to the action that resolves it; others stay in Recent.
RUN_FIXES = (('The search check did not pass', 'run_check'), ('Storage budget reached', 'settings'),
             ('Descriptions are turned off', 'settings'), ('Processing is paused. Select formats', 'settings'))
KEPT_DISMISSALS = 1000


def notices_path(config):
    return config.storage_root('data') / 'library/attention.json'


def _notices(config):
    path = notices_path(config)
    value = read_versioned(path, 'Dismissed notices', 1) if path.exists() else {}
    value.setdefault('schema_version', 1)
    value.setdefault('dismissed', {})  # Card id → {utc, kind, key, assets, tried, hit}.
    return value


def _save_notices(config, value):
    kept = sorted(value['dismissed'].items(), key=lambda kv: kv[1]['utc'], reverse=True)[:KEPT_DISMISSALS]
    path = notices_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, {**value, 'dismissed': dict(kept)})


def _card_id(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]


def _run_fix(reason):
    return next((action for prefix, action in RUN_FIXES if (reason or '').startswith(prefix)), None)


def _search_ready(config):
    from .engines import capability_ready, search_device
    try:
        return capability_ready(config, search_device(config))['ready']
    except (ConfigError, OSError, ValueError, KeyError):
        return False


def _cards(config, blocked, groups, queue):
    """Every attention notice now, before dismissals apply (ids are stable signatures of the fault)."""
    from .folder_view import NO_REASON
    cards = [{'id': _card_id('blocked', b['reason']), 'kind': 'blocked', 'reason': b['reason'], 'fix': b['fix'], 'count': b['assets'],
              'actions': ['settings']} for b in blocked]
    logs = {}
    for item in queue['recent']:
        if item.get('log'):
            logs.setdefault(item['scope']['key'], item['log'])
    for g in groups:
        log = logs.get(g['key'])
        cards.append({'id': _card_id('failure', g['key'], g['stage'], g['reason']), 'kind': 'failure', 'key': g['key'], 'folder': g['folder'],
                      'stage': g['stage'], 'reason': g['reason'], 'no_reason': g['reason'] == NO_REASON, 'count': len(g['assets']),
                      'files': g['assets'], 'actions': ['recheck', 'library', 'copy'] + (['log'] if log else []), **({'log': log} if log else {})})
    seen = {json.dumps([i['action'], i['scope']], sort_keys=True) for i in queue['items']}  # Asked for again: superseded.
    search_ready = None
    for item in queue['recent']:  # Newest first: only the latest run of each scope counts.
        scope = json.dumps([item['action'], item['scope']], sort_keys=True)
        if scope in seen:
            continue
        seen.add(scope)
        fix = _run_fix(item.get('reason')) if item['status'] == 'faulty' else None
        if fix == 'run_check':
            search_ready = _search_ready(config) if search_ready is None else search_ready
            if search_ready:
                continue  # The check passed since; the run's notice no longer has anything to resolve.
        if fix:
            cards.append({'id': _card_id('run', scope, item['reason']), 'kind': 'run', 'key': item['scope']['key'], 'action': item['action'],
                          'title': item.get('title'), 'label': item['label'], 'reason': item['reason'], 'utc': item.get('finished_utc', ''),
                          'actions': [fix] + (['log'] if item.get('log') else []), **({'log': item['log']} if item.get('log') else {})})
    return cards


def _returned(card, entry):
    """A dismissed notice comes back when its fault is triggered again; reopening the app never brings one back."""
    if card['kind'] == 'failure':  # An asset joined it, or a run after the dismissal tried one and it failed again.
        ids = {a['asset_id'] for a in card['files']}
        return bool(ids - set(entry.get('assets', [])) or ids & set(entry.get('tried', [])))
    if card['kind'] == 'run':  # A later run of the same work stopped for the same reason.
        return card['utc'] > entry['utc']
    return bool(entry.get('hit'))  # Blocked: newly queued work hit the same block.


def _settle(cards, notices):
    for card in cards:
        entry = notices['dismissed'].get(card['id'])
        again = bool(entry) and _returned(card, entry)
        card['dismissed'], card['again'] = bool(entry) and not again, again
    return cards


def _hit_blocked(config, reasons):
    """Queued work met a block: a dismissed notice of it comes back. Called holding the queue lease."""
    notices = _notices(config)
    hits = [notices['dismissed'][i] for i in (_card_id('blocked', r) for r in reasons) if i in notices['dismissed']]
    for entry in hits:
        entry['hit'] = now()
    if hits:
        _save_notices(config, notices)


def _tried(config, key, asset_ids):
    """A run in ``key`` attempted these assets: dismissed failures of that folder return if they fail again."""
    notices = _notices(config)
    entries = [e for e in notices['dismissed'].values() if e.get('kind') == 'failure' and e.get('key') == key]
    for entry in entries:
        entry['tried'] = sorted(set(entry.get('tried', [])) | set(asset_ids))
    if entries:
        _save_notices(config, notices)


def dismiss(config, ids):
    """Hide these notices (never deletes anything); each returns when its fault is triggered again."""
    if not isinstance(ids, list) or not ids:
        raise ConfigError('Choose a notice to dismiss')
    with _locked(config):
        queue = load(config)
    cards = {c['id']: c for c in _cards(config, blocked_groups(config), failures(config), queue)}
    found = [cards[i] for i in ids if i in cards]
    if not found:
        raise ConfigError('That notice is no longer shown')
    with _locked(config):
        notices = _notices(config)
        for card in found:
            notices['dismissed'][card['id']] = {'utc': now(), 'kind': card['kind'], 'key': card.get('key'),
                                                **({'assets': [a['asset_id'] for a in card['files']]} if card['kind'] == 'failure' else {})}
        _save_notices(config, notices)
    return state(config)


def restore(config, ids):
    """Bring dismissed notices back (Bring back, or Undo of Dismiss all)."""
    if not isinstance(ids, list):
        raise ConfigError('Choose a notice to bring back')
    with _locked(config):
        notices = _notices(config)
        for identifier in ids:
            notices['dismissed'].pop(str(identifier), None)
        _save_notices(config, notices)
    return state(config)


def state(config):
    """Everything the Asset processing tab shows: Now and next, Needs your attention, Recent activity.

    ``blocked`` and ``failures`` stay for the owner CLI; the page reads them through ``attention``."""
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
    from .agent_sessions import paused
    blocked, groups = blocked_groups(config), failures(config)
    cards = _settle(_cards(config, blocked, groups, queue), _notices(config))
    return {'status': 'ready', 'paused': queue['paused'], 'agents_paused': paused(config), 'running': running, 'up_next': _order(queue['items']),
            'stopped_on_close': sum(bool(i.get('stopped_on_close')) for i in queue['items']),
            'attention': cards, 'dismissed': sum(c['dismissed'] for c in cards),
            'blocked': blocked, 'failures': groups, 'recent': queue['recent']}


def mark_search_pending(config, key, asset_id):
    """An owner edit was saved: search keeps the earlier text until a search update for it finishes, so the
    inspector can offer Update search even when the update was never queued (a declined confirmation, a fault)."""
    with _locked(config):
        queue = load(config)
        queue['search_pending'][asset_id] = {'key': key, 'utc': now()}
        save(config, queue)


def place(config, key, asset_ids):
    """Where description work for these assets stands: running, waiting (with its place) or, for an owner edit's
    search update, the newest one that did not finish, else ``pending`` while no update is queued for a saved edit.
    None when nothing concerns them. Read only."""
    from .folder_view import Reading, connect
    from .library_view import _current
    from .source_operations import RUNNING, operation_status
    from .sources import bound, get_source
    queue = load(config)
    try:
        source = get_source(config, key)
        current = _current(config, source)
    except ConfigError:
        return None
    states, folders = {}, set()
    if current is not None:
        try:
            with closing(connect(current)) as view:
                marks = ','.join('?' * len(asset_ids))
                states = dict(view.execute(f'SELECT asset_id, description FROM assets WHERE asset_id IN ({marks})', asset_ids))
                folders = {r[0] for r in view.execute(f'SELECT folder FROM asset_folders WHERE visible AND asset_id IN ({marks})', asset_ids)}
        except (Reading, ConfigError):
            pass

    def concerns(item):
        scope, mode = item['scope'], item['scope'].get('mode') or 'generate'
        if item['action'] != 'descriptions' or scope['key'] != key:
            return False
        if scope.get('asset_ids'):
            return bool(set(scope['asset_ids']) & set(asset_ids))
        return (scope.get('path') or '') in folders and MODES[mode] in states.values()
    running = next((i for i in queue['items'] if i['status'] in {'running', 'cancelling'}), None)
    if running and running['action'] == 'descriptions' and running['scope']['key'] == key:
        operation = operation_status(bound(config, source))
        if (operation.get('token') == running.get('token') and operation.get('status') in RUNNING
                and set(operation.get('asset_ids') or []) & set(asset_ids)):
            return {'status': 'running', 'mode': running['scope'].get('mode') or 'generate', 'phase': operation.get('phase')}
    for index, item in enumerate(_order(queue['items'])):
        if concerns(item):
            return {'status': 'waiting', 'mode': item['scope'].get('mode') or 'generate', 'position': index + 1 + bool(running),
                    'paused': queue['paused']}
    last = next((i for i in queue['recent'] if i['scope'].get('mode') == 'edited' and concerns(i)), None)
    if last and last['status'] != 'complete':
        return {'status': 'faulty', 'mode': 'edited', 'reason': last.get('reason') or last.get('phase') or 'The search update did not finish'}
    if any(queue['search_pending'].get(i, {}).get('key') == key for i in asset_ids):
        return {'status': 'pending', 'mode': 'edited'}  # Saved, but no search update is queued for it.
    return None
