"""Pack profiles: every answer about one pack's structure as one versioned set of rules (decisions 0023, 0024).

A profile is not a new store. Its rules are the owner's (or an approved agent's) answers that already steer scans and
views (packs, names, image kinds, exclusions, export groups, the texture folder) plus variant rules, scoped to one pack
with paths relative to it. The vocabulary is closed (``KINDS``): agents choose rules and parameters, never patterns.
Applying a profile replaces the pack's answers in one step and records a version, so any version can be restored;
an export is the same rules as a file with a fingerprint of the pack's file names. Nothing is written into a pack.
"""
from contextlib import closing
import json
from pathlib import PurePosixPath

from .catalog import digest
from .config import ConfigError

VERSION = 1
# Kinds a folder view applies at once (``folder_view.VIEW_ANSWERS``) or pack detection reads: they apply without waiting.
INSTANT = ('pack', 'pack_name', 'variant_axis', 'separate_descriptions')
# Kinds a scan applies (image classification, exclusions, export groups, texture recipes): they rescan, never process.
RESCAN = ('image_kind', 'exclude', 'engine_copy', 'export_group', 'texture_folder')
KINDS = INSTANT + RESCAN
ANSWERED = ('pack', 'pack_name', 'image_kind', 'variant_axis', 'separate_descriptions', 'engine_copy')
FIELDS = {'pack': {'folder', 'value'}, 'pack_name': {'value'}, 'image_kind': {'folder', 'value'},
          'variant_axis': {'folder', 'values'}, 'separate_descriptions': {'group'}, 'exclude': {'folder'},
          'engine_copy': {'folder', 'of'}, 'export_group': {'anchor', 'folders', 'decision'},
          'texture_folder': {'folder', 'single_copies'}}
IMPORT_MATCH = 0.8  # A profile file applies to a pack sharing at least this share of its file names.
NOTE = 200  # A rule may carry a short ``note`` (the agent's or owner's reason), shown with its effect.


def _relative(path, pack):
    """``path`` (library-folder relative) relative to ``pack``, or None outside it."""
    if not pack:
        return path
    if path == pack:
        return ''
    return path[len(pack) + 1:] if path.startswith(pack + '/') else None


def _absolute(folder, pack):
    return '/'.join(p for p in (pack, folder) if p)


def _folder(value, field='folder'):
    from .sources import validate_exclusion
    if value == '':
        return ''
    if not isinstance(value, str) or '*' in value:
        raise ConfigError(f'A rule {field} is a folder path inside the pack, like "Models/Unity FBX" ("" is the pack)')
    return validate_exclusion(value)


