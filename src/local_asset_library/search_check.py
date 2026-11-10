"""The search check (decisions 0018 and 0031): the search model reads text and images on this computer's search device.

It runs on two images shipped with Assetarium (a blue cube and a red sphere rendered by scripts/build-samples.py),
never on library assets, so setup can run it before any library exists and processing can run it by itself when
it is missing. Runs in the search runtime; writes only data/embeddings/capability.json.
"""
import hashlib
from pathlib import Path
import json
import sys

IMAGES = Path(__file__).with_name('data') / 'search-check'
INPUTS = (('blue-cube.png', 'A blue cube'), ('red-sphere.png', 'A red sphere'))


def record(config, backend=None):
    """Embed both images and their names, compare, and save the receipt; returns it. Loads the model when not given."""
    import numpy as np
    from .catalog import digest, save_json
    from .config import ConfigError
    from .engines import embedder
    from .retrieval import recorded_contract
    backend = backend or embedder(config)
    images, texts, metrics, inputs = [], [], [], []
    for name, query in INPUTS:
        path = IMAGES / name
        images.append(backend.image(path))
        metrics.append(dict(backend.last_metrics))
        texts.append(backend.text(query))
        metrics.append(dict(backend.last_metrics))
        inputs.append({'path': f'data/search-check/{name}', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'query': query})
    document = backend.text('A small wooden crate with metal corner brackets.', role='document')
    metrics.append(dict(backend.last_metrics))
    if np.allclose(images[0], images[1]) or np.allclose(texts[0], texts[1]):
        raise ConfigError('The search check failed: two different inputs gave the same vector. Nothing was recorded.')
    similarity = np.array(texts) @ np.array(images).T
    if not (similarity[0, 0] > similarity[0, 1] and similarity[1, 1] > similarity[1, 0]):
        raise ConfigError('The search check failed: the model did not match "a blue cube" and "a red sphere" to their '
                          'images. Nothing was recorded.')
    contract = recorded_contract(config, backend.contract)
    report = {'contract': contract, 'contract_fingerprint': digest(contract), 'inputs': inputs,
              'actual_text_and_image_inference': True, 'reference_image_query_support': True,
              'text_image_similarities': similarity.tolist(),
              'image_image_similarities': (np.array(images) @ np.array(images).T).tolist(),
              'document_norm': float(np.linalg.norm(document)), 'metrics': metrics, 'resources': backend.resources(),
              'limitation': 'Capability proof on two built-in sample images; no relevance or benchmark verdict.'}
    save_json(config.output_path('data', 'embeddings/capability.json'), report)
    return report


def main():
    from .config import load_project_config
    from .gpu_queue import lease
    config = load_project_config(Path(__file__).resolve().parents[2])
    with lease(config, 'batch-capability'):
        report = record(config)
    print(json.dumps({k: v for k, v in report.items() if k not in {'contract', 'metrics', 'resources'}}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
