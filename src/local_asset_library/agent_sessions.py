"""Agent sessions (decision 0029): Pause agents, and a journal of each session's changes for Undo all.

A session is one connected MCP server run (its ``run_id``). The gateway marks the calls it runs for a connected agent
(``active``); the modules that save owner data write a journal entry of what each write changed, captured inside their
own lease: tags and collection states before and after, the pack proposals it applied, the jobs it queued. Undo all
reverses a session newest first and skips, with the reason, anything that changed after it. Settings are not
journaled: each is one visible value the owner changes back in Settings. Pause refuses every agent write; reads go on,
and jobs agents queued wait until the owner turns agents back on.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import json

from .config import ConfigError
from .publication import atomic_json, read_json

class Paused(ConfigError):
    """An agent write refused while agents are paused (a refusal, not a fault)."""


PAUSED_REASON = 'Paused by the owner: agents cannot change anything until the owner turns agents back on in Agent activity'
_session = ContextVar('agent_session', default=None)


def _settings(config):
    return config.storage_root('data') / 'library/agents.json'


def paused(config):
    target = _settings(config)
    try:
        return bool(target.exists() and read_json(target).get('paused'))
    except (OSError, ValueError):
        return True  # An unreadable switch keeps agents paused rather than silently letting them write.


def set_paused(config, value):
    """Owner only: the app's switch, or the CLI (resume asks in an interactive terminal)."""
    from .library_store import now
    target = _settings(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(target, {'schema_version': 1, 'paused': bool(value), 'utc': now()})
    if not value:
        from .processing_queue import advance
        advance(config)  # Held agent jobs may start now.
    return {'status': 'saved', 'paused': bool(value)}


@contextmanager
def active(run_id, client=None):
    """Calls inside run for this agent session: writes are journaled under ``run_id``."""
    token = _session.set({'run': run_id, 'agent': (client or {}).get('name') or ''})
    try:
        yield
    finally:
        _session.reset(token)


def current():
    return _session.get()


def _run(config, run_id):
    if not isinstance(run_id, str) or not run_id.isalnum() or len(run_id) != 32:
        raise ConfigError('Unknown agent session')
    return config.output_path('data', 'mcp/runs/' + run_id)


def note(config, kind, **entry):
    """Journal one agent write of the current session; no-op outside one (the owner's own edits)."""
    session = current()
    if session is None:
        return
    from .library_store import now
    folder = _run(config, session['run'])
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'journal.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'kind': kind, 'utc': now(), 'agent': session['agent'], **entry}, ensure_ascii=False) + '\n')


def _journal(folder):
    try:
        lines = (folder / 'journal.jsonl').read_text(encoding='utf-8').splitlines()
    except OSError:
        return []
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue  # A torn last line from a killed server; the rest still undoes.
    return entries


def _undone(folder):
    """What Undo all already did for this session: ``through`` journal entries, the ones among them to try again
    (``pending``: their library folder was busy) and its latest outcome."""
    try:
        value = read_json(folder / 'undo.json')
    except (OSError, ValueError):
        return {'through': 0, 'pending': [], 'last': None}
    return {'through': int(value.get('through', 0)), 'pending': [int(i) for i in value.get('pending', [])], 'last': value.get('last')}


def _what(entry):
    kind = entry['kind']
    if kind == 'tags':
        return f"Tags on {len(entry['before'])} asset{'s' if len(entry['before']) != 1 else ''}"
    if kind == 'collection':
        name = (entry.get('after') or entry.get('before') or {}).get('name', 'a collection')
        return f'Collection “{name}”'
    if kind == 'profile':
        return f"Pack profile of “{entry.get('pack') or 'the library folder'}”"
    return f"Job: {entry.get('label', 'processing')}"


def summary(config, run_id):
    """One session's changes for Agent activity: counts by kind, and whether Undo all ran."""
    folder = _run(config, run_id)
    entries = _journal(folder)
    if not entries:
        return None
    counts = {}
    for entry in entries:
        counts[entry['kind']] = counts.get(entry['kind'], 0) + 1
    done = _undone(folder)
    return {'run_id': run_id, 'agent': next((e['agent'] for e in entries if e.get('agent')), ''), 'started_utc': entries[0]['utc'],
            'last_utc': entries[-1]['utc'], 'changes': len(entries), 'counts': counts, 'undone': done['last'],
            'to_undo': len(entries) - done['through'] + len(done['pending'])}


def sessions(config, limit=10):
    """The newest sessions that changed something, newest first."""
    root = config.output_path('data', 'mcp/runs')
    if not root.is_dir():
        return []
    found = []
    for folder in root.iterdir():
        journal = folder / 'journal.jsonl'
        if journal.is_file():
            found.append((journal.stat().st_mtime_ns, folder.name))
    result = []
    for _, run_id in sorted(found, reverse=True)[:limit]:
        try:
            value = summary(config, run_id)
        except ConfigError:
            continue
        if value:
            result.append(value)
    return result


def undo(config, run_id):
    """Undo all of one session, newest first. Returns what was undone, what was skipped and why, and the library folders
    that need one rescan each (the caller starts it once, after every change). Processing already done is kept.

    A session still connected may change more after an Undo all; the next Undo all takes only those changes, and the
    ones refused only because their library folder was busy (``sources.Busy``), which stay to undo.
    """
    from . import asset_collections, asset_tags, processing_queue
    from .library_store import now
    from .pack_agent import decide
    from .sources import Busy
    folder = _run(config, run_id)
    entries = _journal(folder)
    if not entries:
        raise ConfigError('This agent session changed nothing')
    done = _undone(folder)
    todo = sorted(set(done['pending']) | set(range(done['through'], len(entries))), reverse=True)
    if not todo:
        raise ConfigError('Undo all already took back everything this session changed')
    undone, skipped, rescan, pending = [], [], [], []
    for index in todo:
        entry = entries[index]
        what = _what(entry)
        try:
            if entry['kind'] == 'tags':
                reason = asset_tags.undo(config, entry['before'], entry['after'])
            elif entry['kind'] == 'collection':
                reason = asset_collections.undo(config, entry['collection_id'], entry.get('before'), entry.get('after'))
            elif entry['kind'] == 'profile':
                result, reason = decide(config, entry['proposal'], 'undo'), None
                if result.get('rescan') and result['library_folder'] not in rescan:
                    rescan.append(result['library_folder'])
            else:
                reason = processing_queue.withdraw(config, entry['item'])
        except Busy as exc:
            reason = str(exc) + '; Undo all again when it ends'
            pending.append(index)
        except ConfigError as exc:
            reason = str(exc)
        (skipped.append({'what': what, 'reason': reason}) if reason else undone.append(what))
    record = {'utc': now(), 'undone': len(undone), 'skipped': skipped}
    atomic_json(folder / 'undo.json', {'schema_version': 1, 'through': len(entries), 'pending': sorted(pending), 'last': record})
    from .logs import kv
    import logging
    logging.getLogger(__name__).info('Agent session undone · %s', kv(run=run_id[:8], undone=len(undone), skipped=len(skipped)))
    return {'status': 'undone', 'run_id': run_id, 'undone': undone, 'skipped': skipped, 'rescan': rescan}
