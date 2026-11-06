"""What a parser read from a file's bytes, saved by content hash so an unchanged file is not read again (decision 0027).

A result is keyed by the file's SHA-256 and by the parsers' own source code, so editing a parser starts new keys
instead of answering from old ones. Only answers the bytes alone decide are saved; a read failure is never saved,
and matching references to the files that exist still runs on every scan. Losing the store only costs time.
"""
from contextlib import closing, contextmanager
from contextvars import ContextVar
import hashlib
import inspect
import json
import sqlite3

_session = ContextVar('parse_cache_session', default=None)


def parser_key():
    from . import catalog, image_kinds
    parts = [inspect.getsource(f) for f in (catalog.read_text, catalog.parsed_references, image_kinds.fbx_names)]
    parts += [image_kinds.FBX_NAMES.pattern.decode('ascii'), str(image_kinds.FBX_LIMIT)]
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()[:16]


class Session:
    def __init__(self, path):
        self.path, self.key, self.new, self.misses = path, parser_key(), {}, 0
        self.known = {}
        if path.is_file():
            try:
                with closing(sqlite3.connect(path, timeout=30)) as db:
                    self.known = {(k, s): v for k, s, v in db.execute('SELECT kind, sha256, value FROM parsed WHERE parser=?', (self.key,))}
            except sqlite3.Error:
                self.known = {}  # A damaged cache is only slower: everything is parsed again and saved afresh.

    def remember(self, kind, sha256, compute):
        found = self.known.get((kind, sha256)) if sha256 else None
        if found is not None:
            return json.loads(found)
        self.misses += 1
        value, cacheable = compute()
        if cacheable and sha256:
            self.known[(kind, sha256)] = self.new[(kind, sha256)] = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        return value

    def save(self):
        if not self.new:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=30)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS parsed(parser TEXT, kind TEXT, sha256 TEXT, value TEXT, PRIMARY KEY(parser, kind, sha256))')
            db.execute('DELETE FROM parsed WHERE parser<>?', (self.key,))  # Answers of an edited parser are never read again.
            db.executemany('INSERT OR IGNORE INTO parsed VALUES (?,?,?,?)', [(self.key, k, s, v) for (k, s), v in self.new.items()])
        self.new = {}


@contextmanager
def session(config):
    """Parse results of one scan come from, and go to, the library store's cache."""
    if _session.get() is not None:
        yield _session.get()
        return
    current = Session(config.library_store() / 'parse-cache.sqlite')
    token = _session.set(current)
    try:
        yield current
        current.save()
    finally:
        _session.reset(token)


def remember(kind, sha256, compute):
    """``compute() -> (value, cacheable)``; outside a scan session it simply runs."""
    current = _session.get()
    return current.remember(kind, sha256, compute) if current else compute()[0]
