# Expansion step 5 - Audio playback and direct audio search

Work in `C:\BrunoOS\Local-Asset-Library`; implement only expansion step 5 of [Project_v2_expansion.md](../Project_v2_expansion.md). Verify step 1 and the established shared search/preview conventions from step 2. Do not spawn subagents. This prompt does not approve installation, model loading, or bulk processing.

## Read and obtain approval

Read root `AGENTS.md`, `docs/decisions/` (especially 0005), `docs/progress.md`, the expansion plan's shared requirements/step 5/verification/storage sections, current embedding contract/model pin/runtime lock, and GPU/worker contracts. Claude also reads `CLAUDE.md`. Begin at `embedding_backend.py`, `scripts/asset-worker.py`, `mcp_server.py`, `gpu_queue.py`, type dispatch, retrieval aggregation, and desktop/MCP media boundaries.

Investigate available decoders, pinned audio model components, representative files, and segmentation policies read-only. Reverify current official EmbeddingGemma audio documentation. State scope, exclusions, pilot membership, and UX ambiguities; ask **"Does this scope match what you want?"** and wait. Explain implementation, ownership, risks, checks, duration, and additional peak/retained disk estimates, including codecs, contracts/reindexing, temporary decode buffers, and any runtime. Ask **"Is this implementation plan clear, and do you approve proceeding?"** and wait. An audio worker request changes decision 0005: obtain approval for that amendment and update it with the implementation. Honor applicable existing approval.

## Implement after approval

Add WAV, OGG, MP3, and FLAC only where the actual decoder path is verified. Inspect duration, channels, sample rate, format, and supplied loop metadata. Add waveform, play/pause, seeking, volume, and user-controlled repeat playback. No browsing autoplay; repeat playback alone does not establish a seamless loop. Saved browsing/playback and keyword search must remain usable without AI.

Enable EmbeddingGemma's audio encoder under a validated versioned contract. Planning found audio tensors in the existing checkpoint, not proven audio inference. Verify actual decoded samples are consumed and produce finite normalized embeddings. Use the documented model-input resampling/mono policy while preserving original files and listening playback. Do not patch dependencies or silently change precision/device/runtime. Keep model loading behind the GPU lease, ranking in the caller, startup inference-free, and worker idle/liveness behavior intact.

Use distinct bounded short-SFX and long-track policies. Record analyzed intervals, context limits, aggregation, and match timestamps; cover the track honestly rather than silently using only its intro. Never present disjoint excerpts as continuous audio. Avoid retained full decoded copies. Group segment results under one asset and support navigation to the relevant passage.

Proposed pilot: about 40 SFX/ambience clips and 10 BGM tracks. No generated audio captions in this step. If direct search is weak, preserve the result and propose a separately bounded specialist comparison; do not silently install CLAP or another model.

## Verify and hand off

Check real decoding/playback, silence, short/long clips, multichannel handling, corruption, segmentation/aggregation, invalidation, GPU contention, and source preservation. Demonstrate actual local audio inference and text-to-audio searches; compare metadata and direct-audio channels with held-out SFX/BGM queries separately. Prove desktop/MCP result parity and distinguish delivered audio content from a returned local path. Check relevant existing search behavior.

Save required fresh installation/bulk storage receipts, including source output. Update decision/embedding/API contracts, usage, and `docs/progress.md` with supported codecs, actual inference, latency/resources, faults, partial results, owner listening/relevance review, and the next scope. No commits, pushes, PRs, or automatic captioning are authorized.
