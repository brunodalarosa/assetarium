---
tags: [hub]
code: [src/local_asset_library, frontend/src, scripts, runtime, skills, tests]
verified: 2026-10-28
branch: feature/library-view
---
# Codebase

Module map of `src/local_asset_library/` (package name `local_asset_library`; brand name
Assetarium, older name LAL). Every module opens with a one-line docstring stating its guarantee:
read it first. Up: [Notebook](Notebook.md).

## Layout

| Path | What |
| --- | --- |
| `src/local_asset_library/` | The Python package (flat: one module per concern) |
| `frontend/` | React + TypeScript source of the desktop UI; builds into `src/local_asset_library/ui/build/` (committed) |
| `src/local_asset_library/ui/` | `index.html`, the sandboxed viewer (`viewer.html`, `viewer.js`, `interactive-preview.js`), `build/`, `vendor/` |
| `runtime/{mcp,caption,embedding,embedding-cpu}/` | Separately pinned uv projects behind the wrappers in `scripts/` ([Runtimes](Platform%20and%20Storage/Runtimes.md)) |
| `scripts/` | Wrappers, `library-batch.py`, `verify-*.py` WebView2 checks, evidence and maintenance tools |
| `tests/` | pytest suite, synthetic fixtures, real Blender fixtures (`conftest.py` prints a `Real-Blender tests:` line) |
| `skills/` | Agent-facing skills shipped to users: `local-asset-library` (MCP usage), `assetarium-setup` |
| `docs/` | User manual, plus JSON manifests and evidence that code reads ([Home](../Home.md#user-manual-outside-the-vault)) |
| `prompts/` | Versioned caption prompts (`caption-v1.txt` … `caption-v4.txt`, `caption-image-v1.txt`); their bytes are fingerprint inputs |

## Modules by area

- **Config and boundaries:** `config` (validated roots; the only path-boundary API; `venv_python`,
  `runtime_command`, `load_project_config`, `with_saved_blender`), `settings` (app-owned
  `data/library/settings.json`), `publication` (atomic JSON, pinned immutable generations,
  `verified_hash`), `store_versions` (stores refuse a newer format unchanged), `hash_cache` (shared stat-identity hash record), `parse_cache` (what parsers read from
  file bytes, by SHA-256; decision 0027), `library_policy` (neutral
  membership and budget defaults), `retention`, `maintenance_files`, `model_storage`,
  `notifications`, `search_check` (the search check on built-in sample images, [Core features](Platform%20and%20Storage/Core%20features.md)), `logs` (session logs: [Session logs](Platform%20and%20Storage/Session%20logs.md)).
- **Sources and catalog:** `sources` (library folders, scans, the combined catalog), `library_store`
  (`library.sqlite`: folders, recognized assets, recognition history, owner answers), `packs`
  (packs and bundles from folder structure), `pack_profiles` (a pack's answers as versioned rules, effect,
  signals), `variant_groups` (variant groups assigned in folder views), `quick_look` (names-only walk for the Add library
  folder wizard), `pack_agent` (pack tools for agents), `agent_activity` (the app's agent feed), `agent_practice`
  and `agent_practice_assets` (Try your agent), `transient` (practice log/cache isolation), `image_kinds` (model texture, material texture or 2D
  image), `library_view` (the Asset sources tab's tree, states and folder contents), `folder_view`
  (the small per-catalog views those tabs read instead of whole records),
  `library_migration` (the one-time move into the store; the only code naming the old folder),
  `source_operations`, `source_storage`, `source_browser`, `catalog`,
  `asset_structure`, `image_catalog`, `membership`, `recheck`, `texture_folders`. The October 14
  migration script was removed in November 2026; in git history at commit `af02e91`. See [Sources and Catalog](Sources%20and%20Catalog/Sources%20and%20Catalog.md).
- **Processing:** `incremental` (stage ledger and publication), `result_store` (results keyed by
  inputs, the result index, reuse for duplicates and moved files), `processing_queue` (Make
  previews / Generate descriptions queue), `inspection`, `blender_worker`,
  `blender_batch_worker`, `render_pool`, `render_devices`, `render_math`, `texture_repair`,
  `blender_repair_worker`, `blender_shared_dependency_worker`, `dependency_resolution`,
  `dependency_overrides`, `image_inspection`, `image_media`, `svg_worker`, `captions`,
  `caption_backend`, `caption_batching`, `caption_quality`,
  `library_index`, `gpu_queue`. See [Processing](Processing/Processing.md).
- **Search:** `retrieval`, `search_policy`, `library_cache`, `embedding_backend`, `embedding_cpu`,
  `search_speed`, `evaluation`. See [Search](Search/Search.md).
- **MCP:** `mcp_server`, `mcp_assets`, `setup_agent`; `scripts/asset-mcp.py` and
  `scripts/asset-worker.py`. See [MCP](MCP/MCP.md).
- **Desktop:** `desktop` (`DesktopBridge`), `desktop_service`, `interactive_preview`,
  `asset_collections`, `asset_tags`, `collection_export`. See [Desktop App](Desktop%20App/Desktop%20App.md).
- **Setup and engines:** `setup_core`, `setup_agent`, `description_engines`, `engines`,
  `engine_transformers`, `engine_server`. See [Setup and Engines](Setup%20and%20Engines/Setup%20and%20Engines.md).
- **Entry points:** `cli` (`local-assets`), `owner_commands` (owner terminal commands; deletions
  need an interactive terminal, no bypass flag).

## Third-party code

- `src/local_asset_library/ui/vendor/`: Online 3D Viewer, Draco decoder, lighting cube, with
  upstream notices; byte-for-byte (`-text` in `.gitattributes`). See [3D preview](Desktop%20App/3D%20preview.md).
- `frontend/src/components/beui/` and `frontend/src/lib/`: beUI components (MIT), adapted where
  marked "Assetarium"; Geist font (OFL). Licenses in `frontend/licenses/`.
- Models (not in the repo): Qwen3-VL-2B-Instruct (descriptions) and EmbeddingGemma (search),
  pinned by revision in `docs/caption-model.json` and `docs/embedding-model.json`, stored in the
  shared models folder set as `[storage].models`. See [Upstream](../Reference/Upstream.md).

## Misleading or historical names

- **"Step N" in names and docstrings is history, not scope.** The project began as a 40-asset
  pilot in eight steps (October 2026); `catalog.py` and `cli.py` still mention "step 2". The
  pilot-only code paths were removed in November 2026.
- **Search indexes from 0.2.0 still carry pilot-era names** (`"pilot-retrieval-v1"`, `pilot_ids`).
  `retrieval.current_meta` reads them as `retrieval-v1` / `member_ids`; the next processing run
  rewrites them. Drop `retrieval.LEGACY_NAMES` only in a release that stops upgrading from 0.2.0.
- `catalog-summary.json` and `embedding-contract.json` are generated under `data/`
  (`data/reports/`, `data/library/`), not docs.
- `docs/library-membership.json` is referenced by `library_policy.LEGACY` and tests but is absent on
  purpose: only an older install that still has one keeps that contract.
- The package and CLI keep the old name (`local_asset_library`, `local-assets`, `Local Asset
  Library.vbs`); the app is branded Assetarium.
- **Before renaming anything, check whether the file is hashed into a fingerprint.** Editing
  `caption_backend.py`, `caption_batching.py`, `engine_server.py`, the Blender workers
  (`blender_worker.py`, `render_math.py`, repair workers) or a `runtime/*/uv.lock` sends finished
  descriptions or inspections back to pending (`incremental.py`, decision 0022). Search-index
  metadata names are not fingerprint inputs: vector reuse keys on each vector's own fingerprint.
- The pilot-era and one-time scripts (`scripts/historical/`) were removed in November 2026: they needed
  the original owner's data and called code removed since. Run them from commit `af02e91` or earlier.
