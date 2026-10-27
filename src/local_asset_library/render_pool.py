"""Parallel kept-open Blender processes for inspection renders (decision 0022).

Each slot runs one Blender at a time and gives every job a fresh factory session, so results
match one process per asset. A timeout or crash fails only that job; the slot starts a new
Blender for the next one, which is not a retry. Texture-repair workers patch the worker module
at import, so they keep one Blender per job inside the same slots.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

from .config import ConfigError
from .description_engines import EngineStop
from .publication import atomic_json, read_json

GIB = 1024**3
MAX_PROCESSES = 8
HEADROOM = 1 * GIB  # Never plan into the last free memory: paging makes every render slower.
SHARE = 0.7  # Automatic allowance: this share of the memory free when processing starts.
PROCESS_MEMORY = 1 * GIB  # One CPU render process: 0.8–0.9 GiB peak on low-poly packs (2026-10-26).
GPU_PROCESS_MEMORY = 3 * GIB  # One GPU render process before a speed test measured it (HIP: 2.5 GiB).
RECYCLE_AFTER = 50  # Jobs per Blender before a fresh one, bounding slow leaks.
HOST = "blender_batch_worker.py"
DONE = "LAL_JOB_DONE"

_active = None
_active_lock = threading.Lock()
_job = None


def bind_lifetime(process):
    """Kill this Blender when the processing run ends, however it ends, so a resumed run never meets an
    orphan still writing the same output. Windows uses a kill-on-close job object; Linux sets a
    parent-death signal at spawn (``child_setup``). A Blender also exits once its input closes."""
    global _job
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    if _job is None:
        class Basic(ctypes.Structure):
            _fields_ = [("user_time", ctypes.c_int64), ("job_time", ctypes.c_int64), ("flags", wintypes.DWORD),
                        ("min_set", ctypes.c_size_t), ("max_set", ctypes.c_size_t), ("processes", wintypes.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]

        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ("reads", "writes", "others", "read_bytes",
                                                            "write_bytes", "other_bytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", Counters), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        job = kernel.CreateJobObjectW(None, None)
        info = Extended()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not job or not kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            return  # Best effort: stdin closing still ends the Blender after its current job.
        _job = job
    kernel.AssignProcessToJobObject(wintypes.HANDLE(_job), wintypes.HANDLE(int(process._handle)))


def child_setup():
    # Linux ties the signal to the spawning thread; slots spawn from threads that outlive their jobs.
    if sys.platform.startswith("linux"):
        import ctypes
        import signal
        ctypes.CDLL(None).prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG


def available_memory():
    """Bytes of physical memory available now, or None when the platform does not say."""
    if os.name == "nt":
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                        ("available", ctypes.c_ulonglong), ("page_total", ctypes.c_ulonglong),
                        ("page_available", ctypes.c_ulonglong), ("virtual_total", ctypes.c_ulonglong),
                        ("virtual_available", ctypes.c_ulonglong), ("extended", ctypes.c_ulonglong)]
        status = Status(length=ctypes.sizeof(Status))
        return status.available if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def cores():
    return (os.process_cpu_count() if hasattr(os, "process_cpu_count") else None) or os.cpu_count() or 1


def settings_path(config):
    return config.storage_root("data") / "library/rendering.json"


class DeviceUnavailable(EngineStop):
    """The chosen render device cannot render now; assets stay pending (never an asset fault)."""


def validate(processes, memory_gib, device=None):
    if device is not None and (type(device) is not str or not device or len(device) > 300):
        raise ConfigError("Choose Automatic, CPU or a listed GPU as the render device in Settings → General")
    if processes is not None and (type(processes) is not int or not 1 <= processes <= MAX_PROCESSES):
        raise ConfigError(f"Choose Automatic or 1 to {MAX_PROCESSES} render processes in Settings → General")
    if memory_gib is not None and (type(memory_gib) is not int or not 1 <= memory_gib <= 4096):
        raise ConfigError("Choose Automatic or a whole number of GiB for render memory in Settings → General")
    return processes, memory_gib, device


def saved(config):
    """The owner's choices: ``device`` (None = fastest tested), ``processes`` caps parallel renders,
    ``memory_gib`` sets their memory allowance."""
    path = settings_path(config)
    value = read_json(path) if path.exists() else {}
    processes, memory, device = validate(value.get("processes"), value.get("memory_gib"), value.get("device"))
    return {"device": device, "processes": processes, "memory_gib": memory}


def save(config, processes, memory_gib, device=None):
    processes, memory_gib, device = validate(processes, memory_gib, device)
    atomic_json(settings_path(config), {"schema_version": 1, "device": device, "processes": processes,
                                        "memory_gib": memory_gib})
    return saved(config)


def chosen_device(limits, test):
    """(device key, device or None for the CPU, its speed-test result or None)."""
    wanted = limits["device"] or (test or {}).get("chosen") or "cpu"
    result = next((r for r in (test or {}).get("results", []) if r["key"] == wanted), None)
    if wanted == "cpu":
        return wanted, None, result
    device = result["device"] if result else next(
        (d for d in (test or {}).get("devices", []) if f"{d['backend']}:{d['id']}" == wanted), None)
    if device is None:
        backend, _, identifier = wanted.partition(":")
        device = {"backend": backend, "id": identifier, "name": identifier}
    return wanted, device, result


def plan(config, available=None, count=None, ignore_test=False):
    """Which device renders and how many Blender processes to start now, and why that many.

    The speed test's fastest count is the best one (before a test: one per 8 cores, at most 4).
    The owner's limits only lower the count or raise the memory allowance; neither may pass the
    best count or the memory free now, so a setting never makes rendering slower.
    """
    from . import render_devices
    limits = saved(config)
    count = count or cores()
    available = available_memory() if available is None else available
    test = None if ignore_test else render_devices.saved(config)
    device_key, device, result = chosen_device(limits, test)
    per = PROCESS_MEMORY if device is None else GPU_PROCESS_MEMORY
    if result and result.get("best"):
        best, best_reason = result["best"]["processes"], "fastest in the speed test"
        if result["best"].get("peak_process_bytes"):
            per = result["best"]["peak_process_bytes"] * render_devices.MARGIN
    elif device is None:
        best, best_reason = max(1, min(4, count // 8)), "automatic for this processor"
    else:
        best, best_reason = 1, "not speed-tested yet"
    processes, reason = best, best_reason
    if limits["processes"] and limits["processes"] < processes:
        processes, reason = limits["processes"], "your limit"
    allowance = None
    if available is not None:
        free = max(0, available - HEADROOM)
        allowance = min(limits["memory_gib"] * GIB, free) if limits["memory_gib"] else SHARE * available
        fits = max(1, int(allowance // per))
        if fits < processes:
            processes, reason = fits, ("your memory allowance" if limits["memory_gib"] and limits["memory_gib"] * GIB <= free
                                       else "memory free now")
    return {"processes": processes, "threads": max(1, count // processes), "reason": reason, "best": best,
            "best_reason": best_reason, "cores": count, "available_bytes": available,
            "allowance_bytes": None if allowance is None else int(allowance), "process_bytes": int(per),
            "limits": limits, "device_key": device_key, "device": device, "device_label": render_devices.label(device),
            "tested": test is not None}


class Slot:
    """One Blender at a time: kept open for worker jobs, one-shot for patched repair workers."""

    def __init__(self, pool, index):
        from .inspection import environment
        self.pool, self.index, self.process, self.jobs, self.lines = pool, index, None, 0, None
        # Built once, before any slot runs: creating the same folders from several threads races.
        self.env = environment(pool.config)
        temp = pool.config.output_path("scratch", f"blender-tmp/slot-{index}")
        temp.mkdir(parents=True, exist_ok=True)
        self.env.update({key: str(temp) for key in ("TEMP", "TMP", "TMPDIR") if key in self.env})

    def environment(self):
        return dict(self.env)

    def start(self, blender):
        from .inspection import blender_command
        host = Path(__file__).with_name(HOST)
        command = blender_command(blender, *self.pool.thread_args, "--python", str(host))
        self.process = subprocess.Popen(command, cwd=self.pool.config.project_root, env=self.environment(),
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                        preexec_fn=child_setup if os.name != "nt" else None)
        bind_lifetime(self.process)
        self.jobs, self.lines = 0, queue.Queue()
        threading.Thread(target=self.read, args=(self.process.stdout, self.lines), daemon=True).start()

    @staticmethod
    def read(stream, lines):
        for raw in iter(stream.readline, b""):
            lines.put(raw.decode("utf-8", errors="replace"))
        lines.put(None)

    def stop(self, kill=False):
        process, self.process = self.process, None
        if process is None:
            return
        try:
            if kill:
                process.kill()
            else:
                process.stdin.close()
            process.wait(timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait()

    def run(self, blender, worker, task, timeout):
        if Path(worker).name != "blender_worker.py":
            from .inspection import blender_command, run_process
            command = blender_command(blender, *self.pool.thread_args, "--python-exit-code", "5",
                                      "--python", str(worker), "--", str(task))
            return run_process(command, self.pool.config.project_root, self.environment(), timeout)
        if self.process is None or self.process.poll() is not None or self.jobs >= RECYCLE_AFTER:
            self.stop()
            self.start(blender)
        started, output = time.perf_counter(), []
        try:
            self.process.stdin.write((str(task) + "\n").encode("utf-8"))
            self.process.stdin.flush()
        except OSError:
            pass  # A Blender that died while idle reports itself below, through its closed output.
        deadline = time.monotonic() + timeout
        while True:
            try:
                line = self.lines.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                self.stop(kill=True)
                return {"returncode": None, "timed_out": True, "output": "".join(output),
                        "elapsed_seconds": round(time.perf_counter() - started, 3)}
            if line is None:
                process = self.process
                self.stop()
                return {"returncode": process.returncode if process else None, "timed_out": False,
                        "output": "".join(output) + "\nBlender exited during this job.\n",
                        "elapsed_seconds": round(time.perf_counter() - started, 3)}
            if line.strip() == DONE:
                self.jobs += 1
                return {"returncode": 0, "timed_out": False, "output": "".join(output),
                        "elapsed_seconds": round(time.perf_counter() - started, 3)}
            output.append(line)


class Pool:
    def __init__(self, config, processes, threads, device=None):
        self.config, self.processes, self.device = config, processes, device
        self.thread_args = ("--threads", str(threads)) if processes > 1 else ()
        self.free, self.busy, self.lock = queue.Queue(), 0, threading.Lock()
        self.slots = [Slot(self, index) for index in range(processes)]
        for slot in self.slots:
            self.free.put(slot)

    def run(self, blender, worker, task, timeout):
        slot = self.free.get()
        # Heavier assets than planned: wait for a running render instead of paging. One always runs.
        while self.busy and (available_memory() or HEADROOM) < HEADROOM:
            time.sleep(.5)
        with self.lock:
            self.busy += 1
        try:
            return slot.run(blender, worker, task, timeout)
        finally:
            with self.lock:
                self.busy -= 1
            self.free.put(slot)

    def close(self):
        for slot in self.slots:
            slot.stop()


@contextmanager
def opened(config, processes, threads, device=None):
    """Make a pool the active Blender runner for this process until the block ends."""
    global _active
    pool = Pool(config, processes, threads, device)
    with _active_lock:
        _active = pool
    try:
        yield pool
    finally:
        with _active_lock:
            _active = None
        pool.close()


def job_device(config):
    """The ``render_device`` for a new job: the active pool's GPU, or None for the CPU."""
    pool = _active
    if pool is not None and pool.config.project_root == config.project_root and pool.device:
        return {"type": "GPU", **pool.device}
    return None


def run(config, blender, worker, task, timeout):
    """Run one worker job in the active pool, or in its own Blender when none is open."""
    pool = _active
    if pool is not None and pool.config.project_root == config.project_root:
        return pool.run(blender, worker, task, timeout)
    from .inspection import blender_command, environment, run_process
    command = blender_command(blender, "--python-exit-code", "5", "--python", str(worker), "--", str(task))
    return run_process(command, config.project_root, environment(config), timeout)
