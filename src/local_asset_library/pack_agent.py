"""Pack structure tools for agents (decision 0024): paged folder outlines, profiles, proposals and their decisions.

Every response is bounded (``CAP`` characters, about 2,000 tokens) so a small local model can read a pack page by
page: an outline shows one folder level with counts and collapsed names (``Car_11_{B,G,R}``, ``Rock_{01..20}``),
never a file dump. An agent only proposes: a proposal whose rules all apply without a scan (variant rules, pack
boundaries and names) is applied at once and can be undone from the app; any other waits for the owner's Apply. One
proposal per pack waits at a time; a newer one replaces it. Nothing is written into a library folder.
"""
from contextlib import closing
import json
from pathlib import PurePosixPath
import uuid

from .config import ConfigError

CAP = 8000
PAGE = 30
SAY = 300
STATES = ('pending', 'applied', 'rejected', 'superseded', 'undone')
TABLE = """CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, folder_id TEXT, folder_key TEXT, pack TEXT, rules TEXT,
  origin TEXT, effect TEXT, state TEXT, utc TEXT, decided_utc TEXT, version INTEGER, previous INTEGER)"""
VOCABULARY = {
    'pack': 'folder (inside the pack, "" = the pack), value make_pack | merge',
    'pack_name': 'value: the display name',
    'image_kind': 'folder, value texture | image (2D asset)',
    'variant_axis': 'folder, values: subset of letters, colors, materials, lod, numbers ([] = no variants there); '
                    'default letters, colors, materials, lod',
    'separate_descriptions': 'group: a variant group key "Folder/Base" that gets one description per variant',
    'exclude': 'folder: skipped by scans (nothing is deleted)',
    'engine_copy': 'folder: a copy of the pack for another engine (Unity, Godot…), of: the folder it copies; excluded',
    'export_group': 'anchor, folders [sibling names], decision group | separate (answers a current suggestion)',
    'texture_folder': 'folder (a current suggestion) or null, single_copies true | false'}


def _db(config):
    from .library_store import connect
    db = connect(config)
    db.execute(TABLE)
    return db


def _source(config, key):
    from .sources import get_source
    if not isinstance(key, str) or not key:
        raise ConfigError('Give library_folder, a key from list_packs')
    return get_source(config, key)


def _view(config, source):
    from .folder_view import connect
    from .library_view import _current
    current = _current(config, source)
    if current is None:
        raise ConfigError('This library folder has not been scanned yet')
    return connect(current)


def _bounded(payload, removable):
    from .mcp_assets import bounded
    return bounded(payload, CAP, removable)


def collapse(names, limit=12):
    """Names as short patterns: ``Car_11_{B,G,R}.obj``, ``Rock_{01..20}.fbx``, with the count of each pattern."""
    from .variant_groups import VALUES, candidate, natural
    groups = {}
    for name in names:
        path = PurePosixPath(name)
        match = candidate(path.stem, VALUES)
        key = (match[0], path.suffix.casefold()) if match else (path.stem, path.suffix.casefold())
        groups.setdefault(key, []).append(match[1] if match else None)
    lines = []
    for (base, suffix), values in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
        values = sorted({v for v in values if v}, key=natural)
        if not values:
            lines.append(f'{base}{suffix}' + (f' ×{len(groups[(base, suffix)])}' if len(groups[(base, suffix)]) > 1 else ''))
        elif all(v.isdigit() for v in values) and len(values) > 3:
            lines.append(f'{base}_{{{values[0]}..{values[-1]}}}{suffix} ({len(values)})')
        else:
            shown = ','.join(values[:8]) + (',…' if len(values) > 8 else '')
            lines.append(f'{base}_{{{shown}}}{suffix} ({len(values)})')
    return lines[:limit], max(0, len(lines) - limit)


