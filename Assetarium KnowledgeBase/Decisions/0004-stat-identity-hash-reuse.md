---
tags: [decision]
decided: 2026-10-17
---
# 0004 — Re-hash files only when their identity changes

**Decision.** Runtime verification (`publication.verified_hash`, used by
`captions.file_hash`) reuses a recorded SHA-256 while the file's identity is
unchanged: size, modification time, NTFS ChangeTime and file ID
(`hash_cache.file_identity`; other platforms use `os.stat` size/mtime/ctime/inode).
- One shared record, `cache/file-hashes.sqlite`, serves the desktop app, MCP
  server, embedding worker and scans. Scans seed it, so even the first search
  after launch reuses scan hashes.
- The record is an accelerator, not evidence. A missing, busy or corrupt record
  only means hashing the bytes again. Tests use an isolated record
  (`tests/conftest.py`, `LAL_HASH_CACHE`).
- Explicit byte audits re-read contents: `maintenance_files` removal checks pass
  `fresh=True`, and `verify-storage.py`, `verify-library-preservation.py` and
  `verify-model-relocation.py` call `hash_cache.require_fresh()`.
- Boundary checks (source directory validation, storage roots, registry and
  ownership reads, directory resolution) run once per pinned request instead of
  per file; a leaf that is a link is still resolved and rejected if it escapes.
- Thumbnails show the verified preview image only (cached by preview identity,
  320 px, fast PNG encode). Detail and agent `get_asset` still verify sources.

**Why.** Every search re-hashed about 8,000 source files and 11,500 preview PNGs
(keyword 7 s, combined 19.5 s warm; 34 s cold). The scanner already trusted
stat identity. NTFS ChangeTime is updated by every write and is not reset by
ordinary timestamp-restoring tools, so an edit that restores the modification
time is still detected (`tests/test_hash_cache.py`).

**Limitation (accepted by the owner).** A tool that deliberately rewrites
ChangeTime through low-level file-information APIs could hide a same-size edit
until the next fresh audit. Run a `require_fresh()` audit when that matters.

**Keep true.** Changed, replaced or missing files must still be excluded and
recorded as faults exactly as before. Do not add other hash caches; route new
checks through `verified_hash`. Removal and audit paths must stay fresh.
