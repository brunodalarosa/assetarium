---
tags: [hub]
---
# Decisions

Up: [Home](../Home.md). Decisions are owner-owned: agents never edit one on their own initiative (see `AGENTS.md` → Recorded decisions).

Owner-approved decisions that later changes must respect. Each file states the decision, why it was made, and
what future work must keep true. **Every file here is current.** How to change one (place it, check it, replace
without keeping halves) is in `AGENTS.md` → Recorded decisions; `tests/test_decisions.py` enforces the
mechanical rules. Each decision has an `area` (a Notebook area, or `Project` for project-wide ones) and a
`## Changes` list of dated edits.

**Replacing a decision.** The new decision lists the numbers it takes over in `replaces`, carries over the why and
any alternatives the owner rejected, and the old file is deleted. Its number stays in [Replaced](#replaced) below,
never reused, so a "decision 00xx" in code or docs still leads somewhere. The full old text is in git history
(the replaced files' last version is in commit `b8ccfd0`).

| # | Decision | Date |
| --- | --- | --- |
| [0002](0002-startup-scan-and-change-detection.md) | Startup scan, stat-token change detection, no manual Scan/Status | 2026-10-17 |
| [0003](0003-per-publication-read-caches.md) | Read paths reuse per-publication caches | 2026-10-17 |
| [0005](0005-embedding-worker-and-prestart.md) | Worker returns vectors; app pre-starts it; 10 min idle | 2026-10-17 |
| [0006](0006-retention.md) | Keep active + 2 generations, 10 launch audits; reusable pytest folder | 2026-10-17 |
| [0009](0009-general-capabilities.md) | Every fix and processing capability is a reusable system feature | 2026-10-19 |
| [0010](0010-shared-project-dependencies.md) | Verify shared project-layout dependencies across enabled sources | 2026-10-19 |
| [0011](0011-react-desktop-ui.md) | React desktop UI: rail navigation, inspection sidebar, Asset processing, themes | 2026-10-21 |
| [0013](0013-platform-support.md) | Windows primary; Linux v1 is CLI + MCP (no GUI yet); owner CLI on both platforms; deletions need an interactive owner | 2026-10-24 |
| [0017](0017-license-and-cla.md) | AGPL-3.0-only plus a Contributor License Agreement; third-party licenses unchanged | 2026-10-25 |
| [0018](0018-cpu-search-embedder.md) | CPU search embedder (`search_device`), CPU-only search lock, search check for every install, local-server descriptions without the description runtime | 2026-10-25 |
| [0019](0019-source-folders-and-export-variants.md) | Excluded folders per source, owner-confirmed duplicate export folders, folder variants in `get_asset` | 2026-10-26 |
| [0020](0020-alternate-file-faults-and-recheck.md) | A broken alternate file fails alone; owner-confirmed recheck of check failures (app and CLI) | 2026-10-26 |
| [0021](0021-texture-folder-choice.md) | Owner-chosen texture folder per source for models whose textures were not found (exact names, all or nothing) | 2026-10-26 |
| [0027](0027-saved-catalog-first-and-fast-scan.md) | Saved catalog first at launch; stat-only change check that parses only changed files and their referencing models; silent per-card updates; no launcher window | 2026-11-06 |
| [0028](0028-result-identity.md) | Result identity: what each result is keyed by, the named exceptions (render device, batched wording, server model by name, file identity, line endings, equivalent workers), what re-queues work | 2026-11-07 |
| [0029](0029-agent-trust.md) | Agent trust: agents act freely and at once (structure, settings, processing), in the open: told before connecting, Agent activity, Stop, Pause agents, Undo per session; owner-only list; the manipulated-agent risk accepted | 2026-11-07 |
| [0030](0030-counted-exclusions.md) | Left-out items are hidden, counted once: off formats hidden with a count line (re-inspected from a format that is on), search counts descriptions it can't use | 2026-11-07 |
| [0031](0031-setup.md) | Setup: short checks (Blender, runtimes and weights, search check on built-in samples, server connection) leave every core feature working; never processes library assets; three surfaces on `setup_core`; agent setup; formats | 2026-11-07 |
| [0032](0032-library-store-and-queue.md) | Library store (nothing in asset folders, assets as light identities, identity by recognition, Missing/Offline, no migration from 0.1.0), library folders → packs, every type included, the processing queue | 2026-11-07 |
| [0033](0033-descriptions-and-engines.md) | Descriptions are optional; notifications; batched generation and out-of-memory stops; inference ports, adapters and the experimental local model server | 2026-11-07 |
| [0034](0034-rendering.md) | Kept-open parallel Blender renders, per-asset faults, render device, speed test, owner limits, edge-on flat models | 2026-11-07 |
| [0035](0035-packs-and-variant-groups.md) | Pack profiles (closed vocabulary, versions, export, signals, effect before apply), variant groups, shared variant descriptions, Add library folder wizard, Try your agent | 2026-11-07 |
| [0036](0036-collections-and-tags.md) | Collections (per-collection labels and notes), app-wide owner tags, exports, owner-only deletion | 2026-11-07 |

## Replaced

| # | Was | Decided | Now in |
| --- | --- | --- | --- |
| 0001 | `config.local.toml` overrides `config.example.toml` | 2026-10-17 | [Setup core](../Notebook/Setup%20and%20Engines/Setup%20core.md) → Rules (a convention, not a decision) |
| 0004 | Re-hash files only when their identity changes | 2026-10-17 | [0028](0028-result-identity.md) |
| 0007 | Batched descriptions (default 8); finished ones kept; out of GPU memory stays pending | 2026-10-18 | [0033](0033-descriptions-and-engines.md), [0028](0028-result-identity.md) |
| 0008 | Descriptions are optional; Generate descriptions per source; notifications | 2026-10-18 | [0033](0033-descriptions-and-engines.md), [0030](0030-counted-exclusions.md) |
| 0012 | Collections (per-collection labels/notes), app-wide tags, agent write tools, confirmed deletions | 2026-10-24 | [0036](0036-collections-and-tags.md), [0029](0029-agent-trust.md) |
| 0014 | Setup wizard (app + CLI) on `setup_core`; first-run rule; `descriptions_enabled`; Blender in `config.local.toml` | 2026-10-25 | [0031](0031-setup.md), [0028](0028-result-identity.md) |
| 0015 | Inference ports and adapters; experimental loopback local-server description engine | 2026-10-25 | [0033](0033-descriptions-and-engines.md), [0028](0028-result-identity.md) |
| 0016 | Agent setup through MCP: user-opened setup session, Blender proposals applied by the user, live connection records, bounded status | 2026-10-25 | [0031](0031-setup.md), [0029](0029-agent-trust.md) |
| 0022 | Parallel kept-open Blender renders on the CPU or a GPU; speed test picks device and count; owner limits never slower; proven-equivalent worker edits keep fingerprints | 2026-10-26 | [0034](0034-rendering.md), [0028](0028-result-identity.md) |
| 0023 | Central library store with results keyed by inputs, identity by recognition, library folders → bundles → packs, every type included, implicit processing queue, one-time migration | 2026-10-30 | [0032](0032-library-store-and-queue.md), [0028](0028-result-identity.md), [0029](0029-agent-trust.md) |
| 0024 | Pack profiles (versioned, exportable rules per pack, signals, effect before apply), variant groups instead of pair lists, one shared description per variant group | 2026-10-31 | [0035](0035-packs-and-variant-groups.md), [0029](0029-agent-trust.md) |
| 0025 | Design principles P1–P5 | 2026-11-01 | [Design language](../Architecture/Desktop%20App/Design%20language.md) |
| 0026 | Setup leaves every core feature working (search check on built-in samples, Connect your agent), built-in sample assets, formats Assetarium uses (off means hidden; textures always read) | 2026-11-01 | [0031](0031-setup.md), [0030](0030-counted-exclusions.md) |
