"""Owner collections: virtual bundles of assets from any source and of any type (decision 0012).

A collection keeps asset IDs with a per-collection label and notes; it never moves,
copies or edits original files. The app and agent servers share one atomic JSON
file under the collections lease, so concurrent edits are serialized and none is
lost. Availability is resolved when read: an asset that leaves the library keeps
its entry, label and notes, and shows why it is unavailable.
"""
from contextlib import closing
import re
import uuid

from .config import ConfigError
from .gpu_queue import lease
from .publication import atomic_json, read_json
from .sources import now

COLLECTION_PATTERN = r'col_[0-9a-f]{16}'
ID_PATTERN = r'asset_[0-9a-f]{32}'
NAME_LENGTH, DESCRIPTION_LENGTH, LABEL_LENGTH, NOTES_LENGTH = 80, 2000, 60, 4000
COLLECTION_LIMIT, ITEM_LIMIT, BATCH_LIMIT = 500, 2000, 200


def path(config):
    return config.storage_root('data') / 'library/collections.json'


def load(config):
    target = path(config)
    if not target.exists():
        return {'schema_version': 1, 'revision': 0, 'collections': []}
    try:
        value = read_json(target)
    except (OSError, ValueError) as exc:
        raise ConfigError('Collections file is unreadable; it is kept unchanged for review: ' + str(exc)) from exc
    if value.get('schema_version') != 1 or not isinstance(value.get('collections'), list):
        raise ConfigError('Collections file has an unknown format; it is kept unchanged for review')
    return value


def text(value, limit, what, multiline=False, required=False):
    if value is None:
        value = ''
    if not isinstance(value, str):
        raise ConfigError(what + ' must be text')
    value = value.strip() if multiline else ' '.join(value.split())
    allowed = '\n\t' if multiline else ''
    if any(ord(c) < 32 and c not in allowed for c in value):
        raise ConfigError(what + ' contains control characters')
    if required and not value:
        raise ConfigError(what + ' is required')
    if len(value) > limit:
        raise ConfigError(f'{what} is limited to {limit} characters')
    return value


def asset_ids(values):
    if not isinstance(values, list) or len(values) > BATCH_LIMIT or any(
            not isinstance(i, str) or not re.fullmatch(ID_PATTERN, i) for i in values):
        raise ConfigError(f'Give at most {BATCH_LIMIT} asset IDs')
    return list(dict.fromkeys(values))


def find(value, identifier):
    if not isinstance(identifier, str) or not re.fullmatch(COLLECTION_PATTERN, identifier):
        raise ConfigError('Malformed collection ID')
    found = next((c for c in value['collections'] if c['id'] == identifier), None)
    if found is None:
        raise ConfigError('Collection not found; it may have been deleted')
    return found


def named(value, name):
    """Names are unique ignoring case, so people and agents can refer to them by name."""
    return next((c for c in value['collections'] if c['name'].casefold() == name.casefold()), None)


def library(config):
    """Visible library records by ID; an unpublished library simply has none."""
    from .retrieval import pilot_records
    try:
        return {r['asset_id']: r for r in pilot_records(config)}
    except (OSError, ValueError):
        return {}


def source_records(config, key, identifiers):
    """Published records of one registered source (disabled sources stay browsable)."""
    from .catalog import parse_record, read_database
    from .sources import bound, get_source
    scoped = bound(config, get_source(config, key))
    marks = ','.join('?' * len(identifiers))
    with closing(read_database(scoped)) as db:
        rows = db.execute(f'SELECT asset_id,pack_id,name,CAST(record AS BLOB) FROM assets WHERE asset_id IN ({marks})',
                          list(identifiers)).fetchall()
    return {row[0]: parse_record(*row) for row in rows}


def snapshot(config, record, source_key):
    from .asset_structure import asset_type
    from .sources import get_source
    try:
        source_name = get_source(config, source_key)['name'] if config.sources_registry else source_key
    except ConfigError:
        source_name = source_key
    return {'name': record['display_name'], 'pack': record['pack_id'], 'asset_type': asset_type(record),
            'source_key': source_key, 'source_name': source_name}


