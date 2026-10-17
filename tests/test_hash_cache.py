"""Stat-identity hash reuse never hides a content change (decision 0004)."""
import hashlib
import os

import pytest

from local_asset_library import hash_cache
from local_asset_library.publication import verified_hash


@pytest.fixture
def record(tmp_path, monkeypatch):
    monkeypatch.setenv('LAL_HASH_CACHE', str(tmp_path / 'hashes.sqlite'))
    hash_cache.reset()
    yield tmp_path
    hash_cache.reset()


def test_recorded_hash_is_shared_across_processes_and_reused(record):
    path = record / 'model.obj'
    path.write_bytes(b'v 1 0 0')
    expected = hashlib.sha256(b'v 1 0 0').hexdigest()
    assert verified_hash(path) == expected
    hash_cache.reset()  # A new process starts with an empty memory but the same record.
    assert hash_cache.lookup(path, hash_cache.file_identity(path)) == expected


def test_content_change_with_restored_timestamps_is_rehashed(record):
    path = record / 'model.obj'
    path.write_bytes(b'v 1 0 0')
    stamp = path.stat()
    first = verified_hash(path)
    path.write_bytes(b'v 2 0 0')  # Same size.
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert path.stat().st_mtime_ns == stamp.st_mtime_ns
    assert verified_hash(path) == hashlib.sha256(b'v 2 0 0').hexdigest() != first


def test_fresh_audits_ignore_recorded_hashes(record, monkeypatch):
    path = record / 'model.obj'
    path.write_bytes(b'bytes')
    monkeypatch.setattr(hash_cache, 'lookup', lambda *args: 'recorded')
    assert verified_hash(path) == 'recorded'
    actual = hashlib.sha256(b'bytes').hexdigest()
    assert verified_hash(path, fresh=True) == actual
    hash_cache.require_fresh()
    assert verified_hash(path) == actual


def test_unusable_record_degrades_to_hashing(record):
    (record / 'hashes.sqlite').write_bytes(b'not a sqlite database' * 64)
    path = record / 'model.obj'
    path.write_bytes(b'bytes')
    assert verified_hash(path) == hashlib.sha256(b'bytes').hexdigest()
    with pytest.raises(FileNotFoundError):
        verified_hash(record / 'missing.obj')


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    from test_incremental import library
    monkeypatch.setenv('LAL_HASH_CACHE', str(tmp_path / 'hashes.sqlite'))
    hash_cache.reset()
    config, _ = library.__wrapped__(tmp_path)
    yield config
    hash_cache.reset()


def test_scanner_records_hashes_runtime_checks_reuse(seeded):
    from local_asset_library.catalog import walk_source
    rows = [r for r in walk_source(seeded) if r.get('sha256')]
    assert rows
    hash_cache.reset()
    for row in rows:
        path = seeded.source_file(row['path'])
        assert hash_cache.lookup(path, hash_cache.file_identity(path)) == row['sha256']
