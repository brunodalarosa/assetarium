"""Explicit, receipt-backed KayKit glTF-only maintenance; never runs at startup."""
import argparse
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.catalog import detail, digest, encoded
from local_asset_library.config import ConfigError, load_config
from local_asset_library.gpu_queue import lease
from local_asset_library.incremental import (working, update_record, ledger, checkpoint,
    caption_input, run_caption, stage_content, CAPTION_PROMPT_VERSION)
from local_asset_library.maintenance_files import contained, tree_files, manifest, remove_manifest, remove_empty_parents
from local_asset_library.publication import atomic_json, read_json, generation, verified_hash
from local_asset_library.sources import (bound, get_source, registry, read_records, scan_source,
    aggregate, now, write_membership)
from local_asset_library.source_operations import publish_source, active_operation, state


def save(path, value):
    if path.exists():
        raise ConfigError('Existing maintenance receipt is immutable: ' + str(path))
    atomic_json(path, value)


def model_guard(record, failed=False):
    keys = ('files', 'dependencies', 'technical', 'previews', 'inspection_run', 'primary_inspection_path', 'owner_overlay')
    if not failed:
        keys += ('description', 'suggested_uses', 'caption_provenance', 'processing', 'embeddings')
    return digest({key: record.get(key) for key in keys})


def rows_guard(db_path, table, exclude_ids=(), images_only_ids=()):
    if not db_path.exists():
        return {}
    with closing(sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)) as db:
        columns = [r[1] for r in db.execute('PRAGMA table_info(' + table + ')')]
        ids = columns.index('asset_id')
        channel = columns.index('channel') if 'channel' in columns else None
        result = {}
        for row in db.execute('SELECT * FROM ' + table):
            if row[ids] in exclude_ids:
                continue
            if row[ids] in images_only_ids and channel is not None and row[channel] != 'image':
                continue
            result[row[0]] = digest([hashlib.sha256(v).hexdigest() if isinstance(v, bytes) else v for v in row])
        return result