def validate(rules):
    """The rules in canonical form, or ConfigError naming the first rule that is not in the vocabulary."""
    from .variant_groups import validate_values
    if not isinstance(rules, list) or len(rules) > 500:
        raise ConfigError('A profile is a list of up to 500 rules')
    cleaned, seen = [], set()
    for number, rule in enumerate(rules, 1):
        try:
            if not isinstance(rule, dict) or rule.get('kind') not in KINDS:
                raise ConfigError('kind must be one of ' + ', '.join(KINDS))
            kind, note = rule['kind'], rule.get('note')
            extra = set(rule) - FIELDS[kind] - {'kind', 'note'}
            if extra or FIELDS[kind] - set(rule):
                raise ConfigError(f'{kind} takes ' + ', '.join(sorted(FIELDS[kind])) + ' (and an optional note)')
            if note is not None and (not isinstance(note, str) or len(note) > NOTE):
                raise ConfigError(f'note is text of up to {NOTE} characters')
            value = {'kind': kind}
            if kind == 'pack':
                if rule['value'] not in {'make_pack', 'merge'}:
                    raise ConfigError('pack value is make_pack or merge')
                value.update(folder=_folder(rule['folder']), value=rule['value'])
            elif kind == 'pack_name':
                if not isinstance(rule['value'], str) or not 0 < len(rule['value'].strip()) <= 120:
                    raise ConfigError('pack_name value is a name of up to 120 characters')
                value['value'] = rule['value'].strip()
            elif kind == 'image_kind':
                if rule['value'] not in {'texture', 'image'}:
                    raise ConfigError('image_kind value is texture or image')
                value.update(folder=_folder(rule['folder']), value=rule['value'])
            elif kind == 'variant_axis':
                value.update(folder=_folder(rule['folder']), values=validate_values(rule['values']))
            elif kind == 'separate_descriptions':
                group = _folder(rule['group'], 'group')
                if not group:
                    raise ConfigError('separate_descriptions group is a variant group key, like "Cars/Car_11"')
                value['group'] = group
            elif kind in {'exclude', 'engine_copy'}:
                value['folder'] = _folder(rule['folder'])
                if not value['folder']:
                    raise ConfigError(f'{kind} folder is a folder inside the pack, never the pack itself')
                if kind == 'engine_copy':
                    value['of'] = _folder(rule['of'], 'of')
            elif kind == 'export_group':
                folders = rule['folders']
                if (not isinstance(folders, list) or not 2 <= len(folders) <= 20
                        or any(not isinstance(f, str) or not f or '/' in f for f in folders)):
                    raise ConfigError('export_group folders are 2 to 20 sibling folder names')
                if rule['decision'] not in {'group', 'separate'}:
                    raise ConfigError('export_group decision is group or separate')
                value.update(anchor=_folder(rule['anchor'], 'anchor'), folders=sorted(folders), decision=rule['decision'])
            elif kind == 'texture_folder':
                if type(rule['single_copies']) is not bool or not (rule['folder'] is None or isinstance(rule['folder'], str)):
                    raise ConfigError('texture_folder takes a suggested folder (or null) and single_copies true or false')
                value.update(folder=None if rule['folder'] is None else _folder(rule['folder']), single_copies=rule['single_copies'])
            if note:
                value['note'] = note.strip()
        except ConfigError as exc:
            raise ConfigError(f'Rule {number}: {exc}') from None
        identity = _identity(value)
        if identity in seen:
            raise ConfigError(f'Rule {number}: another rule already sets this')
        seen.add(identity)
        cleaned.append(value)
    return sorted(cleaned, key=lambda r: (KINDS.index(r['kind']), json.dumps(r, sort_keys=True)))


def _identity(rule):
    """What a rule sets: two rules with one identity contradict each other."""
    kind = rule['kind']
    if kind in {'pack_name', 'texture_folder'}:
        return (kind,)
    if kind == 'export_group':
        return (kind, rule['anchor'], tuple(rule['folders']))
    if kind == 'separate_descriptions':
        return (kind, rule['group'])
    return ('exclude' if kind == 'engine_copy' else kind, rule['folder'])


def current(config, source, pack):
    """The pack's rules as saved now: answers, exclusions, export answers and the texture folder inside it."""
    from .library_store import answers
    from .sources import bound, excluded_folders, export_decisions, texture_folder
    rules = []
    saved = answers(config, source['id'])
    for answer in saved:
        relative = _relative(answer['path'], pack)
        if relative is None or answer['kind'] not in ANSWERED:
            continue
        kind, value = answer['kind'], answer['value']
        if kind == 'pack_name':
            if relative == '':
                rules.append({'kind': kind, 'value': value})
        elif kind == 'variant_axis':
            rules.append({'kind': kind, 'folder': relative, 'values': value})
        elif kind == 'separate_descriptions':
            if value and relative:
                rules.append({'kind': kind, 'group': relative})
        elif kind == 'engine_copy':
            rules.append({'kind': kind, 'folder': relative, 'of': value})
        else:
            rules.append({'kind': kind, 'folder': relative, 'value': value})
    copies = {r['folder'] for r in rules if r['kind'] == 'engine_copy'}
    scoped = bound(config, source)
    for pattern in excluded_folders(scoped):
        relative = _relative(pattern, pack)
        if relative and '*' not in pattern and relative not in copies:
            rules.append({'kind': 'exclude', 'folder': relative})
    for decision in export_decisions(scoped):
        relative = _relative(decision.get('anchor', ''), pack)
        if relative is not None:
            rules.append({'kind': 'export_group', 'anchor': relative, 'folders': sorted(decision['folders']), 'decision': decision['decision']})
    chosen = texture_folder(scoped)
    if chosen and (chosen['folder'] is None and pack == '' or chosen['folder'] is not None and _relative(chosen['folder'], pack) is not None):
        rules.append({'kind': 'texture_folder', 'folder': None if chosen['folder'] is None else _relative(chosen['folder'], pack),
                      'single_copies': chosen['single_copies']})
    return validate(rules)


