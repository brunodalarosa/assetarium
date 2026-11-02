"""Session logs: one readable file per Assetarium session that every process of the session writes into.

A session starts when the desktop app, the MCP server or a CLI command starts (``logs/<started>_<kind>.log``).
Child processes (operation workers, the embedding worker) join it through ``ASSETARIUM_LOG_SESSION`` and append
under a short file lock, so lines from several processes never tear. Lines say ``time LEVEL process[pid] area:
message · key=value``. A line repeating within ``REPEAT_SECONDS`` is counted, not written, and summarized once.
Raw output (Blender, worker stderr) stays in its own files; the session log points to them. Retention keeps the
newest ``KEEP_SESSIONS`` sessions under ``FOLDER_BYTES``; a session file splits at ``PART_BYTES``. Standard
library only: every runtime and worker can import it.
"""
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import sys
import threading
import time
import tomllib

ENV, LEVEL_ENV = 'ASSETARIUM_LOG_SESSION', 'ASSETARIUM_LOG_LEVEL'
LEVELS = {'debug': logging.DEBUG, 'info': logging.INFO, 'warning': logging.WARNING, 'error': logging.ERROR}
KINDS = ('app', 'mcp', 'cli')
KEEP_SESSIONS, PART_BYTES, FOLDER_BYTES = 30, 20 * 1024 * 1024, 200 * 1024 * 1024
REPEAT_SECONDS = 10
SESSION = re.compile(r'^(\d{4}-\d\d-\d\d_\d\d-\d\d-\d\d_([a-z]+)(?:-\d+)?)(?:\.(\d+))?(?:\.[a-z]+)?\.log$')
_session = None


def _settings(root):
    """``[storage].logs`` and ``[logging].level`` from config.local.toml, else config.example.toml."""
    found = {}
    for name in ('config.example.toml', 'config.local.toml'):
        try:
            raw = tomllib.loads((Path(root) / name).read_text(encoding='utf-8'))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        for section, key in (('storage', 'logs'), ('logging', 'level')):
            value = raw.get(section, {}).get(key) if isinstance(raw.get(section), dict) else None
            if isinstance(value, str) and value:
                found[key] = value
    return found


def folder(root):
    path = Path(_settings(root).get('logs', 'logs'))
    return path if path.is_absolute() else Path(root) / path


def level_of(root, chosen=None):
    """The chosen level (a flag), else ``ASSETARIUM_LOG_LEVEL``, else ``[logging].level``, else info."""
    name = (chosen or os.environ.get(LEVEL_ENV) or _settings(root).get('level') or 'info').lower()
    if name not in LEVELS:
        raise ValueError(f'Log level must be one of {", ".join(LEVELS)}')
    return name


def kv(**fields):
    """``key=value`` pairs for the end of a line; empty values are left out."""
    return ' '.join(f'{k}={v}' for k, v in fields.items() if v not in (None, ''))


class _Lock:
    """An exclusive lock on a sidecar file, held only while one line is appended."""

    def __init__(self, path):
        self.stream = open(path, 'a+b')

    def __enter__(self):
        if os.name == 'nt':
            import msvcrt
            self.stream.seek(0)
            while True:
                try:
                    msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
                    return self
                except OSError:
                    time.sleep(0.005)
        import fcntl
        fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        if os.name == 'nt':
            import msvcrt
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)


def kind_of(stem):
    return SESSION.match(stem + '.log').group(2)


def part(path, index):
    return path if index == 1 else path.with_name(f'{path.stem}.{index}.log')


