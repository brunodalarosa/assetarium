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


def generation(config):
    if config.catalog_generation:
        return config.catalog_generation
    pinned = _snapshot.get()
    if pinned and pinned[0] == str(config.project_root):
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
    if parent and parent[0] == str(config.project_root):
        yield
        return
    token = _snapshot.set((str(config.project_root), generation(config)))
    hashes_token = _hashes.set({})
    try:
        yield
    finally:
        _snapshot.reset(token)
        _hashes.reset(hashes_token)


def verified_hash(path):
    """Share reads within one pinned request only; later requests verify bytes afresh."""
    import hashlib
    before = path.stat()
    key = (str(path), before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    cache = _hashes.get()
    if cache is not None and key in cache:
        return cache[key]
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            value.update(chunk)
    after = path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ctime_ns) != (after.st_size,after.st_mtime_ns,after.st_ctime_ns):
        raise ConfigError('File changed while verifying bytes: ' + str(path))
    result=value.hexdigest()
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
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + ".pending")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    deadline=time.monotonic()+2
    while True:
        try:
            os.replace(temp,path)
            break
        except PermissionError:
            if time.monotonic()>=deadline:
                raise
            time.sleep(.02)  # Bounded application publication sharing race, never an asset retry.


def read_json(path):
    """Windows readers permit atomic manifest replacement while holding an old handle."""
    if os.name!='nt':
        return json.loads(path.read_text(encoding='utf-8'))
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.CreateFileW(str(path),0x80000000,7,None,3,0x80,None)
    if handle==ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(descriptor,'rb') as stream:
        data=stream.read(1024*1024+1)
    if len(data)>1024*1024:
        raise ConfigError('Managed manifest exceeds its bounded size')
    return json.loads(data.decode('utf-8'))