def _lanes(before, after):
    """Which kinds change between two rule lists."""
    strip = lambda rules: {json.dumps({k: v for k, v in r.items() if k != 'note'}, sort_keys=True) for r in rules}
    changed = strip(before) ^ strip(after)
    return {json.loads(r)['kind'] for r in changed}


def apply(config, key, pack, rules, origin):
    """Make ``rules`` the pack's whole profile; returns the new version and whether a rescan must follow.

    ``origin``: ``{'by': 'owner' | 'agent' | 'import' | 'revert', 'agent'?: name, 'model'?: name, 'approved'?: 'auto' | 'owner'}``.
    Rescan rules that need a current suggestion (export groups, texture folder) are checked first; nothing is saved
    when one no longer matches.
    """
    from .library_store import replace_answers
    from .sources import get_source
    source = get_source(config, key)
    pack = _folder(pack, 'pack')
    rules = validate(rules)
    before = current(config, source, pack)
    changed = _lanes(before, rules)
    if not changed:
        return {'status': 'unchanged', 'version': _latest(config, source, pack), 'rescan': False, 'changed': []}
    plan = _rescan_plan(config, source, pack, before, rules) if changed & set(RESCAN) else None
    if not _latest(config, source, pack):
        _record(config, source, pack, before, {'by': 'earlier'})  # Version 1: how the pack stood before its first profile.
    rows = []
    for rule in rules:
        path = _absolute(rule.get('folder') or rule.get('group') or '', pack)
        if rule['kind'] == 'pack_name':
            rows.append((pack, 'pack_name', rule['value']))
        elif rule['kind'] == 'variant_axis':
            rows.append((path, 'variant_axis', rule['values']))
        elif rule['kind'] == 'separate_descriptions':
            rows.append((path, 'separate_descriptions', True))
        elif rule['kind'] == 'engine_copy':
            rows.append((path, 'engine_copy', rule['of']))
        elif rule['kind'] in {'pack', 'image_kind'}:
            rows.append((path, rule['kind'], rule['value']))
    replace_answers(config, source['id'], ANSWERED, pack, rows)
    if plan:
        plan()
    version = _record(config, source, pack, rules, origin)
    return {'status': 'saved', 'version': version, 'rescan': bool(changed & set(RESCAN + ('pack',))), 'changed': sorted(changed)}


def _rescan_plan(config, source, pack, before, rules):
    """Check the scan-applied rules against current suggestions; returns the function that saves them."""
    from .sources import (_change_source_settings, bound, excluded_folders, export_decisions, source_status, texture_folder)
    scoped = bound(config, source)
    status = source_status(config, source)
    excluded = [p for p in excluded_folders(scoped) if '*' in p or _relative(p, pack) is None]
    excluded += [_absolute(r['folder'], pack) for r in rules if r['kind'] in {'exclude', 'engine_copy'}]
    if len(set(excluded)) > 50:
        raise ConfigError('A library folder can exclude up to 50 folders')
    wanted = {(_absolute(r['anchor'], pack), tuple(r['folders'])): r['decision'] for r in rules if r['kind'] == 'export_group'}
    kept = [d for d in export_decisions(scoped) if _relative(d.get('anchor', ''), pack) is None
            or wanted.get((d['anchor'], tuple(sorted(d['folders'])))) == d['decision']]
    have = {(d['anchor'], tuple(sorted(d['folders']))) for d in kept}
    offered = {(s['anchor'], tuple(sorted(s['folders']))): s for s in status.get('export_suggestions', [])}
    for place, decision in wanted.items():
        if place in have:
            continue
        found = offered.get(place)
        if found is None:
            raise ConfigError(f'No current export suggestion for {", ".join(place[1])} in "{place[0] or "the library folder"}"; '
                              'scan again or leave this rule out')
        entry = {k: found[k] for k in ('id', 'anchor', 'folders', 'reference', 'names', 'name_manifest_sha256')}
        from .library_store import now
        kept.append(dict(entry, decision=decision, utc=now()))
    texture = next((r for r in rules if r['kind'] == 'texture_folder'), None)
    previous = texture_folder(scoped)
    inside = previous and (previous['folder'] is None and pack == '' or previous['folder'] is not None and _relative(previous['folder'], pack) is not None)
    choice = previous if previous and not inside else None
    if texture:
        folder = None if texture['folder'] is None else _absolute(texture['folder'], pack)
        unchanged = inside and previous['folder'] == folder and previous['single_copies'] == texture['single_copies']
        offered_folders = {item['folder'] for item in (status.get('texture_suggestion') or {}).get('folders', [])}
        if not unchanged and folder is not None and folder not in offered_folders:
            raise ConfigError(f'"{folder}" is not a current texture folder suggestion; scan again or leave this rule out')
        if not unchanged and folder is None and not texture['single_copies']:
            raise ConfigError('texture_folder needs a folder, single copies, or both')
        from .library_store import now
        choice = previous if unchanged else {'folder': folder, 'single_copies': texture['single_copies'], 'utc': now()}

    def save():
        def change(value):
            value['excluded_folders'] = list(dict.fromkeys(excluded))
            value['export_decisions'] = kept
            if choice is None:
                value.pop('texture_folder', None)
            else:
                value['texture_folder'] = choice
        _change_source_settings(config, source['key'], change, "Wait for this library folder's operation to finish before changing its packs")
    return save


