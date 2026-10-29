---
tags: [reference]
parent: "[Expansion plan](../Expansion%20plan.md)"
---
# Expansion step 5 - Audio playback and direct audio search

Up: [Expansion plan](../Expansion%20plan.md).

Work in this repository; implement only expansion step 5 of [Project_v2_expansion.md](../Expansion%20plan.md). Verify step 1 and the established shared search/preview conventions from step 2. Do not spawn subagents. This prompt does not approve installation, model loading, or bulk processing.

## Read and obtain approval

Read root `AGENTS.md`, `KnowledgeBase/Decisions/` (especially 0005), `KnowledgeBase/Status.md`, the expansion plan's shared requirements/step 5/verification/storage sections, current embedding contract/model pin/runtime lock, and GPU/worker contracts. Claude also reads `CLAUDE.md`. Begin at `embedding_backend.py`, `scripts/asset-worker.py`, `mcp_server.py`, `gpu_queue.py`, type dispatch, retrieval aggregation, and desktop/MCP media boundaries.

Investigate available decoders, pinned audio model components, representative files, and segmentation policies read-only. Reverify current official EmbeddingGemma audio documentation. In one checkpoint, restate scope in one sentence, identify inclusions, exclusions, pilot membership, and UX ambiguities, then explain implementation, ownership, risks, checks, estimated duration, and additional peak/retained disk space with assumptions and significant uncertainty, including codecs, contracts/reindexing, temporary decode buffers, and any runtime. Ask **"Do this scope and implementation plan match what you want, and do you approve proceeding?"**, then stop and wait before implementation edits. An audio worker request changes decision 0005: include the amendment in the approval and update it with the implementation. Honor existing approval for the same unchanged scope and plan; reconfirm material changes.

## Implement after approval

Add WAV, OGG, MP3, and FLAC only where the actual decoder path is verified. Inspect duration, channels, sample rate, format, and supplied loop metadata. Add waveform, play/pause, seeking, volume, and user-controlled repeat playback. No browsing autoplay; repeat playback alone does not establish a seamless loop. Saved browsing/playback and keyword search must remain usable without AI.

Enable EmbeddingGemma's audio encoder under a validated versioned contract. Planning found audio tensors in the existing checkpoint, not proven audio inference. Verify actual decoded samples are consumed and produce finite normalized embeddings. Use the documented model-input resampling/mono policy while preserving original files and listening playback. Do not patch dependencies or silently change precision/device/runtime. Keep model loading behind the GPU lease and verification/ranking in the caller. Preserve desktop library-only worker pre-start, MCP lazy worker startup, 10-minute idle unloading, immediate GPU handoff, busy heartbeats, and transient-error handling; keyword search never contacts the worker. Preserve cheap change tokens, shared caches, and fresh full records for processing.

Use distinct bounded short-SFX and long-track policies. Record analyzed intervals, context limits, aggregation, and match timestamps; cover the track honestly rather than silently using only its intro. Never present disjoint excerpts as continuous audio. Avoid retained full decoded copies. Group segment results under one asset and support navigation to the relevant passage.

Proposed pilot: about 40 SFX/ambience clips and 10 BGM tracks. No generated audio captions in this step. Preserve decisions 0007-0008 for existing image descriptions and notifications. New audio import/playback/direct search must work without descriptions; no missing audio caption becomes an import job, import failure, or search exclusion. Audio-description generation/notifications are integrated only through the separately approved step 6. If direct search is weak, preserve the result and propose a separately bounded specialist comparison; do not silently install CLAP or another model.

## Verify and hand off

Check real decoding/playback, silence, short/long clips, multichannel handling, corruption, segmentation/aggregation, invalidation, GPU contention, and source preservation. Demonstrate actual local audio inference and text-to-audio searches without descriptions; compare metadata and direct-audio channels with held-out SFX/BGM queries separately. Prove desktop/MCP result parity and distinguish delivered audio content from a returned local path. Check relevant existing search, worker startup/liveness, and optional-description behavior.

Save required fresh installation/bulk storage receipts, including source output. Update decision/embedding/API contracts, usage, and `KnowledgeBase/Status.md` with supported codecs, actual inference, latency/resources, faults, partial results, owner listening/relevance review, and the next scope. No commits, pushes, PRs, or automatic captioning are authorized.