def lookup(config, identifiers, source_key=None):
    """Snapshots for new members: the library, or the source browser that showed them."""
    found = {}
    if source_key is None:
        records = library(config)
        found = {i: snapshot(config, records[i], records[i]['pack_id']) for i in identifiers if i in records}
    else:
        try:
            records = source_records(config, source_key, identifiers)
        except (OSError, ValueError) as exc:
            raise ConfigError('This source has no saved assets to add: ' + str(exc)) from exc
        found = {i: snapshot(config, records[i], source_key) for i in identifiers if i in records}
    missing = [i for i in identifiers if i not in found]
    if missing:
        raise ConfigError(f'{len(missing)} asset ID(s) are not in the library' +
                          ('' if source_key is None else ' or this source') + ': ' + ', '.join(missing[:3]))
    return found


def _edit(config, update, notice=None):
    with lease(config, 'collections', resource='collections'):
        value = load(config)
        result = update(value)
        value['revision'] = value.get('revision', 0) + 1
        atomic_json(path(config), value)
    if notice:
        # Agent edits raise one notice per collection; it opens the collection in the app.
        from .notifications import notify_collection
        try:
            notify_collection(config, *notice(value))
        except (OSError, ValueError):
            pass  # The edit is saved; a notice fault never undoes it.
    return dict(result, revision=value['revision'])


def _touch(collection):
    collection['updated_at'] = now()


def _items(collection, snapshots, label, notes):
    present = {item['asset_id'] for item in collection['items']}
    added = [i for i in snapshots if i not in present]
    if len(collection['items']) + len(added) > ITEM_LIMIT:
        raise ConfigError(f'A collection holds at most {ITEM_LIMIT} assets')
    stamp = now()
    collection['items'].extend({'asset_id': i, 'label': label, 'notes': notes, 'added_at': stamp,
                                'snapshot': snapshots[i]} for i in added)
    return added


def _agent_notice(actor, message):
    return message if actor == 'agent' else None


def create(config, name, description='', members=(), source_key=None, label='', notes='', actor='app'):
    name = text(name, NAME_LENGTH, 'Collection name', required=True)
    description = text(description, DESCRIPTION_LENGTH, 'Description', multiline=True)
    label, notes = text(label, LABEL_LENGTH, 'Label'), text(notes, NOTES_LENGTH, 'Notes', multiline=True)
    members = asset_ids(list(members))
    snapshots = lookup(config, members, source_key) if members else {}
    identifier = 'col_' + uuid.uuid4().hex[:16]
    def update(value):
        if named(value, name):
            raise ConfigError(f'A collection named “{name}” already exists')
        if len(value['collections']) >= COLLECTION_LIMIT:
            raise ConfigError(f'Assetarium keeps at most {COLLECTION_LIMIT} collections')
        stamp = now()
        collection = {'id': identifier, 'name': name, 'description': description, 'created_at': stamp,
                      'updated_at': stamp, 'created_by': actor, 'items': []}
        _items(collection, {i: snapshots[i] for i in members}, label, notes)
        value['collections'].append(collection)
        return {'status': 'created', 'collection_id': identifier, 'name': name, 'added': len(members)}
    notice = _agent_notice(actor, lambda value: (find(value, identifier), 'created',
                                                 f'An agent created this collection with {len(members)} asset(s).'))
    return _edit(config, update, notice)


def update(config, identifier, name=None, description=None, actor='app'):
    name = None if name is None else text(name, NAME_LENGTH, 'Collection name', required=True)
    description = None if description is None else text(description, DESCRIPTION_LENGTH, 'Description', multiline=True)
    def change(value):
        collection = find(value, identifier)
        if name is not None:
            other = named(value, name)
            if other and other['id'] != identifier:
                raise ConfigError(f'A collection named “{name}” already exists')
            collection['name'] = name
        if description is not None:
            collection['description'] = description
        _touch(collection)
        return {'status': 'saved', 'collection_id': identifier, 'name': collection['name']}
    notice = _agent_notice(actor, lambda value: (find(value, identifier), 'updated', 'An agent renamed or described this collection.'))
    return _edit(config, change, notice)


def delete(config, identifier):
    """App only, after the owner confirms; agents cannot delete collections."""
    def change(value):
        collection = find(value, identifier)
        value['collections'].remove(collection)
        return {'status': 'deleted', 'collection_id': identifier, 'name': collection['name']}
    result = _edit(config, change)
    from .notifications import forget_collection
    try:
        forget_collection(config, identifier)  # Its notice could no longer open anything.
    except (OSError, ValueError):
        pass
    return result


