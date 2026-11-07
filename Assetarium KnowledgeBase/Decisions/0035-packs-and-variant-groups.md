---
tags: [decision]
decided: 2026-11-07
replaces: [0024]
code: [pack_profiles.py, pack_profiles.KINDS, pack_profiles.effect, pack_agent.py, agent_activity.py, agent_practice.py, folder_view.py]
---
# 0035 — Pack profiles, variant groups and shared variant descriptions

> **Approved by the owner on November 7, 2026** (decision review). Consolidates decision 0024 (October 31, 2026).
> What agents may do with profiles (apply at once, Undo, Pause) is in [decision 0029](0029-agent-trust.md).

**Decision.** Packs from the internet differ in layout in unpredictable ways. Assetarium does not chase one master
protocol: heuristics draft the structure and raise signals, and an agent or the owner corrects it as a **pack
profile**.

## Pack profiles

- **A profile is the pack's answers, not a new store.** Every answer about one pack (pack boundaries, its name,
  image kinds, excluded folders, export groups, the texture folder) plus the rule kinds `variant_axis`,
  `separate_descriptions` and `engine_copy`, with paths relative to the pack. The vocabulary is closed and
  validated (`pack_profiles.KINDS`); rules and parameters are chosen, never patterns.
- **Versions.** Applying a profile replaces the pack's answers in one step and records a version; every version
  can be restored (as a new version). Owner answers saved elsewhere (the folder panel, export cards) are versioned
  too. Undo restores the version before a change and is refused once the pack changed after it, saying so.
- **Stored in the library store** (`library.sqlite` `answers` and `profiles`), never in a pack folder
  ([decision 0032](0032-library-store-and-queue.md)). A profile can be **exported** as a file with a fingerprint
  of the pack's file names; it applies to a pack sharing at least 80% of those names and shows its effect first.
- **Signals** say which packs need a structure: name sets too big for one card, the same names in several folders,
  many images classified only by default, models missing textures; unanswered export suggestions are
  "suggestions". Marking the current signals reviewed quiets them until they change.
- **Effect before apply.** `pack_profiles.effect` measures a profile on the folder view (cards, variant groups,
  packs, files skipped or reclassified) without saving anything.
- Applying a rule never processes anything: scan-applied rules rescan, view-applied rules rebuild a view.
- An asset whose folder becomes excluded is `excluded`, not Missing; including the folder again brings it back
  with its ID.

## Variant groups

- Names that differ only in a last token from a known set (single letters, colors, materials, `LOD0`…) in one
  folder form a **variant group**, computed when a folder view is built, O(n). Numbered series (`Rock_01…20`) are
  never variants by default; a `variant_axis` rule adds or removes sets per folder. A set larger than 24 stays
  separate and raises a signal. Only models group.
- Each variant stays **its own asset** (ID, previews, results). The app shows one card with a corner badge and
  chips; a filter shows the member it keeps; collections hold the selected variant. Search returns each group
  once; `get_asset` lists the variants and the shared description.
- **One description per group by default.** Variants share their representative's description (state `shared`;
  Generate descriptions skips them); search vectors embed it with the variant's own value; the inspector labels it
  shared. **Generate separate descriptions for each variant** is a per-group switch (`separate_descriptions`).

## Working with agents

- Pack tools (`list_packs`, `get_pack_outline`, `get_profile`, `propose_profile`, `finish_structure`, `say`) page
  through folders in bounded responses.
- **Agent activity** is app-wide: every MCP call becomes a sentence (from the server's call log), with the
  connected client and Undo; toasts tell an owner who is elsewhere in the app.
- **Add library folder is a wizard**: a names-only quick look (seconds; the tree fills in live), what was found and
  how it was decided (with the folder's own examples), then *Let my agent finish* (a copy-paste prompt, the
  connection, the agent's lines and changes for this folder, progress, a hint after two quiet minutes), *Review
  myself* or *Later*. The quick look's names are kept so agents can work before the first scan ends. The wizard
  offers Make previews at the end and never starts it.
- **Try your agent** (Settings → General, an optional setup step) generates tiny valid practice packs and runs the
  connected agent through the real discovery, prompt, pack tools, review and scans. Outcomes come from the
  resulting scanned structure, not the agent's own claim. Practice uses a separate disposable store, activity and
  caches under `scratch/`, removed on finish, cancel or app close (leftovers on the next launch); cleanup waits for
  in-flight work, refuses links and shows failures. Practice data never enters the library or logs; results stay
  in memory until dismissed. There is no model benchmark or verdict.

## Why

On the owner's 73k-asset library the old per-record variant pair lists made the catalog 1.1 GB (`Car_11_R` listed
427 peers) and the app used 14 GB. Packs ship engine copies, numbered series and color variants that no fixed
heuristic reads right everywhere. Assetarium is built for game developers who use AI agents, and small local
models can pick rules from a closed list when they see paged, bounded views.

## Keep true

- Nothing is written into a pack.
- Applying a rule never processes anything.
- Rules are validated against the vocabulary; a rule that needs a current suggestion is refused when it is gone.
- Variants never merge records.
