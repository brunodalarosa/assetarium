"""Describe the fixed 40-image step 2 evaluation set, then index and publish its descriptions.

Same caption stage, batching, per-asset outcomes, description vectors and publication
as Generate descriptions, restricted to the owner-approved evaluation set. Phases run
in their own runtimes: ``caption`` (caption runtime), ``index`` (embedding runtime),
``publish`` (base runtime). The remaining pilot images keep missing descriptions.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library import sources
from local_asset_library.config import load_project_config
from local_asset_library.gpu_queue import lease
from local_asset_library.incremental import working
from local_asset_library.membership import records

KENNEY = Path(r'C:/Users/backup pc/Documents/General game assets/Kenney Game Assets All-in-1 3.7.0')
# Stratified: tiny pixel art, white and black transparent icons (with scale/colour duplicates),
# and self-contained SVGs without a declared canvas. Fixed before any description exists.
EVALUATION = {
    KENNEY / '2D assets/Tiny Dungeon/Tiles': [f'image:tile_{n:04}' for n in
                                               (116, 115, 114, 128, 105, 118, 90, 84, 108, 46, 82, 96, 0, 29)],
    KENNEY / 'Icons/Game Icons/PNG': ['image:White/1x/trophy', 'image:Black/2x/trophy', 'image:White/1x/gear',
                                      'image:Black/1x/locked', 'image:White/2x/zoom', 'image:Black/1x/trashcan',
                                      'image:White/1x/gamepad', 'image:Black/2x/musicOn', 'image:White/1x/home',
                                      'image:Black/1x/star', 'image:White/2x/warning', 'image:Black/1x/arrowUp',
                                      'image:White/1x/cart', 'image:Black/2x/medal1'],
    KENNEY / 'Icons/Board Game Icons/Vector/Icons': [f'image:{name}' for name in
                                                      ('d6', 'chess_knight', 'crown_a', 'hourglass', 'campfire', 'skull',
                                                       'suit_hearts', 'bow', 'shield', 'sword', 'resource_apple', 'structure_house')],
}
OUT = ROOT / 'data/verification/image-pilot-20261020'


def selected(config):
    for folder, identities in EVALUATION.items():
        source = next(s for s in sources.registry(config)['sources'] if Path(s['path']) == folder)
        scoped = sources.bound(config, source)
        found = {r['source_relative_identity']: r['asset_id'] for r in records(working(scoped))}
        missing = [i for i in identities if i not in found]
        assert not missing, missing
        yield source, scoped, {found[i] for i in identities}


def caption(config):
    from local_asset_library.caption_backend import QwenBackend
    from local_asset_library.incremental import process
    contract = json.loads((ROOT / 'docs/caption-model.json').read_text(encoding='utf-8'))
    reports = []
    with lease(config, 'image-pilot-describe', timeout=600):
        backend = None
        for source, scoped, ids in selected(config):
            backend = backend or QwenBackend(scoped, contract)
            backend.config = scoped
            result = process(scoped, 'caption', limit=1000, backend=backend, asset_ids=ids)
            reports.append({'source': source['key'], 'selected': len(ids), **{k: result.get(k) for k in
                            ('pending', 'complete', 'failed', 'unsupported', 'retained', 'elapsed_seconds', 'resources', 'stopped')}})
        backend.close()
    return reports


def index(config):
    from local_asset_library.embedding_backend import EmbeddingBackend
    from local_asset_library.library_index import index_library
    reports = []
    with lease(config, 'image-pilot-describe-index', timeout=600):
        backend = None
        for source, scoped, _ in selected(config):
            backend = backend or EmbeddingBackend(scoped)
            result = index_library(working(scoped), backend)
            reports.append({'source': source['key'], **{k: result.get(k) for k in ('pending', 'processed', 'deferred_descriptions', 'vectors')}})
    return reports


def publish(config):
    from local_asset_library.source_operations import publish_source
    reports = []
    for source, scoped, _ in selected(config):
        publish_source(scoped)
    sources.aggregate(config)
    for source, scoped, _ in selected(config):
        status = sources.scan_source(config, source)
        reports.append({'source': source['key'], 'pending': status['pending'], 'failed': status['failed'],
                        'descriptions': status.get('descriptions')})
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('caption', 'index', 'publish'))
    phase = parser.parse_args().phase
    config = load_project_config(ROOT)
    result = {'caption': caption, 'index': index, 'publish': publish}[phase](config)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'describe-{phase}.json').write_text(json.dumps(result, indent=1, default=str), encoding='utf-8')
    print(json.dumps(result, indent=1, default=str))