def add(config, identifier, members, source_key=None, label='', notes='', actor='app'):
    members = asset_ids(members)
    if not members:
        raise ConfigError('Choose at least one asset to add')
    label, notes = text(label, LABEL_LENGTH, 'Label'), text(notes, NOTES_LENGTH, 'Notes', multiline=True)
    snapshots = lookup(config, members, source_key)
    def change(value):
        collection = find(value, identifier)
        added = _items(collection, {i: snapshots[i] for i in members}, label, notes)
        if added:
            _touch(collection)
        return {'status': 'saved', 'collection_id': identifier, 'name': collection['name'],
                'added': len(added), 'already_present': len(members) - len(added)}
    notice = _agent_notice(actor, lambda value: (find(value, identifier), 'updated', f'An agent added {len(members)} asset(s).'))
    return _edit(config, change, notice)


def remove(config, identifier, members, actor='app'):
    """Returns the removed entries with their positions so the app can offer Undo."""
    members = set(asset_ids(members))
    def change(value):
        collection = find(value, identifier)
        removed = [dict(item, position=index) for index, item in enumerate(collection['items']) if item['asset_id'] in members]
        collection['items'] = [item for item in collection['items'] if item['asset_id'] not in members]
        if removed:
            _touch(collection)
        return {'status': 'saved', 'collection_id': identifier, 'name': collection['name'], 'removed': removed}
    notice = _agent_notice(actor, lambda value: (find(value, identifier), 'updated', f'An agent removed {len(members)} asset(s).'))
    return _edit(config, change, notice)


def restore(config, identifier, removed):
    """Undo a removal: entries return to their positions with labels and notes intact."""
    if not isinstance(removed, list) or len(removed) > ITEM_LIMIT:
        raise ConfigError('Nothing to restore')
    entries = []
    for item in removed:
        if not isinstance(item, dict) or not re.fullmatch(ID_PATTERN, str(item.get('asset_id'))):
            raise ConfigError('Restored entries are malformed')
        snap = item.get('snapshot') if isinstance(item.get('snapshot'), dict) else {}
        entries.append((int(item.get('position', 10 ** 6)), {
            'asset_id': item['asset_id'], 'label': text(item.get('label'), LABEL_LENGTH, 'Label'),
            'notes': text(item.get('notes'), NOTES_LENGTH, 'Notes', multiline=True),
            'added_at': str(item.get('added_at') or now())[:40],
            'snapshot': {k: text(snap.get(k), 200, 'Snapshot') for k in ('name', 'pack', 'asset_type', 'source_key', 'source_name')}}))
    def change(value):
        collection = find(value, identifier)
        present = {item['asset_id'] for item in collection['items']}
        restored = 0
        for position, entry in sorted(entries, key=lambda e: e[0]):
            if entry['asset_id'] not in present:
                collection['items'].insert(min(position, len(collection['items'])), entry)
                present.add(entry['asset_id'])
                restored += 1
        if len(collection['items']) > ITEM_LIMIT:
            raise ConfigError(f'A collection holds at most {ITEM_LIMIT} assets')
        _touch(collection)
        return {'status': 'saved', 'collection_id': identifier, 'restored': restored}
    return _edit(config, change)


def set_item(config, identifier, member, label=None, notes=None, actor='app'):
    if not isinstance(member, str) or not re.fullmatch(ID_PATTERN, member):
        raise ConfigError('Malformed asset ID')
    label = None if label is None else text(label, LABEL_LENGTH, 'Label')
    notes = None if notes is None else text(notes, NOTES_LENGTH, 'Notes', multiline=True)
    def change(value):
        collection = find(value, identifier)
        item = next((i for i in collection['items'] if i['asset_id'] == member), None)
        if item is None:
            raise ConfigError('This asset is not in the collection')
        if label is not None:
            item['label'] = label
        if notes is not None:
            item['notes'] = notes
        _touch(collection)
        return {'status': 'saved', 'collection_id': identifier, 'asset_id': member, 'label': item['label'], 'notes': item['notes']}
    notice = _agent_notice(actor, lambda value: (find(value, identifier), 'updated', 'An agent changed asset labels or notes.'))
    return _edit(config, change, notice)


def member_ids(config, identifier):
    return [item['asset_id'] for item in find(load(config), identifier)['items']]


