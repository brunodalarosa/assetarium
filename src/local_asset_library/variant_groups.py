"""Variant groups: assets of one folder whose names differ only in a last token from a known set (change C).

``Car_11_R``, ``Car_11_G`` and ``Car_11_B`` are one group ``Car_11`` with the values R, G and B; ``Rock_01`` to
``Rock_20`` stay separate assets (a numbered series) unless a pack profile says otherwise. A group is never a guess
across folders, never larger than ``CAP`` (a bigger set is flagged, not shown as one card) and never merges records:
each variant keeps its own asset ID, previews and results. Groups are derived when a folder view is built, from the
names and the folder's ``variant_axis`` answers, so changing a rule never makes work pending.
"""
from pathlib import PurePosixPath
import re

CAP = 24
VALUES = ('letters', 'colors', 'materials', 'lod', 'numbers')
DEFAULT = ('letters', 'colors', 'materials', 'lod')
SEPARATOR = re.compile(r'[-_ .]+')
COLORS = {'red', 'green', 'blue', 'yellow', 'orange', 'purple', 'violet', 'pink', 'black', 'white', 'grey', 'gray', 'brown',
          'cyan', 'magenta', 'teal', 'gold', 'golden', 'silver', 'bronze', 'beige', 'dark', 'light', 'navy', 'lime', 'olive',
          'maroon', 'turquoise', 'crimson', 'rust'}
MATERIALS = {'wood', 'wooden', 'metal', 'metallic', 'stone', 'brick', 'glass', 'plastic', 'concrete', 'marble', 'iron', 'steel',
             'copper', 'leather', 'fabric', 'cloth', 'rubber', 'ceramic', 'clay', 'paper', 'bone', 'crystal', 'ice', 'sand', 'moss',
             'mossy', 'snow', 'snowy', 'rusty', 'painted', 'clean', 'dirty', 'old', 'new', 'broken', 'damaged'}
LOD = re.compile(r'^lod\d{1,2}$', re.I)
NUMBER = re.compile(r'^\d{1,4}$')


def axis_of(token):
    """Which value set a last name token belongs to, or None."""
    lowered = token.casefold()
    if LOD.match(token):
        return 'lod'
    if len(token) == 1 and token.isalpha():
        return 'letters'
    if lowered in COLORS:
        return 'colors'
    if lowered in MATERIALS:
        return 'materials'
    if NUMBER.match(token):
        return 'numbers'
    return None


def candidate(name, allowed=DEFAULT):
    """``(base, value, axis)`` when ``name`` ends in a token from an allowed set and keeps a base, else None."""
    tokens = [t for t in SEPARATOR.split(name) if t]
    if len(tokens) < 2:
        return None
    axis = axis_of(tokens[-1])
    if axis is None or axis not in allowed:
        return None
    base = name[:name.rfind(tokens[-1])].rstrip('-_ .')
    return (base, tokens[-1], axis) if base else None


def allowed_for(folder, rules):
    """The value sets of the nearest ``variant_axis`` answer at or above ``folder`` (``rules``: {path: [values]})."""
    parts = PurePosixPath(folder).parts if folder else ()
    for depth in range(len(parts), -1, -1):
        path = '/'.join(parts[:depth])
        if path in rules:
            return tuple(rules[path])
    return DEFAULT


def validate_values(values):
    """A ``variant_axis`` rule's value sets; an empty list turns variants off for that folder."""
    if not isinstance(values, list) or any(v not in VALUES for v in values) or len(set(values)) != len(values):
        from .config import ConfigError
        raise ConfigError('Variant values are a list from ' + ', '.join(VALUES) + ' (empty turns variants off)')
    return sorted(values, key=VALUES.index)


def natural(value):
    return [(0, int(part), '') if part.isdigit() else (1, 0, part.casefold()) for part in re.split(r'(\d+)', value) if part]


def shared_map(current):
    """``{variant asset_id: (representative asset_id, value)}`` for variants sharing their group's description.

    ``current`` is a library folder's catalog config (the one search vectors are built for); empty without a view.
    """
    from contextlib import closing
    from .config import ConfigError
    from .folder_view import connect
    if not current.source_key or current.metadata_root is None:
        return {}
    try:
        view = connect(current, fresh=True)
    except ConfigError:
        return {}
    with closing(view):
        return {r[0]: (r[1], r[2]) for r in view.execute(
            "SELECT a.asset_id, r.asset_id, a.variant FROM assets a JOIN assets r ON r.group_key = a.group_key "
            "AND r.representative = 1 WHERE a.description = 'shared'")}


def membership(config, record):
    """An asset's variant group from its library folder's view: key, its value, every member and whether it shares
    the representative's description; None when it is in no group or its folder has no view yet."""
    from contextlib import closing
    from .config import ConfigError
    from .folder_view import connect
    from .library_view import _current
    from .sources import registry
    if not config.sources_registry or not record.get('files'):
        return None
    source = next((s for s in registry(config)['sources'] if s['key'] == record['files'][0]['path'].split('/', 1)[0]), None)
    current = source and _current(config, source)
    if current is None:
        return None
    try:
        view = connect(current)
    except ConfigError:
        return None
    with closing(view):
        own = view.execute('SELECT group_key, variant, description FROM assets WHERE asset_id=?', (record['asset_id'],)).fetchone()
        if not own or not own[0]:
            return None
        members = view.execute('SELECT asset_id, name, variant, representative FROM assets WHERE group_key=? '
                               'ORDER BY representative DESC, name_key', (own[0],)).fetchall()
    from .library_store import answers
    first = next(m for m in members if m[3])
    separate = any(a['path'] == own[0] and a['value'] for a in answers(config, source['id'], 'separate_descriptions'))
    return {'group': own[0], 'key': source['key'], 'value': own[1], 'shared': own[2] == 'shared', 'separate': separate,
            'representative': {'asset_id': first[0], 'name': first[1]},
            'variants': [{'asset_id': m[0], 'name': m[1], 'value': m[2]} for m in members]}


def assign(rows, rules=None):
    """Group keys for ``rows`` of ``(asset_id, folder, name, kind)``; returns ``({asset_id: (key, value, first)}, oversized)``.

    ``first`` marks the representative (the first value in natural order, ``LOD0`` before ``LOD1``). Only models
    group; images keep their own evidence (identical bytes). ``oversized`` lists ``{folder, base, members}`` sets above
    ``CAP``, which stay separate assets and raise a "needs a structure" signal.
    """
    rules = rules or {}
    found = {}
    for asset_id, folder, name, kind in rows:
        if kind != 'model_3d':
            continue
        match = candidate(name, allowed_for(folder, rules))
        if match:
            base, value, _ = match
            found.setdefault((folder, base.casefold()), []).append((natural(value), asset_id, value, base))
    groups, oversized = {}, []
    for (folder, _), members in sorted(found.items()):
        if len(members) < 2:
            continue
        if len(members) > CAP:
            oversized.append({'folder': folder, 'base': members[0][3], 'members': len(members)})
            continue
        members.sort()
        key = (folder + '/' if folder else '') + members[0][3]
        for position, (_, asset_id, value, _) in enumerate(members):
            groups[asset_id] = (key, value, position == 0)
    return groups, oversized
