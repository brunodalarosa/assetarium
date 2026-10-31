"""The one-time library migration (decision 0023): copy, re-key, relink, verify; never re-render or re-describe."""
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

import pytest

from test_sources import managed, ready_source  # noqa: F401 -- fixtures
from local_asset_library import library_migration as migration, library_store, sources
from local_asset_library.config import ConfigError
from local_asset_library.incremental import checkpoint, ledger, working
from local_asset_library.library_migration import LEGACY_METADATA_DIR
from local_asset_library.membership import records


def legacify(config, source, settings=None):
    """Turn a folder's store data back into the old layout: a generated folder inside the source, old fingerprints."""
    scoped = sources.bound(config, source)
    legacy = Path(source['path']) / LEGACY_METADATA_DIR
    shutil.copytree(scoped.metadata_root, legacy)
    found = {'path': source['path'], 'metadata': str(legacy), 'id': source['id'], 'key': source['key']}
    work = working(migration.legacy_bound(config, found))
    for record in records(working(scoped)):
        for area in ('inspection', 'captions/corrections'):
            for path in config.library_store().joinpath(area).glob(record['asset_id'] + '*'):
                target = legacy / area / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                (shutil.copytree if path.is_dir() else shutil.copy2)(path, target)
    with closing(sqlite3.connect(legacy / 'library/jobs.sqlite')) as db:
        db.executescript('CREATE TABLE IF NOT EXISTS jobs(asset_id TEXT, stage TEXT, fingerprint TEXT, status TEXT, evidence TEXT, '
                         'updated TEXT, PRIMARY KEY(asset_id,stage)); CREATE TABLE IF NOT EXISTS history(sequence INTEGER PRIMARY KEY, '
                         'asset_id TEXT, stage TEXT, fingerprint TEXT, status TEXT, evidence TEXT, updated TEXT);')
        for record in records(work):
            old = migration.legacy_inspection_input(work, record)[3]
            checkpoint(db, record['asset_id'], 'inspection', old, 'complete',
                       {'fault_content': migration.legacy_stage_content(work, record, 'inspection')})
    (legacy / 'source.json').write_text(json.dumps({'schema_version': 1, 'id': source['id'], 'key': source['key'], **(settings or {})}))
    return found


@pytest.fixture
def old_install(managed, monkeypatch):
    """Two old sources with generated folders, an old registry and no store, as before decision 0023."""
    config, backend, one, two = managed
    ready_source(config, backend, one)
    sources.scan_source(config, two)
    published = {r['asset_id'] for r in records(config)}
    legacify(config, one)
    legacify(config, two, {'import_types': ['model_3d'], 'import_formats': ['gltf']})
    registry = {'schema_version': 1, 'revision': 'old', 'sources': [one, two], 'detached': []}
    (config.project_root / 'data/library/sources.json').write_text(json.dumps(registry))
    shutil.rmtree(config.library_store())
    sources._registry_file.cache_clear()
    from local_asset_library import source_storage
    monkeypatch.setattr(source_storage, 'receipt', lambda *args: {'totals': {'allocated_bytes': 0}})
    monkeypatch.setattr(migration, 'app_processes', lambda: [])
    return config, one, two, published


def yes(_):
    return True


def originals(root):
    return {str(p): p.read_bytes() for p in Path(root).rglob('*') if p.is_file() and LEGACY_METADATA_DIR not in p.parts}


def test_dry_run_plans_and_apply_imports_without_re_queuing(old_install):
    config, one, two, published = old_install
    assert migration.needed(config)['needed']
    # Before the migration the last published search stays usable, read only, with its previews.
    assert {r['asset_id'] for r in records(config)} == published
    item = next(r for r in records(config) if r['previews'])
    assert config.output_path('data', item['previews'][0]['path'][5:]).is_file()
    before = {s['key']: originals(s['path']) for s in (one, two)}
    (Path(two['path']) / 'Extra').mkdir()
    (Path(two['path']) / 'Extra/only.fbx').write_text('synthetic')
    (Path(two['path']) / 'Extra/sprite.png').write_bytes(b'\x89PNG')
    plan, path = migration.plan(config)
    assert path.exists() and not config.library_store().joinpath('library.sqlite').exists()  # A dry run writes the plan only.
    planned = {f['key']: f for f in plan['folders']}
    enroll = planned['two']['enroll']  # Images were off and only glTF was imported: both are enrolled now.
    assert enroll['images_previously_off'] == 1 and enroll['import_formats'] == ['gltf']
    assert enroll['other_format_models'] == 4 and enroll['proposed_exclusions'] == ['Extra']
    assert planned['one']['status'] == planned['two']['status'] == 'ready'
    receipt, path = migration.apply(config, plan, yes)
    assert {f['key']: f['status'] for f in receipt['folders']} == {'one': 'verified', 'two': 'verified'}, receipt
    sources._registry_file.cache_clear()
    assert [s['key'] for s in sources.registry(config)['sources']] == ['one', 'two']
    assert published <= {r['asset_id'] for s in sources.registry(config)['sources'] for r in records(working(sources.bound(config, s)))}
    # Results re-keyed into the ledger: nothing finished became pending again.
    assert receipt['folders'][0]['check']['newly_pending'] == {'inspection': [], 'caption': []}
    assert receipt['folders'][0]['rekeyed'].get('inspection:complete') == 3
    # The old folders are intact (copy, never move) and originals untouched.
    assert all((Path(s['path']) / LEGACY_METADATA_DIR / 'source.json').exists() for s in (one, two))
    assert {s['key']: originals(s['path']) for s in (one, two)}['one'] == before['one']
    assert not migration.needed(config)['needed']
    # Once per folder: a second run finds nothing to import.
    again, _ = migration.plan(config)
    assert {f['status'] for f in again['folders']} == {'already imported'}
    with pytest.raises(ConfigError, match='Nothing to import'):
        migration.apply(config, again, yes)


