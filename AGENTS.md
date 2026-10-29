This project is developed with both Codex and Claude (Claude Code). Every agent
follows this file; Claude also loads `CLAUDE.md`, which imports these rules and
adds codebase orientation only.

## Recorded decisions

Read `KnowledgeBase/Decisions/` before changing behavior. Those owner-approved decisions
bind future changes; if a change would contradict one, ask the owner first and
update the decision record together with the code.

## Knowledge base

`KnowledgeBase/` (an Obsidian vault, also readable on GitHub) holds what the code doesn't
say: `Home.md` (conventions), `Status.md`, `Notebook/` (working notes per area, agents first),
`Architecture/` (how and why, humans first), `Decisions/` (binding owner decisions) and
`Reference/` (external docs with a trust rating). User-facing guides stay in `docs/`.

- For a task in an area, read its hub (`Notebook/<Area>/<Area>.md`) and the notes for the
  systems involved first. `Notebook/Codebase.md` maps every module to its area.
- Notes can be stale: the code wins. Report a wrong note and fix it in the same change.
- At the end of each task, propose 0-3 learnings (target note, exact text, `code` anchors)
  and 0-3 friction items for `Notebook/Improvements.md`. Write them only after the owner
  approves. Learnings are what cost real effort to find or what the owner explained that
  exists nowhere else, not a log of the work.
- Architecture docs and decisions are human-owned: agent edits to Architecture stay
  `status: draft`; decisions change only as described under "Recorded decisions".

## Required checkpoint before implementation

Before starting implementation, **confirm the scope and implementation plan** in one step. Restate the task in one sentence, identify what is included and excluded, and surface any unclear requirements. Then explain the proposed changes, state ownership, risks, and verification approach in plain language. Include an estimated duration to complete the plan and an estimate of the additional disk space it will use, with the main assumptions and any significant uncertainty. Ask the user: “Do this scope and implementation plan match what you want, and do you approve proceeding?” Stop and wait for their answer.

Do not edit implementation files until the user has explicitly approved this checkpoint. Read-only investigation needed to clarify the scope or prepare the plan is allowed. If the scope or plan changes materially, confirm the checkpoint again before continuing.

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

Apply `KnowledgeBase/Architecture/Processing/Caption severity.md` when processing or reviewing new assets. Do not
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
- **`scratch/` must always be safe to delete as a whole, at any time, without losing
  anything.** Use it as much as needed, but only for disposable files: test temp folders,
  throwaway fixture projects, probes and caches that rebuild themselves. Never put evidence,
  reports, receipts, results or anything a doc, script or code comment cites there; those go
  under `data/` (for example `data/evidence/`, `data/gui/`). Never leave a link (junction or
  symlink) in `scratch/` that points outside it: a run that links an environment there
  removes the link when it ends (`scripts/scratch_links.py`). Nothing may read from
  `scratch/` expecting it to persist.
- Reuse a bounded temporary directory for repeatable checks when it contains no
  evidence that must be preserved. Keep fault records, reports, previews and usable
  partial results. Never recursively delete directories containing junctions or
  links without a reviewed containment check; never clear generic system caches.
- Record cleanup targets, savings, verification and faults separately. The
  one-time consolidation script refuses automatic reruns. See `KnowledgeBase/Notebook/Platform and Storage/Storage discipline.md`.

## Versioning

Assetarium follows [Semantic Versioning](https://semver.org/). 0.1.0 is the first public
release; while the version is 0.x, minor releases may change behavior or settings, and
the changes are listed in [CHANGELOG.md](CHANGELOG.md).

- Record user-visible changes under an `Unreleased` heading in `CHANGELOG.md` as part of
  the change itself.
- Choose a new version number, release, or tag (`vX.Y.Z`) only when the owner asks. A
  release updates every version field together: `pyproject.toml`, `runtime/*/pyproject.toml`
  and `frontend/package.json`.

## Branching (git flow)

- `main` holds released versions only; each merge into it is tagged `vX.Y.Z`.
- `develop` is the integration branch. Start work from it and open pull requests into it.
- `feature/<name>` and `bugfix/<name>` branch from `develop` and merge back into it.
- `release/X.Y.Z` branches from `develop` to prepare a release (version fields, changelog),
  then merges into `main` (tagged) and back into `develop`.
- `hotfix/X.Y.Z` branches from `main` for urgent fixes, then merges into `main` (tagged) and
  `develop`.
- Never commit directly to `main` or `develop`, and never force-push them.
