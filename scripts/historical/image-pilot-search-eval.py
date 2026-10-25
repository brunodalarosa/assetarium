"""Measure filename, image and description channels separately on the published image pilot.

Uses the preregistered held-out queries and labels from the preprocessing evaluation,
the real shared SearchEngine and the actual EmbeddingGemma model (embedding runtime).
Read-only: no processing or asset writes. Evidence: data/verification/<run-name>/.
"""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
FOLDERS = {'PNG': 'game-icons', 'Tiles': 'tiny-dungeon', 'Icons': 'board-game-icons'}
NEGATIVES = ['red sports car', 'spaceship', 'palm tree', 'office chair']


def score(ranking, relevant, keys, allowed=None):
    ranked, seen = [], set()
    for item in ranking:
        if allowed is not None and item['asset_id'] not in allowed:
            continue
        key = keys.get(item['asset_id'])
        if key and key not in seen:
            seen.add(key)
            ranked.append(key)
        if len(ranked) == 10:
            break
    first = next((i + 1 for i, key in enumerate(ranked) if key in relevant), None)
    return {'top5': ranked[:5], 'reciprocal_rank': 1 / first if first else 0.0,
            'success_at_5': any(key in relevant for key in ranked[:5])}


def summary(rows):
    return {'queries': len(rows), 'mrr_at_10': round(statistics.mean(r['reciprocal_rank'] for r in rows), 4) if rows else None,
            'success_at_5': round(statistics.mean(r['success_at_5'] for r in rows), 4) if rows else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name', required=True)
    args = parser.parse_args()
    out = ROOT / 'data/verification' / args.run_name
    out.mkdir(parents=True, exist_ok=False)
    from local_asset_library.config import load_project_config
    from local_asset_library.embedding_backend import EmbeddingBackend
    from local_asset_library.gpu_queue import lease
    from local_asset_library.retrieval import SearchEngine, pilot_records
    config = load_project_config(ROOT)
    queries = json.loads((ROOT / 'data/verification/image-preprocessing-eval-20261020/preregistration.json').read_text(encoding='utf-8'))['queries']
    images = [r for r in pilot_records(config) if r.get('asset_type') == 'image' and r['pack_id'] in FOLDERS]
    keys = {r['asset_id']: FOLDERS[r['pack_id']] + '/' + r['display_name'] for r in images}
    described = {r['asset_id'] for r in images if r['processing'].get('caption') == 'complete'}
    report = {'images': len(images), 'described': len(described), 'queries': {}, 'negatives': {}, 'timing': {},
              'relevance': 'Preregistered labels (data/verification/image-preprocessing-eval-20261020/preregistration.json)',
              'owner_relevance_review': 'pending'}
    with lease(config, 'image-pilot-search-eval', timeout=600):
        clock = time.perf_counter()
        backend = EmbeddingBackend(config)
        report['timing']['model_load_seconds'] = round(time.perf_counter() - clock, 2)
        engine = SearchEngine(config, backend)
        warm = []
        for query, relevant in queries.items():
            clock = time.perf_counter()
            response, evidence = engine.search(query, mode='combined', filters={'asset_type': 'image'}, limit=10)
            warm.append(time.perf_counter() - clock)
            rankings = evidence['channel_rankings']
            fused = [{'asset_id': r['asset_id']} for r in response['results']]
            row = {'all': {channel: score(rankings.get(channel, []), relevant, keys) for channel in ('keyword', 'image', 'description')}}
            row['all']['combined'] = score(fused, relevant, keys)
            if any(keys.get(i) in relevant for i in described):
                row['described_subset'] = {channel: score(rankings.get(channel, []), relevant, keys, described)
                                           for channel in ('keyword', 'image', 'description')}
            report['queries'][query] = row
        for query in NEGATIVES:
            response, evidence = engine.search(query, mode='image', filters={'asset_type': 'image'}, limit=5)
            report['negatives'][query] = [{'name': keys.get(r['asset_id']), 'cosine': round(r['score'], 4)} for r in response['results']]
        report['resources'] = backend.resources()
    report['timing'].update(first_query_seconds=round(warm[0], 2), warm_median_seconds=round(statistics.median(warm[1:]), 2))
    report['summary'] = {
        'all_pilot_images': {c: summary([q['all'][c] for q in report['queries'].values()]) for c in ('keyword', 'image', 'description', 'combined')},
        'described_subset': {c: summary([q['described_subset'][c] for q in report['queries'].values() if 'described_subset' in q])
                             for c in ('keyword', 'image', 'description')}}
    (out / 'report.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('images', 'described', 'summary', 'timing')}, indent=1))


if __name__ == '__main__':
    main()
