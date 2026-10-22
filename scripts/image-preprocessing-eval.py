"""Compare candidate 2D model-input contracts on real pilot images (read-only originals).

Two phases in two runtimes, both writing only under the evidence directory:
  prepare (MCP runtime): decode/rasterize every pilot image and write candidate model inputs.
  embed   (embedding runtime): embed inputs and held-out text queries, then score them.
Relevance labels and the decision rule are fixed in PREREGISTRATION before any result.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
KENNEY = Path(r'C:/Users/backup pc/Documents/General game assets/Kenney Game Assets All-in-1 3.7.0')
FOLDERS = {'game-icons': KENNEY / 'Icons/Game Icons/PNG', 'tiny-dungeon': KENNEY / '2D assets/Tiny Dungeon/Tiles',
           'board-game-icons': KENNEY / 'Icons/Board Game Icons/Vector/Icons'}
CANDIDATES = ('a', 'b', 'c')


def tiles(*numbers):
    return [f'tiny-dungeon/tile_{n:04}' for n in numbers]


def icons(*names):
    return [f'game-icons/{name}' for name in names]


def board(*names):
    return [f'board-game-icons/{name}' for name in names]


# Labels: Tiny Dungeon tiles by visual inspection of a contact sheet; icons by their
# descriptive filenames, which the image channel never sees. Fixed before scoring.
PREREGISTRATION = {
    'recorded_utc': '2026-10-20 (before any embedding or retrieval result)',
    'relevance': 'A result is relevant when its key (folder/stem) is listed for the query; White/Black and 1x/2x copies share a key.',
    'metrics': 'Image channel only: reciprocal rank of the first relevant item within the top 10 (MRR@10), success@5, relevant@5.',
    'decision': ('Choose the candidate with the highest mean MRR@10 over all queries. Among candidates within 0.02 of the best, '
                 'prefer b (fixed gray backdrop, at least 256 px for descriptions), then a, then c.'),
    'queries': {
        'blue potion icon': tiles(116, 128), 'red health potion': tiles(115, 127), 'green potion bottle': tiles(114, 126),
        'sword': tiles(103, 104, 105, 106, 107) + board('sword'), 'battle axe': tiles(118, 119),
        'treasure chest': tiles(89, 90, 91, 92), 'wizard in a purple robe': tiles(84), 'ghost': tiles(108, 121),
        'wooden door': tiles(21, 22, 23, 33, 34, 35, 45, 46, 47), 'barrel': tiles(82), 'knight in armor': tiles(96, 97),
        'trophy': icons('trophy'), 'gear settings icon': icons('gear'),
        'padlock': icons('locked', 'unlocked') + board('lock_closed', 'lock_open'),
        'magnifying glass': icons('zoom', 'zoomIn', 'zoomOut', 'zoomDefault'), 'trash can': icons('trashcan', 'trashcanOpen'),
        'game controller': icons('gamepad', 'gamepad1', 'gamepad2', 'gamepad3', 'gamepad4'),
        'musical note': icons('musicOn', 'musicOff'), 'house': icons('home') + board('structure_house'),
        'star': icons('star'), 'warning sign': icons('warning', 'exclamation'),
        'six-sided die': board('d6', 'd6_number', 'd6_outline', 'd6_outline_number', 'dice', 'dice_1', 'dice_2', 'dice_3',
                               'dice_4', 'dice_5', 'dice_6', 'dice_3D', 'dice_3D_detailed', 'dice_detailed', 'dice_empty'),
        'chess knight': board('chess_knight'), 'crown': board('crown_a', 'crown_b'),
        'hourglass': board('hourglass', 'hourglass_bottom', 'hourglass_top'), 'campfire': board('campfire', 'fire'),
        'skull': board('skull', 'cards_skull', 'dice_skull'), 'heart card suit': board('suit_hearts', 'suit_hearts_broken'),
        'bow and arrow': board('bow'), 'shield': board('shield', 'dice_shield', 'tag_shield'),
    },
}


def items():
    for name, folder in FOLDERS.items():
        for path in sorted(folder.rglob('*')):
            if path.suffix.lower() in {'.png', '.svg'}:
                yield name, path


def prepare(out):
    from local_asset_library.image_media import decode, model_input, png_bytes
    manifest, faults = [], []
    for folder, path in items():
        key = f'{folder}/{path.stem}'
        try:
            rgba, facts = decode(path, path.suffix.lower()[1:])
        except Exception as exc:
            faults.append({'path': str(path), 'reason': str(exc)})
            continue
        entry = {'key': key, 'path': str(path), 'size': [facts['width'], facts['height']], 'alpha': facts['alpha'], 'inputs': {}}
        for candidate in CANDIDATES:
            image, derivation = model_input(rgba, candidate)
            target = out / candidate / f'{len(manifest):04}.png'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(png_bytes(image))
            entry['inputs'][candidate] = {'path': str(target), 'derivation': derivation}
        manifest.append(entry)
    (out / 'manifest.json').write_text(json.dumps({'items': manifest, 'faults': faults}, indent=1), encoding='utf-8')
    (out / 'preregistration.json').write_text(json.dumps(PREREGISTRATION, indent=1), encoding='utf-8')
    print(json.dumps({'items': len(manifest), 'faults': len(faults)}))


def embed(out):
    import numpy as np
    from local_asset_library.config import load_project_config
    from local_asset_library.embedding_backend import EmbeddingBackend
    from local_asset_library.gpu_queue import lease
    config = load_project_config(ROOT)
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))['items']
    registered = json.loads((out / 'preregistration.json').read_text(encoding='utf-8'))
    assert registered == PREREGISTRATION, 'Preregistration changed after preparation'
    keys = [e['key'] for e in manifest]
    missing = sorted({k for rel in PREREGISTRATION['queries'].values() for k in rel} - set(keys))
    assert not missing, missing
    with lease(config, 'image-preprocessing-eval', timeout=600):
        backend = EmbeddingBackend(config)
        started = time.perf_counter()
        queries = {q: backend.text(q, role='query') for q in PREREGISTRATION['queries']}
        vectors = {c: np.stack([backend.image(Path(e['inputs'][c]['path'])) for e in manifest]) for c in CANDIDATES}
        seconds = time.perf_counter() - started
        resources = backend.resources()
    results = {}
    for candidate in CANDIDATES:
        rows = {}
        for query, relevant in PREREGISTRATION['queries'].items():
            scores = vectors[candidate] @ queries[query]
            ranked, seen = [], set()
            for index in np.argsort(-scores):
                if keys[index] not in seen:  # Aggregate White/Black and 1x/2x copies by key.
                    seen.add(keys[index])
                    ranked.append(keys[index])
                if len(ranked) == 10:
                    break
            first = next((i + 1 for i, key in enumerate(ranked) if key in relevant), None)
            rows[query] = {'top5': ranked[:5], 'relevant_at_5': sum(k in relevant for k in ranked[:5]),
                           'success_at_5': any(k in relevant for k in ranked[:5]), 'reciprocal_rank': 1 / first if first else 0.0}
        results[candidate] = {'mrr_at_10': round(float(np.mean([r['reciprocal_rank'] for r in rows.values()])), 4),
                              'success_at_5': round(float(np.mean([r['success_at_5'] for r in rows.values()])), 4),
                              'tiny_dungeon_mrr': round(float(np.mean([r['reciprocal_rank'] for q, r in rows.items()
                                                                       if PREREGISTRATION['queries'][q][0].startswith('tiny')])), 4),
                              'queries': rows}
    best = max(results[c]['mrr_at_10'] for c in CANDIDATES)
    chosen = next(c for c in ('b', 'a', 'c') if results[c]['mrr_at_10'] >= best - 0.02)
    report = {'chosen': chosen, 'rule': PREREGISTRATION['decision'], 'summary': {c: {k: v for k, v in results[c].items() if k != 'queries'}
              for c in CANDIDATES}, 'images': len(manifest), 'embedding_seconds': round(seconds, 1), 'resources': resources,
              'owner_review': 'pending', 'results': results}
    (out / 'report.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('chosen', 'summary', 'images', 'embedding_seconds')}, indent=1))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'embed'))
    parser.add_argument('--run-name', required=True)
    args = parser.parse_args()
    out = ROOT / 'data/verification' / args.run_name
    if args.phase == 'prepare':
        out.mkdir(parents=True, exist_ok=False)
        prepare(out)
    else:
        embed(out)
