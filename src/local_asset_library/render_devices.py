"""Render devices and the speed test that picks device and parallel renders (decision 0022).

The test renders synthetic shapes (never library assets) with the real worker in kept-open
Blender processes, 1, 2, 4, 6 and 8 at a time per device, within the cores and memory free, and
keeps the fastest pair. A step that does not help by 10% or runs clearly slower ends that
device's test early. It runs again when Blender or the devices change, or when the owner asks.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import time

from .config import Config, ConfigError
from .publication import atomic_json, read_json

BACKENDS = ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI")
STEPS = (1, 2, 4, 6, 8)
GAIN = 1.10  # A step must be at least this much faster to keep going.
SLOWER = 1.5  # A step this much slower than expected is cut off before it can thrash the machine.
BEHIND = 3  # A device this much slower than one already tested cannot win; its test ends early.
MARGIN = 1.25  # Library assets can use more memory than the synthetic shapes.
LIST_DEVICES = """
import bpy, json
preferences = bpy.context.preferences.addons['cycles'].preferences
found = []
for backend in %r:
    try:
        preferences.compute_device_type = backend
    except TypeError:
        continue
    preferences.get_devices()
    found += [{'backend': backend, 'id': d.id, 'name': d.name} for d in preferences.devices if d.type == backend]
print('LAL_DEVICES=' + json.dumps(found), flush=True)
""" % (BACKENDS,)


def probe_path(config):
    return config.storage_root("data") / "library/render-test.json"


def key(device):
    return "cpu" if device is None else f"{device['backend']}:{device['id']}"


def label(device):
    return "CPU" if device is None else f"{device['name']} ({device['backend']})"


def blender_identity(config):
    blender = config.blender
    return {"blender": str(blender), "mtime": blender.stat().st_mtime_ns if blender and blender.exists() else None}


def detect(config):
    """GPUs Blender's Cycles can use, one entry per card (OptiX before CUDA for the same card)."""
    from .inspection import blender_command, environment, run_process
    process = run_process(blender_command(config.blender, "--python-expr", LIST_DEVICES), config.project_root,
                          environment(config), 120)
    line = next((l for l in process["output"].splitlines() if l.startswith("LAL_DEVICES=")), None)
    if process["timed_out"] or line is None:
        raise ConfigError("Blender did not list its render devices; see the processing log")
    devices, names = [], set()
    for device in json.loads(line.removeprefix("LAL_DEVICES=")):
        if device["name"] not in names:
            names.add(device["name"])
            devices.append(device)
    return devices


def saved(config):
    """The last speed test when it was made with the current Blender, else None (never runs Blender)."""
    path = probe_path(config)
    if not path.exists():
        return None
    try:
        value = read_json(path)
    except (OSError, ValueError):
        return None
    return value if value.get("schema_version") == 1 and value.get("blender") == blender_identity(config) else None


def shapes(folder):
    """Four small OBJ models of typical low-poly asset size, written outside the project."""
    def write(name, vertices, faces):
        lines = [f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in vertices]
        lines += ["f " + " ".join(str(i + 1) for i in face) for face in faces]
        (folder / f"{name}.obj").write_text("\n".join(lines) + "\n")

    def grid(u, v, point):
        vertices = [point(i / u, j / v) for j in range(v + 1) for i in range(u + 1)]
        faces = [(j * (u + 1) + i, j * (u + 1) + i + 1, (j + 1) * (u + 1) + i + 1, (j + 1) * (u + 1) + i)
                 for j in range(v) for i in range(u)]
        return vertices, faces
    tau = 2 * math.pi
    write("sphere", *grid(48, 24, lambda a, b: (math.sin(b * math.pi) * math.cos(a * tau),
                                                 math.sin(b * math.pi) * math.sin(a * tau), math.cos(b * math.pi))))
    write("torus", *grid(48, 24, lambda a, b: ((1 + .35 * math.cos(b * tau)) * math.cos(a * tau),
                                                (1 + .35 * math.cos(b * tau)) * math.sin(a * tau), .35 * math.sin(b * tau))))
    write("vase", *grid(32, 16, lambda a, b: ((.4 + .3 * math.sin(b * 5)) * math.cos(a * tau),
                                               (.4 + .3 * math.sin(b * 5)) * math.sin(a * tau), b * 2)))
    vertices, faces = [], []
    for n in range(27):
        x, y, h = n % 3 * 1.5, n // 3 % 3 * 1.5, .5 + n % 5 * .4
        base = len(vertices)
        vertices += [(x + dx, y + dy, dz * h) for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)]
        faces += [tuple(base + i for i in face) for face in
                  ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))]
    write("blocks", vertices, faces)
    return sorted(folder.glob("*.obj"))


