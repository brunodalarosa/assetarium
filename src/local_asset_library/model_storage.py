"""Account only for this project's pinned revisions in shared model storage."""
import json


def project_model_bytes(config):
    total = 0
    for folder, contract_file in (("qwen3-vl-2b", "caption-model.json"),
                                  ("embeddinggemma-2", "embedding-model.json")):
        contract = json.loads((config.project_root / "docs" / contract_file).read_text(encoding="utf-8"))
        directory = config.output_path("models", folder + "/" + contract["revision"])
        for path in directory.rglob("*"):
            checked = config.output_path("models", path.relative_to(config.storage_root("models")).as_posix())
            if checked.is_file():
                total += checked.stat().st_size
    return total

def verify_weights(config, runtime, progress=None):
    """Hash the pinned revision's files against the manifest and write the same receipt a verified download writes.

    Local only: no network, no download, nothing outside the receipt is written. A mismatch is a visible fault
    that names the file; the receipt is then left as it was.
    """
    import time
    from .catalog import save_json
    from .config import ConfigError
    from .engines import WEIGHTS, manifest, weights_path
    from .publication import verified_hash
    listed = manifest(config, runtime)
    if listed is None:
        raise ConfigError('This checkout has no file list for these weights; verify them with the prepare script instead')
    started, measured, total = time.perf_counter(), [], sum(item['size'] for item in listed['files'])
    done = 0
    for item in listed['files']:
        path = weights_path(config, runtime, listed['revision'], item['name'])
        if not path.is_file() or path.stat().st_size != item['size']:
            raise ConfigError('Model file missing or another size: ' + item['name'])
        if verified_hash(path, fresh=True) != item['sha256']:
            raise ConfigError('Model file differs from the pinned revision: ' + item['name'])
        measured.append({'name': item['name'], 'size': item['size'], 'sha256': item['sha256']})
        done += item['size']
        if progress:
            progress(done, total)
    report = {'revision': listed['revision'], 'mode': 'verify_local', 'download_bytes': 0, 'files': measured,
              'verification_seconds': time.perf_counter() - started}
    save_json(config.output_path('data', WEIGHTS[runtime][0]), report)
    return {'status': 'verified', 'model': runtime, 'bytes': total, 'seconds': round(report['verification_seconds'], 1)}


def project_allocation(config):
    """Unique allocated project + source-metadata bytes against the user's saved storage budget.

    Uses the same file-identity accounting as storage receipts (hard links count once), not a
    logical folder sum; shared model storage and originals are excluded.
    """
    from .settings import storage_budget
    from .source_storage import measure_all
    report = measure_all(config)
    return {'allocated_bytes': report['totals']['allocated_bytes'], 'faults': len(report['faults']),
            'budget_bytes': storage_budget(config)['total_allocated_bytes']}