def test_nested_sources_join_a_named_library_folder_and_keep_their_ids(old_install):
    config, one, two, published = old_install
    parent = Path(one['path']).parent
    plan, _ = migration.plan(config, [str(parent)])
    assert {f['library_folder'] for f in plan['folders']} == {str(parent)}
    receipt, _ = migration.apply(config, plan, yes)
    assert all(f['status'] == 'verified' and f['joined'] == parent.name for f in receipt['folders']), receipt
    sources._registry_file.cache_clear()
    [folder] = sources.registry(config)['sources']
    assert folder['path'] == str(parent)
    assert published <= {r['asset_id'] for r in records(working(sources.bound(config, folder)))}


def test_a_moved_source_is_relinked_by_identity_and_a_shared_identity_is_refused(old_install, tmp_path):
    config, one, two, _ = old_install
    moved = tmp_path / 'other drive' / 'one'
    moved.parent.mkdir()
    shutil.move(one['path'], moved)
    plan, _ = migration.plan(config, search=[str(moved.parent)])
    found = next(f for f in plan['folders'] if f['key'] == 'one')
    assert found['relinked_from'] == one['path'] and found['path'] == str(moved)
    clone = tmp_path / 'clone'
    shutil.copytree(moved, clone)
    plan, _ = migration.plan(config, search=[str(moved.parent), str(clone)])
    assert {f['status'] for f in plan['folders'] if f['key'] == 'one'} == {'conflict'}
    shutil.rmtree(clone)
    plan, _ = migration.plan(config)  # Without --search the moved source is reported, not guessed.
    assert any(u['key'] == 'one' and '--search' in u['reason'] for u in plan['unmatched_registry'])


def test_a_fault_stays_in_its_folder_and_links_are_refused(old_install):
    config, one, two, _ = old_install
    (Path(two['path']) / LEGACY_METADATA_DIR / 'library/jobs.sqlite').write_bytes(b'not a database')
    target = Path(one['path']).parent / 'outside'
    target.mkdir()
    link = Path(one['path']) / LEGACY_METADATA_DIR / 'inspection/link'
    if os.name == 'nt':
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)
    plan, _ = migration.plan(config)
    receipt, _ = migration.apply(config, plan, yes)
    status = {f['key']: f for f in receipt['folders']}
    assert status['one']['status'] == 'faulty' and 'Links are not migrated' in status['one']['fault']
    assert status['two']['status'] == 'faulty'
    link.rmdir() if os.name == 'nt' else link.unlink()


def test_cleanup_is_refused_before_a_verified_import_and_asks_for_each_folder(old_install):
    config, one, two, _ = old_install
    with pytest.raises(ConfigError, match='No verified import'):
        migration.remove_old(config, yes)
    plan, _ = migration.plan(config)
    with pytest.raises(ConfigError, match='Cancelled'):
        migration.apply(config, plan, lambda _: False)
    assert not config.library_store().joinpath('library.sqlite').exists()
    migration.apply(config, plan, yes)
    asked = []
    removed = migration.remove_old(config, lambda text: asked.append(text) or 'one' in text)
    assert len(asked) == 2 and [Path(r['metadata']).parent.name for r in removed] == ['one']
    assert not (Path(one['path']) / LEGACY_METADATA_DIR).exists() and (Path(two['path']) / LEGACY_METADATA_DIR).exists()
    # The store keeps working without the old folder.
    sources._registry_file.cache_clear()
    assert sources.scan_source(config, sources.get_source(config, 'one'))['assets'] == 3