class SessionHandler(logging.Handler):
    """Appends formatted lines to the session file (and its later parts), collapsing quick repeats."""

    def __init__(self, path, process):
        super().__init__()
        self.path, self.process = Path(path), process
        self.file_lock = _Lock(self.path.with_name(f'.{self.path.stem}.lock'))  # Not "lock": logging.Handler uses that name for its thread lock.
        self.repeats = {}  # key -> [window start, suppressed count, last line]

    @staticmethod
    def stamp(created):
        return datetime.fromtimestamp(created).strftime('%H:%M:%S.%f')[:12]

    def line(self, record):
        stamp = self.stamp(record.created)
        area = record.name.removeprefix('local_asset_library.').removeprefix('assetarium.')
        text = record.getMessage()
        if record.exc_info:
            text += '\n' + logging.Formatter().formatException(record.exc_info)
        return f'{stamp} {record.levelname:<7} {self.process}[{os.getpid()}] {area}: {text}\n'

    def _expired(self, now, written=None):
        """Summaries of repeat windows that ended by ``now``, stamped when written so the file stays in time order."""
        lines, stamp = [], self.stamp(written or now)
        for key, (start, count, last) in list(self.repeats.items()):
            if now - start >= REPEAT_SECONDS:
                del self.repeats[key]
                if count:
                    lines.append(f'{stamp}{last[12:].rstrip()} · ↻ repeated {count} more time{"s" if count > 1 else ""}, '
                                 f'last at {last[:12]}\n')
        return lines

    def emit(self, record):
        try:
            now = record.created
            key = getattr(record, 'repeat_key', None) or (record.name, record.levelno, record.getMessage())
            lines = self._expired(now)
            seen = self.repeats.get(key)
            if seen:
                seen[1] += 1
                seen[2] = self.line(record)
            else:
                self.repeats[key] = [now, 0, '']
                lines.append(self.line(record))
            if lines:
                self.write(''.join(lines))
        except Exception:
            self.handleError(record)

    def write(self, text):
        data = text.encode('utf-8')
        with self.file_lock:
            index = 1
            while part(self.path, index + 1).exists():
                index += 1
            target = part(self.path, index)
            if target.exists() and target.stat().st_size + len(data) > PART_BYTES:
                target = part(self.path, index + 1)
            with open(target, 'ab') as stream:
                stream.write(data)

    def flush_repeats(self):
        self.acquire()
        try:
            lines = self._expired(float('inf'), time.time())
            if lines:
                self.write(''.join(lines))
        finally:
            self.release()

    def close(self):
        self.flush_repeats()
        self.file_lock.stream.close()
        super().close()


def start(root, kind, level=None, process=None):
    """Start this process's logging; returns the session file.

    ``kind`` in ``KINDS`` starts a new session; any other kind (a worker) joins ``ASSETARIUM_LOG_SESSION`` when set,
    else starts a session of its own. Children inherit the session and level through the environment.
    """
    global _session
    if _session is not None:
        return _session[0]
    try:
        name, refused = level_of(root, level), None
    except ValueError as exc:  # A mistyped level never stops the app; the log says which level it used.
        name, refused = 'info', str(exc)
    joined = os.environ.get(ENV) if kind not in KINDS else None
    if joined and Path(joined).parent.is_dir():
        path = Path(joined)
    else:
        logs = folder(root)
        logs.mkdir(parents=True, exist_ok=True)
        name_at, n = f'{datetime.now():%Y-%m-%d_%H-%M-%S}_{kind}', 1
        while True:  # Claimed by creating it, so two sessions started in one second get _cli and _cli-2.
            path = logs / f'{name_at}{"" if n == 1 else f"-{n}"}.log'
            try:
                open(path, 'x').close()
                break
            except FileExistsError:
                n += 1
        joined = None
    os.environ[ENV], os.environ[LEVEL_ENV] = str(path), name
    handler = SessionHandler(path, process or kind)
    top = logging.getLogger()
    for old in [h for h in top.handlers if isinstance(h, SessionHandler)]:
        top.removeHandler(old)
    top.addHandler(handler)
    restore = (top.level, *_hooks())
    top.setLevel(LEVELS[name])
    for noisy in ('asyncio', 'urllib3', 'httpx', 'httpcore', 'PIL', 'pywebview', 'mcp', 'filelock', 'huggingface_hub'):
        logging.getLogger(noisy).setLevel(max(LEVELS[name], logging.WARNING))
    _session = (path, handler, not joined, restore)
    log = logging.getLogger('assetarium.session')
    if joined:
        log.info('Joined the session · %s', kv(process=process or kind, level=name))
    else:
        from . import __version__
        log.info('Session started · %s', kv(kind=kind, version=__version__, level=name, python=sys.version.split()[0],
                                            platform=sys.platform, date=f'{datetime.now():%Y-%m-%d}'))
        try:
            retire(path.parent, keep=path)
        except OSError as exc:
            log.warning('Old session logs could not be removed · %s', kv(reason=exc))
    if refused:
        log.warning('%s; using info', refused)
    import atexit
    atexit.register(stop)
    return path


def stop():
    """Write pending repeat counts and close the session handler (also runs at exit)."""
    global _session
    if _session is None:
        return
    path, handler, owner, (level, hook, thread_hook) = _session
    handler.flush_repeats()  # Before "Session ended", which a console following the log stops at.
    if owner:
        logging.getLogger('assetarium.session').info('Session ended')
    logging.getLogger().removeHandler(handler)
    logging.getLogger().setLevel(level)
    sys.excepthook, threading.excepthook = hook, thread_hook
    handler.close()
    _session = None


def session():
    return _session[0] if _session else None


