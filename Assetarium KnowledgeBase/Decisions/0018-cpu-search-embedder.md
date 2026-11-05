---
tags: [decision]
decided: 2026-10-25
---
# 0018 — CPU search embedder; local-server descriptions without the description runtime

**Decision (user of this checkout, October 25, 2026; for the owner's review before any merge
upstream).** Search by description and by image can run EmbeddingGemma 2 on the CPU. A saved
setting, `search_device` (`cuda` or `cpu`, default `cuda`), chooses the embedder; nothing ever
falls back from one to the other. This extends [decision 0015](0015-description-engines.md),
whose "only EmbeddingGemma (CUDA, BF16)" bullet it replaces.

- **Same model, own identity.** `embedding_cpu.py` loads the pinned EmbeddingGemma revision with
  the same prompts, preprocessing, BF16 precision and normalization as the CUDA backend. Its
  contract records `device: cpu`, its own adapter hash, the CUDA adapter's hash
  (`base_adapter_sha256`, the helpers it imports) and the installed runtime lock, plus
  `hashed_files` so the LF/CRLF tolerance follows its own files. CPU and CUDA vectors therefore
  never share an index; switching device rebuilds search data on the next Process assets.
  `embedding_backend.py` stays byte-identical, so existing CUDA indexes keep their fingerprints.
- **CPU-only runtime lock.** `runtime/embedding-cpu/` pins the same packages as
  `runtime/embedding/` with Torch `2.10.0+cpu`, installed into the same `.venv-embedding` by the
  same wrapper (about 1 GB instead of about 5 GB). The CUDA lock is unchanged. Readiness reports
  a CPU-only Torch when `cuda` is chosen.
- **Search check for every install.** `scripts/record-embedding-capability.py` writes
  `data/embeddings/capability.json` from two of the library's own processed previews (each
  source's working records, since nothing is published before search data exists), replacing
  the pilot-only historical script. Process assets stops its search stage with that command as
  the reason while the receipt is missing or recorded for the other device; assets stay pending
  and finished stages are kept. A first dry run counts against the receipt's contract.
- **Local-server descriptions run in the app environment.** The server engine sends HTTP and
  needs no Torch, so its caption stage runs in the `mcp` environment; the description runtime
  (`.venv-caption`) is only needed by the built-in engine.
- **Setup and UI.** Settings → General has a Search card; the setup wizard's "Descriptions and
  search" step shows the choice with a per-device checklist and suggests `cpu` on a first run
  without an NVIDIA GPU with BF16; `apply_setup` and `local-assets settings set --search-device`
  accept it.

**Why.** On an AMD Radeon RX 6800 (Windows) no supported PyTorch GPU path exists for this card,
while a 16-core Zen 5 CPU embeds an image in about 1.1 s in BF16 (RTX 5070: about 0.1 s) with
vectors within 0.998 cosine of FP32 (`data/evidence/cpu-embedder-probe-2026-10-25/`). Searching
costs one text vector (about 0.03 s), so only the first index is slower.

**Keep true.** Construct embedders only in `engines.py`. A device records its own identity and
never reuses another device's vectors or receipt. Do not edit `embedding_backend.py` for a new
device. A GPU embedder for other vendors (for example ONNX Runtime with DirectML) is a separate
decision and must be checked against the CPU vectors first.
