# Expansion step 3 - Sprite sheets, atlases, and animated 2D

Work in this repository; implement only expansion step 3 of [Project_v2_expansion.md](../Project_v2_expansion.md). Verify the completed image pipeline and asset relationships from steps 1-2. Do not spawn subagents or interpret this prompt as implementation approval.

## Read and obtain approval

Read root `AGENTS.md`, `docs/decisions/`, `docs/progress.md`, the expansion plan's shared requirements/step 3/verification/storage sections, and contracts produced by steps 1-2. Claude also reads `CLAUDE.md`. Inspect only the relevant type adapter, identity/relationship handling, image previews, retrieval aggregation, and desktop/MCP detail paths first.

Resolve the first concrete atlas metadata dialect, animated-image format, pilot membership, and frame/playback UX through read-only evidence. In one checkpoint, restate scope in one sentence, identify inclusions, exclusions, and ambiguities, then explain implementation, ownership, risks, checks, estimated duration, and additional peak/retained disk space, including crops/videos, contract changes, assumptions, and significant uncertainty. Ask **"Do this scope and implementation plan match what you want, and do you approve proceeding?"**, then stop and wait before implementation edits. Honor existing approval for the same unchanged scope and plan; reconfirm material changes.

## Implement after approval

Keep sheets selectable as parent assets even when individual regions are unknown. Create frame/animation sub-assets only from supplied metadata or explicit owner input, preserving source rectangles, order, timing, trim offsets, rotation, pivots, and provenance where supported. Design stable sub-asset identities and metadata-change/rename handling. Do not guess grids, trim, sequences, or missing timing.

Provide frame inspection and play/pause/scrub/loop controls. Reference the original sheet and metadata; generate only bounded fingerprinted crops/previews needed for display or inference. A frame preview is not a replacement source file. Retain usable parent images and metadata if frame extraction/playback fails, and record the affected fault.

Reuse direct image embeddings for suitable evidence, with frame/sequence context explicit. Optional descriptions belong to separate per-source **Generate descriptions**, with validated inputs/batching/provenance and existing notifications under decisions 0007-0008. Missing/failed descriptions do not block import, frame playback, or other search channels; retain description failures in detail/counts, outside import-failure reporting. Preserve completed results and leave unfinished assets pending on description GPU-memory stops, without automatic retry. Do not treat a whole-sheet caption as verified description of each frame, or independent still embeddings as proof of motion understanding. Aggregate results so frames do not crowd a shortlist; return parent linkage and useful frame/animation references through MCP and desktop.

Proposed pilot: about 10 sheets/atlases plus 10 short animations, selected by the owner. Defer automatic slicing and native authoring-tool adapters unless explicitly scoped. Preserve original packs, existing image/3D IDs and corrections, model/runtime contracts, and fault/retry rules.

## Verify and hand off

Use synthetic fixtures for bounds, padding, rotated/trimmed entries, timing, malformed metadata, source changes, and stable identities. Review actual playback and source-rectangle correctness on approved originals; prove shared result grouping and detail references in both interfaces. Check usable import/playback/search with missing or unusable descriptions, separate description fault visibility, and relevant notification/batch behavior. Measure any inference benefit separately from playback correctness. Check relevant static-image and 3D preservation.

Record source preservation, required storage receipts, preview costs, actual supported dialect/format, failures, pending owner review, and resumable next steps in affected docs and `docs/progress.md`. No commits, pushes, PRs, or automatic step 4 work are authorized.
