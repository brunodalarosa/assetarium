"""Freeze a small library written by this release, for later releases' upgrade tests (ASSETRM-0004).

Run once when a release is tagged: ``build-release-fixture.py --release 0.2.0``. A throwaway project in scratch/
adds the built-in sample assets as a library folder, scans them (no Blender, no models), puts them in a
collection and tags one. The library store and the owner's JSON files are then copied, with a manifest of what a
later release must still read, into tests/fixtures/releases/<release>/. An existing fixture is never replaced.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from local_asset_library import asset_collections, asset_tags, sources  # noqa: E402
from local_asset_library.config import load_project_config  # noqa: E402
from local_asset_library.settings import settings_path  # noqa: E402
from local_asset_library.source_operations import ensure_index, publish_source  # noqa: E402

FIXTURES = ROOT / 'tests/fixtures/releases'


def build(release, into=FIXTURES):
    target = Path(into) / release
    if target.exists():
        raise SystemExit(f'{target} exists; a frozen fixture is never replaced')
    project = ROOT / 'scratch/release-fixture' / uuid.uuid4().hex[:8]
    (project / 'data/library').mkdir(parents=True)
    shutil.copy2(ROOT / 'config.example.toml', project / 'config.example.toml')
    config = load_project_config(project)
    source = sources.add(config, str(ROOT / 'samples/Sample assets'))
    sources.scan_source(config, source)
    scoped = sources.bound(config, source)
    ensure_index(config, scoped)  # The app's own scan → index → publish → aggregate steps, with no vectors.
    publish_source(scoped)
    sources.aggregate(config)
    store = config.library_store()
    with closing(sqlite3.connect(store / 'library.sqlite')) as db:
        ids = sorted(r[0] for r in db.execute("SELECT asset_id FROM assets WHERE state != 'missing'"))
    if not ids:
        raise SystemExit('The scan found no sample assets')
    collection = asset_collections.create(config, 'Sample shapes', 'Release fixture', members=ids, source_key=source['key'])
    asset_tags.change(config, ids[:1], add=['fixture'])
    target.mkdir(parents=True)
    shutil.copytree(store, target / 'library-store')
    for found in (asset_collections.path(config), asset_tags.path(config), settings_path(config), config.sources_registry):
        if found and Path(found).is_file():
            shutil.copy2(found, target / Path(found).name)
    manifest = {'schema_version': 1, 'release': release, 'asset_ids': ids, 'folder_key': source['key'],
                'collection': {'id': collection['collection_id'], 'name': 'Sample shapes'},
                'tag': {'asset_id': ids[0], 'tag': 'fixture'}}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    shutil.rmtree(project)  # Disposable: it holds no links and nothing outside it refers to it.
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--release', required=True)
    print(build(parser.parse_args().release))
