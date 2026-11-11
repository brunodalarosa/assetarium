"""One disposable agent practice session, shared by the desktop and connected MCP processes.

All generated assets, store, activity and coordination files live under one owned scratch root.
Only opaque UUID keys cross the bridge. A closing or expired session never falls back to the real library.
"""
from contextlib import contextmanager, closing
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid

from .config import Config, ConfigError
from .publication import atomic_json, read_json
from .transient import work

PREFIX = 'agent-practice-'
KEY = re.compile(r'^agent-practice-([0-9a-f]{32})$')
_start_lock = threading.Lock()


class Ended(ConfigError):
    """The practice session is gone; callers that remembered its key should forget it."""


def is_key(key):
    return isinstance(key, str) and key.startswith(PREFIX)


def _parent(config):
    return config.project_root / 'scratch' / 'agent-practice'


def _root(config, key):
    match = KEY.fullmatch(key) if isinstance(key, str) else None
    if not match:
        raise Ended('This practice session has ended. Start Try your agent again.')
    root = _parent(config) / match[1]
    # Never follow links, including a substituted ancestor.
    for path in (config.project_root / 'scratch', _parent(config), root):
        if path.is_symlink() or path.is_junction():
            raise ConfigError('Practice folder containment check failed')
    if not root.is_dir():
        raise Ended('This practice session has ended. Start Try your agent again.')
    return root


@contextmanager
def _locked(root):
    """Open an existing lock only: a late caller must never recreate a deleted session."""
    try:
        stream = (root / 'session.lock').open('r+b')
    except OSError:
        raise Ended('This practice session has ended. Start Try your agent again.') from None
    acquired = False
    try:
        started = time.monotonic()
        while not acquired:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() - started > 15:
                    raise ConfigError('Practice work is still finishing; try again shortly') from None
                time.sleep(.025)
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


def _config(root, key):
    base = root / 'project'
    return Config(base, root / key, None, sources_registry=base / 'data/library/sources.json')


def _check(root, *, closing=False):
    from .gpu_queue import process_alive
    state = read_json(root / 'session.json')
    if state.get('state') == 'closing' and not closing:
        raise Ended('This practice session has ended. Start Try your agent again.')
    if not closing and not process_alive(state.get('pid')):
        raise Ended('The practice app closed. Start Try your agent again.')
    return state


def _erase(root):
    """Reviewed containment: refuse any link anywhere before deleting the owned generated root."""
    if (not re.fullmatch('[0-9a-f]{32}', root.name) or root.parent.name != 'agent-practice'
            or root.parent.parent.name != 'scratch' or root.resolve() != root.absolute()):
        raise ConfigError('Practice cleanup containment check failed')
    if root.is_symlink() or root.is_junction():
        raise ConfigError('Practice cleanup refused a linked folder')
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink() or path.is_junction():
                raise ConfigError('Practice cleanup refused a linked file or folder')
    # Keep the closing marker and lock until all generated data is gone. A locked asset must
    # leave a retryable session, rather than half-deleting its coordination files first.
    for path in root.iterdir():
        if path.name in {'session.json', 'session.lock'}:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    (root / 'session.lock').unlink(missing_ok=True)
    (root / 'session.json').unlink(missing_ok=True)
    root.rmdir()
    if root.exists():
        raise ConfigError('Practice files could not all be removed')
    try:
        root.parent.rmdir()
    except OSError:
        pass


def recover(config):
    """Remove abandoned sessions only; a live app's session belongs to that app."""
    from .gpu_queue import process_alive
    parent = _parent(config)
    if not parent.exists():
        return
    if parent.is_symlink() or parent.is_junction() or parent.parent.is_symlink() or parent.parent.is_junction():
        raise ConfigError('Practice folder containment check failed')
    for root in list(parent.iterdir()):
        if not re.fullmatch('[0-9a-f]{32}', root.name):
            raise ConfigError('Unexpected content in the practice folder; cleanup needs attention')
        _root(config, PREFIX + root.name)
        marker = root / 'session.json'
        if not marker.exists() and time.time() - root.stat().st_mtime < 15:
            continue  # Another process may still be claiming this root.
        # A generation interrupted before publishing its marker is also disposable.
        if marker.exists() and process_alive(read_json(marker).get('pid')):
            continue
        if (root / 'session.lock').exists():
            with _locked(root):
                if marker.exists():
                    state = read_json(marker)
                    state['state'] = 'closing'
                    atomic_json(marker, state)
        _erase(root)
    if parent.exists() and not any(parent.iterdir()) and time.time() - parent.stat().st_mtime >= 15:
        parent.rmdir()