def list_packs(config, args):
    """Packs across library folders (or one), those needing a structure first, with their reasons; paged."""
    from .pack_profiles import signals
    from .packs import names_of, structure
    from .sources import registry
    wanted = args.get('status')
    rows = []
    for source in registry(config)['sources']:
        if args.get('library_folder') and source['key'] != args['library_folder']:
            continue
        try:
            found, packs = signals(config, source['key']), structure(config, source)['packs']
        except ConfigError:
            continue
        names = names_of(config, source)
        for path, value in found.items():
            if wanted and value['status'] != wanted:
                continue
            rows.append({'library_folder': source['key'], 'pack': path,
                         'name': names.get(path) or (packs.get(path) or {}).get('name') or PurePosixPath(path).name or source['name'],
                         'status': value['status'], 'reasons': (value['needs'] + value['suggestions'])[:3]})
    order = {'needs_structure': 0, 'suggestions': 1, 'fine': 2}
    rows.sort(key=lambda r: (order[r['status']], r['library_folder'], r['pack']))
    cursor, limit = args.get('cursor', 0), args.get('limit', 20)
    page = rows[cursor:cursor + limit]
    payload = {'status': 'packs' if page else 'no_match', 'total': len(rows), 'packs': page,
               'next_cursor': cursor + limit if cursor + limit < len(rows) else None,
               'next_step': 'get_pack_outline(library_folder, path=pack) to look inside a pack, get_profile for its rules'}
    return _bounded(payload, 'packs')


def outline(config, args):
    """One folder level: its subfolders with counts and pack evidence, and its own files as collapsed names; paged."""
    from .folder_view import inside_sql
    from .packs import structure
    source = _source(config, args.get('library_folder'))
    path = (args.get('path') or '').strip('/')
    prefix = path + '/' if path else ''
    cursor, limit = args.get('cursor', 0), args.get('limit', PAGE)
    with closing(_view(config, source)) as view:
        detected = structure(config, source, view)
        start = len(prefix) + 1
        children = view.execute(
            'SELECT substr(path, ?, instr(substr(path, ?), \'/\') - 1) AS child, COUNT(*) FROM inventory '
            "WHERE substr(path, 1, ?) = ? AND instr(substr(path, ?), '/') > 0 GROUP BY child ORDER BY child",
            (start, start, len(prefix), prefix, start)).fetchall()
        if path and not children and not view.execute('SELECT 1 FROM inventory WHERE substr(path, 1, ?) = ? LIMIT 1',
                                                       (len(prefix), prefix)).fetchone():
            raise ConfigError(f'No folder "{path}" in this library folder; use names from the outline above it')
        folders = []
        for child, files in children[cursor:cursor + limit]:
            full = prefix + child
            where, params = inside_sql(full)
            kinds = dict(view.execute(f'SELECT kind, COUNT(*) FROM assets WHERE {where} GROUP BY kind', params).fetchall())
            pack = detected['packs'].get(full)
            folders.append({'name': child, 'files': files, 'assets': kinds,
                            **({'pack': [m['kind'] + ': ' + m['evidence'] for m in pack['markers']][:3] or [pack['basis']]} if pack else {})})
        own = [r[0][len(prefix):] for r in view.execute(
            "SELECT path FROM inventory WHERE substr(path, 1, ?) = ? AND instr(substr(path, ?), '/') = 0 ORDER BY path",
            (len(prefix), prefix, start))]
    names, more = collapse(own)
    holder = max((p for p in detected['packs'] if not p or path == p or path.startswith(p + '/')), key=len, default='')
    payload = {'status': 'outline', 'library_folder': source['key'], 'path': path, 'in_pack': holder,
               'folders': folders, 'folders_total': len(children),
               'next_cursor': cursor + limit if cursor + limit < len(children) else None,
               'files_here': len(own), 'file_patterns': names, 'more_patterns': more,
               'pattern_help': 'Name_{A,B} = Name_A and Name_B; Name_{01..20} = a numbered series'}
    return _bounded(payload, 'folders')


def get_profile(config, args):
    """A pack's rules, signals and latest version, with the rule vocabulary."""
    from .pack_profiles import current, history, signals
    source = _source(config, args.get('library_folder'))
    pack = args.get('pack', '')
    versions = history(config, source['key'], pack)
    payload = {'status': 'profile', 'library_folder': source['key'], 'pack': pack, 'rules': current(config, source, pack),
               'signals': signals(config, source['key']).get(pack), 'version': versions[0]['version'] if versions else 0,
               'pending_proposal': _pending(config, source, pack), 'vocabulary': VOCABULARY,
               'how': 'propose_profile replaces the whole rule list: send every rule the pack should keep. Paths are inside the pack.'}
    return _bounded(payload, 'rules')


def _pending(config, source, pack):
    with closing(_db(config)) as db:
        row = db.execute("SELECT id, utc FROM proposals WHERE folder_id=? AND pack=? AND state='pending'", (source['id'], pack)).fetchone()
    return {'id': row[0], 'utc': row[1]} if row else None


