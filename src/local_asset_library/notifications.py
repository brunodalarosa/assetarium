"""App notifications; one small atomic JSON file (decisions 0008 and 0012).

Kinds: ``descriptions_ready`` (one per source, replaced by newer facts),
``descriptions_report`` (one per describe run, keyed by its operation token),
``collection_changed`` (one per collection an agent edited, replaced by its latest edit),
``setup_changed`` (one per agent setup session) and ``setup_proposal`` (one per pending proposal).
Notifications never start work; their actions call ordinary bridge operations.
"""
from .gpu_queue import lease
from .publication import atomic_json, read_json
from .sources import now

LIMIT = 50
REPORTED = {'complete', 'complete_with_failures', 'cancelled', 'stopped', 'interrupted'}


def path(config):
    return config.project_root / 'data/library/notifications.json'


def load(config):
    target = path(config)
    try:
        value = read_json(target) if target.exists() else {}
    except (OSError, ValueError):
        value = {}
    items = [item for item in value.get('items', []) if isinstance(item, dict) and item.get('id')]
    dismissed = {k: v for k, v in (value.get('dismissed') or {}).items() if isinstance(v, int)}
    return {'schema_version': 1, 'seeded_existing': bool(value.get('seeded_existing')), 'items': items,
            'dismissed': dismissed}


def _change(config, update):
    with lease(config, 'notifications', resource='notifications'):
        value = load(config)
        before = repr(value)
        update(value)
        # Newest first; unread items are never trimmed before read ones.
        value['items'].sort(key=lambda item: item.get('created_utc', ''), reverse=True)
        while len(value['items']) > LIMIT:
            read = [i for i, item in enumerate(value['items']) if item.get('read')]
            value['items'].pop(read[-1] if read else -1)
        if repr(value) != before:
            atomic_json(path(config), value)
        return value


def ready(source, missing):
    return {'id': 'ready-' + source['id'], 'kind': 'descriptions_ready', 'source_id': source['id'],
            'source_key': source['key'], 'source_name': source['name'], 'missing': missing,
            'created_utc': now(), 'read': False}


def notify_ready(config, source, missing):
    """Raise a ready notice after processing; only new missing descriptions raise it again.

    "Not now" remembers the dismissed count, so reprocessing an unchanged source
    stays quiet. Nothing is shown when nothing is missing.
    """
    from .settings import descriptions_enabled
    enabled = descriptions_enabled(config)
    def update(value):
        identifier = 'ready-' + source['id']
        existing = next((item for item in value['items'] if item['id'] == identifier), None)
        value['items'] = [item for item in value['items'] if item['id'] != identifier]
        if not enabled or not missing or missing <= value['dismissed'].get(source['id'], 0):
            return
        value['items'].append(dict(existing, missing=missing) if existing and missing <= existing['missing']
                              else ready(source, missing))
    return _change(config, update)


def notify_report(config, source, token, outcome, **facts):
    if outcome not in REPORTED:
        raise ValueError('Unknown description report outcome')
    item = {'id': 'report-' + token, 'kind': 'descriptions_report', 'source_id': source['id'],
            'source_key': source['key'], 'source_name': source['name'], 'outcome': outcome,
            'created_utc': now(), 'read': False, **facts}
    def update(value):
        if not any(existing['id'] == item['id'] for existing in value['items']):
            value['items'].append(item)
    return _change(config, update)


def clear_ready(config, source_id):
    """Starting a description run resolves the notice and forgets an earlier "Not now"."""
    def update(value):
        value['items'] = [item for item in value['items'] if item['id'] != 'ready-' + source_id]
        value['dismissed'].pop(source_id, None)
    return _change(config, update)


def notify_collection(config, collection, change, summary):
    """Agent edits raise one notice per collection, replaced by its latest change."""
    item = {'id': 'collection-' + collection['id'], 'kind': 'collection_changed', 'collection_id': collection['id'],
            'collection_name': collection['name'], 'change': change, 'summary': summary,
            'asset_count': len(collection['items']), 'created_utc': now(), 'read': False}
    def update(value):
        value['items'] = [existing for existing in value['items'] if existing['id'] != item['id']] + [item]
    return _change(config, update)


def forget_collection(config, collection_id):
    def update(value):
        value['items'] = [item for item in value['items'] if item['id'] != 'collection-' + collection_id]
    return _change(config, update)


