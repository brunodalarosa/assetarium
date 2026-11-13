---
tags: [decision]
decided: 2026-11-07
area: Processing
replaces: [0004, 0007, 0014, 0015, 0022, 0023]
code: [incremental.inspection_input, image_inspection.inspection_input, incremental.caption_input, incremental.recorded_fingerprint, incremental.EQUIVALENT_WORKERS, retrieval.recorded_contract, inspection.blender_major, library_migration.recognized, library_migration.legacy_inspection_input, result_store.adopt, result_store.location_free, hash_cache.file_identity, publication.verified_hash, scripts/check-render-stability.py, scripts/check-engine-stability.py, scripts/check-rekey.py]
---
# 0028 — Result identity: what makes finished work run again

> **Approved by the owner on November 7, 2026** (decision review; direction "named exceptions": keep reuse
> pragmatic and write every exception down). The format-off rule was amended by
> [decision 0030](0030-counted-exclusions.md) the same day.

**Decision.** A finished result (previews, a description, a search vector) is reused for as long as its
**key** matches. The key holds every input this project controls that can change the result. It never holds
a location, an asset ID, a pack or a machine detail that does not change the result. Anything that **can**
change a result but is left out of its key is a **named exception** below, with the risk the owner accepted.
An exception that is not on this list is a bug.

## What each result is keyed by

