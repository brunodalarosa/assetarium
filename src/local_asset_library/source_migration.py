"""Journaled same-volume migration from the legacy combined asset root.

Original assets are only read. Existing individual results move without changing
their bytes; combined historical reports remain shared evidence and are also
partitioned where they contain source-specific JSON records.
"""
from contextlib import closing
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid

from .config import ConfigError
from .catalog import walk_source, file_hash, digest, encoded
from .publication import atomic_json, read_json
from .sources import (registry, bound, now, write_catalog, write_membership,
                      read_records, scan_source, aggregate, validate_directory)
from .incremental import working, ledger, checkpoint, inspection_input
from .source_operations import publish_source


def rows(config):
    path = config.output_path('data', 'catalog.sqlite')
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        return [json.loads(r[0]) for r in db.execute('SELECT record FROM inventory')]


def split_index(legacy, scoped, identifiers):
    from .retrieval import index_database
    source = legacy.output_path('data', 'embeddings/index.sqlite')
    with closing(index_database(scoped)) as destination, destination:
        if source.exists():
            with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as db:
                destination.executemany('INSERT INTO meta VALUES (?,?)', db.execute('SELECT * FROM meta').fetchall())
                destination.executemany('INSERT INTO jobs VALUES (?,?,?,?,?,?)',
                    [r for r in db.execute('SELECT * FROM jobs') if r[1] in identifiers])
                destination.executemany('INSERT INTO vectors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    [r for r in db.execute('SELECT * FROM vectors') if r[1] in identifiers])
        destination.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('pilot_ids', encoded(sorted(identifiers))))


def _partition(value, key, ownership):
    """Retain shared context and this source's entries in mixed JSON evidence."""
    if isinstance(value, dict):
        identifier = value.get('asset_id')
        if identifier in ownership and ownership[identifier] != key:
            return None
        result = {}
        for name, item in value.items():
            if name in ownership and ownership[name] != key:
                continue
            selected = _partition(item, key, ownership)
            if selected is not None:
                result[name] = selected
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, str) and item in ownership and ownership[item] != key:
                continue
            selected = _partition(item, key, ownership)
            if selected is not None:
                result.append(selected)
        return result
    return value


