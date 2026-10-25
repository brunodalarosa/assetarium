"""Owner tags: many short words per asset, shared by the whole app (decision 0012).

Tags describe the asset itself, independent of any collection; a collection's
per-asset label is separate. One small atomic JSON file, written under the
collections lease so the app and agent servers never lose each other's edits.
"""
import re

from .config import ConfigError
from .gpu_queue import lease
from .publication import atomic_json, read_json

ID_PATTERN = r'asset_[0-9a-f]{32}'
TAG_LENGTH = 32
TAGS_PER_ASSET = 24


def path(config):
    return config.storage_root('data') / 'library/asset-tags.json'


def load(config):
    target = path(config)
    if not target.exists():
        return {'schema_version': 1, 'revision': 0, 'assets': {}}
    try:
        value = read_json(target)
    except (OSError, ValueError) as exc:
        raise ConfigError('Asset tags file is unreadable; it is kept unchanged for review: ' + str(exc)) from exc
    if value.get('schema_version') != 1 or not isinstance(value.get('assets'), dict):
        raise ConfigError('Asset tags file has an unknown format; it is kept unchanged for review')
    return value


def clean(tag):
    if not isinstance(tag, str):
        raise ConfigError('Tags must be text')
    value = ' '.join(tag.split())
    if not value or len(value) > TAG_LENGTH or any(ord(c) < 32 for c in value) or ',' in value:
        raise ConfigError(f'Tags are 1–{TAG_LENGTH} characters without commas')
    return value


def unique(tags):
    seen, result = set(), []
    for tag in map(clean, tags):
        if tag.casefold() not in seen:
            seen.add(tag.casefold())
            result.append(tag)
    if len(result) > TAGS_PER_ASSET:
        raise ConfigError(f'An asset can have at most {TAGS_PER_ASSET} tags')
    return result


def tags_for(config, identifier, value=None):
    return list((value or load(config))['assets'].get(identifier, []))


def change(config, asset_ids, add=(), remove=(), replace=None):
    """Add/remove tags on several assets, or replace one asset's whole list."""
    if not isinstance(asset_ids, list) or not asset_ids or len(asset_ids) > 200 or any(
            not isinstance(i, str) or not re.fullmatch(ID_PATTERN, i) for i in asset_ids):
        raise ConfigError('Give 1–200 asset IDs')
    add, removed = unique(add), {t.casefold() for t in unique(remove)}
    replacement = None if replace is None else unique(replace)
    with lease(config, 'tags', resource='collections'):
        value = load(config)
        for identifier in asset_ids:
            current = replacement if replacement is not None else [
                t for t in value['assets'].get(identifier, []) if t.casefold() not in removed] + add
            current = unique(current)
            if current:
                value['assets'][identifier] = current
            else:
                value['assets'].pop(identifier, None)
        value['revision'] = value.get('revision', 0) + 1
        atomic_json(path(config), value)
    return {'status': 'saved', 'tags': {i: value['assets'].get(i, []) for i in asset_ids}, 'revision': value['revision']}


def known(config, value=None):
    """Every tag in use with its asset count, for suggestions and the Tag filter."""
    counts = {}
    for tags in (value or load(config))['assets'].values():
        for tag in tags:
            name, count = counts.get(tag.casefold(), (tag, 0))
            counts[tag.casefold()] = (name, count + 1)
    return [{'tag': name, 'assets': count} for name, count in sorted(counts.values(), key=lambda t: t[0].casefold())]


def tagged(config, tag):
    wanted = clean(tag).casefold()
    return {i for i, tags in load(config)['assets'].items() if any(t.casefold() == wanted for t in tags)}
