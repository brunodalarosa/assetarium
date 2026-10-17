"""Tests never read or write the project's shared hash record."""
import os

import pytest


@pytest.fixture(autouse=True, scope='session')
def isolated_hash_cache(tmp_path_factory):
    os.environ['LAL_HASH_CACHE'] = str(tmp_path_factory.mktemp('hash-cache') / 'file-hashes.sqlite')
    from local_asset_library import hash_cache
    hash_cache.reset()
    yield
    hash_cache.reset()