def start(config):
    from .agent_practice_assets import generate
    from . import quick_look
    with _start_lock, work():
        scratch = config.project_root / 'scratch'
        if scratch.is_symlink() or scratch.is_junction():
            raise ConfigError('Practice folder containment check failed')
        recover(config)
        parent = _parent(config)
        parent.parent.mkdir(parents=True, exist_ok=True)
        try:
            parent.mkdir()  # Atomic claim across app processes, not just threads.
        except FileExistsError:
            raise ConfigError('A practice session is already open. Finish or cancel it first.') from None
        identifier = uuid.uuid4().hex
        key = PREFIX + identifier
        root = parent / identifier
        try:
            root.mkdir()
            (root / 'session.lock').write_bytes(b'0')
            atomic_json(root / 'session.json', {'state': 'starting', 'pid': os.getpid(), 'key': key, 'started': time.time()})
            generate(root / key)
            scoped = _config(root, key)
            scoped.project_root.mkdir()
            # Practice uses known formats without changing the owner's choices.
            atomic_json(scoped.project_root / 'data/library/settings.json',
                        {'processing_formats': ['obj'], 'image_formats': ['png'], 'descriptions_enabled': False})
            look = quick_look.start(scoped, str(root / key))
            state = _check(root)
            atomic_json(root / 'session.json', dict(state, state='looking', job=look['job']))
            return {'status': 'started', 'key': key, 'job': look['job'], 'name': 'Practice packs'}
        except BaseException:
            if root.exists():
                _erase(root)
            else:
                parent.rmdir()
            raise


def _scan(scoped, key):
    from .sources import aggregate, get_source, scan_source
    source = get_source(scoped, key)
    scan_source(scoped, source)
    aggregate(scoped)


def _entries(root):
    path = root / 'activity.json'
    return read_json(path) if path.exists() else []


def checks(scoped, key, root):
    """Observe the real scanned folder view and saved answers, never the agent's completion claim."""
    from .sources import get_source, bound, excluded_folders
    from .sources import read_records
    from .incremental import working
    from .packs import structure
    source = get_source(scoped, key)
    records = read_records(working(bound(scoped, source)))
    rows = [(r['files'][0]['path'].removeprefix(key + '/'),
             ((r.get('type_metadata') or {}).get('image_kind') or {}).get('value')) for r in records]
    paths = [r[0] for r in rows]
    excluded = excluded_folders(bound(scoped, source))
    covers = lambda folder: any(folder == p or folder.startswith(p + '/') for p in excluded)
    kinds = lambda folder, value: any(p.startswith(folder + '/') for p, _ in rows) and all(
        kind == value for p, kind in rows if p.startswith(folder + '/'))
    packs = structure(scoped, source)['packs']
    activity = _entries(root)
    observed = any(e['tool'] in {'get_profile', 'get_pack_outline'} and e['kind'] != 'refused' for e in activity)
    return [
        {'label': 'Agent inspected the practice packs', 'passed': observed},
        {'label': 'Engine copy excluded and original models retained', 'passed': covers('Village Props/Unity Models') and
         not covers('Village Props/Models') and sum(p.startswith('Village Props/Models/') for p in paths) == 3},
        {'label': 'Version folder kept inside its parent pack', 'passed': 'Castle Kit' in packs and
         not any(p.startswith('Castle Kit/') for p in packs) and sum(p.startswith('Castle Kit/') for p in paths) == 3},
        {'label': 'Ground maps classified as textures', 'passed': kinds('Terrain Pack/Art', 'material_texture')},
        {'label': 'Hero sprites classified as standalone images', 'passed': kinds('Hero Pack/Art', 'image')},
        {'label': 'Six numbered rocks preserved as separate assets', 'passed': sum(p.startswith('Rock Pack/Rocks/') for p in paths) == 6 and
         not covers('Rock Pack/Rocks') and _rock_cards(scoped, source) == 6},
    ]


def _rock_cards(scoped, source):
    from .pack_profiles import open_view
    with closing(open_view(scoped, source)) as db:
        return db.execute("SELECT COUNT(DISTINCT card) FROM assets WHERE folder='Rock Pack/Rocks'").fetchone()[0]


def _status(scoped, key, root):
    from .pack_agent import counts, proposals
    state = _check(root)
    result = checks(scoped, key, root) if state['state'] == 'working' else []
    # Connection records are read-only; the practice activity itself stays in this root.
    return {'status': 'ready', 'checks': result, 'entries': _entries(root), 'proposals': proposals(scoped),
            'applied': proposals(scoped, state='applied'),
            'signals': counts(scoped, key), 'complete': bool(result) and all(c['passed'] for c in result) and not proposals(scoped)}


