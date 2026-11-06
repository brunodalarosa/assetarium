---
area: Processing
tags: [system]
code: [captions.py, caption_backend.QwenBackend, caption_batching.py, caption_quality.py, caption_review.py, overnight.py, engines.description_engine, incremental.run_captions, scripts/record_caption_review.py, prompts]
verified: 2026-10-28
branch: feature/library-view
---
# Descriptions

Hub: [Processing](Processing.md). Optional visual descriptions of each asset, written from its
rendered previews by Qwen3-VL (or an experimental local model server). Start at
`incremental.run_captions` and `engines.description_engine`. Decisions:
[0007](../../Decisions/0007-batched-description-generation.md),
[0008](../../Decisions/0008-optional-descriptions-and-notifications.md),
[0015](../../Decisions/0015-description-engines.md).

## How it works

- Descriptions run only from **Generate descriptions** (per source) or an owner-started overnight run
  (`overnight.py`); Process assets never writes them.
- Batches default to 8 assets; finished ones are kept, and running out of GPU memory leaves the rest
  pending with a suggestion to lower the batch size.
- The core parses and validates every engine's text, so every engine meets the same rules
  ([Inference ports](../../Architecture/Setup%20and%20Engines/Inference%20ports.md)).
- Caption severity (`caption_quality.py`) is stored separately from immutable generation and review
  evidence: `clear`, `review_note`, `warning` or `fault`.

## Rules

- **Descriptions are optional**: a missing, failed or stale description never makes work pending and
  never makes an asset faulty for search.
- **Apply [Caption severity](../../Architecture/Processing/Caption%20severity.md) when reviewing**:
  uncertain detail is a `review_note`; a misleading identity, color or structure error is a `warning`;
  `caption_faulty` only for failed or unusable generation. New AI reviews go through
  `scripts/record_caption_review.py` with `findings` (`severity`, `evidence`, `reason`).
- **Never rerun models, rewrite assets or manufacture a caption to clear a note.**
- Inference is offline with no fallback to another device, model or engine.

## Gotchas

- Prompt files are fingerprint inputs (`incremental.prompt_hash`); a prompt edit re-queues every
  description made with that prompt version.
- Switching engines never redoes finished descriptions: each keeps the mode and engine it was made with.
- Caption rules were calibrated on Qwen3-VL-2B; other models are unverified.

## Related

[Stage ledger and fingerprints](Stage%20ledger%20and%20fingerprints.md) · [GPU lease](GPU%20lease.md) ·
`docs/caption-contract.md` · [Overnight descriptions](../../../docs/overnight-descriptions.md).
