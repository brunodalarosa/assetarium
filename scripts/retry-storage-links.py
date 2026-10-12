"""Explicitly approved retry: use loaded embedding DLLs as the canonical copies.

The first receipt and every fault are preserved. This changes the replacement
direction so the active worker can stay running. No process is terminated.
"""
import json
import os
import sys

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location("reduce_storage", ROOT / "scripts/reduce-storage.py")
helpers = module_from_spec(spec)
spec.loader.exec_module(helpers)


def main():
    target = ROOT / "data/storage/approved-retry.json"
    helpers.checked(target.parent)
    with target.open("x", encoding="utf-8") as stream:
        json.dump({"status": "running"}, stream)
    first = json.loads((ROOT / "data/storage/consolidation.json").read_text())
    report = {"status": "running", "authorization": "User explicitly approved worker stop and retry; replacement direction avoids stopping it",
              "linked": [], "faults": [], "reclaimed_bytes": 0, "worker_stopped": False}
    for fault in first["faults"]:
        source = ROOT / fault["path"]
        destination = ROOT / ".venv-caption/Lib/site-packages/torch/lib" / source.name
        temporary = destination.with_name(destination.name + ".approved-retry-link")
        partial = ROOT / fault["partial_link"] if fault.get("partial_link") else None
        try:
            helpers.checked(source)
            helpers.checked(destination)
            if source.parent != ROOT / ".venv-embedding/Lib/site-packages/torch/lib":
                raise ValueError("Unexpected retry target")
            expected = helpers.digest(source)
            before = destination.stat()
            if helpers.digest(destination) != expected or before.st_size != source.stat().st_size:
                raise ValueError("Retry requires exactly matching installed bytes")
            if temporary.exists() or os.path.samefile(source, destination):
                raise ValueError("Unexpected existing link; do not repeat work")
            if partial:
                helpers.checked(partial)
                if partial.parent != source.parent or partial.name != source.name + ".storage-link":
                    raise ValueError("Unexpected partial link")
                if not os.path.samefile(partial, destination) or helpers.digest(partial) != expected:
                    raise ValueError("Partial result changed; preserve it")
            os.link(source, temporary)
            if not os.path.samefile(source, temporary) or helpers.digest(temporary) != expected:
                raise ValueError("New link failed integrity check")
            current = destination.stat()
            if (current.st_ino, current.st_size, current.st_mtime_ns) != (
                    before.st_ino, before.st_size, before.st_mtime_ns):
                raise ValueError("Installed file changed during retry")
            os.replace(temporary, destination)
            if not os.path.samefile(source, destination) or helpers.digest(destination) != expected:
                raise ValueError("Final link failed integrity check")
            # The successful final link supersedes this earlier usable partial link.
            if partial:
                partial.unlink()
            report["linked"].append({"source": str(source.relative_to(ROOT)),
                                      "destination": str(destination.relative_to(ROOT)),
                                      "sha256": expected, "bytes": before.st_size,
                                      "superseded_partial": str(partial.relative_to(ROOT)) if partial else None})
            report["reclaimed_bytes"] += before.st_size
        except (OSError, ValueError) as exc:
            report["faults"].append({"path": str(destination.relative_to(ROOT)),
                                      "status": "faulty", "reason": str(exc)})
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["status"] = "faulty" if report["faults"] else "passed"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report["status"] != "passed"


if __name__ == "__main__":
    sys.exit(main())
