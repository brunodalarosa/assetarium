"""Read-only timing receipt for startup, browse, thumbnails and search.

Runs in .venv-mcp against the configured library. No model, GPU, audit run or
asset write: combined search uses a deterministic stub query vector so the
receipt measures everything except the model forward pass.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def timed(results, name, function, *args):
    started = time.perf_counter()
    value = function(*args)
    results[name] = round(time.perf_counter() - started, 3)
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-name', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', args.run_name):
        raise SystemExit('Invalid run name')
    output = ROOT / 'data/benchmarks' / (args.run_name + '.json')
    if output.exists():
        raise SystemExit('Benchmark output exists; existing receipts are evidence')
    results = {}
    started = time.perf_counter()
    import local_asset_library.desktop  # noqa: F401  Same imports as the desktop shell.
    results['import_desktop_module'] = round(time.perf_counter() - started, 3)
    from contextlib import closing
    import numpy as np
    from local_asset_library.config import load_project_config
    from local_asset_library.desktop_service import DesktopService
    from local_asset_library.retrieval import SearchEngine, index_database
    config = load_project_config(ROOT)
    service = DesktopService(config)
    context = timed(results, 'context_1', service.context)
    timed(results, 'context_2', service.context)
    results['members'] = context['pilot_count']
    page = timed(results, 'browse_1', service.browse, {}, 0, 40)
    timed(results, 'browse_2', service.browse, {}, 0, 40)
    identifiers = [item['asset_id'] for item in page['items']][:12]
    started = time.perf_counter()
    for identifier in identifiers:
        service.thumbnail(identifier, context['generation'])
    results['thumbnails_12'] = round(time.perf_counter() - started, 3)
    if identifiers:
        timed(results, 'detail_1', service.asset, identifiers[0], None, 'three_quarter', context['generation'])
    keyword = {'query': 'red car', 'mode': 'keyword', 'filters': {}, 'limit': 20}
    timed(results, 'keyword_search_1', service.execute, 'search_assets', keyword)
    timed(results, 'keyword_search_2', service.execute, 'search_assets', dict(keyword, query='wooden house'))
    with closing(index_database(config, readonly=True)) as db:
        contract = json.loads(dict(db.execute('SELECT key,value FROM meta'))['contract'])

    class StubBackend:
        last_metrics = {}
        def text(self, text, role='query'):
            vector = np.random.default_rng(0).standard_normal(768).astype(np.float32)
            return vector / np.linalg.norm(vector)

    engine = SearchEngine(config, StubBackend(), contract)
    timed(results, 'combined_search_stub_1', engine.search, 'red car', 'combined', None, None, 20)
    timed(results, 'combined_search_stub_2', engine.search, 'wooden house', 'combined', None, None, 20)
    from local_asset_library.sources import registry, revision, source_status
    from local_asset_library.source_operations import operation_status
    def sources():
        return ([source_status(config, s) for s in registry(config)['sources']], revision(config), operation_status(config))
    timed(results, 'sources_poll_1', sources)
    timed(results, 'sources_poll_2', sources)
    try:
        import psutil
        results['rss_bytes'] = psutil.Process().memory_info().rss
    except ImportError:
        results['rss_bytes'] = None
    report = {'run_name': args.run_name, 'generation': context['generation'], 'seconds': results,
              'method': 'Single read-only run; combined search uses a stub query vector (no model/GPU).'}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
