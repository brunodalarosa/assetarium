"""Per-publication read caches rebuild on any publication or source change."""
import os

from test_sources import managed, ready_source  # noqa: F401  (fixtures)
from local_asset_library import library_cache, sources
from local_asset_library.desktop import DesktopBridge
from local_asset_library.membership import records
from local_asset_library.retrieval import pilot_records


def test_records_are_reused_slim_and_rebuilt_after_publication(managed):
    config, backend, one, two = managed
    library_cache.clear()
    ready_source(config, backend, one)
    sources.aggregate(config)
    first = pilot_records(config)
    assert first is pilot_records(config)  # Unchanged publication: shared view, no reparse.
    assert first and all('variants' not in r and 'license_evidence' not in r for r in first)
    assert {r['asset_id'] for r in first} == {r['asset_id'] for r in records(config)}
    full = {r['asset_id']: r for r in records(config)}
    for record in first:
        assert set(record['technical'] or {}) <= set(library_cache.TECHNICAL)
        assert record['files'] == full[record['asset_id']]['files']
    ready_source(config, backend, two)
    sources.aggregate(config)
    second = pilot_records(config)
    assert second is not first and len(second) > len(first)


def test_publication_digest_recomputes_when_file_changes(tmp_path):
    path = tmp_path / 'catalog.sqlite'
    path.write_bytes(b'one')
    first = library_cache.file_digest(path)
    assert library_cache.file_digest(path) == first
    path.write_bytes(b'two-changed')
    os.utime(path, ns=(1, 1))
    assert library_cache.file_digest(path) != first


def test_unchanged_scan_keeps_status_and_change_tokens(managed):
    config, backend, one, two = managed
    sources.scan_source(config, one)
    status = sources.bound(config, one).output_path('data', 'library/source-status.json')
    before = status.stat().st_mtime_ns, status.read_text(encoding='utf-8')
    revision = sources.revision(config)
    bridge = DesktopBridge(config)
    try:
        tokens = bridge.changes()
        sources.scan_source(config, one)
        assert (status.stat().st_mtime_ns, status.read_text(encoding='utf-8')) == before
        assert sources.revision(config) == revision
        assert bridge.changes() == tokens
        sources.set_enabled(config, two['key'], False)
        changed = bridge.changes()
        assert changed['sources'] != tokens['sources'] and changed['library'] != tokens['library']
    finally:
        bridge._close()
