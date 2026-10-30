"""Storage receipts cover the project and the library store, without originals."""
import importlib.util
import uuid

from .config import ConfigError
from .publication import atomic_json


def receipt(config, label):
    report = measure_all(config)
    path = config.project_root / "data/storage" / ("sources-" + label + "-" + uuid.uuid4().hex + ".json")
    atomic_json(path, report)
    if report["faults"]:
        raise ConfigError("Storage accounting has faults; see " + str(path))
    return report


def measure_all(config):
    """The project and the library store (when it lives elsewhere), deduplicated by file identity; writes nothing."""
    script = config.project_root / "scripts/storage-report.py"
    spec = importlib.util.spec_from_file_location("lal_storage_report", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen = set()
    project = module.measure(config.project_root, seen)
    reports = [project]
    store = config.library_store()
    if store.exists() and not store.is_relative_to(config.project_root):
        reports.append(module.measure(store, seen))
    faults = [fault for report in reports for fault in report["faults"]]
    totals = {key: sum(r["totals"][key] for r in reports) for key in project["totals"]}
    return {"status": "faulty" if faults else "passed", "totals": totals,
            "project": project, "library_store": reports[1:], "faults": faults,
            "notes": ["File identities deduplicated across Assetarium and its library store.",
                      "Original asset files and shared models are excluded."]}
