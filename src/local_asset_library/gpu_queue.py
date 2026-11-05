"""Cross-process inference lease; OS releases it after crashes, without PID killing."""
from contextlib import contextmanager
import json
import os
import time
import uuid

from .config import ConfigError
from .publication import atomic_json,read_json


def process_alive(pid):
    if type(pid) is not int or pid<=0:
        return False
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:return False
        code=wintypes.DWORD()
        try:return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
        finally:kernel.CloseHandle(handle)
    try:
        os.kill(pid,0)
    except OSError:return False
    # Linux: an exited child its parent has not reaped still answers kill(0). Read its
    # state instead of reaping it, which would hide the exit code from its Popen owner.
    try:
        with open(f'/proc/{pid}/stat','rb') as stream:
            return stream.read().rsplit(b')',1)[1].split()[0]!=b'Z'
    except (OSError,IndexError):return True


def batch_requested(config):
    path=config.output_path('data','library/gpu-batch-request.json')
    if not path.exists():return False
    try:
        value=read_json(path)
        return process_alive(value.get('pid'))
    except (OSError,ValueError):return False


def peer_requested(config):
    path=config.output_path('data','library/gpu-search-request.json')
    if not path.exists():return False
    try:
        value=read_json(path)
        return value.get('pid')!=os.getpid() and process_alive(value.get('pid'))
    except (OSError,ValueError):return False


@contextmanager
def lease(config, owner, timeout=15, resource='gpu'):
    if resource not in {'gpu', 'operations', 'sources', 'notifications', 'collections', 'setup', 'setup_agent', 'queue'}:
        raise ConfigError('Unknown lease resource')
    path = config.output_path("data", "library/" + resource + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    stream.seek(0, 2)
    if stream.tell() == 0:
        stream.write(b"0")
        stream.flush()
    started = time.monotonic()
    acquired = False
    marker=config.output_path('data','library/gpu-batch-request.json')
    token=uuid.uuid4().hex if resource=='gpu' and owner.startswith('batch-') else None
    waiter=config.output_path('data','library/gpu-search-request.json')
    wait_token=uuid.uuid4().hex if resource=='gpu' and owner.startswith('search-') else None
    if token:
        atomic_json(marker,{'token':token,'owner':owner,'pid':os.getpid()})
    try:
        while not acquired:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if wait_token:
                    atomic_json(waiter,{'token':wait_token,'owner':owner,'pid':os.getpid()})
                if time.monotonic() - started >= timeout:
                    raise ConfigError("Inference queue busy; bounded wait expired. Browse/keyword search remain available.")
                time.sleep(0.1)
        if wait_token and waiter.exists():
            try:
                if read_json(waiter).get('token')==wait_token:
                    waiter.unlink()
            except (OSError,ValueError):pass
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()
        if wait_token and waiter.exists():
            try:
                if read_json(waiter).get('token')==wait_token:
                    waiter.unlink()
            except (OSError,ValueError):pass
        if token and marker.exists():
            try:
                if read_json(marker).get('token')==token:
                    marker.unlink()
            except (OSError,ValueError):
                pass  # PID liveness makes a retained stale marker harmless.
