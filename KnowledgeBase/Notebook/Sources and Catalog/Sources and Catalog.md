---
area: Sources and Catalog
tags: [hub]
code: [sources.py, source_operations.py, catalog.py, membership.py, publication.py, library_policy.py]
---
# Sources and Catalog

Registered asset folders ("sources"), what a scan finds in them, how files group into logical
assets, and how each source's results combine into one read-only catalog. Up: [Notebook](../Notebook.md).

## Systems

- [Sources](Sources.md): registry, source-owned `metadata-lal/`, scans, exclusions and duplicate export folders.
- [Publication](Publication.md) *(gap)*: per-source publications, the combined catalog and index, pinned immutable generations (`publication.py`, `membership.py`).
- [Logical assets](Logical%20assets.md) *(gap)*: grouping files into one asset, alternate files and variants (`catalog.py`, `asset_structure.py`).

## Read first

- User guide: [Asset sources](../../../docs/asset-sources.md).
- Contract: [Catalog contract](../../Architecture/Sources%20and%20Catalog/Catalog%20contract.md).
- Decisions: [0002](../../Decisions/0002-startup-scan-and-change-detection.md) (startup scan, change
  detection), [0004](../../Decisions/0004-stat-identity-hash-reuse.md) (hash reuse),
  [0019](../../Decisions/0019-source-folders-and-export-variants.md) (excluded folders, export
  variants), [0020](../../Decisions/0020-alternate-file-faults-and-recheck.md) (alternate file
  faults, recheck), [0021](../../Decisions/0021-texture-folder-choice.md) (texture folder choice).