def _latest(config, source, pack):
    from .library_store import connect, database_path
    if not database_path(config).exists():
        return 0
    with closing(connect(config)) as db:
        return db.execute('SELECT COALESCE(MAX(version), 0) FROM profiles WHERE folder_id=? AND pack=?', (source['id'], pack)).fetchone()[0]


def _record(config, source, pack, rules, origin):
    from .library_store import connect, now
    with closing(connect(config)) as db, db:
        version = db.execute('SELECT COALESCE(MAX(version), 0) + 1 FROM profiles WHERE folder_id=? AND pack=?', (source['id'], pack)).fetchone()[0]
        db.execute('INSERT INTO profiles VALUES (?,?,?,?,?,?)', (source['id'], pack, version, json.dumps(rules), json.dumps(origin), now()))
    return version


def pack_at(config, source, folder):
    """The detected pack holding ``folder`` (the deepest pack at or above it; '' for the library folder)."""
    from .packs import structure
    packs = structure(config, source)['packs']
    return max((p for p in packs if _relative(folder, p) is not None), key=len, default='')


def record_change(config, key, folder, origin):
    """After a single answer saved elsewhere (the folder panel, an export card), version the pack it belongs to."""
    from .sources import get_source
    source = get_source(config, key)
    pack = pack_at(config, source, folder)
    rules = current(config, source, pack)
    latest = _latest(config, source, pack)
    if latest and not _lanes(version_rules(config, key, pack, latest), rules):
        return latest
    return _record(config, source, pack, rules, origin)


def history(config, key, pack):
    """Every version of a pack's profile, newest first: number, origin, time and rule count."""
    from .library_store import connect, database_path
    from .sources import get_source
    source = get_source(config, key)
    if not database_path(config).exists():
        return []
    with closing(connect(config)) as db:
        rows = db.execute('SELECT version, rules, origin, utc FROM profiles WHERE folder_id=? AND pack=? ORDER BY version DESC',
                          (source['id'], pack)).fetchall()
    return [{'version': v, 'rules': len(json.loads(r)), 'origin': json.loads(o), 'utc': u} for v, r, o, u in rows]


def version_rules(config, key, pack, version):
    from .library_store import connect
    from .sources import get_source
    source = get_source(config, key)
    with closing(connect(config)) as db:
        row = db.execute('SELECT rules FROM profiles WHERE folder_id=? AND pack=? AND version=?', (source['id'], pack, version)).fetchone()
    if row is None:
        raise ConfigError(f'Version {version} of this pack profile is not saved')
    return json.loads(row[0])


def revert(config, key, pack, version, origin=None):
    """Restore an earlier version as a new version (the history keeps every step)."""
    return apply(config, key, pack, version_rules(config, key, pack, version), dict(origin or {'by': 'owner'}, reverted_to=version))


def _names(view, pack):
    """Pack-relative file names (lowercase), streamed from the folder view's inventory."""
    start = (pack + '/') if pack else ''
    for (path,) in view.execute('SELECT path FROM inventory WHERE substr(path, 1, ?) = ? ORDER BY path', (len(start), start)):
        yield path[len(start):].casefold()


