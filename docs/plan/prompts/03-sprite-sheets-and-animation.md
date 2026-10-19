# Expansion step 3 - Sprite sheets, atlases, and animated 2D

Work in `C:\BrunoOS\Local-Asset-Library`; implement only expansion step 3 of [Project_v2_expansion.md](../Project_v2_expansion.md). Verify the completed image pipeline and asset relationships from steps 1-2. Do not spawn subagents or interpret this prompt as implementation approval.

## Read and obtain approval

Read root `AGENTS.md`, `docs/decisions/`, `docs/progress.md`, the expansion plan's shared requirements/step 3/verification/storage sections, and contracts produced by steps 1-2. Claude also reads `CLAUDE.md`. Inspect only the relevant type adapter, identity/relationship handling, image previews, retrieval aggregation, and desktop/MCP detail paths first.

Resolve the first concrete atlas metadata dialect, animated-image format, pilot membership, and frame/playback UX through read-only evidence. State scope and exclusions, ask **"Does this scope match what you want?"**, and wait. Explain implementation, ownership, risks, checks, duration, and peak/retained disk estimates, including crops/videos and contract changes; ask **"Is this implementation plan clear, and do you approve proceeding?"**, and wait. Honor applicable existing approval and reconfirm material changes.

## Implement after approval

Keep sheets selectable as parent assets even when individual regions are unknown. Create frame/animation sub-assets only from supplied metadata or explicit owner input, preserving source rectangles, order, timing, trim offsets, rotation, pivots, and provenance where supported. Design stable sub-asset identities and metadata-change/rename handling. Do not guess grids, trim, sequences, or missing timing.

Provide frame inspection and play/pause/scrub/loop controls. Reference the original sheet and metadata; generate only bounded fingerprinted crops/previews needed for display or inference. A frame preview is not a replacement source file. Retain usable parent images and metadata if frame extraction/playback fails, and record the affected fault.

Reuse image caption/embedding paths for suitable evidence, with frame/sequence context explicit. Do not treat a whole-sheet caption as verified description of each frame, or independent still embeddings as proof of motion understanding. Aggregate results so frames do not crowd a shortlist; return parent linkage and useful frame/animation references through MCP and desktop.

Proposed pilot: about 10 sheets/atlases plus 10 short animations, selected by the owner. Defer automatic slicing and native authoring-tool adapters unless explicitly scoped. Preserve original packs, existing image/3D IDs and corrections, model/runtime contracts, and fault/retry rules.

## Verify and hand off

Use synthetic fixtures for bounds, padding, rotated/trimmed entries, timing, malformed metadata, source changes, and stable identities. Review actual playback and source-rectangle correctness on approved originals; prove shared result grouping and detail references in both interfaces. Measure any inference benefit separately from playback correctness. Check relevant static-image and 3D preservation.

Record source preservation, required storage receipts, preview costs, actual supported dialect/format, failures, pending owner review, and resumable next steps in affected docs and `docs/progress.md`. No commits, pushes, PRs, or automatic step 4 work are authorized.
