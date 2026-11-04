"""Session logs: one file per session, joined by child processes, leveled, repeats collapsed, bounded retention."""
import io
import logging
import os
import re
import subprocess
import sys
import threading

import pytest

from local_asset_library import logs, owner_commands

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINE = re.compile(r'^\d\d:\d\d:\d\d\.\d{3} (DEBUG|INFO|WARNING|ERROR)\s+[\w-]+\[\d+\] [\w.]+: ')


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    """A clean logs folder, no inherited session: each test starts its own."""
    monkeypatch.setattr(logs, 'folder', lambda root: tmp_path / 'logs')
    monkeypatch.delenv(logs.ENV, raising=False)
    logs.stop()
    return tmp_path / 'logs'


def text(path):
    return path.read_text(encoding='utf-8')


def test_a_session_is_one_named_file_with_levels_and_an_end(fresh):
    path = logs.start(ROOT, 'app', 'info')
    assert re.fullmatch(r'\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d_app\.log', path.name) and os.environ[logs.ENV] == str(path)
    log = logging.getLogger('local_asset_library.sources')
    log.debug('hidden at info')
    log.info('Scan finished · %s', logs.kv(folder='KayKit', files=1009, empty=''))
    logs.stop()
    lines = text(path).splitlines()
    assert all(LINE.match(line) for line in lines)
    assert 'Session started · kind=app' in lines[0] and lines[-1].endswith('session: Session ended')
    assert any(line.endswith('sources: Scan finished · folder=KayKit files=1009') for line in lines)
    assert 'hidden at info' not in text(path)


def test_repeats_collapse_into_one_line_before_the_session_ends(fresh):
    path = logs.start(ROOT, 'app', 'debug')
    for ms in range(40):
        logging.getLogger('local_asset_library.desktop').debug('sources · ms=%d', ms, extra={'repeat_key': 'poll'})
    logs.stop()
    lines = text(path).splitlines()
    assert sum('sources · ms=' in line for line in lines) == 2
    assert re.search(r'sources · ms=39 · ↻ repeated 39 more times, last at \d\d:\d\d:\d\d\.\d{3}$', lines[-2])
    assert lines[-1].endswith('Session ended') and [l[:12] for l in lines] == sorted(l[:12] for l in lines)  # Summaries are stamped when written.


def test_child_processes_join_the_session_without_torn_lines(fresh):
    path = logs.start(ROOT, 'app', 'info')
    child = ("import logging, sys; sys.path.insert(0, sys.argv[1]); from local_asset_library import logs; "
             "logs.start(sys.argv[2], 'operation', process='scan'); "
             "[logging.getLogger('local_asset_library.sources').info('line %d · ' + 'x' * 300, i) for i in range(150)]")
    children = [subprocess.Popen([sys.executable, '-c', child, os.path.join(ROOT, 'src'), ROOT]) for _ in range(4)]
    assert [c.wait(timeout=60) for c in children] == [0, 0, 0, 0]
    logs.stop()
    lines = text(path).splitlines()
    assert all(LINE.match(line) for line in lines)
    assert sum(' scan[' in line and 'sources: line' in line for line in lines) == 600
    assert sum('Joined the session · process=scan' in line for line in lines) == 4 and len(logs.sessions(fresh)) == 1


def test_a_mistyped_level_falls_back_to_info_and_says_so(fresh, monkeypatch):
    monkeypatch.setenv(logs.LEVEL_ENV, 'loud')
    path = logs.start(ROOT, 'cli')
    logs.stop()
    assert 'Log level must be one of debug, info, warning, error; using info' in text(path)
    assert logs.level_of(ROOT, 'WARNING') == 'warning'


@pytest.mark.filterwarnings('ignore::pytest.PytestUnhandledThreadExceptionWarning')  # The error is the point.
def test_uncaught_thread_errors_are_logged_and_hooks_restored(fresh):
    before = threading.excepthook
    path = logs.start(ROOT, 'app')
    thread = threading.Thread(target=lambda: 1 / 0, name='worker-x')
    thread.start()
    thread.join()
    logs.stop()
    assert 'ERROR' in text(path) and 'Uncaught ZeroDivisionError in thread worker-x' in text(path)
    assert threading.excepthook is before


def test_a_full_part_continues_in_the_next_file(fresh, monkeypatch):
    monkeypatch.setattr(logs, 'PART_BYTES', 2000)
    path = logs.start(ROOT, 'app')
    for i in range(40):
        logging.getLogger('local_asset_library.test').info('filler %d %s', i, 'y' * 80)
    logs.stop()
    parts = sorted(fresh.glob(path.stem + '*.log'))
    assert len(parts) >= 2 and all(p.stat().st_size <= 2000 for p in parts)
    out = io.StringIO()
    logs.show(ROOT, path.stem, out=out, color=False)
    assert out.getvalue().count('filler ') == 40 and 'Session ended' in out.getvalue()