def original_guard(scoped):
    result = {}
    def fail(exc):
        raise exc
    for directory, dirs, files in os.walk(scoped.source_root, followlinks=False, onerror=fail):
        for name in dirs[:]:
            path = Path(directory) / name
            if name.casefold() == 'metadata-lal':
                dirs.remove(name)
            elif path.is_symlink() or path.is_junction():
                raise ConfigError('Original tree contains a link; retain it for review')
        for name in files:
            path = Path(directory) / name
            if path.is_symlink():
                raise ConfigError('Original file is a link')
            stat = path.stat()
            result[path.relative_to(scoped.source_root).as_posix()] = {
                'sha256': verified_hash(path), 'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
    return result


def baseline(config, scoped, out):
    out.mkdir(parents=True, exist_ok=False)
    current = read_records(scoped)
    keep = [r for r in current if r['files'][0]['format'] in {'gltf', 'glb'}]
    keep_ids = {r['asset_id'] for r in keep}
    excluded = [r for r in current if r['asset_id'] not in keep_ids]
    failed = [r['asset_id'] for r in keep if r['processing']['caption'] == 'failed']
    excluded_ids = {r['asset_id'] for r in excluded}
    save(out / 'originals-before.json', original_guard(scoped))
    save(out / 'gltf-records-before.json', {r['asset_id']: model_guard(r, r['asset_id'] in failed) for r in keep})
    save(out / 'retired-imports.json', [{'asset_id': r['asset_id'], 'files': r['files'],
        'processing': r['processing']} for r in excluded])
    save(out / 'license-evidence-before.json', current[0].get('license_evidence', []))
    fault_ids = []
    for r in excluded:
        run = r.get('inspection_run') or {}
        if (run.get('source_faults') or run.get('errors') or r.get('stage_faults')
                or any(s in {'failed', 'partial', 'unsupported'} for s in r['processing'].values())):
            save(out / 'retired-fault-records' / (r['asset_id'] + '.json'), r)
            fault_ids.append(r['asset_id'])
    for r in keep:
        if r['asset_id'] in failed:
            save(out / 'caption-failures-before' / (r['asset_id'] + '.json'), r)
    kept_files = []
    for identifier in keep_ids:
        path = scoped.metadata_root / 'inspection' / identifier
        if path.exists():
            kept_files.extend(manifest(scoped.metadata_root, [path]))
    for folder in ('captions/corrections', 'captions/library'):
        path = scoped.metadata_root / folder
        if path.exists():
            for file in tree_files(scoped.metadata_root, path):
                if any(identifier in str(file) for identifier in keep_ids):
                    kept_files.extend(manifest(scoped.metadata_root, [file]))
    save(out / 'gltf-files-before.json', kept_files)
    combined = read_records(config)
    save(out / 'other-records-before.json', {r['asset_id']: digest(r) for r in combined if r['pack_id'] != scoped.source_key})
    index = config.output_path('data', 'embeddings/index.sqlite')
    save(out / 'protected-vectors-before.json', rows_guard(index, 'vectors', excluded_ids, failed))
    other_sources = {}
    for source in registry(config)['sources']:
        if source['key'] == scoped.source_key:
            continue
        other = bound(config, source)
        for cfg in (other, working(other)):
            for relative in ('catalog.sqlite', 'embeddings/index.sqlite', 'library/membership.json'):
                path = cfg.output_path('data', relative)
                if path.exists():
                    other_sources[str(path)] = verified_hash(path)
    save(out / 'other-source-files-before.json', other_sources)
    save(out / 'before.json', {'utc': now(), 'source_generation': generation(scoped),
        'combined_generation': generation(config), 'source_identity': read_json(scoped.metadata_root / 'source.json'),
        'retained_count': len(keep), 'removed_count': len(excluded), 'failed_caption_ids': failed,
        'retired_fault_ids': fault_ids, 'settings_sha256': verified_hash(ROOT / 'data/library/settings.json')})
    return {'retained': len(keep), 'excluded': len(excluded), 'failed_captions': len(failed), 'retained_fault_records': len(fault_ids)}


def check_preservation(config, scoped, out, include_combined=True):
    before = read_json(out / 'before.json')
    expected = read_json(out / 'gltf-records-before.json')
    failed = set(before['failed_caption_ids'])
    current = read_records(working(scoped))
    assert len(current) == before['retained_count']
    assert set(expected) == {r['asset_id'] for r in current}
    assert all({f['format'] for f in r['files']} <= {'gltf', 'glb'} for r in current)
    assert all(model_guard(r, r['asset_id'] in failed) == expected[r['asset_id']] for r in current)
    assert read_json(out / 'originals-before.json') == original_guard(scoped)
    for row in read_json(out / 'gltf-files-before.json'):
        path = scoped.metadata_root / row['path']
        assert path.stat().st_size == row['bytes'] and verified_hash(path) == row['sha256'], row['path']
    for path, sha in read_json(out / 'other-source-files-before.json').items():
        assert verified_hash(Path(path)) == sha, path
    assert verified_hash(ROOT / 'data/library/settings.json') == before['settings_sha256']
    if include_combined:
        assert {r['asset_id']: digest(r) for r in read_records(config) if r['pack_id'] != scoped.source_key} == read_json(out / 'other-records-before.json')
        retired = {r['asset_id'] for r in read_json(out / 'retired-imports.json')}
        assert rows_guard(config.output_path('data', 'embeddings/index.sqlite'), 'vectors', retired, failed) == read_json(out / 'protected-vectors-before.json')
    return {'status': 'passed', 'original_files': len(read_json(out / 'originals-before.json')),
            'gltf_assets': len(current), 'other_sources_unchanged': True}


def publish(config, scoped):
    publish_source(scoped)
    result = aggregate(config)
    scan_source(config, get_source(config, scoped.source_key))
    return result


def prepare(config, scoped, out):
    if (out / 'prepared.json').exists():
        raise ConfigError('This cleanup was already prepared; do not automatically rerun it')
    before = read_json(out / 'before.json')
    assert generation(scoped) == before['source_generation']
    identity = dict(before['source_identity'], import_formats=['gltf'])
    atomic_json(scoped.metadata_root / 'source.json', identity)
    status = scan_source(config, get_source(config, scoped.source_key))
    assert status['assets'] == before['retained_count']
    check_preservation(config, scoped, out, include_combined=False)
    with closing(sqlite3.connect(working(scoped).output_path('data', 'catalog.sqlite'))) as db:
        db.execute('VACUUM')
    result = publish(config, scoped)
    preservation = check_preservation(config, scoped, out)
    save(out / 'prepared.json', {'status': 'passed', 'utc': now(), 'publication': result, 'preservation': preservation})
    return {'publication': result, 'preservation': preservation}


def retry(config, scoped, out):
    from local_asset_library.caption_backend import QwenBackend
    from local_asset_library.captions import image_inputs
    from local_asset_library.retrieval import source_check
    before = read_json(out / 'before.json')
    assert (out / 'prepared.json').exists()
    work = working(scoped)
    backend = None
    outcomes = []
    try:
        with lease(config, 'batch-kaykit-caption-retry', timeout=30):
            for identifier in before['failed_caption_ids']:
                done = out / 'caption-retry-outcomes' / (identifier + '.json')
                intent = out / 'caption-retry-intents' / (identifier + '.json')
                if done.exists():
                    outcomes.append(read_json(done))
                    continue
                if intent.exists():
                    raise ConfigError('Interrupted caption attempt retained; explicit review is required before another attempt')
                record = detail(work, identifier)
                assert record['processing']['caption'] == 'failed'
                source_check(work, record)
                image_inputs(work, record)
                if backend is None:
                    backend = QwenBackend(scoped, json.loads((ROOT / 'docs/caption-model.json').read_text(encoding='utf-8')))
                fingerprint = caption_input(work, record, prompt_version=CAPTION_PROMPT_VERSION)
                save(intent, {'asset_id': identifier, 'utc': now(), 'fingerprint': fingerprint,
                    'authorization': 'Owner approved one targeted attempt per failed KayKit glTF caption; previous evidence retained.'})
                print('Caption retry ' + str(len(outcomes) + 1) + '/' + str(len(before['failed_caption_ids'])) + ': ' + record['display_name'], flush=True)
                outcome = run_caption(work, record, fingerprint, backend)
                updated = detail(work, identifier)
                if updated.get('stage_faults', {}).get('caption') and outcome['status'] == 'complete':
                    updated['stage_faults'].pop('caption')
                    update_record(work, updated)
                outcome.update(asset_id=identifier, fault_content=stage_content(work, updated, 'caption'),
                               maintenance_run=out.name, previous_evidence=str(out / 'caption-failures-before' / (identifier + '.json')))
                with closing(ledger(scoped)) as db:
                    checkpoint(db, identifier, 'caption', fingerprint, outcome['status'], outcome)
                save(done, outcome)
                outcomes.append(outcome)
    finally:
        if backend is not None:
            backend.close()
    summary = {'status': 'complete', 'attempted': len(outcomes),
        'complete': sum(r['status'] == 'complete' for r in outcomes), 'failed': sum(r['status'] != 'complete' for r in outcomes)}
    save(out / 'caption-retry-summary.json', summary)
    return summary


def embeddings(config, scoped, out):
    from local_asset_library.embedding_backend import EmbeddingBackend
    from local_asset_library.library_index import index_library
    assert (out / 'caption-retry-summary.json').exists()
    with lease(config, 'batch-kaykit-text-embeddings', timeout=30):
        backend = EmbeddingBackend(scoped)
        result = index_library(working(scoped), backend, limit=1000, description_only=True)
    save(out / 'embeddings.json', result)
    publication = publish(config, scoped)
    preservation = check_preservation(config, scoped, out)
    save(out / 'published.json', {'publication': publication, 'preservation': preservation})
    return {'processed': result['processed'], 'publication': publication, 'preservation': preservation}


def cleanup(config, scoped, out):
    assert (out / 'published.json').exists()
    if (out / 'cleanup-plan.json').exists():
        raise ConfigError('Cleanup already planned; retained progress must be reviewed before a rerun')
    before = read_json(out / 'before.json')
    check_preservation(config, scoped, out)
    retired = {r['asset_id'] for r in read_json(out / 'retired-imports.json')}
    root = scoped.metadata_root
    targets = []
    for identifier in retired:
        for relative in ('inspection/' + identifier, 'captions/library/' + identifier, 'captions/corrections/' + identifier + '.json'):
            path = root / relative
            if path.exists():
                targets.append(path)
    # Fault records and their full generated evidence are saved separately from
    # the removed imports. All moves are individual, checked generated files.
    for identifier in before['retired_fault_ids']:
        source = root / 'inspection' / identifier
        if source.exists():
            for path in tree_files(root, source):
                target = out / 'retired-fault-files' / path.relative_to(root)
                contained(ROOT, target)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise ConfigError('Fault evidence destination already exists')
                os.replace(contained(root, path), target)
    source_generations = root / 'library/generations'
    for directory in source_generations.iterdir():
        if directory.is_dir() and directory.name not in {'work', generation(scoped)}:
            path = directory / 'catalog.sqlite'
            if path.exists():
                with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
                    ids = {r[0] for r in db.execute('SELECT asset_id FROM assets')}
                if ids & retired:
                    targets.append(directory)
    source_rows = manifest(root, targets)
    # Retire only derived combined snapshots containing the removed KayKit IDs.
    # Every other source's authoritative snapshots and the new combined rows
    # and vectors were verified unchanged before this retirement.
    shared_targets, retired_generations = [], set()
    for directory in (ROOT / 'data/library/generations').iterdir():
        if directory.is_dir() and directory.name not in {'work', generation(config)}:
            path = directory / 'catalog.sqlite'
            if path.exists():
                with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
                    ids = {r[0] for r in db.execute('SELECT asset_id FROM assets WHERE pack_id=?', (scoped.source_key,))}
                if ids & retired:
                    shared_targets.append(directory)
                    retired_generations.add(directory.name)
    for path in (ROOT / 'data/library/combined-publications').glob('*.json'):
        if read_json(path).get('generation') in retired_generations:
            shared_targets.append(path)
    shared_rows = manifest(ROOT, shared_targets)
    save(out / 'cleanup-plan.json', {'source_root': str(root.resolve()), 'source': source_rows,
        'project_root': str(ROOT.resolve()), 'derived_publications': shared_rows,
        'fault_records_preserved': before['retired_fault_ids']})
    results = {'source': remove_manifest(root, source_rows), 'derived_publications': remove_manifest(ROOT, shared_rows)}
    results['empty_directories'] = {'source': remove_empty_parents(root, source_rows),
                                    'derived_publications': remove_empty_parents(ROOT, shared_rows)}
    # Keep fault history, retire successful per-import job metadata, and shrink
    # the active ledger without touching records for retained glTF assets.
    with closing(ledger(scoped)) as db, db:
        db.executemany('DELETE FROM jobs WHERE asset_id=?', [(identifier,) for identifier in retired])
        db.executemany("DELETE FROM history WHERE asset_id=? AND status NOT IN ('failed','unsupported','partial')", [(identifier,) for identifier in retired])
    with closing(sqlite3.connect(root / 'library/jobs.sqlite')) as db:
        db.execute('VACUUM')
    faults = (results['source']['faults'] + results['derived_publications']['faults']
              + results['empty_directories']['source']['faults'] + results['empty_directories']['derived_publications']['faults'])
    results.update(status='faulty' if faults else 'passed', faults=faults, utc=now(),
        bytes_unlinked=sum(r['bytes'] for r in source_rows + shared_rows if r['path'] in results['source']['removed'] + results['derived_publications']['removed']))
    save(out / 'cleanup.json', results)
    return {'status': results['status'], 'files_removed': len(results['source']['removed']) + len(results['derived_publications']['removed']),
            'logical_bytes_unlinked': results['bytes_unlinked'], 'faults': faults}


def finish_empty(config, scoped, out):
    """Remove empty containers left when fault evidence moved before pruning."""
    assert read_json(out / 'cleanup.json')['status'] == 'passed'
    receipt = out / 'empty-directories.json'
    if receipt.exists():
        raise ConfigError('Empty-directory cleanup already has a receipt')
    root = scoped.metadata_root
    targets = [root / 'inspection' / r['asset_id'] for r in read_json(out / 'retired-imports.json')]
    targets += list((root / 'library/generations').glob('scan_*'))
    removed, faults = [], []
    for target in targets:
        if not target.exists():
            continue
        try:
            if tree_files(root, target):
                raise ConfigError('Unexpected files retained in a retired container; no file retry or deletion')
            for directory, _, _ in os.walk(target, topdown=False, followlinks=False):
                path = contained(root, Path(directory))
                if not any(path.iterdir()):
                    path.rmdir()
                    removed.append(path.relative_to(root).as_posix())
        except (OSError, ValueError) as exc:
            faults.append({'path': str(target), 'status': 'faulty', 'reason': str(exc)})
    result = {'status': 'faulty' if faults else 'passed', 'removed': removed, 'faults': faults, 'files_deleted': 0}
    save(receipt, result)
    return {'status': result['status'], 'empty_directories_removed': len(removed), 'faults': faults}


def verify(config, scoped, out):
    preserved = check_preservation(config, scoped, out)
    source = get_source(config, scoped.source_key)
    before = [r for r in read_records(working(scoped))]
    path = working(scoped).output_path('data', 'catalog.sqlite')
    old_hash = verified_hash(path)
    statuses = [scan_source(config, source), scan_source(config, source)]
    assert read_records(working(scoped)) == before
    assert verified_hash(path) == old_hash
    assert not statuses[-1]['pending'] and not statuses[-1]['removed']
    from local_asset_library.desktop_service import DesktopService
    from local_asset_library.mcp_assets import AssetService
    from local_asset_library.interactive_preview import InteractivePreviewService
    service = DesktopService(scoped)
    browser = service.browse()
    assert browser['total_count'] == 1492
    sample = next(r for r in before if r['display_name'] == 'arch_blue')
    response = service.asset(sample['asset_id'])
    assert response['payload']['usable'] and response['image']
    preview = InteractivePreviewService(service)
    ready = preview.prepare(sample['asset_id'], 'gltf', generation(scoped))
    assert ready['status'] == 'ready', ready
    preview.release(ready['ticket'])
    payload, image, _ = AssetService(scoped).execute('get_asset', {'asset_id': sample['asset_id'], 'include_metadata': True, 'include_preview': True})
    assert payload['usable'] and image and len(encoded(payload)) <= 16000
    search, _, _ = service.execute('search_assets', {'query': 'arch_blue', 'mode': 'keyword', 'limit': 5})
    assert sample['asset_id'] in {r['asset_id'] for r in search['results']}
    for cfg in (working(scoped), scoped, config):
        for relative in ('catalog.sqlite', 'embeddings/index.sqlite'):
            with closing(sqlite3.connect(cfg.output_path('data', relative).as_uri() + '?mode=ro', uri=True)) as db:
                assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    result = {'status': 'passed', 'utc': now(), 'preservation': preserved,
        'assets': len(before), 'caption_complete': sum(r['processing']['caption'] == 'complete' for r in before),
        'caption_failed': sum(r['processing']['caption'] == 'failed' for r in before),
        'stable_rescans': True, 'detail_and_image': True, 'interactive_package_ready': True,
        'keyword_search': True, 'sqlite_integrity': True,
        'sample_asset': sample['asset_id'], 'agent_detail_characters': len(encoded(payload))}
    save(out / ('verification-' + uuid.uuid4().hex + '.json'), result)
    return result


def semantic(config, scoped, out):
    from local_asset_library.embedding_backend import EmbeddingBackend
    from local_asset_library.mcp_assets import AssetService
    with lease(config, 'search-kaykit-verification', timeout=30):
        backend = EmbeddingBackend(scoped)
        payload, _, evidence = AssetService(scoped, backend=backend).execute(
            'search_assets', {'query': 'blue curved arch', 'mode': 'combined', 'limit': 5})
    ids = {r['asset_id'] for r in read_records(scoped)}
    assert payload['results'] and all(r['asset_id'] in ids for r in payload['results'])
    result = {'status': 'passed', 'mode': 'combined', 'actual_gpu_inference': True,
              'results': payload['results'], 'generation': generation(scoped),
              'excluded': evidence.get('excluded', []), 'utc': now()}
    save(out / 'semantic-search.json', result)
    return {'status': 'passed', 'mode': 'combined', 'results': len(payload['results']), 'actual_gpu_inference': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('baseline', 'prepare', 'retry', 'embeddings', 'cleanup', 'finish_empty', 'verify', 'semantic'))
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    if not args.run.startswith('kaykit-gltf-') or not args.run.replace('-', '').isalnum():
        parser.error('Use a unique kaykit-gltf- run name')
    config = load_config(ROOT / 'config.example.toml', ROOT)
    scoped = bound(config, get_source(config, 'KayKit_Free_pack'))
    if scoped.source_root != Path('C:/BrunoOS/Game assets/KayKit_Free_pack'):
        raise ConfigError('This approved cleanup is limited to the configured KayKit free pack')
    out = ROOT / 'data/library/maintenance' / args.run
    contained(ROOT, out)
    if args.action == 'semantic':
        result = semantic(config, scoped, out)  # Pinned read-only retrieval remains available during cleanup.
    else:
        with lease(config, 'kaykit-gltf-maintenance', resource='operations', timeout=3):
            if active_operation(scoped) or active_operation(config):
                raise ConfigError('Wait for the current source operation to finish before maintenance')
            result = globals()[args.action](config, scoped, out)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
