"""Shared stat-identity hash record (decision 0004).

A file is re-hashed only when its size, modification time, creation/change time
or file ID changes; otherwise the hash recorded for that exact identity is
reused. Every LAL process shares one SQLite record under ``cache/``. The record
is an accelerator, never evidence: any read/write problem degrades to hashing
the bytes again, and nothing here can turn a changed or missing file into a
success.
"""
import os
from pathlib import Path
import sqlite3
import threading

_lock = threading.Lock()
_memory = {}
_state = {'db': None, 'loaded': False, 'disabled': False, 'fresh': False}


def identity(stat):
    """Portable fallback: size, modification, creation/change time and file ID."""
    return (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)


def file_identity(path):
    """Identity used for reuse. On Windows the third field is NTFS ChangeTime.

    Python's ``st_ctime`` is the creation time on Windows. ChangeTime is updated
    by every content or metadata write and, unlike the modification time, is
    not reset by ordinary timestamp-restoring tools (``os.utime``/SetFileTime).
    """
    if os.name != 'nt':
        return identity(os.stat(path))
    kernel = _kernel()
    from .publication import filesystem_path
    handle = kernel.CreateFileW(filesystem_path(path), 0x80, 7, None, 3, 0x02000000, None)
    if handle == _INVALID:
        import ctypes
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        import ctypes
        info, basic = _ByHandle(), _Basic()
        if (not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)) or
                not kernel.GetFileInformationByHandleEx(handle, 0, ctypes.byref(basic), ctypes.sizeof(basic))):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)
    # FILETIME (100 ns since 1601) to Unix nanoseconds, matching os.stat values.
    to_ns = lambda value: (value - 116444736000000000) * 100
    return ((info.nFileSizeHigh << 32) | info.nFileSizeLow, to_ns(basic.LastWriteTime),
            to_ns(basic.ChangeTime), (info.nFileIndexHigh << 32) | info.nFileIndexLow)


_INVALID = -1 & (2 ** 64 - 1)
_api = {}


def _kernel():
    if 'kernel' not in _api:
        import ctypes
        from ctypes import wintypes
        global _ByHandle, _Basic
        class _ByHandle(ctypes.Structure):
            _fields_ = [('dwFileAttributes', wintypes.DWORD), ('ftCreationTime', wintypes.FILETIME),
                        ('ftLastAccessTime', wintypes.FILETIME), ('ftLastWriteTime', wintypes.FILETIME),
                        ('dwVolumeSerialNumber', wintypes.DWORD), ('nFileSizeHigh', wintypes.DWORD),
                        ('nFileSizeLow', wintypes.DWORD), ('nNumberOfLinks', wintypes.DWORD),
                        ('nFileIndexHigh', wintypes.DWORD), ('nFileIndexLow', wintypes.DWORD)]
        class _Basic(ctypes.Structure):
            _fields_ = [('CreationTime', ctypes.c_longlong), ('LastAccessTime', ctypes.c_longlong),
                        ('LastWriteTime', ctypes.c_longlong), ('ChangeTime', ctypes.c_longlong),
                        ('FileAttributes', wintypes.DWORD)]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.GetFileInformationByHandle.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        _api['kernel'] = kernel
    return _api['kernel']


def location():
    configured = os.environ.get('LAL_HASH_CACHE')
    if configured == 'off':
        return None
    return Path(configured) if configured else Path(__file__).resolve().parents[2] / 'cache/file-hashes.sqlite'


def require_fresh(value=True):
    """Explicit byte audits (verification scripts) bypass reuse for this process."""
    _state['fresh'] = value


def fresh_required():
    return _state['fresh']


def _database():
    if _state['disabled']:
        return None
    if _state['db'] is None:
        path = location()
        if path is None:
            _state['disabled'] = True
            return None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(path, timeout=2, check_same_thread=False, isolation_level=None)
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA synchronous=OFF')
            db.execute('CREATE TABLE IF NOT EXISTS hashes (path TEXT PRIMARY KEY, size INTEGER NOT NULL, '
                       'mtime_ns INTEGER NOT NULL, ctime_ns INTEGER NOT NULL, ino INTEGER NOT NULL, sha256 TEXT NOT NULL)')
            _state['db'] = db
        except (OSError, sqlite3.Error):
            _state['disabled'] = True
            return None
    return _state['db']


def lookup(path, ident):
    key = str(path)
    with _lock:
        cached = _memory.get(key)
        if cached and cached[0] == ident:
            return cached[1]
        db = _database()
        if db is None:
            return None
        try:
            if not _state['loaded']:
                # One bulk read; other processes' later entries are found per miss below.
                _memory.update((r[0], (tuple(r[1:5]), r[5])) for r in db.execute('SELECT * FROM hashes'))
                _state['loaded'] = True
                cached = _memory.get(key)
                if cached and cached[0] == ident:
                    return cached[1]
            row = db.execute('SELECT size,mtime_ns,ctime_ns,ino,sha256 FROM hashes WHERE path=?', (key,)).fetchone()
        except sqlite3.Error:
            _state['disabled'] = True
            return None
        if row and tuple(row[:4]) == ident:
            _memory[key] = (ident, row[4])
            return row[4]
    return None


def store(path, ident, sha256):
    key = str(path)
    with _lock:
        if _memory.get(key) == (tuple(ident), sha256):
            return
        _memory[key] = (tuple(ident), sha256)
        db = _database()
        if db is None:
            return
        try:
            db.execute('INSERT OR REPLACE INTO hashes VALUES (?,?,?,?,?,?)', (key, *ident, sha256))
        except sqlite3.Error:
            pass  # A busy or unwritable record only means hashing again later.


def reset():
    """Test helper: forget in-process state (the shared record is untouched)."""
    with _lock:
        _memory.clear()
        if _state['db'] is not None:
            _state['db'].close()
        _state.update(db=None, loaded=False, disabled=False, fresh=False)
