---
area: Sources and Catalog
tags: [system]
code: [sources.registry, sources.add, sources.Covered, sources.scan_source, sources.aggregate, sources.generated_path, sources.bound, sources.importing_failures, folder_view.py, folder_view.connect, library_store.py, library_store.recognize, result_store.py, result_store.reattach, source_operations.py, library_migration.py, catalog.walk_source, hash_cache.py, library_policy.DEFAULT_BUDGET, library_policy.LEGACY]
verified: 2026-10-31
branch: feature/library-view
---
# Sources

Hub: [Sources and Catalog](Sources%20and%20Catalog.md). A library folder (in code still a "source") is
one watched root. Start reading at `sources.py` (folders, scans, the combined catalog),
`library_store.py` (folders, recognized assets and their history) and `source_operations.py`
(durable, cancellable operations the [processing queue](../Processing/Processing%20queue.md) starts). User guide: [Asset sources](../../../docs/asset-sources.md).
Binding: [decision 0032](../../Decisions/0032-library-store-and-queue.md).

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
- **Fast scans** (decision 0027): the walk reuses hashes by stat identity (decision 0004); what a
  file's bytes say (FBX texture names, glTF/OBJ/MTL/DAE references) comes from
  `parse_cache.py` (`parse-cache.sqlite` in the store), keyed by SHA-256, the parser kind (which
  includes the file extension: the same bytes as `.glb` and `.gltf` parse differently) and the
  parsers' own source (`parse_cache.parser_key`), so editing `catalog.parsed_references`,
  `image_kinds.fbx_names` or `catalog.read_text` starts fresh keys. New answers are saved only when
  the session ends without error (`scan_source` keeps it open through the "Verifying files" walk)
  and only for files whose size and mtime still match their hash (`parse_cache.unchanged`); a
  damaged or unwritable cache is logged and never fails a scan. Matching references to existing
  files (`catalog.dependencies`, including OBJ's existing-file `mtllib` choice) still runs every
  scan. `build_inventory` runs in `publication.request_scope`, so path checks resolve each folder
  once. Each scan logs `Scan finished · …` with files, hashed, new/changed/removed assets,
  `reparsed` and seconds per phase (`sources.log_scan`).
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
- **Processing never starts from a scan**; Make previews and Generate descriptions are always explicit actions.

- **Folder views** (`folder_view.py`): the Asset sources tab, the processing queue (`resolve`, `failures`,
  blocked counts), source status (`sources._format_status`), `importing_failures`, `locate` and
  `setup_core.processed_models` read one small SQLite view per catalog generation
  (`<store>/folders/<id>/library/views/<generation>-<stamp>.sqlite`), never whole records. The stamp covers
  the catalog and embedding index stats and the processing formats. A build streams the catalog with
  `json_remove` dropping heavy fields (`folder_view.HEAVY`), one per catalog, at most two at once.
  **Never call `sources.read_records` from a window or MCP read path**: a 73k-asset catalog is 1.1 GB and
  costs ~2.6 GiB to load; that is what made the app use 14 GB (October 31, 2026).
- **Packs** (`packs.detect`, cached by `packs.structure`) come from folder structure only and are never
  stored in records, so detecting them never makes assets pending. Owner answers (`pack`, `pack_name`,
  `image_kind`, `variant_axis`, `separate_descriptions`, `engine_copy`, `structure_reviewed`, `visit`) live in
  `library.sqlite` `answers`; a pack's answers form its [pack profile](Pack%20profiles.md).
- Assets whose folder is excluded become `excluded` (not Missing) and return with their IDs when included again.
- **Image kinds** (`image_kinds.classify`, called from `image_catalog.image_assets`): model references,
  then an owner answer, then the pack prior, model stems, material names, folder words and neighbours;
  decoded pixel hints (`pixel_evidence`, recorded by `image_inspection.run`) decide only an image with no
  other evidence. Model textures become `model_dependency_image` inventory rows, not assets.

## Gotchas

- A view may lag its catalog: readers wait `folder_view.WAIT` seconds for a rebuild, then use the last view,
  and a view that took a second or more to build is rebuilt at most every three build durations. Code that
  acts on the result (the queue resolving work, `locate`, `importing_failures`) uses `connect(fresh=True)`.
- Missing assets keep their whole saved record in `library.sqlite`; lists use
  `library_store.missing_list` / `missing_count`, which never parse it.

- The old-folder migration (`library_migration.apply`) computes old fingerprints and per-folder keys under
  `_old_world`, a view of the old source registry: once folders are joined, a model's provider is no longer a
  library folder, yet its old key still needs it. Its check (`verify`) measures only active folders; a
  `replaced` folder has no assets of its own. A rerun joins faulty folders into an existing library folder and
  re-checks `unverified` ones from `absorbed/<id>/jobs.sqlite`.
- Kept IDs need not match the `asset_id(pack, locator)` formula; `asset_structure.validate_record` checks
  only the format.

- Recognition is by content, so moved-and-edited at once is a new asset plus a Missing one.
- A moved asset keeps its previews and descriptions at once, but its search vectors hash source
  paths, so its search data is pending until the next Make previews (CPU only).
- Nested license files attach only to assets under their ancestor folders. Internet shortcuts are
  documentation, not license evidence.
- Equal manifests in sibling `fbx`, `fbx(unity)`, `gltf` and `obj` export trees can group exports
  into one logical asset; that does not prove the geometry is equivalent.
- `catalog.parsed_references` and `image_kinds.fbx_names` must stay pure functions of the file's
  bytes: their answers are cached by SHA-256 (`parse_cache.py`). Anything that depends on which
  files exist (OBJ's existing-file `mtllib` choice, a parse stopped by a bad `mtllib` line) is
  decided at replay in `catalog.dependencies`. A read failure (`ConfigError`, `OSError`) is never cached.
- The October 14, 2026 move from one combined root to sources is history:
  `scripts/historical/source_migration.py` (receipts under `data/library/source-migration/`).

## Related

[Catalog contract](../../Architecture/Sources%20and%20Catalog/Catalog%20contract.md) ·
[Library updates](../../Architecture/Processing/Library%20updates.md) ·
[Storage discipline](../Platform%20and%20Storage/Storage%20discipline.md) ·
[Stage ledger and fingerprints](../Processing/Stage%20ledger%20and%20fingerprints.md) ·
[Hash reuse and caches](../Search/Hash%20reuse%20and%20caches.md).
