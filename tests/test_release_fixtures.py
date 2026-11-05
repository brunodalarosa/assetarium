"""Libraries frozen by earlier releases still read: asset IDs, collections and tags (ASSETRM-0004).

``scripts/build-release-fixture.py`` freezes one per release in tests/fixtures/releases/. A fresh build runs the
same checks, so the script and the checks are proven before the first fixture is frozen.
"""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from local_asset_library import asset_collections, asset_tags, library_store

ROOT = Path(__file__).resolve().parents[1]
FROZEN = sorted(p for p in (ROOT / 'tests/fixtures/releases').glob('*') if (p / 'manifest.json').is_file())


def builder():
    spec = importlib.util.spec_from_file_location('build_release_fixture', ROOT / 'scripts/build-release-fixture.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(fixture, tmp_path):
    copy = shutil.copytree(fixture, tmp_path / 'copy')  # Frozen fixtures stay byte-for-byte as their release wrote them.
    data = tmp_path / 'data'
    (data / 'library').mkdir(parents=True)
    for name in ('collections.json', 'asset-tags.json'):
        if (copy / name).is_file():
            shutil.copy2(copy / name, data / 'library' / name)
    config = SimpleNamespace(library_store=lambda: copy / 'library-store', storage_root=lambda _kind: data)
    manifest = json.loads((copy / 'manifest.json').read_text(encoding='utf-8'))
    with closing(library_store.connect(config)) as db:
        ids = sorted(r[0] for r in db.execute("SELECT asset_id FROM assets WHERE state != 'missing'"))
    assert ids == manifest['asset_ids']
    collection = asset_collections.find(asset_collections.load(config), manifest['collection']['id'])
    assert collection['name'] == manifest['collection']['name']
    assert sorted(i['asset_id'] for i in collection['items']) == manifest['asset_ids']
    tag = manifest['tag']
    assert tag['tag'] in asset_tags.load(config)['assets'][tag['asset_id']]


@pytest.mark.parametrize('fixture', FROZEN, ids=[p.name for p in FROZEN])
def test_frozen_release_still_reads(fixture, tmp_path):
    check(fixture, tmp_path)


def test_fresh_fixture_passes_the_same_checks(tmp_path):
    fixture = builder().build('fresh', into=tmp_path / 'built')
    check(fixture, tmp_path)
    with pytest.raises(SystemExit, match='never replaced'):
        builder().build('fresh', into=tmp_path / 'built')
