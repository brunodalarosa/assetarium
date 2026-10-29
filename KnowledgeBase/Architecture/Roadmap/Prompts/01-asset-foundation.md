---
tags: [reference]
parent: "[Expansion plan](../Expansion%20plan.md)"
---
# Expansion step 1 - Shared asset foundation

Up: [Expansion plan](../Expansion%20plan.md).

Work in the existing `C:\BrunoOS\Local-Asset-Library` repository. Implement only step 1 of [Project_v2_expansion.md](../Expansion%20plan.md); historical v1 step numbers are not this workflow. Do not recreate the repository or spawn subagents. This prompt is a proposed scope, not implementation approval.

## Read and obtain approval

Read root `AGENTS.md`, `KnowledgeBase/Decisions/`, `KnowledgeBase/Status.md`, the expansion plan's authority/shared requirements/step 1/verification/storage sections, `KnowledgeBase/Architecture/Sources and Catalog/Catalog contract.md`, `docs/asset-sources.md`, and `KnowledgeBase/Architecture/Processing/Library updates.md`. Claude also reads `CLAUDE.md`. Current rules and recorded decisions override historical proposals.

Use read-only investigation to identify the actual baseline. In one checkpoint, restate the scope in one sentence, identify inclusions, exclusions, and ambiguities, then explain the implementation, ownership, risks, verification, estimated duration, and additional peak/retained disk space with assumptions and significant uncertainty. Ask **"Do this scope and implementation plan match what you want, and do you approve proceeding?"**, and stop for the answer. Honor explicit existing approval for the same unchanged scope and plan; confirm again after a material change. Do not edit implementation files before explicit approval.

## Implement after approval

Start with `catalog.py`, `incremental.py`, `settings.py`, `membership.py`, `library_cache.py`, and the source/publication contracts. Inspect API validation and presentation only where the foundation requires them. Propose the smallest versioned representation of asset types, file roles, preview capabilities, applicable stages, and parent/child/dependency relationships. Avoid an unused general plugin framework.

Preserve existing 3D identities, source binding, overlays, generated results, faults, and search behavior. Explicitly design catalog and sub-asset identity migrations, compatibility, atomic publication, and recovery; size index/publication copies before making them. Do not infer equivalence from names or introduce duplicate originals.

Use synthetic model/image/audio records to prove that non-model assets can have appropriate stages without requiring Blender. Preserve decisions 0007-0008: **Process assets** excludes captions and description vectors; separate per-source **Generate descriptions** handles optional missing descriptions, their vectors, and publication. Retain missing/failed description states in detail/source counts without creating import work/failures or excluding otherwise usable assets from search. Preserve notification readiness and the distinction between optional work, unsupported content, and actual failures. Extend coverage, format eligibility, caches, and bounded API validation only as needed. A synthetic image path is sufficient here; real pack processing, image captioning, and complete image browsing belong to step 2.

Keep config precedence, startup scans without inference, cheap `changes()` tokens/stable cards, shared hash/read caches, caller-side ranking, worker pre-start/lazy model loading, GPU coordination, and retention decisions intact. Processing/indexing read fresh full `membership.records`; cached slim records are read-only and serve list/search paths. Preserve current description batching, fingerprints/provenance, machine-limit handling, and notifications. Obtain an owner-approved decision amendment before changing a binding contract. No new model/runtime installation or source enrollment is implied.

## Verify and hand off

Check synthetic identity/relationships, applicable stages, publication/reload, old-catalog compatibility or migration, and existing 3D retrieval/overlays. Include missing/failed descriptions with successful direct-media vectors: importing stays complete, keyword/direct search stays usable, and retained description faults stay outside import-failure reports. Check applicable notification states without starting work. Test changed/missing dependencies and partial results where the schema change affects them. Use existing wrappers; no dependency updates merely to run checks. Preserve fault evidence and read-only originals.

Update directly affected contracts and `KnowledgeBase/Status.md` with evidence, migration/storage implications, completion versus owner review, and the next runnable step. No commit, push, PR, or repository publication is authorized by this prompt. Stop before step 2 unless the owner explicitly approved the combined scope and plan.