| Result | In the key | Never in the key |
| --- | --- | --- |
| **3D inspection** (views, technical facts) | Source content and format; each required dependency's content and path *relative to the model*; texture-repair recipe (location-free); resolution; `blender_worker.py` (through `EQUIVALENT_WORKERS`), `render_math.py`, the repair worker when one applies; **Blender's major version** as it reports it (see [Blender](#blender-major-version-only)) | Asset ID, pack, absolute path, library folder; Blender's install path, minor and patch version (E7); render device; renders at a time; the kept-open host process |
| **2D image inspection** | Content of every available file; chosen format; adapter version; image policy; its code files; SVG renderer version for SVG | Path, name, asset ID |
| **Description** (built-in engine) | View image contents (not paths); model id and revision; prompt bytes; `caption_backend.py`; `runtime/caption/uv.lock`; generation policy; `caption_batching.py` for batched work | Batch size; which assets shared the batch; the engine configured today |
| **Description** (local-server engine) | View contents; the engine identity **the server reports** (engine, model); adapter file hash; prompt; policy | The model file's bytes |
| **Search vectors** | Embedding contract: model, **device (`cpu` or `cuda`)**, adapter hashes, runtime lock | Thread count (vectors are bit-identical at 8–32 threads) |

File hashes (`cache/file-hashes.sqlite`) are not results: they are an accelerator keyed by file identity (size,
mtime, NTFS ChangeTime and file ID; elsewhere size, mtime, ctime and inode). A missing or damaged record only
means hashing the bytes again.

## Verifying files

- **One shared hash record** (`cache/file-hashes.sqlite`) serves the desktop app, MCP server, embedding worker and
  scans; scans seed it, so the first search after launch reuses scan hashes. Runtime checks go through
  `publication.verified_hash`; do not add another hash cache. Tests use an isolated record (`LAL_HASH_CACHE`).
- **Fresh audits re-read bytes:** removal checks (`maintenance_files`, `fresh=True`) and the storage,
  preservation and relocation verify scripts (`hash_cache.require_fresh()`). Run one when exception E4 matters.
- **Boundary checks** (library folder validation, storage roots, registry and ownership reads, directory
  resolution) run once per request, not per file; a leaf that is a link is still resolved and rejected if it
  escapes.
- **Thumbnails** show the verified preview image only (cached by preview identity, 320 px). Asset detail and agent
  `get_asset` still verify the source files.
- Changed, replaced or missing files are still excluded and recorded as faults.
- Why: every search re-hashed about 8,000 source files and 11,500 preview PNGs (keyword 7 s, combined 19.5 s warm,
  34 s cold); the scanner already trusted file identity, and NTFS ChangeTime catches an edit that restores the
  modification time (`tests/test_hash_cache.py`).

## Named exceptions (inputs that can change a result but are not in its key)

| # | Exception | What can go wrong | Why it is accepted | Detect or undo |
| --- | --- | --- | --- | --- |
| E1 | **Render device.** A GPU and the CPU produce the same key. | GPU previews may differ from CPU previews by a few pixels; a library can mix both. | Re-rendering thousands of assets after switching device costs hours; previews are per asset, so a mix is harmless to search. Equivalence is proven for CPU→CPU only. | `render_settings` records the device on every preview. |
| E2 | **Batched descriptions.** Batch mates change the wording. | Describing the same asset again can word it differently. | 4.2× faster; the owner reviewed batched output as acceptable. The key proves the inputs, not the exact words. | Provenance records `batch` (size, assets, position). |
| E3 | **Local-server model by name.** | Swapping the model file behind the same name is not detected; old descriptions look current. | The server owns the file; Assetarium cannot hash it. Experimental engine only. | Provenance records what the server reported. |
| E4 | **File identity instead of bytes** (see [Verifying files](#verifying-files)). | A tool that rewrites NTFS ChangeTime on purpose can hide a same-size edit. | Re-hashing ~20,000 files on every search cost 7–35 s. | Run a `require_fresh()` byte audit. |
| E5 | **Line endings.** | None in practice: an LF/CRLF-only difference in a fingerprinted file is ignored. | A CRLF checkout nearly re-queued 11,635 results. | Any other byte change still counts. |
| E6 | **Proven-equivalent worker edits.** | An edit to `blender_worker.py` keeps old keys. | Only when `scripts/check-render-stability.py` shows identical CPU renders. | `EQUIVALENT_WORKERS` lists each mapping. |
| E7 | **Blender minor and patch version.** 5.1 and 5.5 produce the same key. | A rendering or importer change within one major version goes unnoticed: a few pixels, a triangle count, or a file that now imports (or no longer does) keeps its old result or fault. | Cycles and the Standard view are pinned, so minor releases render near-identically; re-rendering then re-describing the library costs hours (owner, November 13, 2026). | Every result records the full version (`technical.blender_version`). |

**Why devices differ between renders and vectors:** vectors from CPU and CUDA measurably differ (0.998 cosine)
and one index cannot mix them, so search keys the device (E1 does not apply to vectors). Previews stand alone.

## Blender: major version only

3D inspection keys hold the **major version** Blender reports (`inspection.blender_major`), never where it is
installed: moving, reinstalling or a minor update (5.1 → 5.5) re-renders nothing; 6.x renders anew (E7).
Setup asks to confirm a re-render only for another major version (`setup_core.keeps_inspections`).

- **Versions are remembered.** `blender --version` runs once per executable (path, size, mtime); the answer is
  kept in the ignored `data/inspection/blender-versions.json`. Never at app startup: only when a key is computed
  or setup checks a Blender.
- **Older keys** held the install path and its mtime. They stay current, never re-keyed or re-queued: an old key
  that matches any remembered Blender of today's major version counts (`library_migration.recognized`). A
  Blender never seen by this checkout cannot be recognized, so after upgrading, let the app compute keys once
  (open it, scan or process) before moving Blender. Deleting the file loses that memory for moved Blenders.
- A damaged file or a Blender that reports no version is a visible fault, never a guessed key.

## The quick answer: what re-queues work?

**Runs again:**
- The asset's content or a required dependency's content changes.
- The texture-repair recipe changes.
- A fingerprinted file changes: `blender_worker.py` (unless in `EQUIVALENT_WORKERS`), `render_math.py`, repair
  workers, caption prompts, `caption_backend.py`, `caption_batching.py`, the image code files, the embedding
  adapter, any `runtime/*/uv.lock`.
- The caption model revision changes.
- Blender changes major version (5.x → 6.x).
- Search device switches between `cpu` and `cuda` (search data only).
- A format is turned off and an asset's previews came from it while another of its formats is on: it becomes
  pending from that format ([decision 0030](0030-counted-exclusions.md); not built yet). Its old results are kept,
  so turning the format back on reuses them without rendering.

**Does not run again (on purpose):**
- A file moves, is renamed, duplicated or reorganized; a folder joins or splits.
- Blender moves, is reinstalled or gets a minor or patch update (E7).
- Render device, renders at a time, batch size, search threads, or the configured engine changes: finished
  work is checked against what it recorded.
- A fingerprint **definition** changes: existing results are recognized or re-keyed, never re-queued.
- An unchanged failure: it is kept and skipped, never retried automatically.

## Keep true

- Keys hold inputs, never locations or IDs. New result kinds get a row in the table above.
- An input left out of a key needs a new row in the exceptions table, with its risk, before it ships.
- Changing how a key is computed never re-queues existing results: old keys are recognized
  (`library_migration.recognized`) or re-keyed, proven by `scripts/check-rekey.py` on copies of real ledgers.
- Switching an engine, device or performance setting never invalidates another engine's or device's
  finished results.
- Engine refactors keep fingerprints (`scripts/check-engine-stability.py --compare`).

## Changes

- 2026-11-10: the Keep true line on re-keying no longer names code. The only re-keying code translated 0.1.0 keys and was removed with the 0.1.0 migration (owner: 0.2.0 is a fresh start; migrations are supported from 0.2.0 on).
- 2026-11-13: Blender is keyed by major version, not path and mtime (E7, owner); the Over-keyed section became [Blender: major version only](#blender-major-version-only). The Keep true line on key changes names `library_migration.recognized` and `scripts/check-rekey.py`.
