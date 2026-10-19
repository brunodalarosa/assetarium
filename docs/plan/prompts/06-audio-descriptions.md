# Expansion step 6 - Evaluate and add audio descriptions

Work in `C:\BrunoOS\Local-Asset-Library` and implement only expansion step 6 of [Project_v2_expansion.md](../Project_v2_expansion.md). Verify step 5's actual playback/search evidence. Do not spawn subagents. Candidate models in the roadmap are research leads, not approved installations or selections.

## Read and obtain approval

Read root `AGENTS.md`, `docs/decisions/`, `docs/progress.md`, the expansion plan's shared requirements/step 6/verification/storage/references, `docs/caption-quality.md`, current caption provenance/overlay contracts, audio segmentation evidence, and runtime/storage policies. Claude also reads `CLAUDE.md`.

Begin with read-only model/runtime research using current primary sources. Compare audio/music understanding, publisher terms, checkpoint sizes, context limits, supported local precision, Windows compatibility, and measured hardware constraints. Do not assume Qwen3-VL listens to audio, that transcription describes instrumental music/SFX, or that a smaller Qwen variant has the same terms as a larger one.

Propose a bounded feasibility study with an explicit candidate count, audio/time limits, stopping rule, cost, and integration decision. Ask **"Does this scope match what you want?"** and wait. Explain ownership, changes, risks, evaluation, duration, and exact expected download/installed/peak/retained storage; include any new environment and alternatives. Ask **"Is this implementation plan clear, and do you approve proceeding?"** and wait. If model selection materially changes the scope/plan or integration was not included, obtain the affected approval before continuing. Honor explicit approval already in force.

## Study and implement within the approved plan

Evaluate candidates on a fixed owner-approved SFX/ambience/BGM sample. The roadmap records Qwen2.5-Omni-7B, Qwen3-Omni Captioner, and Audio Flamingo Next research. Recheck exact publisher terms and sizes: noncommercial research checkpoints are not a suitable default for the intended public release. A model load is insufficient; prove actual audio consumption, caption usefulness, local resources, and runtime compatibility. Do not retry unchanged faulty items or run an open-ended model sweep.

Select a model only with evidence. If no candidate meets the agreed criteria, retain a partial feasibility report and propose a bounded next scope. Do not claim the milestone complete or fabricate captions. Use existing runtime wrappers, shared model storage, immutable dependencies, and GPU coordination. Any independently pinned runtime must have its storage cost approved.

For approved integration, produce descriptions of actual audible events, texture/timbre, rhythm, energy, and instrumentation only where supported. Separate perceptual mood/suggested uses, measured facts, and tempo/key estimates. Preserve segment coverage/timestamps, raw outputs, model/revision, prompt, settings, input fingerprints, and owner overlays. Extend review handling explicitly while retaining review_note/warning/generation-fault distinctions. Keep optional ungenerated captions separate from failed generation.

Compare filename/direct-audio retrieval with and without description retrieval on held-out SFX and BGM queries. Caption availability must not gate playback or direct search. CLAP, if separately approved, is a retrieval model with its own vector space, not a caption generator.

## Verify and hand off

Review actual audio/caption pairs for misleading events, instrumentation, timing, and mood claims. Check schema, correction overlays, caption-content versus severity-only invalidation, partial results, fault visibility, and desktop/MCP parity. Report listening review separately from technical validation.

Save fresh pre/post installation and bulk storage receipts; document model decision, failed candidates without deletion of evidence, quality/latency/resources, runtime pins, supported durations, unresolved owner review, and actual completion in affected docs and `docs/progress.md`. No commits, pushes, PRs, or automatic step 7 work are authorized.