def fingerprint(config, source, pack):
    """``{'sha256', 'files', 'names'}`` of the pack's file names, so a profile file finds its pack again elsewhere.

    The names (pack-relative, lowercase) let a copy with a few files more or fewer match partially (``match``).
    """
    import hashlib
    hashed, names = hashlib.sha256(), []
    with closing(open_view(config, source)) as opened:
        for name in _names(opened, pack):
            hashed.update(name.encode() + b'\n')
            names.append(name)
    return {'sha256': hashed.hexdigest(), 'files': len(names), 'names': names}


def export(config, key, pack):
    """The pack's profile as a file body: its rules, its name and a fingerprint of its file names."""
    from .packs import names_of
    from .sources import get_source
    source = get_source(config, key)
    rules = current(config, source, pack)
    latest = history(config, key, pack)
    return {'assetarium_profile': VERSION, 'pack': {'name': names_of(config, source).get(pack) or PurePosixPath(pack).name or source['name'],
            **fingerprint(config, source, pack)}, 'rules': rules, 'origin': latest[0]['origin'] if latest else {'by': 'heuristics'}}


def read_file(body):
    """A profile file's rules after checking its shape; the pack it belongs to is matched separately."""
    if not isinstance(body, dict) or body.get('assetarium_profile') != VERSION or not isinstance(body.get('pack'), dict):
        raise ConfigError('This is not an Assetarium pack profile file')
    return validate(body.get('rules'))


def match(config, key, pack, body):
    """How alike a profile file's pack and this pack are: shared file names over the larger name list (0 to 1)."""
    from .sources import get_source
    read_file(body)
    mine = fingerprint(config, get_source(config, key), pack)
    if mine['sha256'] == body['pack'].get('sha256'):
        return 1.0
    names = body['pack'].get('names')
    if not isinstance(names, list) or not names:
        return 0.0
    wanted, here = {n.casefold() for n in names if isinstance(n, str)}, set(mine['names'])
    return round(len(wanted & here) / max(len(wanted), len(here)), 3)


def open_view(config, source):
    """The folder view, or before the first scan the quick look's names snapshot (``quick_look.save``)."""
    from .folder_view import _open, connect
    from .library_view import _current
    from .quick_look import snapshot_path
    from .sources import bound
    work = _current(config, source)
    if work is not None:
        return connect(work)
    path = snapshot_path(bound(config, source))
    if not path.exists():
        raise ConfigError('This library folder has not been read yet')
    snapshot = _open(path)
    snapshot.snapshot = True
    return snapshot


def _inside(column, pack):
    from .folder_view import inside_sql
    return inside_sql(pack, column)