def _stale_failed_caption(config, source):
    """A failed description whose fingerprint was already stale before the migration: kept failed, never retried."""
    found = {'path': source['path'], 'metadata': str(Path(source['path']) / LEGACY_METADATA_DIR), 'id': source['id'], 'key': source['key']}
    work = working(migration.legacy_bound(config, found))
    record = records(work)[0]
    with closing(sqlite3.connect(Path(found['metadata']) / 'library/jobs.sqlite')) as db:
        evidence = {'error': 'synthetic', 'fault_content': migration.legacy_stage_content(work, record, 'caption')}
        checkpoint(db, record['asset_id'], 'caption', 'an older caption fingerprint', 'failed', evidence)
    return record['asset_id'], evidence


def test_every_folders_blender_probe_and_a_stale_fault_import_without_new_work(old_install):
    config, one, two, _ = old_install
    for number, source in enumerate((one, two)):  # Each old folder recorded its own Blender discovery.
        probe = Path(source['path']) / LEGACY_METADATA_DIR / 'inspection/blender-runtime.json'
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(json.dumps({'executable': f'blender-{number}'}))
    failed, _ = _stale_failed_caption(config, one)
    said = []
    receipt, _ = migration.apply(config, migration.plan(config)[0], yes, said.append)
    assert {f['key']: f['status'] for f in receipt['folders']} == {'one': 'verified', 'two': 'verified'}, receipt
    assert not config.library_store().joinpath('inspection/blender-runtime.json').exists()
    assert receipt['folders'][0]['rekeyed']['caption:stale'] == 1
    with closing(ledger(sources.bound(config, one))) as db:
        assert db.execute("SELECT status FROM jobs WHERE asset_id=? AND stage='caption'", (failed,)).fetchone() == ('failed',)
    assert any('Importing' in text for text in said) and any('Scanning' in text for text in said)


def test_a_rerun_imports_failed_folders_into_the_library_folder_that_now_holds_them(old_install):
    config, one, two, published = old_install
    parent = Path(one['path']).parent
    old_ledger = Path(two['path']) / LEGACY_METADATA_DIR / 'library/jobs.sqlite'
    kept = old_ledger.read_bytes()
    old_ledger.write_bytes(b'not a database')
    receipt, _ = migration.apply(config, migration.plan(config, [str(parent)])[0], yes)
    assert {f['key']: f['status'] for f in receipt['folders']} == {'one': 'verified', 'two': 'faulty'}, receipt
    old_ledger.write_bytes(kept)  # The fault is fixed; the second run takes only that folder.
    plan, _ = migration.plan(config, [str(parent)])
    assert {f['key']: f['status'] for f in plan['folders']} == {'one': 'already imported', 'two': 'ready'}
    receipt, _ = migration.apply(config, plan, yes)
    assert [(f['key'], f['status'], f['joined']) for f in receipt['folders']] == [('two', 'verified', parent.name)], receipt
    sources._registry_file.cache_clear()
    [folder] = sources.registry(config)['sources']
    assert folder['path'] == str(parent)
    assert published <= {r['asset_id'] for r in records(working(sources.bound(config, folder)))}


def test_an_unverified_import_is_checked_again_and_fixed_in_place(old_install, monkeypatch):
    config, one, two, _ = old_install
    failed, evidence = _stale_failed_caption(config, one)
    rekey = migration.rekey

    def before_the_fix(work, db, store=None):  # A stale fault kept its old identity, so the check saw new work.
        counts = rekey(work, db, store)
        with db:
            db.execute("UPDATE jobs SET evidence=? WHERE asset_id=? AND stage='caption'", (json.dumps(evidence), failed))
        return counts
    monkeypatch.setattr(migration, 'rekey', before_the_fix)
    receipt, _ = migration.apply(config, migration.plan(config)[0], yes)
    assert {f['key']: f['status'] for f in receipt['folders']} == {'one': 'unverified', 'two': 'verified'}
    assert receipt['folders'][0]['check']['newly_pending']['caption'] == [failed]
    monkeypatch.setattr(migration, 'rekey', rekey)
    plan, _ = migration.plan(config)
    assert {f['key']: f['status'] for f in plan['folders']} == {'one': 'recheck', 'two': 'already imported'}
    receipt, _ = migration.apply(config, plan, yes)
    [entry] = receipt['folders']
    assert (entry['key'], entry['status'], entry['rechecked']) == ('one', 'verified', True), receipt
    assert entry['updated_rows'] >= 1
    assert migration.migrated(config).keys() >= {str(Path(one['path']) / LEGACY_METADATA_DIR).casefold()}