def test_retention_keeps_the_newest_sessions_and_the_current_one(fresh):
    fresh.mkdir()
    for day in range(1, 8):
        (fresh / f'2026-10-0{day}_10-00-00_app.log').write_text('x' * 100)
    (fresh / '2026-10-01_10-00-00_app.2.log').write_text('x')
    (fresh / '2026-10-02_10-00-00_app.worker.log').write_text('x')
    (fresh / 'notes.txt').write_text('kept')
    removed = logs.retire(fresh, keep=fresh / '2026-10-01_10-00-00_app.log', sessions_kept=3)
    assert removed == ['2026-10-04_10-00-00_app', '2026-10-03_10-00-00_app', '2026-10-02_10-00-00_app']
    assert (fresh / '2026-10-01_10-00-00_app.2.log').exists() and (fresh / 'notes.txt').exists()
    assert logs.retire(fresh, sessions_kept=30, limit=250) == ['2026-10-05_10-00-00_app', '2026-10-01_10-00-00_app']



def test_retention_never_removes_a_session_that_is_still_running(fresh):
    fresh.mkdir()
    live = fresh / '2026-10-01_10-00-00_mcp.log'  # An MCP server up for days while commands come and go.
    live.write_text('x' * 100)
    handler = logs.SessionHandler(live, 'mcp')
    for day in range(2, 6):
        (fresh / f'2026-10-0{day}_10-00-00_cli.log').write_text('x' * 100)
    try:
        removed = logs.retire(fresh, keep=fresh / '2026-10-05_10-00-00_cli.log', sessions_kept=1)
        assert '2026-10-01_10-00-00_mcp' not in removed and live.exists() and (fresh / '.2026-10-01_10-00-00_mcp.lock').exists()
        assert removed == ['2026-10-04_10-00-00_cli', '2026-10-03_10-00-00_cli', '2026-10-02_10-00-00_cli']
    finally:
        handler.close()
    assert logs.retire(fresh, keep=fresh / '2026-10-05_10-00-00_cli.log', sessions_kept=1) == ['2026-10-01_10-00-00_mcp']
    assert not live.exists() and not (fresh / '.2026-10-01_10-00-00_mcp.lock').exists()

def test_show_filters_by_level_and_keeps_tracebacks_with_their_line(fresh):
    path = logs.start(ROOT, 'app', 'debug')
    log = logging.getLogger('local_asset_library.test')
    log.debug('quiet detail')
    try:
        raise ValueError('broken pack')
    except ValueError:
        log.exception('Scan stopped')
    logs.stop()
    out = io.StringIO()
    assert logs.show(ROOT, out=out, level='error', color=False) == path.stem
    shown = out.getvalue()
    assert 'Scan stopped' in shown and 'ValueError: broken pack' in shown and 'quiet detail' not in shown
    assert 'Session started' not in shown


def test_follow_waits_for_the_next_session_and_ends_with_it(fresh):
    out = io.StringIO()
    follower = threading.Thread(target=logs.show, args=(ROOT,),
                                kwargs={'follow': True, 'wait_new': True, 'kind': 'app', 'out': out, 'color': False, 'poll': 0.02})
    follower.start()
    threading.Event().wait(0.2)
    logs.start(ROOT, 'app')
    logging.getLogger('local_asset_library.test').info('live line')
    logs.stop()
    follower.join(timeout=10)
    assert not follower.is_alive()
    assert out.getvalue().startswith('Waiting for Assetarium to start…') and 'live line' in out.getvalue()


def test_the_logs_command_lists_shows_and_refuses_unknown_sessions(fresh, capsys):
    path = logs.start(ROOT, 'cli')
    logging.getLogger('local_asset_library.test').warning('disk almost full')
    logs.stop()
    assert owner_commands.main(['logs', '--list']) == 0 and path.stem in capsys.readouterr().out
    assert owner_commands.main(['logs', '--level', 'warning']) == 0
    assert 'disk almost full' in capsys.readouterr().out
    assert owner_commands.main(['logs', 'nope']) == 2 and 'No session log named nope' in capsys.readouterr().err


def test_sessions_started_in_the_same_second_get_numbered_names(fresh, monkeypatch):
    monkeypatch.setattr(logs.time, 'sleep', lambda _: pytest.fail('starting a session never waits'))
    first = logs.start(ROOT, 'cli')
    logs.stop()
    second = logs.start(ROOT, 'cli')
    logs.stop()
    if first.stem[:19] == second.stem[:19]:
        assert second.stem == first.stem + '-2' and logs.kind_of(second.stem) == 'cli'
    assert logs.pick(fresh, kind='cli') in {first.stem, second.stem}
