"""Results keyed by their inputs, in the central library store (decision 0023).

A key hashes file content, dependency content with paths relative to the inspected file, settings and
code, never an asset ID, pack or source-prefixed path. Duplicates share a result; a moved file keeps
it. The index maps (stage, key) to the logical ``data/...`` path of a finished result.
"""
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import posixpath
import sqlite3

from .config import ConfigError

# Logical data/ areas whose results belong to the whole store, not one library folder.
RESULT_AREAS = ('inspection/', 'captions/', 'results/')
KEY_STAGES = ('inspection', 'caption')


def store_root(config):
    return config.library_store()


def shared_area(relative):
    return relative.startswith(RESULT_AREAS)


def relative_to(base, path):
    """``path`` relative to the folder ``base`` (both source-prefixed POSIX paths)."""
    return posixpath.relpath(path, base or '.')


def location_free(value, base, prefix):
    """``value`` with asset IDs dropped and source-prefixed paths made relative to ``base``."""
    if isinstance(value, dict):
        return {k: location_free(v, base, prefix) for k, v in value.items() if k not in {'asset_id', 'utc'}}
    if isinstance(value, list):
        return [location_free(v, base, prefix) for v in value]
    if isinstance(value, str) and prefix and value.startswith(prefix + '/'):
        return relative_to(base, value)
    return value


def first_sight_key(config, record):
    """The inspection key a not yet inspected copy of this asset has: without the textures Blender reported."""
    from .incremental import inspection_input
    fresh = dict(record, dependencies=[d for d in record.get('dependencies', []) if not d.get('inspection_version')])
    return inspection_input(config, fresh)[3]


def current_key(config, record, stage):
    from .incremental import caption_input, inspection_input
    return inspection_input(config, record)[3] if stage == 'inspection' else caption_input(config, record)


def result_path(stage, key):
    """Where a new result for ``key`` is written (logical, without ``data/``)."""
    return f'results/{stage}/{key[:2]}/{key}'


def _index(config):
    path = store_root(config) / 'results/index.sqlite'
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE IF NOT EXISTS results(stage TEXT, key TEXT, path TEXT, asset_id TEXT, utc TEXT,
                  PRIMARY KEY(stage, key))""")
    return db


def remember(config, stage, key, path, asset_id):
    """Record a finished result; the first producer of a key keeps it."""
    if stage not in KEY_STAGES or not path:
        return
    with closing(_index(config)) as db, db:
        db.execute('INSERT OR IGNORE INTO results VALUES (?,?,?,?,?)',
                   (stage, key, path, asset_id, datetime.now(timezone.utc).isoformat()))


def lookup(config, stage, key):
    """``{'path', 'asset_id'}`` of a finished result for ``key``, or None."""
    path = store_root(config) / 'results/index.sqlite'
    if not path.exists():
        return None
    with closing(_index(config)) as db:
        row = db.execute('SELECT path, asset_id FROM results WHERE stage=? AND key=?', (stage, key)).fetchone()
    return {'path': row[0], 'asset_id': row[1]} if row else None


def forget(config, stage, key):
    """Drop an index entry whose files turned out unusable; the files themselves stay as evidence."""
    path = store_root(config) / 'results/index.sqlite'
    if path.exists():
        with closing(_index(config)) as db, db:
            db.execute('DELETE FROM results WHERE stage=? AND key=?', (stage, key))


def logical(config, path):
    """The ``data/...`` reference of a generated file: store results first, then the folder's own data."""
    path = Path(path)
    for root in (config.metadata_root, store_root(config), config.storage_root('data')):
        if root and path.is_relative_to(root):
            return path.relative_to(root).as_posix()
    raise ConfigError('Generated file is outside the library store')


