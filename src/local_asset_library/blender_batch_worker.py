"""Kept-open Blender host for inspection jobs (decision 0022).

Each stdin line names one job file. The unchanged ``blender_worker`` runs it in a fresh empty
factory session, so results match a new Blender process per asset while startup is paid once.
This host is not part of inspection fingerprints: it only resets state and calls the worker.
"""
import ctypes
import os
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy  # noqa: E402
import blender_worker as worker  # noqa: E402

DONE = "LAL_JOB_DONE"


def flush_native():
    # Blender's own C output is buffered separately; flush it so each job's log stays its own.
    try:
        (ctypes.cdll.ucrtbase if os.name == "nt" else ctypes.CDLL(None)).fflush(None)
    except (OSError, AttributeError):
        pass


for line in sys.stdin:
    job = line.strip()
    if not job:
        continue
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        worker.SOURCE_PREFIX = ""
        sys.argv = [sys.argv[0], "--", job]
        worker.main()
    except Exception:
        traceback.print_exc()  # No result file: the parent records this asset's fault from the log.
    sys.stdout.flush()
    flush_native()
    print(DONE, flush=True)
