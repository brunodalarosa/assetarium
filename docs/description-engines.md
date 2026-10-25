# Description engines and embedders (ports and adapters)

[Decision 0015](decisions/0015-description-engines.md). Model inference is the only part
of Assetarium built as ports and adapters: the caption stage, overnight runs, indexing and
search depend on two small contracts, and the adapters that implement them are chosen in
one place.

| Piece | Module | Role |
| --- | --- | --- |
| Ports | `description_engines.py` | `DescriptionEngine`, `Embedder`, `EngineStop` (`MemoryLimitError`, `EngineUnavailableError`) |
| Composition root | `engines.py` | `description_engine(config)`, `embedder(config)`, `batch_size`, `generation`; the engine table setup reads; static readiness checks |
| Built-in description engine | `engine_transformers.py` | Wraps `QwenBackend` + `caption_batching` (unchanged; CUDA, BF16) |
| Local server engine (experimental) | `engine_server.py` | OpenAI-compatible server on this computer |
| Embedders | `embedding_backend.EmbeddingBackend`, `mcp_server.RemoteBackend` | EmbeddingGemma in process, or through the worker |
| Test adapters | `tests/test_engines.py`, `tests/test_incremental.py` | Fake engines and a fake HTTP server |

## Contracts

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

## Choosing an engine

Settings → General → Descriptions, the setup wizard, or
`local-assets settings set --engine builtin|local-server`. Switching never redoes finished
descriptions and never retries recorded failures: each description keeps the mode and
engine it was made with. New server descriptions record `generation_mode: server-v1` and
`engine: {engine, model}`.

## Local model server (experimental)

Assetarium sends previews to a vision model already served on this computer; the server
decides which GPU it uses (AMD, Intel, Apple or NVIDIA, depending on the server and its
build). Assetarium never starts, installs or downloads it. Only `127.0.0.1`, `localhost`
and `[::1]` are accepted, proxies are bypassed, and one asset is sent per request.

Checked setup (October 25, 2026, RTX 5070 through Vulkan): llama.cpp build b11870
`llama-b11870-bin-win-vulkan-x64.zip` and the official `Qwen/Qwen3-VL-2B-Instruct-GGUF`
(revision `52d6c8f…`, `Qwen3VL-2B-Instruct-Q8_0.gguf` + `mmproj-Qwen3VL-2B-Instruct-F16.gguf`,
2.65 GB):

```text
llama-server -m Qwen3VL-2B-Instruct-Q8_0.gguf --mmproj mmproj-Qwen3VL-2B-Instruct-F16.gguf --host 127.0.0.1 --port 8080 -ngl 99 -c 8192 --alias qwen3-vl-2b
```

Then set the server address `http://127.0.0.1:8080/v1` and model `qwen3-vl-2b`, and use
**Test connection** (it only lists models). Newer llama.cpp releases default to port 9931
when `--port` is omitted. Evidence: `data/engines/llama-vulkan-r2/report.json` (3/3 valid
descriptions in 7.1 s) and `data/engines/llama-cpp-check-2026-10-25/downloads.json`.

Faults: an unreachable server, unknown model, refused request or malformed reply stops the
run with the assets pending; a generation that hits the time or token limit fails that
asset only. The model identity is what the server reports (not hash-verified).

**Not verified:** any AMD GPU, Ollama or LM Studio, and descriptions from models other than
Qwen3-VL-2B-Instruct (caption quality rules were calibrated on Qwen).

## Places that still construct a concrete adapter

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
