# Shared local model storage

Models load from `[storage].models`: the project `models/` folder by default, or any
existing shared directory set in `config.local.toml`. Each model lives in
`<models>/<folder>/<revision>` (`qwen3-vl-2b/89644892…`, `embeddinggemma-2/914f7f89…`).
The rest of this page records the original development machine's layout.

On October 11, 2026, Bruno approved moving both AI models directly into
`C:\BrunoOS\Local-models` so other projects can reuse the same files.

| Model | Directory |
| --- | --- |
| Qwen3-VL-2B-Instruct | `C:\BrunoOS\Local-models\qwen3-vl-2b\89644892e4d85e24eaac8bacfd4f463576704203` |
| EmbeddingGemma 2 | `C:\BrunoOS\Local-models\embeddinggemma-2\914f7f89142e33e77833254d9c9b90c3cef7303b` |

Use these revision directories as local model paths from other compatible
Transformers/SentenceTransformers projects. They are original model folders,
not Ollama GGUF files; Ollama does not directly load them as installed models.
Do not change pinned weights in place: this project's offline loaders verify
their sizes and SHA-256 against existing receipts. New revisions should have
separate folders. No project-specific parent directory or compatibility link
was created.

`config.example.toml` sets `[storage].models` to the shared root. A local override
must use the same setting to use the relocated weights. Other storage areas
stay project-local. The absolute model root must exist and must not overlap
the source assets or repository. Relative child paths and resolved links are
still confined to their selected storage root.

The caption, embedding and base wrappers, plus the MCP embedding worker, use
project `cache/` for Hugging Face runtime caches. Only this project's exact two
pinned revision directories count toward its model budget; other models and
revisions in the shared root are excluded. Existing historical evidence retains
its original paths and byte counts as snapshots of earlier runs.

Local evidence is under `data/model-relocation/`: `move.json` preserves every
before/after file hash, and `embedding.json` / `caption.json` record new smoke
checks without overwriting original caption/index/capability evidence.
`scripts/historical/relocate-models.ps1` is a one-time migration record, not a startup step.
It refuses to merge or overwrite existing destinations. Smoke checks similarly
refuse to replace existing receipts or automatically retry faults.
