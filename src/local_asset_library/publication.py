"""A request pins one immutable catalog/index generation; outputs stay shared."""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
import json
import os
import re
import uuid
import time

from .config import ConfigError

_snapshot = ContextVar("asset_publication", default=None)
_hashes = ContextVar('asset_request_hashes', default=None)


def filesystem_path(path):
    """Use Windows' explicit long-path API without changing stored references."""
    value = os.fspath(path)
    if os.name != 'nt' or value.startswith('\\\\?\\'):
        return value
    value = os.path.abspath(value)
    return '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value


def snapshot_key(config):
    return (str(config.project_root), str(config.metadata_root or ""))


def generation(config):
    if config.catalog_generation:
        return config.catalog_generation
    pinned = _snapshot.get()
    if pinned and pinned[0] == snapshot_key(config):
        return pinned[1]
    path = config.output_path("data", "library/active.json")
    if not path.exists():
        return "legacy"
    value = read_json(path)
    selected = value.get("generation", "")
    if not re.fullmatch(r"v_[0-9a-f]{32}", selected):
        raise ConfigError("Invalid publication generation")
    return selected


@contextmanager
def snapshot(config):
    parent = _snapshot.get()
    if parent and parent[0] == snapshot_key(config):
        yield
        return
    token = _snapshot.set((snapshot_key(config), generation(config)))
    hashes_token = _hashes.set({})
    try:
        yield
    finally:
        _snapshot.reset(token)
        _hashes.reset(hashes_token)


def request_memo(key, compute):
    """Reuse a boundary check within one pinned request; later requests recheck."""
    cache = _hashes.get()
    if cache is None:
        return compute()
    key = ('memo', *key)
    if key not in cache:
        cache[key] = compute()
    return cache[key]


def verified_hash(path, fresh=False):
    """SHA-256 reused while the file's stat identity is unchanged (decision 0004).

    ``fresh=True`` (and ``hash_cache.require_fresh()``) re-reads the bytes, for
    explicit audits and removal checks.
    """
    import hashlib
    from . import hash_cache
    fresh = fresh or hash_cache.fresh_required()
    # One identity read per file per pinned request; the same PNG serves several checks.
    identity = (hash_cache.file_identity(path) if fresh else
                request_memo(('identity', str(path)), lambda: hash_cache.file_identity(path)))
    key = (str(path), *identity)
    cache = _hashes.get()
    if cache is not None and key in cache:
        return cache[key]
    if not fresh:
        known = hash_cache.lookup(path, identity)
        if known is not None:
            if cache is not None:
                cache[key] = known
            return known
    value = hashlib.sha256()
    with open(filesystem_path(path), 'rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            value.update(chunk)
    if hash_cache.file_identity(path) != identity:
        raise ConfigError('File changed while verifying bytes: ' + str(path))
    result=value.hexdigest()
    hash_cache.store(path, identity, result)
    if cache is not None:
        cache[key]=result
    return result


_endings = {}


def line_ending_hashes(path):
    """SHA-256 of a text file as stored, with LF and with CRLF line endings.

    Git checkouts (core.autocrlf, fresh clones) may swap endings without changing
    what Python, uv or the model read; recorded hashes are matched against these.
    """
    import hashlib
    from . import hash_cache
    key = (str(path), *hash_cache.file_identity(path))
    if key not in _endings:
        with open(filesystem_path(path), 'rb') as stream:
            data = stream.read()
        lf = data.replace(b'\r\n', b'\n')
        _endings[key] = tuple(dict.fromkeys(hashlib.sha256(d).hexdigest() for d in (data, lf, lf.replace(b'\n', b'\r\n'))))
    return _endings[key]


def pinned(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with snapshot(self.config):
            return method(self, *args, **kwargs)
    return call


def pinned_config(function):
    @wraps(function)
    def call(config,*args,**kwargs):
        with snapshot(config):
            return function(config,*args,**kwargs)
    return call


def atomic_json(path, value):
    from pathlib import Path
    Path(filesystem_path(path.parent)).mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + uuid.uuid4().hex + ".pending")
    with open(filesystem_path(temp), "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    deadline=time.monotonic()+2
    while True:
        try:
            os.replace(filesystem_path(temp),filesystem_path(path))
            break
        except PermissionError:
            if time.monotonic()>=deadline:
                raise
            time.sleep(.02)  # Bounded application publication sharing race, never an asset retry.


def read_json(path, limit=4 * 1024 * 1024):
    """Windows readers permit atomic manifest replacement while holding an old handle."""
    # Full-library preservation receipts contain several thousand vector hashes.
    # Four MiB covers the approved membership while retaining a strict bound;
    # per-file caches that grow with a source's file count pass their own bound.
    if os.name!='nt':
        with path.open('rb') as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ConfigError('Managed manifest exceeds its bounded size')
        return json.loads(data.decode('utf-8'))
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.CreateFileW(filesystem_path(path),0x80000000,7,None,3,0x80,None)
    if handle==ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(descriptor,'rb') as stream:
        data=stream.read(limit+1)
    if len(data)>limit:
        raise ConfigError('Managed manifest exceeds its bounded size')
    return json.loads(data.decode('utf-8'))


def read_only(path):
    """A read-only SQLite connection that survives an interrupted writer.

    A crash or kill mid-write leaves a hot rollback journal that only a writable connection may roll
    back; a read-only one fails with "attempt to write a readonly database" until then. That one case
    gets a short writable open, which is SQLite's own recovery (the unfinished transaction is undone,
    committed data stays), and then the read-only connection. A live writer holds its lock, so its
    journal is never hot and is never touched here.
    """
    import sqlite3
    from pathlib import Path
    uri = Path(path).as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        db.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return db
    except sqlite3.OperationalError as exc:
        db.close()
        if "readonly" not in str(exc) or not Path(str(path) + "-journal").exists():
            raise
    recovering = sqlite3.connect(path)
    try:
        recovering.execute("SELECT count(*) FROM sqlite_master").fetchone()  # Reading rolls the hot journal back.
    finally:
        recovering.close()
    return sqlite3.connect(uri, uri=True)