def propose(config, args, client=None):
    """Validate, measure and record an agent's profile; apply it at once when it needs no scan, else wait for the owner."""
    from .library_store import now
    from .pack_profiles import RESCAN, _latest, effect, validate
    source = _source(config, args.get('library_folder'))
    pack, rules = args.get('pack', ''), validate(args.get('rules'))
    seen = effect(config, source['key'], pack, rules)
    if not seen['changed']:
        return {'status': 'unchanged', 'reason': 'These rules are already the pack profile'}
    agent = {'by': 'agent', **({'agent': client['name']} if client and client.get('name') else {}),
             **({'note': args['note'].strip()[:SAY]} if isinstance(args.get('note'), str) and args['note'].strip() else {})}
    identifier = 'prop_' + uuid.uuid4().hex[:16]
    instant = not set(seen['changed']) & set(RESCAN)
    previous = _latest(config, source, pack)
    with closing(_db(config)) as db, db:
        db.execute("UPDATE proposals SET state='superseded', decided_utc=? WHERE folder_id=? AND pack=? AND state='pending'",
                   (now(), source['id'], pack))
        db.execute('INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', (identifier, source['id'], source['key'], pack,
                   json.dumps(rules), json.dumps(agent), json.dumps(seen), 'pending', now(), None, None, previous))
    if instant:
        result = decide(config, identifier, 'apply', approved='auto')
        return {'status': 'applied', 'proposal_id': identifier, 'version': result['version'], 'effect': seen['lines'],
                'note': 'Applied at once (no scan needed); the owner can undo it in the app.'}
    return {'status': 'pending', 'proposal_id': identifier, 'effect': seen['lines'],
            'note': 'Waits for the owner to Apply in the app (it rescans the library folder; nothing is processed).'}


def proposals(config, state='pending', limit=50):
    """Recent proposals (newest first) for the app's inbox and activity."""
    with closing(_db(config)) as db:
        rows = db.execute('SELECT id, folder_key, pack, rules, origin, effect, state, utc, decided_utc, version, previous FROM proposals '
                          + ('WHERE state=? ' if state else '') + 'ORDER BY utc DESC LIMIT ?', ((state, limit) if state else (limit,))).fetchall()
    return [{'id': r[0], 'library_folder': r[1], 'pack': r[2], 'rules': json.loads(r[3]), 'origin': json.loads(r[4]),
             'effect': json.loads(r[5]), 'state': r[6], 'utc': r[7], 'decided_utc': r[8], 'version': r[9], 'previous': r[10]} for r in rows]


def decide(config, identifier, decision, approved='owner'):
    """Apply, reject or undo a proposal. Apply re-measures nothing: the rules are validated again by ``apply``."""
    from .library_store import now
    from .pack_profiles import apply, revert
    with closing(_db(config)) as db:
        row = db.execute('SELECT folder_key, pack, rules, origin, state, previous FROM proposals WHERE id=?', (identifier,)).fetchone()
    if row is None:
        raise ConfigError('This proposal is not saved any more')
    key, pack, rules, origin, state, previous = row[0], row[1], json.loads(row[2]), json.loads(row[3]), row[4], row[5]
    if decision == 'undo':
        if state != 'applied':
            raise ConfigError('Only an applied proposal can be undone')
        result = revert(config, key, pack, previous, {'by': 'owner', 'undid': identifier}) if previous else \
            apply(config, key, pack, [], {'by': 'owner', 'undid': identifier})
        state = 'undone'
    elif state != 'pending':
        raise ConfigError(f'This proposal is already {state}')
    elif decision == 'reject':
        result, state = {'status': 'rejected', 'rescan': False}, 'rejected'
    elif decision == 'apply':
        result, state = apply(config, key, pack, rules, dict(origin, approved=approved, proposal=identifier)), 'applied'
    else:
        raise ConfigError('Choose apply, reject or undo')
    with closing(_db(config)) as db, db:
        db.execute('UPDATE proposals SET state=?, decided_utc=?, version=COALESCE(?, version) WHERE id=?',
                   (state, now(), result.get('version'), identifier))
    return {**result, 'proposal': identifier, 'state': state, 'library_folder': key, 'pack': pack}


