"""Record the search capability check on two of this library's own processed assets (decision 0018).

Indexing and search require data/embeddings/capability.json for the configured embedder. This runs
real preview pixels and text through it, on any install, replacing the pilot-only historical script.
It reads assets and writes only that receipt. Run it again after changing the search device.
"""
from pathlib import Path
import json
import sys

import numpy as np

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from local_asset_library.catalog import save_json  # noqa: E402
from local_asset_library.config import load_project_config  # noqa: E402
from local_asset_library.engines import embedder  # noqa: E402
from local_asset_library.gpu_queue import lease  # noqa: E402
from local_asset_library.incremental import working  # noqa: E402
from local_asset_library.retrieval import preview_file  # noqa: E402
from local_asset_library.sources import bound, read_records, registry  # noqa: E402

config = load_project_config(root)
picked = []
# Each source's working records: on a fresh install nothing is published until search data exists.
for source in (s for s in registry(config)['sources'] if s.get('enabled', True)):
    work = working(bound(config, source))
    for record in read_records(work):
        # Prefer the three-quarter render the original check used; any verified view will do.
        views = sorted(record.get('previews', []), key=lambda p: p.get('view_label') != 'three_quarter')
        for preview in views:
            try:
                path = preview_file(work, preview)
            except (OSError, ValueError):
                continue
            picked.append((record, preview, path))
            break
        if len(picked) == 2:
            break
    if len(picked) == 2:
        break
if len(picked) < 2:
    raise SystemExit('The search check needs two processed assets with previews. Process a source first '
                     '(Asset processing → Process assets), then run this again.')
with lease(config, 'batch-capability'):
    backend = embedder(config)
    image_vectors, text_vectors, metrics, inputs = [], [], [], []
    for record, preview, path in picked:
        query = record.get('display_name') or record['asset_id']
        image_vectors.append(backend.image(path))
        metrics.append(dict(backend.last_metrics))
        text_vectors.append(backend.text(query))
        metrics.append(dict(backend.last_metrics))
        inputs.append({'asset_id': record['asset_id'], 'path': preview.get('path') or preview.get('source_path'),
                       'sha256': preview['sha256'], 'view_label': preview.get('view_label'), 'query': query})
    document = backend.text('A small wooden crate with metal corner brackets.', role='document')
    metrics.append(dict(backend.last_metrics))
    if np.allclose(image_vectors[0], image_vectors[1]) or np.allclose(text_vectors[0], text_vectors[1]):
        raise SystemExit('Two different inputs gave the same vector; nothing was recorded.')
    report = {'contract': backend.contract, 'contract_fingerprint': backend.fingerprint, 'inputs': inputs,
              'actual_text_and_image_inference': True, 'reference_image_query_support': True,
              'text_image_similarities': (np.array(text_vectors) @ np.array(image_vectors).T).tolist(),
              'image_image_similarities': (np.array(image_vectors) @ np.array(image_vectors).T).tolist(),
              'document_norm': float(np.linalg.norm(document)), 'metrics': metrics, 'resources': backend.resources(),
              'limitation': 'Capability proof using two of this library\'s assets; no human relevance or benchmark verdict.'}
save_json(config.output_path('data', 'embeddings/capability.json'), report)
print(json.dumps({k: v for k, v in report.items() if k not in {'contract', 'metrics'}}, ensure_ascii=False))
