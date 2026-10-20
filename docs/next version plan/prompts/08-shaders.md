# Expansion step 8 - Shader catalog and one engine preview adapter

Work in `C:\BrunoOS\Local-Asset-Library` and implement only expansion step 8 of [Project_v2_expansion.md](../Project_v2_expansion.md). Verify steps 1-2 and relevant dependency/temporal conventions from steps 4 and 7. Do not spawn subagents. Engine/category selection and execution are not preapproved by this prompt.

## Read and obtain approval

Read root `AGENTS.md`, `docs/decisions/`, `docs/progress.md`, the expansion plan's shared requirements/step 8/verification/storage sections, and current catalog, dependency, preview, retrieval, and model contracts. Claude also reads `CLAUDE.md`. Inspect relevant adapters/backend services first; consult current official documentation for candidate engines and shader formats.

Split the milestone into 8A (catalog/text search) and 8B (controlled preview). In one checkpoint, restate scope in one sentence, identify which slice is proposed, pilot membership, engine/category, requirements, inclusions, exclusions, and unknown UX, then explain implementation, ownership, risks, verification, estimated duration, and additional peak/retained disk space with assumptions and significant uncertainty, including any engine/codec/runtime installation. Godot canvas shaders are a candidate, not an owner-selected default. Ask **"Do this scope and implementation plan match what you want, and do you approve proceeding?"**, then stop and wait before implementation edits. If only 8A is approved, complete it and obtain the combined scope/plan approval before 8B. Honor existing approval for the same unchanged scope and plan; reconfirm material changes.

## Slice 8A - Catalog and source search

Catalog shader files with supplied/inspected engine, engine version, renderer/language, parameters, include/texture dependencies, source paths, and license evidence. Avoid guessing engine compatibility from ambiguous extensions. Keep supplied screenshots distinct from verified renders of the selected code/setup.

Provide bounded source/metadata search, useful filters, and dependency/detail retrieval through the shared desktop/MCP backend. If code-semantic retrieval is included, validate a distinct query/document contract rather than silently changing existing description embeddings. Qwen's appearance descriptions require actual visuals; plausible code interpretation does not prove runtime behavior.

Deliver a usable static catalog even for unsupported preview engines. Missing includes/textures and ambiguous dependencies remain recorded faults/limitations with useful partial results. Do not infer that cataloging a shader means it compiles.

## Slice 8B - Approved engine preview

Build one narrow adapter in a controlled temporary preview project. Record exact engine build, shader category, scene/object, textures, uniform values, camera, lighting where relevant, time sampling, preview duration, and resource limits. Keep generated output in approved metadata storage and originals unchanged.

Do not launch arbitrary supplied pack projects or their editor/tool scripts. Pass only bounded approved dependencies into the controlled setup. Compilation/runtime/timeout failures are retained per item; no automatic source repair, missing-texture substitution, engine fallback, or unchanged retry. Preserve 8A's usable catalog and any successful preview evidence.

Use EmbeddingGemma visual/temporal retrieval only after capability/contract validation. Optional Qwen descriptions use actual screenshots/ordered previews through separate per-source **Generate descriptions**, with validated inputs/batching/provenance and existing notifications under decisions 0007-0008. Missing/failed descriptions do not block cataloging or previews, create import failures, or exclude usable assets from code/direct search; retain failures in detail/counts. Preserve completed results on cancellation/resource stops, leave unfinished descriptions pending on GPU-memory exhaustion without automatic retry, and never use notifications to start work. Distinguish a preview under recorded settings from portability or target-game suitability. Additional engines, graph interpreters, universal conversion, and automatic code fixes remain excluded.

## Verify and hand off

Use about 10 approved shaders covering static/animated effects, missing dependencies, and compilation failures. Synthetic fixtures verify parsing, includes/boundaries, parameter handling, invalidation, and fault isolation. Demonstrate actual reproducible rendering and reviewed searches such as "animated water distortion" for 8B. Verify useful catalog/search/preview behavior without descriptions, separate description fault reporting, and applicable generation/notification behavior. Check desktop/MCP parity, source preservation, and relevant existing asset/search paths.

Save required fresh storage receipts. Update affected docs and `docs/progress.md` with 8A and 8B statuses separately, supported engine/category, exact preview setup, actual checks, latency/storage, faults, owner visual/relevance review, and resumable handoff. Finish with cross-type coverage and known limitations; do not claim universal asset support. No commits, pushes, PRs, or additional expansion are authorized.
