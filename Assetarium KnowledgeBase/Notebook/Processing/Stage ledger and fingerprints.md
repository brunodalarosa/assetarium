---
area: Processing
tags: [system]
code: [incremental.ledger, incremental.checkpoint, incremental.inspection_input, incremental.caption_input, incremental.recorded_fingerprint, incremental.prompt_hash, incremental.EQUIVALENT_WORKERS, incremental.process, incremental.publish, retrieval.recorded_contract, publication.line_ending_hashes, scripts/check-render-stability.py, scripts/check-engine-stability.py]
verified: 2026-10-28
branch: feature/library-view
---
# Stage ledger and fingerprints

Hub: [Processing](Processing.md). Every asset moves through stages (inspection, caption,
embeddings); the ledger records each stage's input fingerprint and outcome, and a stage reruns only
when its fingerprint changes. Start at `incremental.inspection_input` and `incremental.caption_input`.

## How it works

- Per-source state: `metadata-lal/library/import-status.json` holds each asset's current file and
  dependency fingerprint, attempted state and outcome; the ledger keeps append-only history.
- The **inspection** fingerprint hashes the source content, the render resolution, the raw bytes of
  `blender_worker.py` and `render_math.py` (plus the repair worker when a texture repair applies),
  **the Blender path and its executable's mtime**. The **caption** fingerprint covers the prompt
  bytes (`prompts/caption-v*.txt`), `caption_backend.py`, `caption_batching.py` and the caption
  runtime lock. The **embedding** contract covers the adapter and the embedding runtime lock.
- Readiness uses saved outcomes: failed or unsupported stages block dependent work; other unfinished
  work stays pending. Captions are not part of import readiness (descriptions are optional, decision 0008).

## Rules

- **Editing a fingerprinted file re-queues every finished result that depends on it.** That covers
  `blender_worker.py`, `render_math.py`, the repair workers, caption code and prompts, the embedding
  adapter and the runtime `uv.lock` files. Don't touch them for portability or style.
- **A `blender_worker.py` edit that keeps CPU renders identical may keep old results only through
  `incremental.EQUIVALENT_WORKERS`**, proven with `scripts/check-render-stability.py` (decision 0022).
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
- Editing `incremental.py`, `overnight.py` or `library_index.py` changes the overnight code
  contract: an overnight run planned before the edit refuses to continue.

## Friction and improvements

- **No `.gitattributes` eol rule for fingerprinted files**: the tolerance code exists because of it.
  See [Improvements](../Improvements.md#tooling-and-build). Seen: 2026-10-18

## Related

[Blender rendering](Blender%20rendering.md) · [Descriptions](Descriptions.md) ·
[Library updates](../../Architecture/Processing/Library%20updates.md) ·
[Inference ports](../../Architecture/Setup%20and%20Engines/Inference%20ports.md).
