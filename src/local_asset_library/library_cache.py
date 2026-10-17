"""Read-only per-publication views. Published generations are immutable, so a
view is reused only while its publication identity, catalog/membership file
stats and source revision are unchanged; any change rebuilds it.

Cached records are slim, shared and must be treated as read-only. Processing
and detail views read full records from the catalog instead.
"""
from collections import OrderedDict
import hashlib
import threading

from .publication import generation, snapshot_key

# Fields never read by list, search, coverage or source checks. Detail views
# load the full record, so nothing is hidden from the owner.
DROPPED = frozenset({'variants', 'grouping', 'dependency_inspection', 'provenance',
                     'texture_repair_history', 'license_evidence', 'effective_caption'})
TECHNICAL = ('inspected_path', 'inspected_sha256', 'inspected_format', 'evaluated_instance_totals', 'armatures')
_lock = threading.Lock()
_records = OrderedDict()
_digests = {}
_json = {}


def _stat(path):
    try:
        value = path.stat()
    except FileNotFoundError:
        return str(path), None, None, None
    return str(path), value.st_size, value.st_mtime_ns, value.st_ctime_ns


def publication_key(config):
    from .sources import revision
    return (snapshot_key(config), config.source_key, generation(config),
            _stat(config.output_path('data', 'catalog.sqlite')),
            _stat(config.output_path('data', 'library/membership.json')), revision(config))


def slim(record):
    value = {k: v for k, v in record.items() if k not in DROPPED}
    if isinstance(record.get('technical'), dict):
        value['technical'] = {k: record['technical'][k] for k in TECHNICAL if k in record['technical']}
    return value


def library_records(config):
    key = publication_key(config)
    with _lock:
        if key in _records:
            _records.move_to_end(key)
            return _records[key]
    from .membership import records
    value = [slim(record) for record in records(config)]
    with _lock:
        _records[key] = value
        while len(_records) > 4:
            _records.popitem(last=False)
    return value


def file_digest(path):
    """SHA-256 of an immutable publication file, recomputed when its stat changes."""
    key = _stat(path)
    with _lock:
        if key in _digests:
            return _digests[key]
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    if _stat(path) != key:
        from .config import ConfigError
        raise ConfigError('File changed while computing its digest: ' + str(path))
    result = value.hexdigest()
    with _lock:
        if len(_digests) > 64:
            _digests.clear()
        _digests[key] = result
    return result


def cached_json(path):
    """Parsed JSON reused until the file's stat changes; returns a shared value."""
    key = _stat(path)
    with _lock:
        if key in _json:
            return _json[key]
    from .publication import read_json
    value = read_json(path)  # Share-mode read: writers can still replace the file atomically.
    with _lock:
        if len(_json) > 16384:
            _json.clear()
        _json[key] = value
    return value


_memos = {}


def memo(name, key, build, size=4):
    """Small named LRU for immutable publication views (vectors, summaries)."""
    with _lock:
        table = _memos.setdefault(name, OrderedDict())
        if key in table:
            table.move_to_end(key)
            return table[key]
    value = build()
    with _lock:
        table[key] = value
        while len(table) > size:
            table.popitem(last=False)
    return value


def clear():
    with _lock:
        _memos.clear()
        _records.clear()
        _digests.clear()
        _json.clear()
