"""Tests never read or write the project's shared hash record; real-Blender runs are counted."""
from collections import Counter
import os
import subprocess

import pytest


@pytest.fixture(autouse=True, scope='session')
def isolated_hash_cache(tmp_path_factory):
    os.environ['LAL_HASH_CACHE'] = str(tmp_path_factory.mktemp('hash-cache') / 'file-hashes.sqlite')
    from local_asset_library import hash_cache
    hash_cache.reset()
    yield
    hash_cache.reset()


@pytest.fixture
def directory_link():
    """A Windows junction (no symlink privilege needed) or a POSIX symlink; skips with the reason."""
    def make(link, target):
        if os.name == 'nt':
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True)
            assert result.returncode == 0, result.stderr.decode(errors='replace')
            return
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f'Directory symlink unavailable: {exc}')
    return make


def pytest_terminal_summary(terminalreporter):
    # A skipped Blender fixture is unverified, not a pass: always say how many really ran.
    outcomes, executables = Counter(), set()
    for reports in terminalreporter.stats.values():
        for report in reports:
            blender = dict(getattr(report, 'user_properties', ())).get('real_blender')
            if blender and (report.when == 'call' or report.outcome != 'passed'):
                outcomes[report.outcome] += 1
                executables.add(blender)
    if outcomes:
        terminalreporter.write_line('Real-Blender tests: ' + ', '.join(f'{n} {k}' for k, n in sorted(outcomes.items()))
                                    + ' (' + ', '.join(sorted(executables)) + ')')
