# Expansion step 4 - Textures and material sets

Work in `C:\BrunoOS\Local-Asset-Library` and implement only expansion step 4 of [Project_v2_expansion.md](../Project_v2_expansion.md). Verify steps 1-2 and reuse step 3's relationship conventions where available. Do not spawn subagents. This prompt does not approve source processing or implementation.

## Read and obtain approval

Read root `AGENTS.md`, `docs/decisions/`, `docs/progress.md`, the expansion plan's shared requirements/step 4/verification/storage sections, caption-quality policy, and current catalog/image/dependency contracts. Claude also reads `CLAUDE.md`. Inspect the image adapter, `catalog.py` dependency handling, existing Blender inspection/preview boundaries, and shared retrieval/detail paths. Existing texture-repair code is orientation, not permission to repair new items.

Read-only inspection should identify supplied material manifests, naming conventions, map formats, and candidate preview bindings. In one checkpoint, restate scope in one sentence, identify inclusions, exclusions, ambiguities, and pilot membership, then explain changes, ownership, risks, verification, estimated duration, and additional peak/retained disk space, including renders/dependencies/reindexing, assumptions, and significant uncertainty. Ask **"Do this scope and implementation plan match what you want, and do you approve proceeding?"**, then stop and wait before implementation edits. Preserve existing approval for the same unchanged scope and plan; reconfirm material changes.

## Implement after approval

Support individual textures and linked material sets without copying originals. Record map roles, resolution, color-space evidence, channel packing, normal conventions, scale/tiling evidence, and completeness. Unknown facts stay unknown. Treat filename-derived groupings as tentative unless supported by a reviewed convention or manifest; do not silently combine unrelated maps.

Build reproducible plane/sphere previews for narrowly supported mappings. Record tool/version, geometry, lighting, bindings, and settings. Do not silently supply missing required maps, reinterpret packed channels, flip normal conventions, or edit original textures. Preserve usable individual records and partial results when material assembly fails; retain fault evidence without automatic retries.

Use appropriate appearance images/assembled previews for EmbeddingGemma direct search during processing. Optional Qwen descriptions use separate per-source **Generate descriptions**, with validated material inputs/prompts, applicable batching/provenance, and notifications under decisions 0007-0008. Missing/failed descriptions do not block usable material imports or other search channels; retain failures in detail/counts rather than import-failure reports. Description GPU-memory stops preserve completed results and leave unfinished assets pending without automatic retry. Do not describe a normal/roughness map as the final visible surface. Keep measured metadata, visual observations, inferred properties, and suggested uses distinct. Expose material/map relationships, filters, complete known dependencies, original paths, and preview limitations consistently through desktop/MCP.

Use about 20 owner-approved varied material sets, including incomplete/packed-channel examples. Defer procedural graph interpreters, speculative map repair, and universal engine compatibility. Reuse the existing renderer/runtime where possible; any additions need explicit cost and approval.

## Verify and hand off

Check grouping evidence, map roles, channel/color-space handling, missing dependencies, changed-map invalidation, source preservation, and reproducible preview settings. Review actual plane/sphere appearance and held-out queries such as "stylized cracked stone". Compare retrieval channels and verify both interfaces return the selected set and known maps. Include usable import/direct search with missing or invalid descriptions, separate description fault visibility, and applicable generation/notification behavior. Check relevant image/3D preservation.

Save required fresh storage receipts with source-generated allocation, update contracts/usage and `docs/progress.md`, and report actual support, evidence, faults, usability/relevance review, and next scope. No commits, pushes, PRs, or automatic audio work are authorized.
