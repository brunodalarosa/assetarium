---
tags: [decision]
decided: 2026-10-18
---
# 0007 — Batched description generation

**Decision.**
- **Batching:** Generate descriptions (the `incremental.process` caption stage; since
  [decision 0008](0008-optional-descriptions-and-notifications.md) no longer part of
  Process assets), also used
  by `library-batch.py` and the CLI) and overnight description runs generate
  descriptions for several assets in one Qwen3-VL call (`caption_batching.py`).
  Model, revision, prompt, image preparation, sampling settings, seed, 1,100-token
  limit and 120-second generation limit are unchanged; sequences are left-padded.
- **Setting:** *Settings → General → Description batch size* offers 1, 2, 4 or 8
  (default 8), saved as `caption_batch_size` in `data/library/settings.json`.
- **Per-asset outcomes:** each asset is still validated, saved, published and
  checkpointed on its own. One invalid output or input fault fails only that
  asset; a batch-wide runtime fault fails the batch's assets without retry.
- **Out of GPU memory** is a machine limit, not an asset fault: the run stops with
  “Not enough GPU memory for description batch size N. Lower it in Settings →
  General …”, nothing is recorded as failed and those assets stay pending.
- **Existing results are kept:** `caption_backend.py` is unchanged and completed
  descriptions are validated against the generation mode recorded in their
  provenance (none recorded = `sequential`), like prompt versions. Their
  fingerprints stay byte-identical. New descriptions record
  `generation_mode: batched-v1` and `batch` (`size`, `assets`, `position`), and
  their fingerprint adds `caption_batching.py` and the batched generation policy.
  The batch size is provenance only, so changing it never re-queues anything.
- **Cancel** waits for the current batch (about 15–20 s at size 8).
- **Overnight interruption:** `inflight.json` lists every asset in the batch; an
  interrupted batch records each as interrupted and is not generated again in
  that run.

**Why.** Generation was limited by per-token overhead, not by the GPU (about 41%
busy, 27 tokens/s). A 20-asset benchmark (`scripts/benchmark-caption-batching.py`,
`data/evidence/caption-batch-benchmark/batching-2026-10-18a/`) measured 9.24 s per asset
one at a time and 2.22 s at batch 8 (4.2×), with 20/20 valid outputs and 6.4 GB
peak GPU memory. The owner reviewed the batched descriptions and found them
acceptable.

**Trade-off accepted.** One-at-a-time generation reproduced stored descriptions
exactly (20/20). Batched wording also depends on which assets share a batch, so a
rerun of the same asset can word its description differently.

**Keep true.** Do not edit `caption_backend.py` without accepting that every
one-at-a-time description is re-queued. Never turn running out of GPU memory into
asset faults or an automatic smaller-batch retry without the owner. Keep batch
provenance on new descriptions.

> **Scope note (October 25, 2026).** Batching applies to the built-in Transformers engine. The
> experimental local-server engine of [decision 0015](0015-description-engines.md) sends one image per
> request (sequential); the batch size setting does not change it.