def effect(config, key, pack, rules):
    """What making ``rules`` the pack's profile would change, measured on its folder view (names only, bounded by the pack).

    Returns counts before and after (cards, variant groups, packs) and what a rescan would skip or reclassify, plus
    short sentences for the effect card. Nothing is saved.
    """
    from itertools import groupby
    from .folder_view import view_answers
    from .library_store import answers
    from .packs import detect
    from .sources import bound, get_source
    from .variant_groups import assign
    source = get_source(config, key)
    pack = _folder(pack, 'pack')
    rules = validate(rules)
    before = current(config, source, pack)
    outside = {path: value for kind, path, value in view_answers(bound(config, source))
               if kind == 'variant_axis' and _relative(path, pack) is None}
    axes = lambda chosen: {**outside, **{_absolute(r['folder'], pack): r['values'] for r in chosen if r['kind'] == 'variant_axis'}}
    where, params = _inside('folder', pack)
    with closing(open_view(config, source)) as view:
        rows = view.execute(f'SELECT asset_id, folder, name, kind FROM assets WHERE {where} ORDER BY folder, asset_id', params).fetchall()

        def cards(chosen):
            groups, members = 0, 0
            for _, chunk in groupby(rows, key=lambda r: r[1]):
                found, _ = assign(list(chunk), axes(chosen))
                groups += len({k for k, _, _ in found.values()})
                members += len(found)
            return len(rows) - members + groups, groups

        def count(folders, table, extra=''):
            total = 0
            for folder in folders:
                inside, values = _inside('path' if table == 'inventory' else 'folder', folder)
                total += view.execute(f'SELECT COUNT(*) FROM {table} WHERE {inside}{extra}', values).fetchone()[0]
            return total
        excluded = lambda chosen: {_absolute(r['folder'], pack) for r in chosen if r['kind'] in {'exclude', 'engine_copy'}}
        skipped = count(excluded(rules) - excluded(before), 'inventory')
        restored = count(excluded(before) - excluded(rules), 'inventory')
        kinds = lambda chosen: {(_absolute(r['folder'], pack), r['value']) for r in chosen if r['kind'] == 'image_kind'}
        reclassified = count({f for f, _ in kinds(rules) ^ kinds(before)}, 'assets', " AND kind IN ('image', 'material_texture')")
        prefix = (pack + '/') if pack else ''
        paths = [r[0] for r in view.execute('SELECT path FROM inventory WHERE substr(path, 1, ?) = ?', (len(prefix), prefix))]
        assets = [r[0][len(source['key']) + 1:] for r in view.execute(f'SELECT path FROM assets WHERE path IS NOT NULL AND {where}', params)]
    other = [a for a in answers(config, source['id'], 'pack') if _relative(a['path'], pack) is None]
    found = lambda chosen: sorted(detect(paths, assets, other + [{'path': _absolute(r['folder'], pack), 'value': r['value']}
                                                                 for r in chosen if r['kind'] == 'pack'])['packs'])
    (cards_before, groups_before), (cards_after, groups_after) = cards(before), cards(rules)
    packs_before, packs_after = found(before), found(rules)
    changed = _lanes(before, rules)
    lines = []
    many = lambda n, one, more: f'{n:,} {one if n == 1 else more}'
    if cards_before != cards_after:
        lines.append(f"{many(len(rows), 'asset', 'assets')} → {many(cards_after, 'card', 'cards')}, {groups_after:,} with variants "
                     f"(now {many(cards_before, 'card', 'cards')})")
    if packs_before != packs_after:
        lines.append(f"{len(packs_before):,} → {many(len(packs_after), 'pack', 'packs')} here")
    if skipped:
        lines.append(f"{many(skipped, 'file', 'files')} skipped by excluded folders (nothing is deleted)")
    if restored:
        lines.append(f"{many(restored, 'file', 'files')} included again")
    if reclassified:
        lines.append(f"{many(reclassified, 'image', 'images')} may change kind")
    if changed & {'export_group', 'texture_folder'}:
        lines.append('Export groups or the texture folder change on the next scan')
    return {'status': 'ready', 'pack': pack, 'assets': len(rows), 'cards': {'before': cards_before, 'after': cards_after},
            'groups': {'before': groups_before, 'after': groups_after}, 'packs': {'before': packs_before, 'after': packs_after},
            'excluded_files': skipped, 'restored_files': restored, 'reclassified_images': reclassified,
            'changed': sorted(changed), 'rescan': bool(changed & set(RESCAN + ('pack',))),
            'instant': not changed & set(RESCAN), 'lines': lines or ['Nothing changes']}


CLASHES = 3  # Same-name assets in different folders of one pack, from this many names on.
DEFAULT_SHARE, DEFAULT_MIN = 0.3, 10  # Images classified only by the default rule.


def _blank():
    return {'oversized': [], 'clashes': 0, 'clash_examples': [], 'default_images': 0, 'images': 0, 'texture_failures': 0,
            'export_suggestions': 0}