def notify_setup_change(config, session_id, changes, finished=False):
    """Agent setup changes raise one notice per setup session, listing every value it changed (decision 0016)."""
    def update(value):
        identifier = 'setup-' + session_id
        existing = next((item for item in value['items'] if item['id'] == identifier), None)
        merged = {change['key']: change for change in (existing or {}).get('changes', [])}
        merged.update({change['key']: change for change in changes})
        value['items'] = [item for item in value['items'] if item['id'] != identifier] + [{
            'id': identifier, 'kind': 'setup_changed', 'session_id': session_id, 'changes': list(merged.values()),
            'finished': finished or bool((existing or {}).get('finished')), 'created_utc': now(), 'read': False}]
    return _change(config, update)


def notify_setup_proposal(config, proposal):
    item = {'id': 'proposal-' + proposal['id'], 'kind': 'setup_proposal', 'proposal_id': proposal['id'], 'key': proposal['key'],
            'path': proposal['path'], 'version': proposal['version'], 'created_utc': now(), 'read': False}
    return _change(config, lambda value: value.update(items=[i for i in value['items'] if i['id'] != item['id']] + [item]))


def forget_setup_proposal(config, proposal_id):
    """A decided or superseded proposal leaves no notice whose action could no longer change anything."""
    def update(value):
        value['items'] = [item for item in value['items'] if item['id'] != 'proposal-' + proposal_id]
    return _change(config, update)


def act(config, action, identifier=None):
    if action not in {'read', 'dismiss', 'read_all'}:
        raise ValueError('Unknown notification action')
    def update(value):
        if action == 'dismiss':
            for item in value['items']:
                if item['id'] == identifier and item['kind'] == 'descriptions_ready':
                    value['dismissed'][item['source_id']] = item['missing']
            value['items'] = [item for item in value['items'] if item['id'] != identifier]
        for item in value['items']:
            if action == 'read_all' or item['id'] == identifier:
                item['read'] = True
    return _change(config, update)


def reconcile(config, statuses):
    """Keep notices true to current source status; seeds existing sources once.

    Ready notices of removed sources or of sources with nothing missing are
    dropped. A describe run that stopped without writing its own report (worker
    exit or coordinator fault) gets one from its saved operation state.
    """
    from .settings import descriptions_enabled
    by_id = {status['id']: status for status in statuses}
    current = load(config)
    reported = {item['id'] for item in current['items']}
    enabled = descriptions_enabled(config)
    def missing(status):
        # Turned-off descriptions are not pending work: ready notices are stale, and none are seeded.
        return (status.get('descriptions') or {}).get('missing', 0) if enabled and status.get('enabled') else 0
    late = []
    for status in statuses:
        operation = status.get('operation') or {}
        if (operation.get('operation') == 'describe' and operation.get('token')
                and operation.get('status') in {'interrupted', 'faulty'}
                and 'report-' + operation['token'] not in reported):
            late.append((status, operation))
    stale = [item for item in current['items'] if item['kind'] == 'descriptions_ready'
             and (item['source_id'] not in by_id or not missing(by_id[item['source_id']])
                  or item.get('missing') != missing(by_id[item['source_id']]))]
    # A dismissed count only suppresses descriptions that are still missing.
    # While descriptions are off, "Not now" counts and first-launch seeding wait for them to return.
    lowered = {key: min(count, missing(by_id[key])) for key, count in current['dismissed'].items()
               if key in by_id and min(count, missing(by_id[key]))} if enabled else current['dismissed']
    if (current['seeded_existing'] or not enabled) and not late and not stale and lowered == current['dismissed']:
        return current
    def update(value):
        if enabled and not value['seeded_existing']:
            for status in statuses:
                if missing(status) and status.get('scanned'):
                    value['items'] = [item for item in value['items'] if item['id'] != 'ready-' + status['id']]
                    value['items'].append(ready(status, missing(status)))
            value['seeded_existing'] = True
        kept = []
        for item in value['items']:
            if item['kind'] == 'descriptions_ready':
                status = by_id.get(item['source_id'])
                if status is None or not missing(status):
                    continue
                # Counts follow the source; read state and position are kept.
                item['missing'] = missing(status)
            kept.append(item)
        value['items'] = kept
        if enabled:
            value['dismissed'] = {key: min(count, missing(by_id[key])) for key, count in value['dismissed'].items()
                                  if key in by_id and min(count, missing(by_id[key]))}
        ids = {item['id'] for item in value['items']}
        for status, operation in late:
            if 'report-' + operation['token'] not in ids:
                value['items'].append({'id': 'report-' + operation['token'], 'kind': 'descriptions_report',
                    'source_id': status['id'], 'source_key': status['key'], 'source_name': status['name'],
                    'outcome': 'stopped' if operation['status'] == 'faulty' else 'interrupted',
                    'reason': operation.get('reason') or 'The description run stopped unexpectedly',
                    'created_utc': now(), 'read': False})
    return _change(config, update)