def _hooks():
    """Uncaught exceptions in any thread reach the session log as errors; returns the hooks to restore."""
    previous, previous_thread = sys.excepthook, threading.excepthook

    def hook(kind, value, trace):
        if not issubclass(kind, KeyboardInterrupt):
            logging.getLogger('assetarium.session').error('Uncaught %s', kind.__name__, exc_info=(kind, value, trace))
        previous(kind, value, trace)

    def thread_hook(args):
        if args.exc_type is not SystemExit:
            logging.getLogger('assetarium.session').error('Uncaught %s in thread %s', args.exc_type.__name__,
                                                          args.thread.name if args.thread else '?',
                                                          exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        previous_thread(args)
    sys.excepthook, threading.excepthook = hook, thread_hook
    return previous, previous_thread


def sessions(logs):
    """Session stems in ``logs``, newest first, each with its files."""
    found = {}
    for path in Path(logs).glob('*.log'):
        match = SESSION.match(path.name)
        if match:
            found.setdefault(match.group(1), []).append(path)
    for path in Path(logs).glob('.*.lock'):
        stem = path.name[1:-len('.lock')]
        if stem in found:
            found[stem].append(path)
    return sorted(found.items(), reverse=True)


def retire(logs, keep=None, sessions_kept=KEEP_SESSIONS, limit=FOLDER_BYTES):
    """Remove whole old sessions beyond the newest ``sessions_kept`` or over ``limit`` bytes; never ``keep``'s."""
    current = SESSION.match(Path(keep).name).group(1) if keep else None
    listed = sessions(logs)
    total, removed = 0, []
    for index, (stem, files) in enumerate(listed):
        size = sum(f.stat().st_size for f in files if f.exists())
        total += size
        if stem != current and (index >= sessions_kept or total > limit):
            for path in files:
                try:
                    path.unlink(missing_ok=True)
                except OSError:  # Still open by a running session elsewhere (its lock); it goes next time.
                    pass
            removed.append(stem)
    return removed


COLORS = {'DEBUG': '\x1b[2m', 'WARNING': '\x1b[33m', 'ERROR': '\x1b[31m', 'CRITICAL': '\x1b[1;31m'}
LINE = re.compile(r'^\d\d:\d\d:\d\d\.\d{3} ([A-Z]+)\s')


def pick(logs, chosen=None, kind=None):
    """A session stem: ``chosen`` (a stem or file name), else the newest (of ``kind``)."""
    listed = [stem for stem, _ in sessions(logs) if not kind or kind_of(stem) == kind]
    if chosen and chosen != 'latest':
        match = SESSION.match(Path(chosen).name if chosen.endswith('.log') else chosen + '.log')
        if not match or match.group(1) not in listed:
            raise ValueError(f'No session log named {chosen}; local-assets logs --list shows them')
        return match.group(1)
    if not listed:
        raise ValueError('No session logs yet')
    return listed[0]


def show(root, chosen=None, level='info', follow=False, kind=None, wait_new=False, out=None, color=None, poll=0.25):
    """Print a session's lines at ``level`` and above; ``follow`` keeps printing new lines (and later parts).

    ``wait_new`` waits for a session (of ``kind``) that starts after this call: the console launcher opens the
    console first, then the app. Following ends at the session's "Session ended" line or Ctrl+C.
    """
    out = out or sys.stdout
    logs, floor = folder(root), LEVELS[level]
    if color is None:
        color = out.isatty() and not os.environ.get('NO_COLOR')
        if color and os.name == 'nt':
            os.system('')  # Turns on ANSI colors in a classic console window.
    if wait_new:
        known = {stem for stem, _ in sessions(logs)} if logs.is_dir() else set()
        out.write('Waiting for Assetarium to start…\n')
        out.flush()
        while True:
            fresh = [stem for stem, _ in (sessions(logs) if logs.is_dir() else [])
                     if stem not in known and (not kind or kind_of(stem) == kind)]
            if fresh:
                stem = fresh[0]
                break
            time.sleep(poll)
    else:
        stem = pick(logs, chosen, kind)
    base, index, offset, shown, ended = logs / f'{stem}.log', 1, 0, LEVELS['info'], False
    out.write(f'Session {stem} · {level} and above\n')
    while True:
        target = part(base, index)
        if target.exists():
            with open(target, 'rb') as stream:
                stream.seek(offset)
                chunk = stream.read()
            complete = chunk[:chunk.rfind(b'\n') + 1]
            offset += len(complete)
            for raw in complete.decode('utf-8', errors='replace').splitlines():
                found = LINE.match(raw)
                if found:  # Lines without a time (tracebacks) keep the level of the line they belong to.
                    shown = LEVELS.get(found.group(1).lower(), logging.ERROR)
                    ended = ended or ' session: Session ended' in raw
                if shown >= floor:
                    tone = COLORS.get(logging.getLevelName(shown)) if color else None
                    out.write(f'{tone}{raw}\x1b[0m\n' if tone else raw + '\n')
            out.flush()
        if part(base, index + 1).exists():
            index, offset = index + 1, 0
            continue
        if not follow or ended:
            return stem
        time.sleep(poll)
