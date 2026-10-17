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
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            value.update(chunk)
    if hash_cache.file_identity(path) != identity:
        raise ConfigError('File changed while verifying bytes: ' + str(path))
    result=value.hexdigest()
    hash_cache.store(path, identity, result)
    if cache is not None:
        cache[key]=result
    return result


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


def read_json(path):
    """Windows readers permit atomic manifest replacement while holding an old handle."""
    # Full-library preservation receipts contain several thousand vector hashes.
    # Four MiB covers the approved membership while retaining a strict bound.
    limit = 4 * 1024 * 1024
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