def action(config, name, key=None, payload=None):
    """Desktop practice entry point; all failures return without entering permanent call logs."""
    try:
        with work():
            if name == 'start':
                return start(config)
            root = _root(config, key)
            if name in {'finish', 'cancel'} and not (root / 'session.lock').exists():
                marker = root / 'session.json'
                state = read_json(marker) if marker.exists() else {}
                if state.get('state') == 'closing' or not any(root.iterdir()):
                    _erase(root)
                    result = state.get('result', {})
                    return {'status': 'cancelled' if name == 'cancel' else 'finished', 'cleaned': True,
                            'checks': result.get('checks', []), 'waiting': len(result.get('proposals', []))}
            with _locked(root):
                state = _check(root, closing=name in {'finish', 'cancel'})
                scoped = _config(root, key)
                from . import quick_look, sources, pack_agent
                if name == 'look':
                    return quick_look.status(state['job'])
                if name == 'add':
                    if state['state'] != 'looking':
                        raise ConfigError('This practice folder was already added')
                    source = sources.add(scoped, str(root / key))
                    quick_look.save(scoped, source, state['job'])
                    _scan(scoped, key)
                    atomic_json(root / 'session.json', dict(state, state='working'))
                    prompt = pack_agent.prompt(dict(source, name='Practice packs')) + (
                        '\nThis is a disposable practice import, scoped ONLY to this library_folder. '
                        'Use the six pack structure tools only; do not use shell or file tools. '
                        'The Ground images are material texture maps; Hero_Run images are standalone sprites. '
                        'Include library_folder in every call, including say. Wait for my proposal review when needed. '
                        'Never claim success just by marking signals reviewed.')
                    return {'status': 'added', 'key': key, 'name': 'Practice packs', 'prompt': prompt}
                if name == 'status':
                    return _status(scoped, key, root)
                if name == 'preview':
                    return pack_agent.preview(scoped, payload)
                if name == 'commit':
                    result = pack_agent.commit(scoped, payload)
                    if result['rescan']:
                        _scan(scoped, key)
                    return result
                if name == 'undo':
                    result = pack_agent.decide(scoped, payload, 'undo')
                    if result.get('rescan'):
                        _scan(scoped, key)
                    return result
                if name not in {'finish', 'cancel'}:
                    raise ConfigError('Unknown practice action')
                result = (_status(scoped, key, root) if state['state'] == 'working' else
                          state.get('result', {'checks': [], 'proposals': [], 'entries': []}))
                atomic_json(root / 'session.json', dict(state, state='closing', result=result))
            # No worker can enter once closing is published. Close our lock handle before deletion on Windows.
            _erase(root)
            quick_look._jobs.pop(state.get('job'), None)
            return {'status': 'finished' if name == 'finish' else 'cancelled', 'checks': result['checks'],
                    'waiting': len(result['proposals']), 'cleaned': True,
                    'faults': [e['text'] for e in result.get('entries', []) if e['kind'] == 'refused']}
    except Exception as exc:
        return {'status': 'faulty', 'reason': str(exc), 'cleaned': False}


def tool(config, key, name, args, client=None):
    """Real pack tools, isolated state, a disposable activity feed, and no permanent audit output."""
    from .mcp_assets import validate
    from .pack_agent import execute
    from .library_store import now
    from .agent_activity import sentence
    root = _root(config, key)
    with work(), _locked(root):
        state = _check(root)
        if state['state'] != 'working':
            raise ConfigError('Open the practice wizard and choose Let my agent finish first')
        try:
            validate(name, args)
            scoped_args = dict(args, library_folder=key)
            result = execute(_config(root, key), name, scoped_args, client, hold=True)  # Practice walks the owner's review.
            error = False
        except Exception as exc:
            result, error = {'status': 'refused', 'reason': str(exc)}, True
        kind, text = sentence(name, scoped_args if 'scoped_args' in locals() else args, result, error)
        text = text.replace(key, 'Practice packs')
        entries = _entries(root)
        entries.append({'utc': now(), 'run': key, 'tool': name, 'kind': kind, 'text': text, 'library_folder': key,
                        **({'proposal_id': result['proposal_id']} if result.get('proposal_id') else {})})
        atomic_json(root / 'activity.json', entries[-120:])
        return result, error