def finish(config, args, client=None):
    """The agent's verdict that a pack's structure is right as it is now: its current signals are marked reviewed."""
    from .pack_profiles import review, signals
    source = _source(config, args.get('library_folder'))
    pack = args.get('pack', '')
    found = signals(config, source['key']).get(pack)
    if found is None:
        raise ConfigError('No such pack; use list_packs')
    if _pending(config, source, pack):
        return {'status': 'waiting', 'reason': 'A proposal for this pack waits for the owner; finish after they decide'}
    if found['status'] == 'fine':
        return {'status': 'fine', 'pack': pack}
    review(config, source['key'], pack, found['evidence'])
    return {'status': 'reviewed', 'pack': pack, 'reviewed_signals': found['needs'] + found['suggestions']}


def say(args):
    """A short note from the agent about what it is doing; it appears in the app's Agent activity."""
    message = args.get('message')
    if not isinstance(message, str) or not message.strip() or len(message) > SAY:
        raise ConfigError(f'message is text of up to {SAY} characters')
    return {'status': 'noted'}


def execute(config, name, args, client=None):
    handlers = {'list_packs': lambda: list_packs(config, args), 'get_pack_outline': lambda: outline(config, args),
                'get_profile': lambda: get_profile(config, args), 'propose_profile': lambda: propose(config, args, client),
                'finish_structure': lambda: finish(config, args, client), 'say': lambda: say(args)}
    return handlers[name]()


TOOLS = ('list_packs', 'get_pack_outline', 'get_profile', 'propose_profile', 'finish_structure', 'say')
WRITE = {'propose_profile', 'finish_structure', 'say'}
_KEY = {'type': 'string', 'maxLength': 128, 'description': 'A library folder key from list_packs.'}
_PACK = {'type': 'string', 'maxLength': 400, 'description': 'The pack folder inside the library folder ("" = the library folder itself).'}
_CURSOR = {'type': 'integer', 'minimum': 0, 'maximum': 1000000}
SCHEMAS = {
    'list_packs': {'type': 'object', 'additionalProperties': False, 'properties': {
        'library_folder': _KEY, 'status': {'type': 'string', 'enum': ['needs_structure', 'suggestions', 'fine']},
        'cursor': _CURSOR, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50}}},
    'get_pack_outline': {'type': 'object', 'required': ['library_folder'], 'additionalProperties': False, 'properties': {
        'library_folder': _KEY, 'path': {'type': 'string', 'maxLength': 400, 'description': 'A folder inside the library folder ("" = its top).'},
        'cursor': _CURSOR, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 60}}},
    'get_profile': {'type': 'object', 'required': ['library_folder', 'pack'], 'additionalProperties': False, 'properties': {
        'library_folder': _KEY, 'pack': _PACK}},
    'propose_profile': {'type': 'object', 'required': ['library_folder', 'pack', 'rules'], 'additionalProperties': False, 'properties': {
        'library_folder': _KEY, 'pack': _PACK, 'note': {'type': 'string', 'maxLength': SAY, 'description': 'Why, in one sentence, for the owner.'},
        'rules': {'type': 'array', 'maxItems': 500, 'items': {'type': 'object'},
                  'description': 'The whole rule list for the pack (see get_profile vocabulary); each rule may carry a short note.'}}},
    'finish_structure': {'type': 'object', 'required': ['library_folder', 'pack'], 'additionalProperties': False, 'properties': {
        'library_folder': _KEY, 'pack': _PACK}},
    'say': {'type': 'object', 'required': ['message'], 'additionalProperties': False, 'properties': {
        'message': {'type': 'string', 'maxLength': SAY, 'description': 'What you are doing now, for the owner watching the app.'}}}}
DESCRIPTIONS = {
    'list_packs': 'Packs in the library, those that need a structure first, with the reasons; paged (cursor).',
    'get_pack_outline': 'One folder level of a library folder: subfolders with file and asset counts and pack evidence, and '
                        'its own files as collapsed name patterns. Page with cursor; go deeper with path. Never a file dump.',
    'get_profile': 'A pack\'s current rules, structure signals, version and the rule vocabulary.',
    'propose_profile': 'Propose a pack\'s whole rule list. Rules that need no scan apply at once (the owner can undo); others '
                       'wait for the owner\'s Apply. Returns the effect (cards, packs, files skipped).',
    'finish_structure': 'Say a pack\'s structure is right as it is now; its current signals stop showing until they change.',
    'say': 'A short line about what you are doing, shown live in the owner\'s Agent activity.'}
