---
tags: [decision]
decided: 2026-11-07
supersedes: [0004, 0007 (identity parts), 0015 (fingerprint part), 0022 (device and equivalent workers), 0023 ("results keyed by inputs")]
code: [incremental.inspection_input, image_inspection.inspection_input, incremental.caption_input, incremental.recorded_fingerprint, incremental.EQUIVALENT_WORKERS, retrieval.recorded_contract, result_store.adopt, result_store.location_free, library_migration.rekey, hash_cache.file_identity, publication.verified_hash, scripts/check-render-stability.py, scripts/check-engine-stability.py, scripts/check-rekey.py]
superseded_in_part_by: "0030"
---
# 0028 — Result identity: what makes finished work run again

> **Approved by the owner on November 7, 2026** (decision review; direction "named exceptions": keep reuse
> pragmatic and write every exception down). It supersedes the parts listed under
> [What this replaces](#what-this-replaces); those records say so at the top.

**Decision.** A finished result (previews, a description, a search vector) is reused for as long as its
**key** matches. The key holds every input this project controls that can change the result. It never holds
a location, an asset ID, a pack or a machine detail that does not change the result. Anything that **can**
change a result but is left out of its key is a **named exception** below, with the risk the owner accepted.
An exception that is not on this list is a bug.

## What each result is keyed by

| Result | In the key | Never in the key |
| --- | --- | --- |
| **3D inspection** (views, technical facts) | Source content and format; each required dependency's content and path *relative to the model*; texture-repair recipe (location-free); resolution; `blender_worker.py` (through `EQUIVALENT_WORKERS`), `render_math.py`, the repair worker when one applies; **Blender path and its executable's mtime** (see [Over-keyed](#over-keyed-blender-path)) | Asset ID, pack, absolute path, library folder; render device; renders at a time; the kept-open host process |
| **2D image inspection** | Content of every available file; chosen format; adapter version; image policy; its code files; SVG renderer version for SVG | Path, name, asset ID |
| **Description** (built-in engine) | View image contents (not paths); model id and revision; prompt bytes; `caption_backend.py`; `runtime/caption/uv.lock`; generation policy; `caption_batching.py` for batched work | Batch size; which assets shared the batch; the engine configured today |
| **Description** (local-server engine) | View contents; the engine identity **the server reports** (engine, model); adapter file hash; prompt; policy | The model file's bytes |
| **Search vectors** | Embedding contract: model, **device (`cpu` or `cuda`)**, adapter hashes, runtime lock | Thread count (vectors are bit-identical at 8–32 threads) |

File hashes (`cache/file-hashes.sqlite`) are not results: they are an accelerator keyed by file identity (size,
mtime, NTFS ChangeTime and file ID; elsewhere size, mtime, ctime and inode). A missing or damaged record only
means hashing the bytes again.

## Named exceptions (inputs that can change a result but are not in its key)

| # | Exception | What can go wrong | Why it is accepted | Detect or undo |
| --- | --- | --- | --- | --- |
| E1 | **Render device.** A GPU and the CPU produce the same key. | GPU previews may differ from CPU previews by a few pixels; a library can mix both. | Re-rendering thousands of assets after switching device costs hours; previews are per asset, so a mix is harmless to search. Equivalence is proven for CPU→CPU only. | `render_settings` records the device on every preview. |
| E2 | **Batched descriptions.** Batch mates change the wording. | Describing the same asset again can word it differently. | 4.2× faster; the owner reviewed batched output as acceptable. The key proves the inputs, not the exact words. | Provenance records `batch` (size, assets, position). |
| E3 | **Local-server model by name.** | Swapping the model file behind the same name is not detected; old descriptions look current. | The server owns the file; Assetarium cannot hash it. Experimental engine only. | Provenance records what the server reported. |
| E4 | **File identity instead of bytes.** | A tool that rewrites NTFS ChangeTime on purpose can hide a same-size edit. | Re-hashing ~20,000 files on every search cost 7–35 s. | Run a `require_fresh()` byte audit. |
| E5 | **Line endings.** | None in practice: an LF/CRLF-only difference in a fingerprinted file is ignored. | A CRLF checkout nearly re-queued 11,635 results. | Any other byte change still counts. |
| E6 | **Proven-equivalent worker edits.** | An edit to `blender_worker.py` keeps old keys. | Only when `scripts/check-render-stability.py` shows identical CPU renders. | `EQUIVALENT_WORKERS` lists each mapping. |

**Why devices differ between renders and vectors:** vectors from CPU and CUDA measurably differ (0.998 cosine)
and one index cannot mix them, so search keys the device (E1 does not apply to vectors). Previews stand alone.

## Over-keyed: Blender path

The Blender **path** and its executable's mtime are in the inspection key. Moving, reinstalling or updating
the same Blender re-renders every 3D asset, although the path alone changes no pixel.

**Owner direction (November 7, 2026):** key Blender by its **version** (what it reports), not by where it is
installed. This needs a code change, re-keying through `library_migration.rekey` so nothing is re-queued, and
the setup confirmation then asks only when the version changes. **Not implemented yet**; until it is, the path
stays in the key and setup keeps asking before saving a different Blender.

## The quick answer: what re-queues work?

**Runs again:**
- The asset's content or a required dependency's content changes.
- The texture-repair recipe changes.
- A fingerprinted file changes: `blender_worker.py` (unless in `EQUIVALENT_WORKERS`), `render_math.py`, repair
  workers, caption prompts, `caption_backend.py`, `caption_batching.py`, the image code files, the embedding
  adapter, any `runtime/*/uv.lock`.
- The caption model revision changes.
- The Blender path or executable changes (until the version change above lands).
- Search device switches between `cpu` and `cuda` (search data only).
- A format is turned off and an asset's previews came from it while another of its formats is on: it becomes
  pending from that format ([decision 0030](0030-counted-exclusions.md); not built yet). Its old results are kept,
  so turning the format back on reuses them without rendering.

**Does not run again (on purpose):**
- A file moves, is renamed, duplicated or reorganized; a folder joins or splits.
- Render device, renders at a time, batch size, search threads, or the configured engine changes: finished
  work is checked against what it recorded.
- A fingerprint **definition** changes: existing results are re-keyed, never re-queued.
- An unchanged failure: it is kept and skipped, never retried automatically.

## Keep true

- Keys hold inputs, never locations or IDs. New result kinds get a row in the table above.
- An input left out of a key needs a new row in the exceptions table, with its risk, before it ships.
- Changing how a key is computed re-keys existing results (`library_migration.rekey`, proven by
  `scripts/check-rekey.py`), never re-queues them.
- Switching an engine, device or performance setting never invalidates another engine's or device's
  finished results.
- Engine refactors keep fingerprints (`scripts/check-engine-stability.py --compare`).

## What this replaces

| Decision | Part superseded by this record | Part that stays where it is |
| --- | --- | --- |
| [0004](0004-stat-identity-hash-reuse.md) | All of it (file identity, accelerator, E4) | Boundary checks per request, thumbnails → Scan pillar |
| [0007](0007-batched-description-generation.md) | Fingerprints, provenance, E2 | Batch size setting, out-of-memory stop, cancel, overnight → Engines pillar |
| [0015](0015-description-engines.md) | Provenance and fingerprints, E3 | Ports and adapters, server rules → Engines pillar |
| [0022](0022-parallel-rendering.md) | Device outside the key, `EQUIVALENT_WORKERS`, E1, E6 | Kept-open renders, speed test, owner limits → Rendering pillar |
| [0023](0023-central-asset-library.md) | "Results are a cache keyed by their inputs" and the re-key rule | Store, identity by recognition, packs, queue → Store pillar |
| [0014](0014-setup-wizard.md) | "Blender change cost" | The rest of setup → Setup pillar |

Notebook detail: [Stage ledger and fingerprints](../Notebook/Processing/Stage%20ledger%20and%20fingerprints.md).
