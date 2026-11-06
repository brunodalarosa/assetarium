import json
import pytest

from local_asset_library.publication import read_json
from local_asset_library.config import ConfigError
from test_sources import managed  # noqa: F401 (fixture)


def test_full_library_preservation_receipt_fits_bounded_reader(tmp_path):
    path = tmp_path / 'protected-before.json'
    hashes = {str(i).zfill(64): 'a' * 64 for i in range(10000)}
    path.write_text(json.dumps({'image_vectors': hashes}), encoding='utf-8')
    assert path.stat().st_size > 1024**2
    assert read_json(path)['image_vectors'] == hashes


def test_manifest_reader_still_refuses_oversized_input(tmp_path):
    path = tmp_path / 'oversized.json'
    path.write_bytes(b' ' * (4 * 1024**2 + 1))
    with pytest.raises(ConfigError, match='bounded size'):
        read_json(path)
    path.write_bytes(b'{}' + b' ' * (4 * 1024**2))
    assert read_json(path, 8 * 1024**2) == {}  # A caller's own bound, still a bound.
    with pytest.raises(ConfigError, match='bounded size'):
        read_json(path, 1024**2)


def test_rescan_reads_a_scan_cache_larger_than_the_manifest_bound(managed):
    from local_asset_library import sources
    config, _, one, _ = managed
    sources.scan_source(config, one)
    path = sources.bound(config, one).output_path('data', 'library/scan-cache.json')
    value = json.loads(path.read_text(encoding='utf-8'))
    # A pack with tens of thousands of files: entries for paths that no longer exist are dropped on rescan.
    value['files'].update({f'{one["key"]}/gone/{i:06d}.png': {'identity': [1, 2, 3, i], 'sha256': 'a' * 64}
                           for i in range(40000)})
    path.write_text(json.dumps(value), encoding='utf-8')
    assert path.stat().st_size > 4 * 1024**2
    sources.scan_source(config, one)
    assert path.stat().st_size < 4 * 1024**2 and not any('/gone/' in key for key in read_json(path)['files'])
