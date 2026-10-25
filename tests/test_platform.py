"""Portable OS shims: process liveness and sleep prevention behave the same way on every platform."""
import os
import subprocess
import sys
import time

import pytest

from local_asset_library import overnight
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


@pytest.mark.skipif(os.name == 'nt', reason='Windows uses SetThreadExecutionState instead of systemd-inhibit')
def test_sleep_prevention_says_so_when_unavailable(tmp_path, monkeypatch, capsys):
    import shutil
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    with overnight.keep_awake():
        pass
    assert 'sleep is not prevented' in capsys.readouterr().out
    failing = tmp_path / 'systemd-inhibit'
    failing.write_text('#!/bin/sh\necho "Access denied" >&2\nexit 1\n')
    failing.chmod(0o755)
    monkeypatch.setattr(shutil, 'which', lambda name: str(failing))
    with overnight.keep_awake():
        pass
    assert 'could not prevent sleep (Access denied)' in capsys.readouterr().out
