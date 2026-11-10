"""Portable OS shims: process liveness and sleep prevention behave the same way on every platform."""
import os
import subprocess
import sys
import time


from local_asset_library.gpu_queue import process_alive


def test_finished_child_is_not_alive_and_keeps_its_exit_code():
    child = subprocess.Popen([sys.executable, '-c', 'raise SystemExit(3)'])
    deadline = time.monotonic() + 30
    while process_alive(child.pid) and time.monotonic() < deadline:
        time.sleep(.05)
    # An exited, unreaped child (a Linux zombie) still answers kill(0); it must not look alive.
    assert not process_alive(child.pid)
    assert child.wait(timeout=10) == 3  # Not reaped by the check: its owner still sees the failure.
    assert process_alive(os.getpid()) and not process_alive(0) and not process_alive('1')
