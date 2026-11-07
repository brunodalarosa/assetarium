"""A store written by a newer Assetarium is refused before anything changes (safe upgrades)."""
from contextlib import closing
import sqlite3
from types import SimpleNamespace

import pytest

from local_asset_library import incremental, library_store, result_store, retrieval
from local_asset_library.config import ConfigError
from local_asset_library.store_versions import checked


def fake_config(tmp_path):
    store = tmp_path / 'store'
    return SimpleNamespace(library_store=lambda: store, source_key='one', catalog_generation='g',
                           output_path=lambda *parts: tmp_path.joinpath(*parts))


OPENERS = {
    'library': (lambda c: library_store.connect(c), lambda c: library_store.database_path(c)),
    'results': (lambda c: result_store._index(c), lambda c: c.library_store() / 'results/index.sqlite'),
    'ledger': (lambda c: incremental.ledger(c), lambda c: c.library_store() / 'ledger.sqlite'),
    'search': (lambda c: retrieval.index_database(c), lambda c: c.output_path('data', 'embeddings/index.sqlite')),
}


@pytest.mark.parametrize('store', sorted(OPENERS))
def test_new_store_is_stamped_and_reopens(tmp_path, store):
    config = fake_config(tmp_path)
    opener, path = OPENERS[store]
    with closing(opener(config)):
        pass
    with closing(opener(config)) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1


@pytest.mark.parametrize('store', sorted(OPENERS))
def test_newer_store_is_refused_unchanged(tmp_path, store):
    config = fake_config(tmp_path)
    opener, path = OPENERS[store]
    target = path(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(target)) as db:
        db.execute('CREATE TABLE future(x)')
        db.execute('PRAGMA user_version=999')
    before = target.read_bytes()
    with pytest.raises(ConfigError, match='newer Assetarium.*Nothing was changed'):
        opener(config)
    assert target.read_bytes() == before


def test_unversioned_store_is_stamped_and_older_unknown_refused(tmp_path):
    with closing(sqlite3.connect(tmp_path / 'a.sqlite')) as db:
        checked(db, 'A', 3)
        assert db.execute('PRAGMA user_version').fetchone()[0] == 3
    with closing(sqlite3.connect(tmp_path / 'b.sqlite')) as db:
        db.execute('PRAGMA user_version=2')
    with pytest.raises(ConfigError, match='unknown format 2'):
        checked(sqlite3.connect(tmp_path / 'b.sqlite'), 'B', 3)


def newer_json(path):
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema_version': 2, 'future': True}), encoding='utf-8')
    return path.read_bytes()


def test_newer_owner_json_is_refused_unchanged(tmp_path):
    from local_asset_library import notifications, processing_queue, sources
    config = SimpleNamespace(**vars(fake_config(tmp_path)), project_root=tmp_path, metadata_root=tmp_path)
    cases = [(processing_queue.queue_path(config), lambda: processing_queue.load(config)),
             (notifications.path(config), lambda: notifications.load(config)),
             (tmp_path / 'data/source.json', lambda: sources._source_settings(config))]
    for path, load in cases:
        before = newer_json(path)
        with pytest.raises(ConfigError, match='newer Assetarium'):
            load()
        assert path.read_bytes() == before


def test_current_owner_json_still_loads(tmp_path):
    from local_asset_library import processing_queue
    config = fake_config(tmp_path)
    processing_queue.save(config, processing_queue.load(config))
    assert processing_queue.load(config)['schema_version'] == 1
