"""Read-only project storage accounting, counting hard-linked files only once."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def measure(root):
    root = root.resolve(strict=True)
    seen = set()
    areas = {}
    faults = []
    excluded_links = []
    allocation_size = None
    if os.name == "nt":
        class FileStandardInfo(ctypes.Structure):
            _fields_ = [("AllocationSize", ctypes.c_longlong), ("EndOfFile", ctypes.c_longlong),
                        ("NumberOfLinks", wintypes.DWORD), ("DeletePending", ctypes.c_ubyte),
                        ("Directory", ctypes.c_ubyte)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                       ctypes.c_void_p, wintypes.DWORD]
        kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL

        def allocation_size(path):
            handle = kernel.CreateFileW(str(path), 0, 7, None, 3, 0, None)
            if handle == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                info = FileStandardInfo()
                if not kernel.GetFileInformationByHandleEx(handle, 1, ctypes.byref(info), ctypes.sizeof(info)):
                    raise ctypes.WinError(ctypes.get_last_error())
                return info.AllocationSize
            finally:
                kernel.CloseHandle(handle)

    def walk_error(exc):
        faults.append({"path": str(exc.filename), "status": "faulty", "reason": str(exc)})

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        for name in dirs[:]:
            path = Path(directory) / name
            if path.is_symlink() or path.is_junction():
                dirs.remove(name)
                excluded_links.append(str(path.relative_to(root)))
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root)
            try:
                if path.is_symlink():
                    raise ValueError("File link excluded from project accounting")
                stat = path.stat()
                if not stat.st_ino:
                    raise ValueError("File identity unavailable; cannot deduplicate accounting")
                area = areas.setdefault(relative.parts[0] if len(relative.parts) > 1 else "root_files",
                                        {"files": 0, "logical_bytes": 0, "unique_bytes": 0,
                                         "allocated_bytes": 0, "shared_paths": 0})
                area["files"] += 1
                area["logical_bytes"] += stat.st_size
                identity = (stat.st_dev, stat.st_ino)
                if identity in seen:
                    area["shared_paths"] += 1
                    continue
                size = allocation_size(path) if allocation_size else stat.st_blocks * 512
                seen.add(identity)
                area["unique_bytes"] += stat.st_size
                area["allocated_bytes"] += size
            except (OSError, ValueError) as exc:
                faults.append({"path": str(relative), "status": "faulty", "reason": str(exc)})
    totals = {key: sum(area[key] for area in areas.values()) for key in
              ("files", "logical_bytes", "unique_bytes", "allocated_bytes", "shared_paths")}
    return {"status": "faulty" if faults else "passed", "root": str(root), "totals": totals,
            "areas": areas, "faults": faults, "excluded_directory_links": excluded_links,
            "notes": ["Unique bytes count each file identity once across the project.",
                      "Allocated bytes exclude directory and filesystem metadata; external hard links are not charged separately.",
                      "Directory links are intentionally excluded to avoid counting external trees and test fixtures twice.",
                      "Shared bytes are attributed to the first encountered area; use totals for comparisons.",
                      "Original assets and shared model weights outside this root are excluded."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="New evidence filename under data/storage; never overwrite")
    args = parser.parse_args()
    report = measure(ROOT)
    if args.output:
        if Path(args.output).name != args.output or not args.output.endswith(".json"):
            parser.error("Output must be a simple JSON filename")
        target = ROOT / "data/storage" / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.parent.resolve() != ROOT / "data/storage":
            raise ValueError("Evidence directory must not escape project")
        with target.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    print(json.dumps(report, indent=2))
    sys.exit(report["status"] != "passed")