def peak_memory(process):
    """Peak private bytes of a running child process, or None."""
    import os
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in ("peak_working", "working", "peak_paged_pool", "paged_pool",
                                                          "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile", "private")]
            counters = Counters(cb=ctypes.sizeof(Counters))
            ok = ctypes.WinDLL("psapi").GetProcessMemoryInfo(wintypes.HANDLE(int(process._handle)),
                                                             ctypes.byref(counters), counters.cb)
            return counters.peak_pagefile if ok else None
        for line in Path(f"/proc/{process.pid}/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, AttributeError):
        pass
    return None


def measure(probe, worker, models, device, processes, threads, limit=None):
    """Seconds per asset with ``processes`` kept-open Blenders after one untimed render each."""
    from . import render_pool
    count, started = [0], [None]

    def job():
        count[0] += 1
        model = models[count[0] % len(models)]
        output = probe.output_path("data", f"{key(device).replace(':', '-')}-{processes}/{count[0]}")
        output.mkdir(parents=True, exist_ok=True)
        task = output / "job.json"
        task.write_text(json.dumps({"schema_version": 1, "asset_id": "render-test", "project_root": str(probe.project_root),
            "source_root": str(probe.source_root), "source_path": model.name, "format": "obj",
            "source_sha256": hashlib.sha256(model.read_bytes()).hexdigest(), "output": str(output), "resolution": 640,
            "render_device": None if device is None else {"type": "GPU", **device}}), encoding="utf-8")
        return task, output

    def run(pool, timeout):
        task, output = job()
        remaining = timeout if started[0] is None else max(10, timeout - (time.monotonic() - started[0]))
        process = pool.run(probe.blender, worker, task, remaining)
        result = output / "result.json"
        if process["timed_out"]:
            return "slower"
        if not result.exists():
            return "Blender stopped: " + process["output"][-300:]
        value = json.loads(result.read_text(encoding="utf-8"))
        return "complete" if value["status"] == "complete" else "; ".join(value.get("errors") or [value["status"]])

    jobs = max(4, 2 * processes)
    with render_pool.opened(probe, processes, threads) as pool, ThreadPoolExecutor(processes) as executor:
        warm = list(executor.map(lambda _: run(pool, 120 if limit else 300), range(processes)))
        if any(outcome != "complete" for outcome in warm):
            return {"processes": processes, "error": next(o for o in warm if o != "complete")}
        started[0] = time.monotonic()
        outcomes = list(executor.map(lambda _: run(pool, limit or 600), range(jobs)))
        elapsed = time.monotonic() - started[0]
        peaks = [peak_memory(slot.process) for slot in pool.slots if slot.process is not None]
    if any(outcome != "complete" for outcome in outcomes):
        failed = next(o for o in outcomes if o != "complete")
        return {"processes": processes, "error": failed, "slower": failed == "slower"}
    peak = max([p for p in peaks if p] or [0]) or None
    return {"processes": processes, "seconds_per_asset": round(elapsed / jobs, 3), "peak_process_bytes": peak}


def test_device(probe, worker, models, device, plan, progress=None, cancelled=None, rival=None):
    """Steps for one device until one stops helping; the fastest step is ``best``.

    ``rival`` is the best seconds per asset of a device tested before; far behind it ends the test.
    """
    from . import render_pool
    steps, best, stopped = [], None, None
    for processes in STEPS:
        if cancelled and cancelled():
            stopped = "cancelled"
            break
        if processes > max(1, plan["cores"] // 2):
            stopped = "processor cores"
            break
        per = (best or {}).get("peak_process_bytes") or render_pool.PROCESS_MEMORY
        if plan["allowance_bytes"] is not None and processes > 1 and processes * per * MARGIN > plan["allowance_bytes"]:
            stopped = "memory"
            break
        if progress:
            progress(f"Testing render speed: {label(device)}, {processes} at a time")
        jobs = max(4, 2 * processes)
        limit = best["seconds_per_asset"] * jobs * SLOWER if best else rival and rival * jobs * BEHIND
        step = measure(probe, worker, models, device, processes, max(1, plan["cores"] // processes), limit)
        steps.append(step)
        if "error" in step:
            stopped = (("slower" if best else "much slower than another device") if step.get("slower")
                       else ("failed: " + step["error"] if best is None else "failed"))
            break
        if best and step["seconds_per_asset"] * GAIN > best["seconds_per_asset"]:
            stopped = "no gain" if step["seconds_per_asset"] <= best["seconds_per_asset"] else "slower"
            if step["seconds_per_asset"] < best["seconds_per_asset"]:
                best = step
            break
        best = step
    return {"device": device, "key": key(device), "label": label(device), "steps": steps, "best": best,
            "stopped": stopped or "tested every step"}


def run(config, progress=None, cancelled=None):
    """Test CPU and every GPU; save and return the result. Original assets are never read."""
    from . import render_pool
    from .gpu_queue import lease
    started = time.monotonic()
    devices = detect(config)
    plan = render_pool.plan(config, ignore_test=True)
    folder = config.output_path("scratch", "render-test")
    shutil.rmtree(folder, ignore_errors=True)  # Disposable outputs of the previous test only.
    source = tempfile.mkdtemp(prefix="assetarium-render-test-")  # The worker refuses sources inside the project.
    try:
        probe = Config(folder, Path(source), config.blender)
        worker = config.project_root / "src/local_asset_library/blender_worker.py"
        models = shapes(probe.source_root)
        results = [test_device(probe, worker, models, None, plan, progress, cancelled)]
        if devices and not (cancelled and cancelled()):
            with lease(config, "batch-render-test", timeout=30):
                for device in devices:
                    rival = min((r["best"]["seconds_per_asset"] for r in results if r["best"]), default=None)
                    results.append(test_device(probe, worker, models, device, plan, progress, cancelled, rival))
    finally:
        shutil.rmtree(source, ignore_errors=True)
        shutil.rmtree(folder, ignore_errors=True)
    ranked = [r for r in results if r["best"]]
    chosen = min(ranked, key=lambda r: r["best"]["seconds_per_asset"]) if ranked else None
    value = {"schema_version": 1, "blender": blender_identity(config), "devices": devices, "cores": plan["cores"],
             "results": results, "chosen": chosen and chosen["key"], "cancelled": bool(cancelled and cancelled()),
             "elapsed_seconds": round(time.monotonic() - started, 1), "utc": datetime.now(timezone.utc).isoformat()}
    if not value["cancelled"]:
        atomic_json(probe_path(config), value)
    return value


def summary(config):
    """Settings → General → Rendering: the owner's choices, what runs now and why, the last speed test."""
    from . import render_pool
    from .source_operations import operation_status
    plan = render_pool.plan(config)
    test = saved(config)
    gib = lambda value: None if value is None else round(value / render_pool.GIB, 1)
    operation = operation_status(config)
    return {"status": "ready", **render_pool.saved(config), "blender": bool(config.blender and config.blender.exists()),
            "plan": {"device": plan["device_label"], "device_key": plan["device_key"], "processes": plan["processes"],
                     "reason": plan["reason"], "best": plan["best"], "best_reason": plan["best_reason"],
                     "allowance_gib": gib(plan["allowance_bytes"]), "available_gib": gib(plan["available_bytes"]),
                     "process_gib": gib(plan["process_bytes"]), "max_processes": render_pool.MAX_PROCESSES},
            "test": test and {"utc": test["utc"], "elapsed_seconds": test["elapsed_seconds"], "chosen": test["chosen"],
                              "results": [{"key": r["key"], "label": r["label"], "stopped": r["stopped"],
                                           "best": r["best"] and {k: r["best"][k] for k in ("processes", "seconds_per_asset")}}
                                          for r in test["results"]]},
            "devices": [{"key": "cpu", "label": "CPU"}] + [{"key": key(d), "label": label(d)} for d in (test or {}).get("devices", [])],
            "operation": operation if operation.get("operation") == "render-test" else None}


def ensure(config, progress=None, cancelled=None):
    """The saved test, run again first when Blender or its devices changed. Needs a configured Blender."""
    if not config.blender or not config.blender.exists():
        return None
    current = saved(config)
    if current is not None and current.get("devices") == detect(config):
        return current
    if progress:
        progress("Testing render speed on this computer")
    result = run(config, progress, cancelled)
    return None if result["cancelled"] else result
