This project is developed with both Codex and Claude (Claude Code). Every agent
follows this file; Claude also loads `CLAUDE.md`, which imports these rules and
adds codebase orientation only.

## Required checkpoints before implementation

Before starting implementation, follow these two steps in order:

1. **Confirm the scope.** Restate the task in one sentence, identify what is included and excluded, and surface any unclear requirements. Ask the user: “Does this scope match what you want?” Stop and wait for their answer.
2. **Confirm the implementation plan.** Explain the proposed changes, state ownership, risks, and verification approach in plain language. Include an estimated duration to complete the plan and an estimate of the additional disk space it will use, with the main assumptions and any significant uncertainty. Ask the user: “Is this implementation plan clear, and do you approve proceeding?” Stop and wait for their answer.

Do not edit implementation files until the user has explicitly approved both checkpoints. Read-only investigation needed to clarify the scope or prepare the plan is allowed. If either the scope or plan changes materially, confirm the affected checkpoint again before continuing.

## User experience

LAL is being refined iteratively for a future open source release. Give user
experience extra care: keep actions clear, make progress and outcomes easy to
understand, and avoid offering actions that cannot resolve the displayed state.
Distinguish actionable pending work from recorded failures while preserving
failure evidence and usable results. When unsure what good UX means for a
particular feature, ask the user before choosing its behavior.

## Fault handling

This policy applies to asset investigation, import/export and processing.
Application and test-harness defects may be diagnosed, fixed and verified normally.

### Caption review severity

Apply `docs/caption-quality.md` when processing or reviewing new assets. Do not
mark a usable caption or asset faulty solely because a visual detail is uncertain,
an exact count is unsupported, a material is inferred, or owner review is pending.
Record minor precision/appearance uncertainty as `review_note`; record meaningful
identity, color or structural errors that could mislead selection as `warning`.
When severity is unclear, retain a warning with the evidence and reason.
Reserve `caption_faulty` for failed/incomplete caption generation or a missing or
unusable description. Successful retrieval does not prove every caption claim,
and notes/warnings do not exclude an otherwise usable source.

New AI review inputs use `findings` entries with `severity` (`review_note` or
`warning`), `evidence`, and `reason`; `scripts/record_caption_review.py` stores
these directly. Legacy unclassified visual findings default to warnings. Retain
original evidence and owner approval states. Do not rerun models, rewrite source
assets, retry failed processing or manufacture a caption to resolve review notes.
Actual source, dependency, geometry, preview and runtime failures still follow
the fault policy below. Caption-specific severity takes precedence over the
general treatment of ambiguity or minor metadata details.

For every kind of fault, mark the affected asset/item as faulty, record the reason
and available evidence, preserve usable partial results, and move on. This applies
to geometry, materials, textures, previews, imports, metadata, dependencies,
timeouts, unsupported formats, ambiguity, and any other definition of faulty.
Do not get stuck diagnosing or repairing individual faulty items, silently
substitute success, or automatically retry unchanged faults. Repairs or retries
require an explicit user request. Keep faults visible separately from successful
processing of other items; never edit originals to resolve them.

## Storage discipline

- Use the existing runtime wrappers. All four environments share `cache/uv`
  with `UV_LINK_MODE=hardlink`. Keep independently pinned environments when
  compatibility requires them; do not merge dependency versions to save space.
- Treat installed dependency files as immutable. Hard links share file contents:
  never patch a dependency or DLL in place. Change the dependency pin and let uv
  replace the installation instead. Do not automatically fall back to copying
  large packages or create another environment without explaining its disk cost
  at the required scope/plan checkpoints.
- Keep original assets read only and shared model revisions in their configured
  shared storage. Do not copy them into project caches, test fixtures or exports
  when an existing path will do. Synthetic small fixtures are preferred for tests.
- Before and after dependency/model installation or bulk processing, run
  `scripts/storage-report.py` using the existing base Python environment and save
  a new receipt under `data/storage/`. Compare unique allocated bytes, not the sum
  of folder sizes, because Windows can count hard links more than once.
- Aim to keep this approved 40-asset pilot below **6 GiB of unique allocated
  project storage**, excluding external assets and shared models. A projected
  increase of **500 MiB or more**, another runtime, or exceeding this target must
  be included in the implementation plan with its purpose and alternatives.
  This is a planning target, not permission to delete results or evidence.
- After a successful installation and runtime verification, clear redundant uv
  cache entries with uv's cache commands against the exact project-local cache.
  Hard-linked installed files remain usable after their cache names are removed.
  Keeping a download cache for offline reinstalls is an explicit disk-space tradeoff.
- Reuse a bounded temporary directory for repeatable checks when it contains no
  evidence that must be preserved. Keep fault records, reports, previews and usable
  partial results. Never recursively delete directories containing junctions or
  links without a reviewed containment check; never clear generic system caches.
- Record cleanup targets, savings, verification and faults separately. The
  one-time consolidation script refuses automatic reruns. See `docs/storage.md`.
