import json
import pytest

from local_asset_library.publication import read_json
from local_asset_library.config import ConfigError


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
