---
tags: [decision]
decided: 2026-11-07
area: Processing
replaces: [0007, 0008, 0015]
code: [description_engines.py, engines.py, engine_transformers.py, engine_server.py, caption_backend.py, caption_batching.py, incremental.process, notifications.py, sources.import_outcome]
---
# 0033 — Descriptions and inference engines

> **Approved by the owner on November 7, 2026** (decision review). Consolidates decisions 0007 (batched
> descriptions, October 18), 0008 (optional descriptions, October 18) and 0015 (inference ports, October 25).
> Their fingerprint and provenance rules are in [0028](0028-result-identity.md); counting descriptions search
> cannot use is in [0030](0030-counted-exclusions.md).

**Decision.** Descriptions are **optional extra data** made by a local model behind a port, in batches, on the
owner's (or an agent's) request. Importing never waits for them and never fails because of them.

## Descriptions are optional

- **Make previews never generates descriptions.** It runs inspection, previews and search vectors, then publishes.
  Image vectors and the asset name make an asset searchable.
- **A pending or failed description is neither import work nor an import failure.** `sources.import_outcome`
  ignores the caption stage and treats search data as complete when no *image* vector failed. Description failures
  are recorded and shown in asset detail and in each library folder's description counts, not as import faults.
- **Search** still fuses descriptions by default; a missing, stale or invalid description leaves only the
  description channel out, and the results say how many ([decision 0030](0030-counted-exclusions.md)). It is not
  an exclusion fault.
- **Generate descriptions** (Asset processing) runs the caption stage on assets whose previews are ready and
  whose description is missing, then description vectors, then publish. It uses the queue, progress, Cancel and
  the storage budget. Recorded failures are not retried. Cancel, out of GPU memory and storage stops still
  publish finished descriptions.
- **Descriptions off** (`descriptions_enabled`, chosen in setup, [decision 0031](0031-setup.md)): the backend
  refuses Generate descriptions and raises no *ready to generate* notice; existing descriptions stay.

## Notifications

`data/library/notifications.json` (bell, panel, toasts): *Descriptions ready to generate* (one per library folder,
raised when processing ends with missing descriptions; **Not now** stays quiet until more are missing) and one
*report* per description run (finished, with failures, cancelled, stopped, interrupted). Notices state facts and
offer only actions that can change the state; they never start work. Several alike notices arriving together
make one (Design language P1).

## Batching (built-in engine)

- Generate descriptions describes several assets in one Qwen3-VL call (`caption_batching.py`).
  Model, revision, prompt, image preparation, sampling, seed, the 1,100-token limit and the 120-second limit are
  the same as one at a time; sequences are left-padded.
- **Batch size**: Settings → General → Description batch size, 1, 2, 4 or 8 (default 8; setup recommends it from
  GPU memory). Changing it never re-queues anything.
- **Per-asset outcomes:** each asset is validated, saved, published and checkpointed on its own. One invalid
  output fails only that asset; a batch-wide runtime fault fails the batch's assets, without retry.
- **Out of GPU memory** is a machine limit, not an asset fault: the run stops with "Not enough GPU memory for
  description batch size N. Lower it in Settings → General", nothing is recorded as failed and the assets stay
  pending. It is never turned into faults or an automatic smaller-batch retry.
- **Cancel** waits for the current batch (about 15–20 s at size 8).
- Why: generation was limited by per-token overhead, not the GPU. A 20-asset benchmark measured 9.24 s per asset
  one at a time and 2.22 s at batch 8 (4.2×), 20/20 valid, 6.4 GB peak; the owner found the batched descriptions
  acceptable. The trade-off (wording depends on batch mates) is exception E2 in
  [decision 0028](0028-result-identity.md).

## Inference ports and engines

- Model inference sits behind two ports in `description_engines.py`: `DescriptionEngine` and `Embedder`, with
  documented contracts (see [description engines](../../docs/description-engines.md)). Adapters live in their own
  modules and are built only in one composition root, `engines.py`. Ports are for inference only: storage,
  catalog, configuration and Blender keep one implementation each.
- **Adapters:** `transformers-qwen3-vl-2b` (built-in, wraps `QwenBackend` and `caption_batching`); EmbeddingGemma's
  `EmbeddingBackend` and the worker proxy `RemoteBackend` as embedders (CPU or CUDA,
  [decision 0018](0018-cpu-search-embedder.md)).
- **Local model server (experimental):** an OpenAI-compatible server already running on this computer (llama.cpp,
  Ollama, LM Studio…), the route to AMD and other GPUs since the server chooses the device. Assetarium never
  starts, installs or downloads it. Loopback addresses only, proxies bypassed, one asset per request (batch size
  does not apply), the same sampling and image preparation as the built-in engine. Unreachable server, unknown
  model, refused request or malformed reply stop the run with assets pending; a timed-out or truncated generation
  fails only its asset. **Test connection** only lists models. It runs in the app environment; the description
  runtime is needed only by the built-in engine.
- **Switching engines never redoes finished work** ([decision 0028](0028-result-identity.md)). Engine refactors
  keep fingerprints (`scripts/check-engine-stability.py --compare`).

## Why

Image and name matching already find assets without descriptions, while describing is the slowest stage (a GPU
model). Blocking imports on it, or warning about every missing description, hid usable assets behind work that
only refines text search. The owner wants Assetarium usable on AMD without hardware to test it here; a local
OpenAI-compatible server is testable through the vendor-neutral llama.cpp Vulkan build.

## Keep true

- Do not add the caption stage back to Make previews or count description faults as import failures.
- A description run never retries recorded failures without an explicit request.
- Notifications state facts and never start work.
- Construct adapters only in `engines.py`. Keep model servers on this computer and server faults as machine stops.
- Do not claim AMD support until it runs on AMD hardware. Caption quality rules were calibrated on Qwen: other
  models get their own review.

## Changes

- 2026-11-09: the separate overnight description runner was removed (owner: it is no longer part of the app); descriptions run only from Generate descriptions.