def migrate(legacy, config_path=None):
    if legacy.sources_registry:
        raise ConfigError('Sources are already configured; migration is not automatically repeated')
    from .source_storage import receipt
    from .gpu_queue import lease
    with lease(legacy, 'source-migration', timeout=0, resource='operations'):
        identifier = uuid.uuid4().hex
        evidence = legacy.project_root / 'data/library/source-migration' / identifier
        evidence.mkdir(parents=True, exist_ok=False)
        atomic_json(evidence / 'state.json', {'status': 'running', 'started': now()})
        before = receipt(legacy, 'migration-before-' + identifier)
        original = walk_source(legacy)
        atomic_json(evidence / 'originals-before.json', original)
        current = read_records(legacy)
        current_work = read_records(working(legacy)) or current
        old_rows, work_rows = rows(legacy), rows(working(legacy)) or rows(legacy)
        packs = sorted({r['pack_id'] for r in current})
        config = replace(legacy, source_root=legacy.project_root.parent / '.lal-managed-sources',
                         sources_registry=legacy.project_root / 'data/library/sources.json')
        if config.sources_registry.exists():
            raise ConfigError('A source registry already exists; migration evidence retained without overwriting it')
        settings = {'schema_version': 1, 'revision': uuid.uuid4().hex, 'sources': [], 'detached': []}
        for key in packs:
            root = validate_directory(config, str(legacy.source_root / key))
            metadata = root / 'metadata-lal'
            if metadata.exists():
                raise ConfigError('Existing metadata-lal needs review before migration: ' + str(metadata))
            settings['sources'].append({'id': uuid.uuid4().hex, 'key': key, 'name': key, 'path': str(root), 'enabled': True})
        atomic_json(config.sources_registry, settings)
        ownership = {r['asset_id']: r['pack_id'] for r in current + current_work}
        # Historical deleted assets still own their previously generated files.
        for path in (legacy.project_root / 'data/library/generations').glob('*/catalog.sqlite'):
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
                ownership.update({i: p for i, p in db.execute('SELECT asset_id,pack_id FROM assets') if p in packs})
        atomic_json(legacy.project_root / 'data/library/asset-sources.json', {'schema_version': 1, 'assets': ownership})
        by_key = {s['key']: s for s in settings['sources']}
        for source in settings['sources']:
            scoped = bound(config, source)
            atomic_json(scoped.metadata_root / 'source.json', {'schema_version': 1, 'id': source['id'], 'key': source['key']})
            for origin, destination, records, inventory in (
                    (legacy, replace(scoped, catalog_generation='migration'), current, old_rows),
                    (working(legacy), working(scoped), current_work, work_rows)):
                selected = [r for r in records if r['pack_id'] == source['key']]
                write_catalog(destination, [r for r in inventory if r['path'].startswith(source['key'] + '/')], selected)
                write_membership(destination, selected)
                split_index(origin, destination, {r['asset_id'] for r in selected})
            # The original published snapshot remains distinct from unfinished work.
            from .incremental import copy_database
            published = replace(scoped, catalog_generation='v_' + uuid.uuid4().hex)
            staging = replace(scoped, catalog_generation='migration')
            for relative in ('catalog.sqlite', 'embeddings/index.sqlite'):
                copy_database(staging.output_path('data', relative), published.output_path('data', relative))
            atomic_json(published.output_path('data','library/membership.json'), read_json(staging.output_path('data','library/membership.json')))
            atomic_json(scoped.output_path('data','library/active.json'), {'generation': published.catalog_generation})
            # Remove only known redundant staging files after the checked copy.
            for relative in ('catalog.sqlite','embeddings/index.sqlite','library/membership.json'):
                staging.output_path('data', relative).unlink()
            old_ledger = legacy.output_path('data','library/jobs.sqlite')
            ids = {r['asset_id'] for r in current_work if r['pack_id'] == source['key']}
            with closing(ledger(scoped)) as dest:
                if old_ledger.exists():
                    with closing(sqlite3.connect(old_ledger.as_uri()+'?mode=ro',uri=True)) as db, dest:
                        for table in ('jobs','history'):
                            records = db.execute('SELECT * FROM ' + table).fetchall()
                            offset = 0 if table == 'jobs' else 1
                            selected = [r for r in records if r[offset] in ids]
                            if selected:
                                dest.executemany('INSERT INTO ' + table + ' VALUES (' + ','.join('?' for _ in selected[0]) + ')', selected)
        faults, moved, distributed = [], 0, 0
        journal = (evidence / 'moves.jsonl').open('x', encoding='utf-8')
        # Explicitly named areas only. Application, benchmark and storage audit
        # artifacts remain centrally owned shared history.
        areas = ('inspection','captions','texture-repairs','overnight-descriptions','library/batches')
        try:
            for area in areas:
                root = legacy.project_root / 'data' / area
                if not root.exists():
                    continue
                for directory, dirs, files in os.walk(root, followlinks=False):
                    for name in dirs[:]:
                        candidate = Path(directory) / name
                        if candidate.is_symlink() or candidate.is_junction():
                            dirs.remove(name)
                            faults.append({'path':str(candidate),'reason':'Directory link excluded; preserved'})
                    for filename in files:
                        path = Path(directory) / filename
                        relative = path.relative_to(legacy.project_root/'data').as_posix()
                        match = re.search(r'asset_[0-9a-f]{32}', relative)
                        key = ownership.get(match[0]) if match else None
                        try:
                            if path.is_symlink():
                                raise ConfigError('File link excluded; original evidence retained')
                            if key:
                                scoped = bound(config, by_key[key])
                                destination = scoped.output_path('data', relative)
                                if not destination.is_relative_to(scoped.metadata_root) or destination.exists():
                                    raise ConfigError('Migration destination is outside metadata or already exists')
                                destination.parent.mkdir(parents=True, exist_ok=True)
                                with path.open('rb') as stream:
                                    sha = file_hash(stream)
                                stat = path.stat()
                                entry = {'source':str(path),'destination':str(destination),'sha256':sha,
                                         'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}
                                journal.write(encoded(dict(entry,status='planned'))+'\n');journal.flush()
                                path.rename(destination)
                                with destination.open('rb') as stream:
                                    if file_hash(stream) != sha:
                                        raise ConfigError('Moved file hash mismatch')
                                journal.write(encoded(dict(entry,status='moved'))+'\n')
                                moved += 1
                            elif path.suffix.lower() in {'.json','.jsonl'} and path.stat().st_size < 16*1024**2:
                                text = path.read_text(encoding='utf-8')
                                relevant = {ownership[i] for i in set(re.findall(r'asset_[0-9a-f]{32}',text)) if i in ownership}
                                if not relevant:
                                    continue
                                values = [json.loads(line) for line in text.splitlines() if line.strip()] if path.suffix == '.jsonl' else json.loads(text)
                                for source_key in relevant:
                                    destination = bound(config, by_key[source_key]).output_path('data','history/shared-reports/'+relative)
                                    atomic_json(destination.with_suffix(destination.suffix+'.json') if path.suffix == '.jsonl' else destination,
                                                _partition(values,source_key,ownership))
                                    distributed += 1
                        except (OSError, ValueError, KeyError) as exc:
                            faults.append({'path':str(path),'reason':str(exc),'status':'faulty'})
        finally:
            journal.close()
        classification = legacy.project_root/'docs/caption-review-classification.json'
        if classification.exists():
            value = json.loads(classification.read_text(encoding='utf-8'))
            for source in settings['sources']:
                atomic_json(bound(config,source).output_path('data','reviews/caption-classification.json'),
                            _partition(value,source['key'],ownership))
        # Rebind completed inspector checkpoints to the unchanged content under
        # the new path resolver. No Blender or model inference is performed.
        for source in settings['sources']:
            scoped = bound(config,source)
            with closing(ledger(scoped)) as db:
                for record in read_records(working(scoped)):
                    if record['processing'].get('inspection') != 'complete':
                        continue
                    try:
                        fp = inspection_input(working(scoped),record)[3]
                        old = db.execute("SELECT evidence FROM jobs WHERE asset_id=? AND stage='inspection'",(record['asset_id'],)).fetchone()
                        prior = json.loads(old[0]) if old else {}
                        checkpoint(db,record['asset_id'],'inspection',fp,'complete',dict(prior,migrated_without_inference=True))
                    except (OSError,ValueError,KeyError) as exc:
                        faults.append({'asset_id':record['asset_id'],'reason':str(exc),'status':'faulty'})
            scan_source(config,source)
        aggregate(config)
        after_original = walk_source(legacy)
        atomic_json(evidence/'originals-after.json',after_original)
        if original != after_original:
            faults.append({'reason':'Original asset inventory changed during migration','status':'faulty'})
        # Activate the new configuration only after the metadata and combined
        # catalog are in place. The original config is retained in the journal.
        if config_path is not None:
            text = config_path.read_text(encoding='utf-8')
            (evidence/'config-before.toml').write_text(text,encoding='utf-8')
            text = re.sub(r'schema_version\s*=\s*1', 'schema_version = 2', text, count=1)
            text = re.sub(r'\[source\][\s\S]*?(?=\n\[storage\])',
                          '[sources]\nregistry = "data/library/sources.json"\n', text, count=1)
            temporary = config_path.with_suffix('.toml.pending')
            temporary.write_text(text,encoding='utf-8');os.replace(temporary,config_path)
        after = receipt(config,'migration-after-'+identifier)
        report = {'status':'faulty' if faults else 'passed','sources':len(packs),'assets':len(current),
                  'moved_files':moved,'distributed_reports':distributed,'faults':faults,
                  'originals_unchanged':original==after_original,'before_allocated_bytes':before['totals']['allocated_bytes'],
                  'after_allocated_bytes':after['totals']['allocated_bytes'],
                  'additional_allocated_bytes':after['totals']['allocated_bytes']-before['totals']['allocated_bytes'],
                  'models_or_renders_generated':0,'completed_utc':now(),'evidence':str(evidence)}
        atomic_json(evidence/'state.json',report)
        atomic_json(legacy.project_root/'data/library/source-migration/latest.json',report)
        return config,report
