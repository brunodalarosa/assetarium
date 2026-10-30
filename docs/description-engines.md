# Description engines and search device

[Decision 0015](../Assetarium%20KnowledgeBase/Decisions/0015-description-engines.md). Descriptions come from the built-in
engine (Qwen3-VL-2B-Instruct) or, experimentally, from a vision model already served on this computer.
Search vectors are made on an NVIDIA GPU or on the CPU. How engines are wired internally (ports, adapters
and the one composition root) is in the knowledge base:
[Inference ports](../Assetarium%20KnowledgeBase/Architecture/Setup%20and%20Engines/Inference%20ports.md).

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

**Checked on AMD (October 25, 2026):** a Radeon RX 6800 (driver 26.7.1) with the same llama.cpp
b11870 Vulkan build, `--device Vulkan0` (the discrete card; the CPU's integrated GPU is
`Vulkan1`) and the official F16 files (`Qwen3VL-2B-Instruct-F16.gguf` +
`mmproj-Qwen3VL-2B-Instruct-F16.gguf`, 4.07 GB): 32 of 32 valid descriptions at 3.9 s per asset
(four views per request). Evidence: `data/evidence/cpu-embedder-e2e-2026-10-25/report.json`.

**Not verified:** other AMD GPUs, Ollama or LM Studio, and descriptions from models other than
Qwen3-VL-2B-Instruct (caption quality rules were calibrated on Qwen).

## Search device (decision 0018)

`search_device` (`cuda` by default, or `cpu`) picks the embedder in `engines.embedder`; there is
no fallback between them. Settings → General → Search, the setup wizard, `apply_setup` or
`local-assets settings set --search-device cpu`. The CPU embedder is the same EmbeddingGemma
revision in BF16 with its own contract (device, adapter and lock hashes), so its vectors are a
separate index: after switching, record the search check again and Process assets.

CPU setup, from the Assetarium folder:

```powershell
.\scripts\embedding-runtime.ps1 sync --locked --project runtime/embedding-cpu
.\scripts\embedding-runtime.ps1 run --locked --no-sync --project runtime/embedding-cpu python scripts/prepare_embedding_model.py --device cpu
# After processing a source once (its search stage waits for this check):
.\scripts\embedding-runtime.ps1 run --locked --no-sync --offline --project runtime/embedding-cpu python scripts/record-embedding-capability.py
```

Measured on a Ryzen 9 9950X3D (16 cores, AVX-512): about 1.1 s per image vector and 0.03 s
per text vector in BF16, 2–10 s model load; vectors within 0.998 cosine of FP32
(`data/evidence/cpu-embedder-probe-2026-10-25/report.json`). `engines.embedder` sets the CPU
embedder's threads from Settings → General → Search, else the speed test's choice, else every
logical thread (Torch defaults to one per physical core): 0.83–0.89 s per image at 24–32 threads on
the same CPU, vectors bit-identical at any count, so no index changes (batches of 4–8 images and
preparing each image once were measured and gave no gain; decision 0022). Every rendered view gets an image
vector, so a 3D asset costs a few seconds to index. A local-server description run uses the app
environment (`.venv-mcp`), so AMD and other GPUs need no description runtime at all.
