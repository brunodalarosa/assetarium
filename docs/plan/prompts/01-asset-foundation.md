# Expansion step 1 - Shared asset foundation

Work in the existing `C:\BrunoOS\Local-Asset-Library` repository. Implement only step 1 of [Project_v2_expansion.md](../Project_v2_expansion.md), not original PROJECT.md step 1. Do not recreate the repository or spawn subagents. This prompt is a proposed scope, not implementation approval.

## Read and obtain approval

Read root `AGENTS.md`, `docs/decisions/`, `docs/progress.md`, the expansion plan's authority/shared requirements/step 1/verification/storage sections, `docs/catalog-contract.md`, `docs/asset-sources.md`, and `docs/library-updates.md`. Claude also reads `CLAUDE.md`. Current rules and recorded decisions override historical proposals.

Use read-only investigation to identify the actual baseline. Restate the scope in one sentence, include exclusions and ambiguities, ask **"Does this scope match what you want?"**, and stop for the answer. Then explain the implementation, ownership, risks, verification, estimated duration, and additional peak/retained disk space with assumptions; ask **"Is this implementation plan clear, and do you approve proceeding?"**, and stop for approval. Honor any explicit existing approval for unchanged scope. Do not edit implementation files before both checkpoints pass.

## Implement after approval

Start with `catalog.py`, `incremental.py`, `settings.py`, `membership.py`, `library_cache.py`, and the source/publication contracts. Inspect API validation and presentation only where the foundation requires them. Propose the smallest versioned representation of asset types, file roles, preview capabilities, applicable stages, and parent/child/dependency relationships. Avoid an unused general plugin framework.

Preserve existing 3D identities, source binding, overlays, generated results, faults, and search behavior. Explicitly design catalog and sub-asset identity migrations, compatibility, atomic publication, and recovery; size index/publication copies before making them. Do not infer equivalence from names or introduce duplicate originals.

Use synthetic model/image/audio records to prove that non-model assets can have appropriate stages without requiring Blender. Define an honest distinction between inapplicable/optional stages, real pending work, unsupported content, and failures. Extend coverage, format eligibility, caches, and bounded API validation only as needed. A synthetic image path is sufficient here; real pack processing, image captioning, and complete image browsing belong to step 2.

Keep config precedence, startup scans without inference, shared hash/read caches, caller-side ranking, GPU coordination, and retention decisions intact. Obtain an owner-approved decision amendment before changing a binding contract. No new model/runtime installation or source enrollment is implied.

## Verify and hand off

Check synthetic identity/relationships, applicable stages, publication/reload, old-catalog compatibility or migration, and existing 3D retrieval/overlays. Test changed/missing dependencies and partial results where the schema change affects them. Use existing wrappers; no dependency updates merely to run checks. Preserve fault evidence and read-only originals.

Update directly affected contracts and `docs/progress.md` with evidence, migration/storage implications, completion versus owner review, and the next runnable step. No commit, push, PR, or repository publication is authorized by this prompt. Stop before step 2 unless the owner explicitly approved the combined scope and plan.
