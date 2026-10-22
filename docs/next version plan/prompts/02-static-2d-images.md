# Expansion step 2 - Static sprites, icons, and images

Work in `C:\BrunoOS\Local-Asset-Library` and implement only expansion step 2 of [Project_v2_expansion.md](../Project_v2_expansion.md). Verify step 1's actual contract/evidence; do not implement against a merely proposed schema. Do not spawn subagents. This prompt does not approve implementation or processing.

## Read and obtain approval

Read root `AGENTS.md`, `docs/decisions/`, `docs/progress.md`, the expansion plan's shared requirements/step 2/verification/storage sections, and current catalog, caption, embedding, and caption-quality contracts. Claude also reads `CLAUDE.md`. Begin read-only at `catalog.py`, type dispatch from step 1, `caption_backend.py`, `embedding_backend.py`, `retrieval.py`, `desktop_service.py`, and `mcp_assets.py`.

In one checkpoint, restate scope in one sentence, identify inclusions, exclusions, pilot membership, and unresolved image UX/preprocessing choices, then explain changes, ownership, risks, verification, estimated duration, and additional peak/retained disk space, including migration/reindex costs, assumptions, and significant uncertainty. Ask **"Do this scope and implementation plan match what you want, and do you approve proceeding?"**, then stop and wait. Use existing explicit approval for the same unchanged scope and plan; reconfirm material changes before editing implementation files.

## Implement after approval

Support PNG, JPEG, and WebP and other common image formats after verifying local decoding. Make sprites, icons, and generic images selectable assets, without promoting every model preview/dependency into an unrelated duplicate. Use supplied evidence or owner labels for purpose; keep unknown purpose as a generic image. Preserve originals and stable IDs.

Add measured dimensions/transparency, thumbnails, native-size/pixel-art viewing, zoom, useful background controls, type/technical filters, source details, and app/MCP retrieval parity. Reuse the shared backend and bounded responses; verify actual image delivery to clients before claiming visual inspection.

Use EmbeddingGemma image vectors during **Process assets** so images are searchable without descriptions. Add optional Qwen3-VL descriptions through separate per-source **Generate descriptions**, with an image-appropriate versioned prompt and actual pixel inputs; preserve observations, suggestions, raw output, and review evidence separately. Reuse and validate `caption_batching.py`, settings, per-asset outcomes/provenance, and notifications under decisions 0007-0008. Preserve existing descriptions/fingerprints; do not change `caption_backend.py` or re-queue existing 3D descriptions to add image support without explicit approval. GPU-memory exhaustion stops with unfinished assets pending, completed results published, and no automatic smaller-batch retry. Reuse description search only when usable vectors exist; missing/stale/failed descriptions neither gate imports nor create exclusion faults or import failures.

Explicitly handle the current under-16-pixel rejection and fixed gray alpha compositing. Test candidate small-image/background treatments before choosing a preprocessing contract, and keep query/index compatibility. Do not invent source colors from preview backgrounds or silently invalidate/recompute existing vectors.

Use about 30-50 owner-approved representative images, including tiny pixel art, white/dark transparent icons, wide artwork, duplicates, and decoding failures. Defer SVG, PSD/Aseprite, atlas slicing, and animation playback. Use existing runtimes/shared weights; dependency or contract changes require the approved plan.

## Verify and hand off

Check decoding, source preservation, transparency/size handling, unchanged-stage reuse, invalidation, explicit faults, filters, and GUI/MCP agreement. Verify import and image/name search before descriptions, search fallback and separate fault visibility after failed/stale descriptions, and actionable notifications without automatic generation. Check per-asset batch isolation, cancellation/resource-stop publication, retained fingerprints, and no re-queue on batch-size changes where these paths are extended. Demonstrate actual local pixel inference and representative searches such as "blue potion icon"; measure filename, optional description, and image channels separately on held-out queries. Distinguish technical success from owner visual/relevance approval and check relevant 3D preservation.

Save required fresh storage receipts around bulk work/installations, including source-generated allocation. Update contracts/usage and `docs/progress.md` with actual coverage, evidence, latency/storage, faults, review state, and the next step. Do not commit, push, open a PR, or continue to step 3 without separate authorization.
