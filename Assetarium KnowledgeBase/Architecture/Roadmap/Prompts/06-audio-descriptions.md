---
tags: [reference]
parent: "[Expansion plan](../Expansion%20plan.md)"
---
# Expansion step 6 - Evaluate and add audio descriptions

Up: [Expansion plan](../Expansion%20plan.md).

Work in this repository and implement only expansion step 6 of [Project_v2_expansion.md](../Expansion%20plan.md). Verify step 5's actual playback/search evidence. Do not spawn subagents. Candidate models in the roadmap are research leads, not approved installations or selections.

## Read and obtain approval

Read root `AGENTS.md`, `KnowledgeBase/Decisions/`, `KnowledgeBase/Status.md`, the expansion plan's shared requirements/step 6/verification/storage/references, `KnowledgeBase/Architecture/Processing/Caption severity.md`, current caption provenance/overlay contracts, audio segmentation evidence, and runtime/storage policies. Claude also reads `CLAUDE.md`.

Begin with read-only model/runtime research using current primary sources. Compare audio/music understanding, publisher terms, checkpoint sizes, context limits, supported local precision, Windows compatibility, and measured hardware constraints. Do not assume Qwen3-VL listens to audio, that transcription describes instrumental music/SFX, or that a smaller Qwen variant has the same terms as a larger one.

Propose a bounded feasibility study with an explicit candidate count, audio/time limits, stopping rule, cost, and integration decision. In one checkpoint, restate scope in one sentence, identify inclusions, exclusions, and ambiguities, then explain ownership, changes, risks, evaluation, estimated duration, and additional download/installed/peak/retained disk space with assumptions and significant uncertainty; include any new environment and alternatives. Ask **"Do this scope and implementation plan match what you want, and do you approve proceeding?"**, then stop and wait before implementation edits or installations. If model selection materially changes the scope/plan or integration was not included, confirm the checkpoint again before continuing. Honor explicit approval for the same unchanged scope and plan.

## Study and implement within the approved plan

Evaluate candidates on a fixed owner-approved SFX/ambience/BGM sample. The roadmap records Qwen2.5-Omni-7B, Qwen3-Omni Captioner, and Audio Flamingo Next research. Recheck exact publisher terms and sizes: noncommercial research checkpoints are not a suitable default for the intended public release. A model load is insufficient; prove actual audio consumption, caption usefulness, local resources, and runtime compatibility. Do not retry unchanged faulty items or run an open-ended model sweep.

Select a model only with evidence. If no candidate meets the agreed criteria, retain a partial feasibility report and propose a bounded next scope. Do not claim the milestone complete or fabricate captions. Use existing runtime wrappers, shared model storage, immutable dependencies, and GPU coordination. Any independently pinned runtime must have its storage cost approved.

For approved integration, produce descriptions of actual audible events, texture/timbre, rhythm, energy, and instrumentation only where supported. Separate perceptual mood/suggested uses, measured facts, and tempo/key estimates. Preserve segment coverage/timestamps, raw outputs, model/revision, prompt, settings, input fingerprints, and owner overlays. Extend review handling explicitly while retaining review_note/warning/generation-fault distinctions. Keep optional ungenerated captions separate from failed generation.

Apply decision 0008 through the separate per-source **Generate descriptions** operation, not **Process assets**. Validate audio input readiness and the selected model's generation/batch contract before extending the existing missing-only workflow; recorded failures require an explicit retry request. Reuse the lease, progress, Cancel, budget, description-vector stage, publication, and notification delivery. Preserve ready-to-generate notices, **Not now** suppression, per-run outcome reports, and actions that can change the state; notices never start work. Missing/failed descriptions stay in detail/source counts, outside main-view source cards and **Importing failures report**; missing/stale/invalid descriptions silently leave only their search channel in desktop/MCP.

Preserve decision 0007 for existing image generation without assuming its model settings or batch sizes work for audio. Validate any audio batching, per-asset outcomes, cancellation boundary, and generation provenance explicitly; keep existing image-description fingerprints and results. Description GPU-memory exhaustion is a machine limit: stop with unfinished assets pending, preserve/publish finished results, and never automatically reduce the batch or record those assets faulty. Cancellation/storage stops also publish finished descriptions. Do not change `caption_backend.py` or the existing image-generation contract to integrate another model without explicit approval for the resulting invalidation.

Compare filename/direct-audio retrieval with and without description retrieval on held-out SFX and BGM queries. Caption availability must not gate importing, playback, or direct search. CLAP, if separately approved, is a retrieval model with its own vector space, not a caption generator.

## Verify and hand off

Review actual audio/caption pairs for misleading events, instrumentation, timing, and mood claims. Check schema, correction overlays, caption-content versus severity-only invalidation, partial results, fault visibility, and desktop/MCP parity. Verify optional missing/failed descriptions do not become import failures or exclude playable/direct-searchable assets; exercise actionable notifications, no unchanged-failure retry, and publication on cancellation/resource stops. Check new batching/provenance only within its validated contract and preserve existing image results. Report listening review separately from technical validation.

Save fresh pre/post installation and bulk storage receipts; document model decision, failed candidates without deletion of evidence, quality/latency/resources, runtime pins, supported durations, unresolved owner review, and actual completion in affected docs and `KnowledgeBase/Status.md`. No commits, pushes, PRs, or automatic step 7 work are authorized.
