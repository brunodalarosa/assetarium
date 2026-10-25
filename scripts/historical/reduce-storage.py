"""One-time approved consolidation of byte-identical installed Torch libraries.

No downloads, package upgrades, cache deletion, source assets or model weights.
Existing evidence prevents automatic reruns, including unchanged faults.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "data/storage/consolidation.json"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked(path):
    if not path.is_relative_to(ROOT) or path.resolve(strict=True) != path:
        raise ValueError("Path escapes project or follows a link")
    for parent in (path, *path.parents):
        if parent == ROOT:
            break
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("Linked path refused")
    return path


def run():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    checked(TARGET.parent)
    # Exclusive creation is the no-retry guard, before any dependency mutation.
    with TARGET.open("x", encoding="utf-8") as stream:
        json.dump({"status": "running", "started": time.time()}, stream)
    report = {"status": "running", "linked": [], "different": [], "faults": [],
              "reclaimed_bytes": 0}

    def save():
        TARGET.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    source = ROOT / ".venv-caption/Lib/site-packages/torch/lib"
    destination = ROOT / ".venv-embedding/Lib/site-packages/torch/lib"
    try:
        checked(source)
        checked(destination)
        for original in sorted(source.iterdir()):
            if not original.is_file() or original.stat().st_size < 1024 * 1024:
                continue
            duplicate = destination / original.name
            if not duplicate.exists():
                continue
            temporary = duplicate.with_name(duplicate.name + ".storage-link")
            try:
                checked(original)
                checked(duplicate)
                before = duplicate.stat()
                if os.path.samefile(original, duplicate):
                    continue
                if before.st_size != original.stat().st_size:
                    report["different"].append(original.name)
                    continue
                expected = digest(original)
                if digest(duplicate) != expected:
                    report["different"].append(original.name)
                    continue
                if temporary.exists():
                    raise ValueError("Unexpected temporary file; preserve it for review")
                os.link(original, temporary)
                # Original duplicate stays usable until the verified replacement is ready.
                if digest(temporary) != expected or not os.path.samefile(original, temporary):
                    raise ValueError("Replacement link failed integrity check")
                current = duplicate.stat()
                if (current.st_ino, current.st_size, current.st_mtime_ns) != (
                        before.st_ino, before.st_size, before.st_mtime_ns):
                    raise ValueError("Installed file changed during consolidation")
                os.replace(temporary, duplicate)
                if not os.path.samefile(original, duplicate) or digest(duplicate) != expected:
                    raise ValueError("Final file failed integrity check")
                report["linked"].append({"source": str(original.relative_to(ROOT)),
                                          "destination": str(duplicate.relative_to(ROOT)),
                                          "bytes": before.st_size, "sha256": expected})
                report["reclaimed_bytes"] += before.st_size
            except (OSError, ValueError) as exc:
                report["faults"].append({"path": str(duplicate.relative_to(ROOT)),
                                          "status": "faulty", "reason": str(exc),
                                          "partial_link": str(temporary.relative_to(ROOT)) if temporary.exists() else None})
            save()
    except (OSError, ValueError) as exc:
        report["faults"].append({"status": "faulty", "reason": str(exc)})
    report["status"] = "faulty" if report["faults"] else "passed"
    save()
    print(json.dumps(report, indent=2))
    return report["status"] != "passed"


if __name__ == "__main__":
    sys.exit(run())
