"""What a parser read from a file's bytes, saved by content hash so an unchanged file is not read again (decision 0027).

A result is keyed by the file's SHA-256, the parser (``kind``, which names the file format) and the parsers' own
source code, so editing a parser starts new keys instead of answering from old ones. Only answers the bytes alone
decide are saved; a read failure is never saved, and an answer is kept only if its file still has the size and time
it was hashed with when the session ends (a scan also verifies its files first). Matching references to the files
that exist still runs on every scan. Losing or damaging the store only costs time: a scan never fails over it.
"""
from contextlib import closing, contextmanager
from contextvars import ContextVar
import hashlib
import inspect
import json
import logging
import sqlite3

_session = ContextVar('parse_cache_session', default=None)


def parser_key():
    from . import catalog, image_kinds
    parts = [inspect.getsource(f) for f in (catalog.read_text, catalog.parsed_references, image_kinds.fbx_names)]
    parts += [image_kinds.FBX_NAMES.pattern.decode('ascii'), str(image_kinds.FBX_LIMIT)]
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()[:16]


def unchanged(config, path, size, mtime_ns):
    """A check that the file still has the size and modification time its hash was taken with."""
    def check():
        try:
            info = config.source_file(path).stat()
        except (OSError, ValueError):
            return False
        return size is not None and (info.st_size, info.st_mtime_ns) == (size, mtime_ns)
    return check


class Session:
    def __init__(self, path):
        self.path, self.key, self.new, self.misses = path, parser_key(), {}, 0
        self.known = {}
        if path.is_file():
            try:
                with closing(sqlite3.connect(path, timeout=30)) as db:
                    self.known = {(k, s): v for k, s, v in db.execute('SELECT kind, sha256, value FROM parsed WHERE parser=?', (self.key,))}
            except sqlite3.Error:
                self.known = {}  # A damaged cache is only slower: everything is parsed again.

    def remember(self, kind, sha256, compute, still=None):
        """``still()`` says the file's bytes are still the hashed ones; without it nothing is saved."""
        found = self.known.get((kind, sha256)) if sha256 else None
        if found is not None:
            return json.loads(found)
        self.misses += 1
        value, cacheable = compute()
        if cacheable and sha256 and still:
            self.known[(kind, sha256)] = text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
            self.new[(kind, sha256)] = (text, still)
        return value

    def save(self):
        rows = [(self.key, k, s, text) for (k, s), (text, still) in self.new.items() if still()]
        self.new = {}
        if not rows:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=30)) as db, db:
                db.execute('CREATE TABLE IF NOT EXISTS parsed(parser TEXT, kind TEXT, sha256 TEXT, value TEXT, PRIMARY KEY(parser, kind, sha256))')
                db.execute('DELETE FROM parsed WHERE parser<>?', (self.key,))  # Answers of an edited parser are never read again.
                db.executemany('INSERT OR IGNORE INTO parsed VALUES (?,?,?,?)', rows)
        except (sqlite3.Error, OSError) as exc:
            logging.getLogger(__name__).warning('Parse cache not saved; the next scan parses these files again · reason=%s path=%s',
                                                exc, self.path)


@contextmanager
def session(config):
    """Parse results of one scan come from the library store's cache; new ones are saved if the block succeeds."""
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


def remember(kind, sha256, compute, still=None):
    """``compute() -> (value, cacheable)``; outside a scan session it simply runs."""
    current = _session.get()
    return current.remember(kind, sha256, compute, still) if current else compute()[0]
