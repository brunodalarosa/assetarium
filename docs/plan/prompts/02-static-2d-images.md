# Expansion step 2 - Static sprites, icons, and images

Work in `C:\BrunoOS\Local-Asset-Library` and implement only expansion step 2 of [Project_v2_expansion.md](../Project_v2_expansion.md). Verify step 1's actual contract/evidence; do not implement against a merely proposed schema. Do not spawn subagents. This prompt does not approve implementation or processing.

## Read and obtain approval

Read root `AGENTS.md`, `docs/decisions/`, `docs/progress.md`, the expansion plan's shared requirements/step 2/verification/storage sections, and current catalog, caption, embedding, and caption-quality contracts. Claude also reads `CLAUDE.md`. Begin read-only at `catalog.py`, type dispatch from step 1, `caption_backend.py`, `embedding_backend.py`, `retrieval.py`, `desktop_service.py`, and `mcp_assets.py`.

Restate scope, inclusions, exclusions, pilot membership, and unresolved image UX/preprocessing choices. Ask **"Does this scope match what you want?"** and wait. Then explain changes, ownership, risks, verification, estimated duration, and additional peak/retained disk space, including migration/reindex costs; ask **"Is this implementation plan clear, and do you approve proceeding?"** and wait. Use existing explicit approval when applicable; reconfirm material changes.

## Implement after approval

Support PNG, JPEG, and WebP after verifying local decoding. Make sprites, icons, and generic images selectable assets, without promoting every model preview/dependency into an unrelated duplicate. Use supplied evidence or owner labels for purpose; keep unknown purpose as a generic image. Preserve originals and stable IDs.

Add measured dimensions/transparency, thumbnails, native-size/pixel-art viewing, zoom, useful background controls, type/technical filters, source details, and app/MCP retrieval parity. Reuse the shared backend and bounded responses; verify actual image delivery to clients before claiming visual inspection.

Reuse Qwen3-VL with an image-appropriate versioned prompt and actual pixel inputs; preserve observations, suggestions, raw output, and review evidence separately. Reuse EmbeddingGemma for image and description search. Explicitly handle the current under-16-pixel rejection and fixed gray alpha compositing. Test candidate small-image/background treatments before choosing a preprocessing contract, and keep query/index compatibility. Do not invent source colors from preview backgrounds or silently invalidate/recompute existing vectors.

Use about 30-50 owner-approved representative images, including tiny pixel art, white/dark transparent icons, wide artwork, duplicates, and decoding failures. Defer SVG, PSD/Aseprite, atlas slicing, and animation playback. Use existing runtimes/shared weights; dependency or contract changes require the approved plan.

## Verify and hand off

Check decoding, source preservation, transparency/size handling, unchanged-stage reuse, invalidation, explicit faults, filters, and GUI/MCP agreement. Demonstrate actual local pixel inference and representative searches such as "blue potion icon"; measure filename, description, and image channels separately on held-out queries. Distinguish technical success from owner visual/relevance approval and check relevant 3D preservation.

Save required fresh storage receipts around bulk work/installations, including source-generated allocation. Update contracts/usage and `docs/progress.md` with actual coverage, evidence, latency/storage, faults, review state, and the next step. Do not commit, push, open a PR, or continue to step 3 without separate authorization.
