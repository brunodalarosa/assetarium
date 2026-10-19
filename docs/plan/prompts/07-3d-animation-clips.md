# Expansion step 7 - Selectable 3D animation clips

Work in `C:\BrunoOS\Local-Asset-Library`; implement only expansion step 7 of [Project_v2_expansion.md](../Project_v2_expansion.md). Verify step 1 and temporal/sub-asset conventions from step 3. Do not spawn subagents. Existing action enumeration is not completed animation playback support.

## Read and obtain approval

Read root `AGENTS.md`, `docs/decisions/`, `docs/progress.md`, the expansion plan's shared requirements/step 7/verification/storage sections, current inspection/catalog/sub-asset contracts, `docs/gui/3d-preview.md`, and caption/embedding contracts. Claude also reads `CLAUDE.md`. Start at `blender_worker.py`, `inspection.py`, `interactive_preview.py`, viewer controls, type dispatch, and shared retrieval/detail resolution.

Read-only inspection should identify clip bindings, source formats, rigs, timing evidence, and the viewer's actual animation capabilities. State the first supported format/rig path, pilot membership, inclusions, exclusions, and UX uncertainties; ask **"Does this scope match what you want?"** and wait. Explain implementation, ownership, risks, verification, estimated duration, and peak/retained storage for rendering, video dependencies, and contract/reindex changes. Ask **"Is this implementation plan clear, and do you approve proceeding?"** and wait. Preserve existing approval for unchanged scope and amend binding decisions only with owner approval.

## Implement after approval

Represent selectable animation clips as children linked to the original source file/model and its rig. Distinguish bound clips/actions from unused action data. Preserve model IDs and define clip identity/change/rename behavior. Start with the approved skeletal-animation path in supported glTF/GLB or FBX; avoid promising all importers or animation systems.

Record clip range, evaluated duration/timing, skeleton/bone references, dependencies, and measured root transform/motion where available. Do not treat Blender scene FPS defaults as proven source timing. For animation-only files without a compatible preview mesh/rig, preserve useful metadata and record the preview limitation/fault. Do not substitute a static pose as successful animation playback.

Provide clip selection and play/pause/scrub/loop controls, plus bounded recorded previews. Render only approved inputs without modifying originals or executing embedded scripts. Preserve source/dependency boundaries and partial results. Automatic retargeting, rig repair, source conversion, and target-game compatibility claims are excluded. Morph/baked/vertex animation is later work unless explicitly selected.

For descriptions/search, evaluate ordered timestamped frames or video using actual inputs. Reverify Qwen/EmbeddingGemma video APIs and runtime support; existing image support is not proof. Choose and test temporal sampling for fast motions rather than assuming the default one frame per second is adequate. Unordered still averages cannot establish movement direction. Keep model/runtime/index contract changes explicit and approved.

Proposed pilot: 10-20 clips covering idle, locomotion, jumps, attacks, short actions, root/in-place motion, and animation-only cases. Aggregate clips/views appropriately without filling results with frames.

## Verify and hand off

Check binding, identity, timing, source preservation, playback/scrubbing, root-motion facts, missing rigs/dependencies, invalidation, and relevant static-model behavior. Review real preview playback and held-out motion queries, including near matches/short actions. Verify desktop/MCP expose the same clip/source/rig references; separate temporal relevance, target-game suitability, and owner approval from technical success.

Save required fresh storage receipts and update contracts/usage and `docs/progress.md` with exact format/rig support, sampling/settings, inference and playback evidence, costs, faults, review state, and the next scope. No commits, pushes, PRs, or automatic shader work are authorized.
