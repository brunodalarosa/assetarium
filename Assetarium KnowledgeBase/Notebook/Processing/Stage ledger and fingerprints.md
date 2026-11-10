---
area: Processing
tags: [system]
code: [result_store.py, result_store.adopt, result_store.reattach, incremental.ledger, incremental.checkpoint, incremental.inspection_input, incremental.caption_input, incremental.recorded_fingerprint, incremental.prompt_hash, incremental.EQUIVALENT_WORKERS, incremental.process, incremental.publish, retrieval.recorded_contract, publication.line_ending_hashes, scripts/check-render-stability.py, scripts/check-engine-stability.py]
verified: 2026-10-30
branch: feature/library-view
---
# Stage ledger and fingerprints

Hub: [Processing](Processing.md). Every asset moves through stages (inspection, caption,
embeddings); the ledger records each stage's input fingerprint and outcome, and a stage reruns only
when its fingerprint changes. Start at `incremental.inspection_input` and `incremental.caption_input`.

## How it works

- **Keys hold inputs, never locations (decision 0028).** The inspection key hashes the inspected file's
  content and format, each dependency's content with its path *relative to the inspected file*, the
  texture-repair recipe without asset IDs (a shared-texture recipe through `dependency_resolution.portable`:
  provider paths relative to the model, no folder IDs, so joining split folders keeps the key), and the settings/code below; the caption key hashes view
  contents, not view paths; the image key hashes content only. No asset ID, pack or source-prefixed
  path. One ledger (`library-store/ledger.sqlite`) serves every library folder.
- `result_store` indexes finished results by (stage, key). New results go to
  `results/<stage>/<kk>/<key>/`. A record whose key has a finished result adopts it (a duplicate, a
  moved file, a folder added around others) at scan time (`reattach`) or when processing runs; nothing
  renders. Publishing an inspection adds the textures Blender found to the record, which changes its
  key, so `incremental.process` indexes the result under both the key it ran with (what a fresh copy
  has) and the key it finished with.

- Per-folder state: `library/import-status.json` in the folder's working data holds each asset's current file and
  dependency fingerprint, attempted state and outcome; the ledger keeps append-only history.
- The **inspection** fingerprint hashes the source content, the render resolution, the raw bytes of
  `blender_worker.py` and `render_math.py` (plus the repair worker when a texture repair applies),
  **the Blender path and its executable's mtime**. The **caption** fingerprint covers the prompt
  bytes (`prompts/caption-v*.txt`), `caption_backend.py`, `caption_batching.py` and the caption
  runtime lock. The **embedding** contract covers the adapter and the embedding runtime lock.
- Readiness uses saved outcomes: failed or unsupported stages block dependent work; other unfinished
  work stays pending. Captions are not part of import readiness (descriptions are optional, decision 0033).

## Rules

- **A fingerprint-definition change re-keys, never re-queues** (decision 0028). No re-keying code exists right
  now: the one for the 0.1.0 → store move left with that move in November 2026 (commit `af02e91` has it). What it taught: recompute the old fingerprint verbatim, give the new key only to a
  row the old one still matches, leave stale rows pending, and translate a stale *failed* row's `fault_content`
  or the unchanged fault looks changed and is retried. Prove it on copies of the ledgers before shipping.

- **Editing a fingerprinted file re-queues every finished result that depends on it.** That covers
  `blender_worker.py`, `render_math.py`, the repair workers, caption code and prompts, the embedding
  adapter and the runtime `uv.lock` files. Don't touch them for portability or style.
- **A `blender_worker.py` edit that keeps CPU renders identical may keep old results only through
  `incremental.EQUIVALENT_WORKERS`**, proven with `scripts/check-render-stability.py` (decision 0028).
  Add both the LF and CRLF hashes, as the existing entries do.
- **Engine refactors must keep fingerprints**: prove it with `scripts/check-engine-stability.py --compare`.
- Changing the saved Blender (or upgrading it in place) changes the inspection fingerprint and
  re-renders 3D previews; that's why setup asks before saving a different Blender.
- Unchanged failures are retained and skipped; processing is never permission to repair originals or
  retry them.

## Gotchas

- Fingerprints hash raw bytes, so a CRLF checkout of an LF file would re-queue everything.
  `incremental.recorded_fingerprint`, `retrieval.recorded_contract` and
  `publication.line_ending_hashes` accept LF/CRLF-only differences against the recorded value
  (added October 18, 2026, after it nearly re-queued 11,635 results). Any other byte change still counts.
  For search the recorded value is the search check's receipt, or else the published index's
  contract: vectors from another checkout's generated data with no receipt used to fail every query
  with "Query/index embedding contract mismatch" (fixed October 30, 2026).

## Friction and improvements

- **No `.gitattributes` eol rule for fingerprinted files**: the tolerance code exists because of it.
  See [Improvements](../Improvements.md#tooling-and-build). Seen: 2026-10-18

## Related

[Blender rendering](Blender%20rendering.md) · [Descriptions](Descriptions.md) ·
[Library updates](../../Architecture/Processing/Library%20updates.md) ·
[Inference ports](../../Architecture/Setup%20and%20Engines/Inference%20ports.md).
