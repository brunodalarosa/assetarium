# 0015 — Inference ports and adapters; experimental local model server engine

**Decision (owner, October 25, 2026).** Model inference sits behind two ports
(`description_engines.py`): `DescriptionEngine` and `Embedder`, with documented contracts
(inputs, outputs, errors, invariants; see [description engines](../description-engines.md)).
Adapters live in their own modules and are chosen in one composition root, `engines.py`;
the core never constructs one. Ports and adapters are used only for inference: storage,
catalog, configuration and Blender keep one implementation each.

- **Adapters.** `transformers-qwen3-vl-2b` (`engine_transformers.py`) wraps `QwenBackend`
  and `caption_batching` unchanged; EmbeddingGemma's `EmbeddingBackend` and the worker proxy
  `RemoteBackend` are the embedders. `local-server` (`engine_server.py`) is a new,
  **experimental** description engine for an OpenAI-compatible model server already
  running on this computer (llama.cpp, Ollama, LM Studio…). It is the route to AMD and other
  GPUs: the server chooses the device. Assetarium never starts, installs or downloads it.
- **Server rules.** Loopback addresses only (`127.0.0.1`, `localhost`, `[::1]`), proxies
  bypassed, one asset per request (batch size does not apply), the same sampling settings
  and image preparation as the built-in engine. Unreachable server, unknown model, refused
  request or malformed reply stop the run with assets pending (`EngineUnavailableError`,
  like out of GPU memory); a timed-out or truncated generation fails only its asset.
  Setup's **Test connection** only lists models; it never generates text.
- **Provenance and fingerprints.** New server descriptions record `generation_mode:
  server-v1` and `engine: {engine, model}`; their fingerprint uses that identity, the
  adapter file's hash and the prompt. The model identity is **what the server reports**
  (model id and, for llama.cpp, model path and build), not a hash-verified file: this
  weakens the pinned, hash-verified guarantee of the built-in engine and is accepted for
  this engine only. Changing the model file behind the same name is not detected.
- **Finished work is never redone by a switch.** Completed descriptions are validated
  against the mode and engine recorded with them, so switching engines re-queues nothing;
  recorded failures stay failures. `caption_backend.py`, `caption_batching.py` and
  `embedding_backend.py` stay byte-identical (decision 0007); a dry run on the owner's
  library before and after the refactor showed identical pending counts and fingerprints
  (`scripts/check-engine-stability.py`).
- **Embeddings.** Only EmbeddingGemma (CUDA, BF16) exists; semantic and image search on
  AMD remain unsupported, and the UI says so. *Superseded by
  [decision 0018](0018-cpu-search-embedder.md): EmbeddingGemma also runs on the CPU.*

**Why.** The owner wants Assetarium usable on AMD setups without hardware to test them
here. A local OpenAI-compatible server is testable on the owner's NVIDIA GPU through the
vendor-neutral llama.cpp Vulkan build, so the adapter is verified even though AMD itself
is not.

**Keep true.** Construct adapters only in `engines.py`. Do not claim AMD support until it
runs on AMD hardware. Keep server addresses on this computer and server faults as machine
stops. A new engine records its own mode and identity and never invalidates other
engines' results. Caption quality rules were calibrated on Qwen: other models get their
own review.
