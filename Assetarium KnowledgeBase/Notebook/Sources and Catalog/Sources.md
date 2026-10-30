---
area: Sources and Catalog
tags: [system]
code: [sources.registry, sources.add, sources.scan_source, sources.aggregate, sources.generated_path, sources.importing_failures, source_operations.py, source_migration.py, catalog.walk_source, hash_cache.py, library_policy.DEFAULT_BUDGET, library_policy.LEGACY]
verified: 2026-10-28
branch: feature/library-view
---
# Sources

Hub: [Sources and Catalog](Sources%20and%20Catalog.md). A source is one registered asset folder.
Start reading at `sources.py` (registry, scans, the combined catalog) and `source_operations.py`
(durable, cancellable Process assets operations). User guide: [Asset sources](../../../docs/asset-sources.md).

## How it works

- The registry is `data/library/sources.json`. Each source's `metadata-lal/source.json` holds its
  persistent identifier and catalog key, plus per-source choices (`import_types`, `import_formats`,
  excluded folders, export-folder answers, texture folder).
- **Everything generated for a source lives in its own `metadata-lal/`**: catalog snapshots, the
  working catalog, inventory, stage ledger and job history, vector snapshots, inspections and
  previews, captions, owner overlays, review classification, operation logs. Saved `data/...`
  references inside records are logical and resolve to that folder (`sources.generated_path`),
  which kept asset IDs and fingerprints stable when results moved out of the project.
- The central catalog and search index are derived combinations of source publications
  (`sources.aggregate`). Enabling or disabling a source filters visible membership without copying,
  re-rendering or re-indexing. App logs, capability receipts, caches and storage receipts stay
  central under `data/`.
- Scans reuse a file's hash while its stat identity (file ID, size, mtime, change time) is unchanged
  and seed the shared `cache/file-hashes.sqlite` (`hash_cache.py`, decision 0004). Scans never run
  models or renders. A source's own `metadata-lal/` is always excluded from its scan.
- Removing a source keeps its files and `metadata-lal/`; re-adding the folder recovers its identity
  and published results.

## Rules

- **Originals are read only; nothing here writes into a source except its `metadata-lal/`.**
- Directories must not overlap each other, the project or shared model storage; links and metadata
  escapes are rejected (`sources.validate_directory` through `config`).
- An unavailable source is recorded in availability diagnostics and excluded from search; it is
  never recreated just to write an error. Other sources still scan.
- **Processing never starts from a scan**; Process assets is always an explicit action.

## Gotchas

- Nested license files attach only to assets under their ancestor folders. Internet shortcuts are
  documentation, not license evidence.
- Equal manifests in sibling `fbx`, `fbx(unity)`, `gltf` and `obj` export trees can group exports
  into one logical asset; that does not prove the geometry is equivalent.
- Membership comes from registered sources (`library_policy`). The old pack list is history
  (`docs/history/library-membership-2026-10-14.json`); an install that still has its own
  `docs/library-membership.json` (`library_policy.LEGACY`) keeps that contract.
- After the October 14, 2026 move from one combined asset root to sources, reconnect MCP servers
  that were already running; `source_migration.py` refuses to run again (receipts under
  `data/library/source-migration/`).
- The owner-approved KayKit glTF cleanup (`scripts/historical/kaykit-gltf-maintenance.py`, receipts
  in `data/library/maintenance/kaykit-gltf-20261016/`) is the model for a one-time, manifest-driven
  removal of generated imports: it refuses links, out-of-root targets and reruns.

## Related

[Catalog contract](../../Architecture/Sources%20and%20Catalog/Catalog%20contract.md) ·
[Library updates](../../Architecture/Processing/Library%20updates.md) ·
[Storage discipline](../Platform%20and%20Storage/Storage%20discipline.md) ·
[Hash reuse and caches](../Search/Hash%20reuse%20and%20caches.md).
