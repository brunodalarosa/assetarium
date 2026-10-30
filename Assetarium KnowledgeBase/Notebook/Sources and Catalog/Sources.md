---
area: Sources and Catalog
tags: [system]
code: [sources.registry, sources.add, sources.Covered, sources.scan_source, sources.aggregate, sources.generated_path, sources.bound, sources.importing_failures, library_store.py, library_store.recognize, result_store.py, result_store.reattach, source_operations.py, library_migration.py, catalog.walk_source, hash_cache.py, library_policy.DEFAULT_BUDGET, library_policy.LEGACY]
verified: 2026-10-30
branch: feature/library-view
---
# Sources

Hub: [Sources and Catalog](Sources%20and%20Catalog.md). A library folder (in code still a "source") is
one watched root. Start reading at `sources.py` (folders, scans, the combined catalog),
`library_store.py` (folders, recognized assets and their history) and `source_operations.py`
(durable, cancellable Process assets operations). User guide: [Asset sources](../../../docs/asset-sources.md).
Binding: [decision 0023](../../Decisions/0023-central-asset-library.md).

## How it works

- **Nothing is written into a library folder.** The library store (`config.library_store()`:
  `[storage].library`, default the ignored `data/library-store/`) holds `library.sqlite` (folders,
  assets, recognition history, owner answers), `ledger.sqlite` (one stage ledger for the store),
  `folders/<folder id>/` (each folder's working data: catalog generations, status, batches,
  operation logs, `source.json` settings) and the shared result areas `inspection/`, `captions/`
  and `results/`.
- `sources.registry` keeps its old shape (`sources`, `detached`) but reads `library.sqlite`.
  `sources.bound` points `metadata_root` at `folders/<id>/`; `sources.generated_path` sends
  `inspection/`, `captions/` and `results/` to the store root for every folder, so results keyed
  by inputs (`result_store.py`) are shared by duplicates and survive moves.
- **Recognition** (`library_store.recognize`, called by `scan_source` right after
  `build_inventory`): a known locator (`source_relative_identity`) keeps its ID (new content =
  edited); otherwise the same content as a vanished or Missing asset is that asset moved; the same
  content as a present asset is a duplicate with its own formula ID. Vanished assets become
  Missing with a record snapshot until `forget_missing`. Every non-trivial recognition is in the
  `recognition` table (`library_store.history`).
- After a scan writes the working catalog, `result_store.reattach` fills recognized, moved or
  duplicated assets from finished results with the same key. Nothing renders or runs a model.
- Adding a folder **inside** a library folder raises `sources.Covered` (the app offers Show it).
  Adding one **around** library folders marks them `replaced`, moves their assets' locators one
  level down (`library_store.relocate`), and the next scan carries their records over
  (`library_store.carried`). Removing a folder keeps everything; adding the same path again
  restores its ID and key.
- The combined catalog and search index are derived from the folders' publications
  (`sources.aggregate`). Scans reuse hashes while a file's stat identity is unchanged (decision
  0004) and never run models or renders.

## Rules

- **Originals are read only, and no code writes into a library folder.** The worker refuses an
  output root inside the source.
- Folders must not overlap each other, the project, the library store or shared models; links are
  rejected (`sources.validate_directory`).
- An old generated folder (`library_migration.LEGACY_METADATA_DIR`) is never scanned or read as an
  original; only `library_migration.py` names it (`tests/test_metadata_name.py`).
- **Processing never starts from a scan**; Process assets is always an explicit action.

## Gotchas

- Recognition is by content, so moved-and-edited at once is a new asset plus a Missing one.
- A moved asset keeps its previews and descriptions at once, but its search vectors hash source
  paths, so its search data is pending until the next Make previews (CPU only).
- Nested license files attach only to assets under their ancestor folders. Internet shortcuts are
  documentation, not license evidence.
- Equal manifests in sibling `fbx`, `fbx(unity)`, `gltf` and `obj` export trees can group exports
  into one logical asset; that does not prove the geometry is equivalent.
- The October 14, 2026 move from one combined root to sources is history:
  `scripts/historical/source_migration.py` (receipts under `data/library/source-migration/`).

## Related

[Catalog contract](../../Architecture/Sources%20and%20Catalog/Catalog%20contract.md) ·
[Library updates](../../Architecture/Processing/Library%20updates.md) ·
[Storage discipline](../Platform%20and%20Storage/Storage%20discipline.md) ·
[Stage ledger and fingerprints](../Processing/Stage%20ledger%20and%20fingerprints.md) ·
[Hash reuse and caches](../Search/Hash%20reuse%20and%20caches.md).
