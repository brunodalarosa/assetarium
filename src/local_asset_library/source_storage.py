"""Storage receipts cover the project and source metadata, without originals."""
import importlib.util
import uuid

from .config import ConfigError
from .publication import atomic_json
from .sources import registry, bound


def receipt(config, label):
    report = measure_all(config)
    path = config.project_root / "data/storage" / ("sources-" + label + "-" + uuid.uuid4().hex + ".json")
    atomic_json(path, report)
    if report["faults"]:
        raise ConfigError("Storage accounting has faults; see " + str(path))
    return report


def measure_all(config):
    """The project and every source's metadata, deduplicated by file identity; writes nothing."""
    script = config.project_root / "scripts/storage-report.py"
    spec = importlib.util.spec_from_file_location("lal_storage_report", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen = set()
    project = module.measure(config.project_root, seen)
    reports = [project]
    value = registry(config)
    directories = set()
    for source in value["sources"] + value.get("detached", []):
        directory = bound(config, source).metadata_root
        if directory in directories or not directory.exists():
            continue
        directories.add(directory)
        reports.append(module.measure(directory, seen))
    faults = [fault for report in reports for fault in report["faults"]]
    totals = {key: sum(r["totals"][key] for r in reports) for key in project["totals"]}
    return {"status": "faulty" if faults else "passed", "totals": totals,
            "project": project, "source_metadata": reports[1:], "faults": faults,
            "notes": ["File identities deduplicated across LAL and all source metadata directories.",
                      "Original asset files and shared models are excluded."]}
