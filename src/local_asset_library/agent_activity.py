"""What agents do in Assetarium, as short sentences for the app's Agent activity drawer (decision 0029).

The feed is read from the audit log every MCP server already writes (``data/mcp/runs/<run>/calls.jsonl``), so it
shows what happened even when a model says nothing; the ``say`` tool adds the agent's own lines. Reads are bounded:
the newest runs only, and only the tail of each log. Nothing here changes state.
"""
import json
from datetime import datetime, timezone

RUNS = 6
TAIL = 512 * 1024
LIMIT = 120
IDLE_SECONDS = 120
_parsed = {}  # (path, size, mtime) -> entries; the app polls every few seconds and most logs have not changed.


def _tail(path):
    with path.open('rb') as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - TAIL))
        lines = stream.read().split(b'\n')
    return lines[1:] if size > TAIL else lines


def _where(args):
    pack = args.get('pack') if args.get('pack') not in (None, '') else (args.get('path') or '')
    return ' / '.join(part for part in (args.get('library_folder'), pack) if part) or 'the library'


def sentence(tool, args, response, error):
    """One line for a call; ``kind`` is read, change, waiting, say or refused."""
    if error:
        return 'refused', f"{tool.replace('_', ' ').capitalize()} refused: {str(response.get('reason') or response.get('error') or '')[:160]}"
    status = response.get('status')
    if tool == 'say':
        return 'say', args.get('message', '')
    if tool == 'list_packs':
        return 'read', 'Listed packs' + (f" ({args['status'].replace('_', ' ')})" if args.get('status') else '') + f" · {response.get('total', 0)} found"
    if tool == 'get_pack_outline':
        page = (args.get('cursor') or 0) // max(1, args.get('limit') or 30) + 1
        return 'read', f"Reading {_where(args)}" + (f' (page {page})' if page > 1 else '')
    if tool == 'get_profile':
        return 'read', f'Read the profile of {_where(args)}'
    if tool == 'propose_profile':
        effect = '; '.join(response.get('effect') or [])
        if status == 'applied':
            scan = {'started': ' · rescanning', None: ''}.get(response.get('scan'), ' · scan not started')
            return 'change', f'Applied rules to {_where(args)}: {effect}{scan}'
        if status == 'pending':
            return 'waiting', f'Proposed rules for {_where(args)}, waiting for you: {effect}'
        return 'read', f'Proposed rules for {_where(args)}: nothing would change'
    if tool == 'finish_structure':
        return 'change', f'Marked {_where(args)} as structured' if status == 'reviewed' else f'Finished {_where(args)} ({status})'
    if tool == 'search_assets':
        return 'read', f"Searched for “{str(args.get('query', ''))[:80]}”"
    if tool == 'get_asset':
        return 'read', f"Looked at {response.get('name') or args.get('asset_id')}"
    if tool in {'list_collections', 'get_collection'}:
        return 'read', 'Read collections'
    if tool in {'edit_collection', 'tag_assets'}:
        return 'change', 'Changed a collection' if tool == 'edit_collection' else 'Changed tags'
    if tool == 'start_processing':
        verb = 'Make previews' if args.get('action') == 'previews' else 'Generate descriptions'
        if status == 'confirm':
            return 'read', f"Asked for the estimate of {verb} for {_where(args)}"
        return 'change', f"Started {verb} for {response.get('job') or _where(args)}" if status == 'started' else             f"Queued {verb} for {response.get('job') or _where(args)}"
    if tool == 'get_setup_status':
        return 'read', 'Checked the setup status'
    if tool == 'validate_blender':
        return 'read', 'Checked a Blender executable'
    if tool == 'apply_setup':
        return 'change', 'Changed settings: ' + (', '.join(response.get('changed') or []) or 'nothing')
    if tool == 'propose_setup':
        return 'waiting', 'Proposed a Blender executable, waiting for you'
    if tool == 'finish_setup':
        return 'change', 'Finished setup'
    return 'read', tool.replace('_', ' ').capitalize()


def _entries(path, run):
    stat = path.stat()
    key = (str(path), stat.st_size, stat.st_mtime_ns)
    if key in _parsed:
        return _parsed[key]
    found = []
    for line in _tail(path):
        try:
            call = json.loads(line)
        except ValueError:
            continue
        if not isinstance(call, dict) or not call.get('utc'):
            continue
        args = call.get('arguments') if isinstance(call.get('arguments'), dict) else {}
        response = call.get('response') if isinstance(call.get('response'), dict) else {}
        kind, text = sentence(call.get('tool', ''), args, response, call.get('is_error'))
        found.append({'utc': call['utc'], 'run': run[:8], 'tool': call.get('tool'), 'kind': kind, 'text': text[:400],
                      **({'proposal_id': response['proposal_id']} if response.get('proposal_id') else {}),
                      **({'library_folder': args['library_folder'], 'pack': args.get('pack', args.get('path', ''))}
                         if args.get('library_folder') else {})})
    for stale in [k for k in _parsed if k[0] == key[0]]:
        del _parsed[stale]
    if len(_parsed) > 32:
        _parsed.clear()
    _parsed[key] = found[-LIMIT:]
    return _parsed[key]


def _runs(config, newest=RUNS):
    """Run folders to read: every connected server's run, then the newest others (a log grows without touching its folder)."""
    from .setup_agent import connections_dir
    root = config.output_path('data', 'mcp/runs')
    if not root.is_dir():
        return []
    live = []
    folder = connections_dir(config.project_root)
    for path in folder.glob('*.json') if folder.is_dir() else []:
        try:
            live.append(json.loads(path.read_text(encoding='utf-8')).get('run_id'))
        except (OSError, ValueError):
            continue
    runs = [root / r for r in live if isinstance(r, str) and (root / r).is_dir()]
    others = sorted((p for p in root.iterdir() if p.is_dir() and p not in runs), key=lambda p: p.stat().st_mtime_ns, reverse=True)
    return runs + others[:newest]


def token(config):
    """Stat-only change token of the call logs the feed reads, for the app's change poll."""
    found = []
    for run in _runs(config, 1):
        try:
            value = (run / 'calls.jsonl').stat()
            found.append((run.name, value.st_size, value.st_mtime_ns))
        except OSError:
            continue
    return found


def recent(config, since=None):
    """The newest entries (oldest first), whether an agent is connected and whether it went quiet.

    ``since``: an ISO time; only later entries are returned (the app polls with the last one it has).
    """
    from .setup_agent import connections
    runs = _runs(config)
    entries = []
    for run in runs:
        path = run / 'calls.jsonl'
        if path.is_file():
            entries += [e for e in _entries(path, run.name) if not since or e['utc'] > since]
    entries.sort(key=lambda e: e['utc'])
    entries = entries[-LIMIT:]
    live = [c for c in connections(config.project_root) if c.get('mode') == 'normal']
    last = entries[-1]['utc'] if entries else None
    quiet = None
    if last:
        quiet = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
    return {'status': 'ready', 'entries': entries, 'connected': [c.get('client') or {} for c in live],
            'last_utc': last, 'working': bool(live) and quiet is not None and quiet < IDLE_SECONDS,
            'idle_seconds': IDLE_SECONDS}