def translate(result, source_path):
    """A shared inspection result as seen from another file with the same inputs: its paths follow that file."""
    result = deepcopy(result)
    old, new = posixpath.dirname(result['source_path']), posixpath.dirname(source_path)
    moved = lambda path: posixpath.normpath(posixpath.join(new, relative_to(old, path))) if path else path
    for texture in (result.get('technical') or {}).get('textures', []):
        texture['path'] = moved(texture.get('path'))
    for row in result.get('sources', []):
        row['path'] = moved(row['path'])
    result['source_path'] = source_path
    return result


def adopt_inspection(config, record, key, cached):
    """Publish a finished 3D inspection another file with the same inputs produced; nothing renders."""
    from .incremental import inspection_input
    from .inspection import publish
    from .retrieval import preview_file
    asset, source, reason, current = inspection_input(config, record, recorded=key)
    if current != key:
        raise ConfigError('Inputs changed; the shared result does not apply')
    relative = cached['path'].removeprefix('data/')
    result = json.loads(config.output_path('data', relative + '/result.json').read_text(encoding='utf-8'))
    if result.get('status') != 'complete' or result.get('format') != source['format']:
        raise ConfigError('The shared result is not a finished inspection of this format')
    for view in result.get('previews', []):
        preview_file(config, {'path': f'data/{relative}/{view["filename"]}', 'sha256': view['sha256']})
    publish(config, asset, source, reason, translate(result, source['path']), key, relative)
    return {'status': 'complete', 'reused': cached['path'], 'reused_from': cached['asset_id']}


def adopt_caption(config, record, key, cached):
    """Publish a description generated for the same views; the model does not run."""
    from .captions import image_inputs, publish
    image_inputs(config, record)
    saved = json.loads(config.output_path('data', cached['path'].removeprefix('data/')).read_text(encoding='utf-8'))
    provenance = saved.get('provenance') or {}
    if saved.get('status') != 'complete' or provenance.get('fingerprint') != key:
        raise ConfigError('The shared description does not match these views')
    outcome = {k: v for k, v in saved.items() if k not in {'asset_id', 'provenance'}}
    publish(config, record['asset_id'], outcome, {**provenance, 'reused_from': cached['asset_id']})
    return {'status': 'complete', 'reused': cached['path'], 'reused_from': cached['asset_id'], 'attempts': outcome.get('attempts')}


def adopt(config, record, stage, key):
    """Reuse a finished result for ``key``, or None when there is none (or it is unusable, then it is forgotten)."""
    from .asset_structure import asset_type
    if stage not in KEY_STAGES or (stage == 'inspection' and asset_type(record) != 'model_3d'):
        return None
    cached = lookup(config, stage, key)
    if not cached:
        return None
    try:
        return (adopt_inspection if stage == 'inspection' else adopt_caption)(config, record, key, cached)
    except (OSError, ValueError, KeyError):
        forget(config, stage, key)  # Missing or changed files: the stage runs normally instead.
        return None


def reattach(work, identifiers):
    """At scan time, finished results with the same inputs fill in recognized assets (moved, carried over from a
    replaced folder, duplicated). Nothing renders or runs a model; a miss leaves the asset pending as before."""
    from .asset_structure import asset_type
    from .catalog import detail
    from .incremental import caption_input, checkpoint, inspection_input, ledger, stage_content
    if not identifiers or not (store_root(work) / 'results/index.sqlite').exists():
        return []
    filled = []
    with closing(ledger(work)) as db:
        for identifier in sorted(identifiers):
            record = detail(work, identifier)
            for stage in KEY_STAGES:
                if record['processing'].get(stage) == 'complete' or (stage == 'inspection' and asset_type(record) != 'model_3d'):
                    continue
                try:
                    key = inspection_input(work, record)[3] if stage == 'inspection' else caption_input(work, record)
                except (OSError, ValueError, KeyError):
                    continue
                if lookup(work, stage, key) is None:
                    continue
                outcome = adopt(work, record, stage, key)
                if outcome:
                    record = detail(work, identifier)
                    checkpoint(db, identifier, stage, current_key(work, record, stage), 'complete',
                               {**outcome, 'fault_content': stage_content(work, record, stage)})
                    filled.append((identifier, stage))
    return filled