def signals(config, key):
    """Each pack's structure status with its evidence: ``fine``, ``suggestions`` or ``needs_structure``.

    Needs a structure: variant sets too big for one card, the same names in several folders, many images classified
    only by default, models failing on missing textures. Suggestions: unanswered duplicate export folders. A pack whose
    owner or agent marked these same signals reviewed (``review``) is ``fine``.
    """
    from .library_store import answers
    from .packs import structure
    from .sources import get_source, source_status
    source = get_source(config, key)
    try:
        opened = open_view(config, source)
    except ConfigError:
        return {}
    with closing(opened) as view:
        detected = structure(config, source, view)
        found = {path: _blank() for path in detected['packs']}
        entry = lambda folder: found.setdefault(detected['pack_of'].get(folder, ''), _blank())
        meta = dict(view.execute('SELECT key, value FROM meta'))
        for item in json.loads(meta.get('oversized', '[]')):
            entry(item['folder'])['oversized'].append(item)
        for folder, number in view.execute("SELECT folder, COUNT(*) FROM assets WHERE failed LIKE '%texture%' GROUP BY folder"):
            entry(folder)['texture_failures'] += number
        for folder, defaults, number in view.execute("SELECT folder, SUM(kind_basis = 'default'), COUNT(*) FROM assets "
                                                     "WHERE kind = 'image' GROUP BY folder"):
            entry(folder)['default_images'] += defaults or 0
            entry(folder)['images'] += number
        names = {}
        for name, folder in view.execute('SELECT name_key, folder FROM assets WHERE name_key IN '
                                         '(SELECT name_key FROM assets GROUP BY name_key HAVING COUNT(DISTINCT folder) > 1)'):
            names.setdefault((detected['pack_of'].get(folder, ''), name), set()).add(folder)
        for path, pack in detected['packs'].items():
            # A pack only because its name carries a version, inside a folder with its own pack evidence (a license, a
            # readme): most likely that pack's version folder.
            if path and pack['markers'] and all(m['kind'] == 'versioned_name' for m in pack['markers']):
                outer = next((a for a in _ancestors(path) if _marked(view, a)), None)
                if outer is not None:
                    found.setdefault(path, _blank())['version_of'] = outer
    for (pack, name), folders in names.items():
        if len(folders) > 1:
            value = found.setdefault(pack, _blank())
            value['clashes'] += 1
            if len(value['clash_examples']) < 3:
                value['clash_examples'].append(name)
    for suggestion in source_status(config, source).get('export_suggestions', []):
        anchor = suggestion.get('anchor', '')
        pack = next((p for p in sorted(found, key=len, reverse=True) if _relative(anchor, p) is not None), '')
        found.setdefault(pack, _blank())['export_suggestions'] += 1
    reviewed = {a['path']: a['value'] for a in answers(config, source['id'], 'structure_reviewed')}
    result = {}
    for pack, value in found.items():
        needs = []
        if value['oversized']:
            big = value['oversized'][0]
            needs.append(f"{len(value['oversized'])} name sets too big for one card (for example {big['base']}, {big['members']} assets)")
        if value['clashes'] >= CLASHES:
            needs.append(f"{value['clashes']} names repeat in several folders (for example {', '.join(value['clash_examples'])})")
        if value['images'] >= DEFAULT_MIN and value['default_images'] / value['images'] > DEFAULT_SHARE:
            needs.append(f"{value['default_images']} of {value['images']} images have no evidence of what they are")
        if value.get('version_of') is not None:
            needs.append(f"looks like a version folder of “{value['version_of'] or 'the library folder'}”, not a pack of its own")
        if value['texture_failures']:
            needs.append(f"{value['texture_failures']} models can’t find their textures")
        suggestions = [f"{value['export_suggestions']} duplicate export folder suggestions"] if value['export_suggestions'] else []
        evidence = digest([needs, suggestions])[:16]
        status = ('fine' if reviewed.get(pack) == evidence or not (needs or suggestions) else
                  'needs_structure' if needs else 'suggestions')
        result[pack] = {'pack': pack, 'status': status, 'needs': needs, 'suggestions': suggestions, 'evidence': evidence,
                        'reviewed': reviewed.get(pack) == evidence and bool(needs or suggestions)}
    return result


def _ancestors(path):
    parts = PurePosixPath(path).parts
    return ['/'.join(parts[:depth]) for depth in range(len(parts) - 1, 0, -1)]


def _marked(view, folder):
    """Whether a folder's own files carry pack markers other than a versioned name."""
    from .packs import markers
    prefix = folder + '/'
    names = [r[0][len(prefix):] for r in view.execute("SELECT path FROM inventory WHERE substr(path, 1, ?) = ? AND instr(substr(path, ?), '/') = 0",
                                                       (len(prefix), prefix, len(prefix) + 1))]
    return any(m['kind'] != 'versioned_name' for m in markers(folder, names))


def review(config, key, pack, evidence):
    """Mark a pack's current signals as reviewed (its structure is right as it is); new signals show again."""
    from .library_store import save_answer
    from .sources import get_source
    source = get_source(config, key)
    now = signals(config, key).get(pack)
    if now is None:
        raise ConfigError('This pack is not in the library folder any more')
    if now['evidence'] != evidence:
        raise ConfigError('This pack changed since its signals were shown; look at them again')
    save_answer(config, source['id'], pack, 'structure_reviewed', evidence)
    return {'status': 'saved', 'pack': pack}