def resolve(config, items, records=None, tags=None):
    """Current state of each entry; library first, then its source, else unavailable with a reason."""
    from .asset_tags import load as load_tags
    from .sources import registry
    records = library(config) if records is None else records
    tags = load_tags(config)['assets'] if tags is None else tags
    sources = {s['key']: s for s in registry(config)['sources']} if config.sources_registry else {}
    outside = {}
    for item in items:
        if item['asset_id'] not in records:
            outside.setdefault(item['snapshot'].get('source_key'), []).append(item['asset_id'])
    found, faults = {}, {}
    for key, identifiers in outside.items():
        if key not in sources:
            continue
        try:
            found.update(source_records(config, key, identifiers))
        except (OSError, ValueError) as exc:
            faults[key] = str(exc)
    result = []
    for item in items:
        identifier, snap = item['asset_id'], item['snapshot']
        entry = {'asset_id': identifier, 'label': item['label'], 'notes': item['notes'], 'added_at': item['added_at'],
                 'tags': tags.get(identifier, []), 'name': snap.get('name'), 'pack': snap.get('pack'),
                 'asset_type': snap.get('asset_type'), 'source_key': snap.get('source_key'),
                 'source_name': snap.get('source_name'), 'in_library': identifier in records}
        record = records.get(identifier) or found.get(identifier)
        if record:
            from .asset_structure import asset_type
            entry.update(name=record['display_name'], pack=record['pack_id'], asset_type=asset_type(record),
                         formats=sorted({f['format'] for f in record['files']}), processing=record.get('processing'))
        if identifier in records:
            entry['availability'] = 'available'
        elif record:
            source = sources.get(entry['source_key']) or {}
            entry.update(availability='source_only', reason=(
                'Its source is disabled, so library search skips it; it opens from its source.'
                if source.get('enabled') is False else
                'Not in the published library yet (awaiting processing or excluded by the last scan); it opens from its source.'))
        else:
            key = entry['source_key']
            entry.update(availability='unavailable', reason=(
                'Its asset source was removed from Assetarium.' if key not in sources and config.sources_registry else
                'Its source results are unreadable: ' + faults[key] if key in faults else
                'It is no longer in the library or its source.'))
        result.append(entry)
    return result


def terms(query):
    return re.findall(r'[^\W_]+', (query or '').casefold())


def haystack(entry, record=None):
    parts = [entry.get('name'), entry.get('pack'), entry.get('source_name'), entry.get('label'), entry.get('notes'),
             ' '.join(entry.get('tags') or [])]
    if record:
        description = record.get('description')
        if isinstance(description, dict):
            for value in description.values():
                parts.append(' '.join(map(str, value)) if isinstance(value, list) else str(value))
        parts.extend(f['path'] for f in record.get('files', []))
    return ' '.join(p for p in parts if p).casefold()


def found_in(words, value):
    return all(word in value for word in words)


def summaries(config, query='', containing=None):
    """Collections tab: newest first, matched by name/description or by what is inside."""
    from .asset_tags import load as load_tags
    value = load(config)
    words = terms(text(query, 200, 'Search'))
    records = library(config)
    tags = load_tags(config)['assets']
    result = []
    for collection in sorted(value['collections'], key=lambda c: c['updated_at'], reverse=True):
        summary = {'collection_id': collection['id'], 'name': collection['name'], 'description': collection['description'],
                   'created_at': collection['created_at'], 'updated_at': collection['updated_at'],
                   'asset_count': len(collection['items'])}
        if containing:
            summary['contains'] = any(item['asset_id'] == containing for item in collection['items'])
        if words:
            own = found_in(words, (collection['name'] + ' ' + collection['description']).casefold())
            hits = [entry for entry in resolve(config, collection['items'], records, tags)
                    if found_in(words, haystack(entry, records.get(entry['asset_id'])))]
            if not own and not hits:
                continue
            summary['match'] = {'collection': own, 'assets': len(hits), 'names': [h['name'] for h in hits[:3]]}
        summary['cover'] = resolve(config, collection['items'][:4], records, tags)
        result.append(summary)
    return {'status': 'ready', 'collections': result, 'total': len(value['collections']), 'revision': value.get('revision', 0)}


def detail(config, identifier, query=''):
    collection = find(load(config), identifier)
    records = library(config)
    items = resolve(config, collection['items'], records)
    words = terms(text(query, 200, 'Search'))
    if words:
        for entry in items:
            entry['text_match'] = found_in(words, haystack(entry, records.get(entry['asset_id'])))
    return {'status': 'ready', 'collection_id': identifier, 'name': collection['name'],
            'description': collection['description'], 'created_at': collection['created_at'],
            'updated_at': collection['updated_at'], 'created_by': collection.get('created_by', 'app'),
            'items': items, 'asset_count': len(items),
            'unavailable_count': sum(e['availability'] == 'unavailable' for e in items)}
