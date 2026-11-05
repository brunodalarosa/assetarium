---
tags: [architecture]
level: system
parent: "[Architecture](../Architecture.md)"
status: draft
code: [description_engines.DescriptionEngine, description_engines.Embedder, description_engines.EngineStop, engines.description_engine, engines.embedder, engine_transformers.py, engine_server.py, embedding_cpu.EmbeddingCpuBackend, mcp_server.RemoteBackend, scripts/check-engine-stability.py]
verified:
branch:
---
# Inference ports

> Model inference is the only part of Assetarium built as ports and adapters: the caption stage,
> overnight runs, indexing and search depend on two small contracts, and `engines.py` is the only
> place that picks the adapter. Refactors must keep fingerprints, proven with
> `scripts/check-engine-stability.py --compare`.

Up: [Architecture](../Architecture.md) · Decision: [0015](../../Decisions/0015-description-engines.md),
[0018](../../Decisions/0018-cpu-search-embedder.md) · Where in code: [Setup and Engines](../../Notebook/Setup%20and%20Engines/Setup%20and%20Engines.md) ·
User guide: [docs/description-engines.md](../../../docs/description-engines.md)

Moved from `docs/description-engines.md` on 2026-10-28.

## Concepts

| Piece | Module | Role |
| --- | --- | --- |
| Ports | `description_engines.py` | `DescriptionEngine`, `Embedder`, `EngineStop` (`MemoryLimitError`, `EngineUnavailableError`) |
| Composition root | `engines.py` | `description_engine(config)`, `embedder(config)`, `batch_size`, `generation`; the engine table setup reads; static readiness checks |
| Built-in description engine | `engine_transformers.py` | Wraps `QwenBackend` + `caption_batching` (unchanged; CUDA, BF16) |
| Local server engine (experimental) | `engine_server.py` | OpenAI-compatible server on this computer |
| Embedders | `embedding_backend.EmbeddingBackend` (CUDA), `embedding_cpu.EmbeddingCpuBackend` (CPU), `mcp_server.RemoteBackend` | EmbeddingGemma in process on the saved search device, or through the worker |
| Test adapters | `tests/test_engines.py`, `tests/test_incremental.py` | Fake engines and a fake HTTP server |

### Contracts

**DescriptionEngine.** `contract` (identity saved in provenance), `settings`,
`generation_mode` (selects the fingerprint rule), `generate_batch(inputs_list, prompt,
max_new_tokens)` returning, per asset and in order, `(raw_text, metrics)` or the exception
that failed it, `resources()` and `close()`. Inputs are project-rendered views (`path`
under `data/`, `sha256`); engines verify them. The core parses and validates the text, so
every engine meets the same description rules. An exception returned for one asset fails
only that asset; raising `EngineStop` stops the run with nothing recorded as failed;
anything else fails that batch, without retry. No silent fallback to another device,
model or engine.

**Embedder.** `contract` (part of the index fingerprint: vectors from different embedders
are never mixed), `text(text, role)` and `image(path)` returning a normalized vector,
`last_metrics`, `resources()`. Faults raise.

## Known debt and direction

On purpose, and listed so a later change knows about them:

- `incremental.caption_input` knows the built-in engine's fingerprint inputs
  (`caption_backend.py`, `caption_batching.py`, the caption lock): they are frozen
  evidence of every finished description (decision 0007).
- `captions.infer_captions` still accepts a bare `QwenBackend` for the historical
  evidence scripts.
- `scripts/asset-worker.py` hosts the EmbeddingGemma runtime (`runtime_contract`, its
  library pre-load); it builds the embedder through `engines.embedder`.
- One-off evidence and maintenance scripts build Qwen or EmbeddingGemma directly:
  `benchmark-caption-batching.py`, `caption_pilot.py`, `image-pilot-describe.py`,
  `image-pilot-search-eval.py`, `image-preprocessing-eval.py`, `kaykit-gltf-maintenance.py`,
  `embedding_capability.py`, `embedding_demo.py`, `benchmark_evaluation.py`,
  `measure_embedding_search.py`, `repair-textures.py`, `verify-model-relocation.py`,
  `verify-storage.py`, `prepare_*_model.py`. Those tied to the original pilot or library
  are in `scripts/historical/` (see its README).
- `scripts/historical/embedding_capability.py` uses this project's own pilot asset IDs, so a fresh install
  cannot record the search capability receipt yet (a follow-up for open source).
