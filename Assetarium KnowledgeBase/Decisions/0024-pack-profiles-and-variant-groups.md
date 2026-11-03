---
tags: [decision]
decided: 2026-10-31
---
# 0024 — Pack profiles, variant groups, shared variant descriptions

**Decision (owner, October 31, 2026; co-designed in a brainstorm, approved for implementation).** Packs from
the internet differ in layout in unpredictable ways. Assetarium does not chase one master protocol: heuristics
draft the structure and raise signals, and an agent (or the owner) corrects it as a **pack profile**.

- **A profile is the pack's answers, not a new store.** Every answer about one pack (pack boundaries, its
  name, image kinds, excluded folders, export groups, the texture folder) plus new rule kinds
  (`variant_axis`, `separate_descriptions`, `engine_copy`), with paths relative to the pack. The vocabulary
  is closed and validated (`pack_profiles.KINDS`); agents choose rules and parameters, never patterns.
  Applying a profile replaces the pack's answers in one step and records a **version**; every version can be
  restored (as a new version). Owner answers saved elsewhere (the folder panel, export cards) are versioned too.
- **Profiles live in the library store** (`library.sqlite` `answers` and `profiles`) and are never written
  into a pack folder ([decision 0023](0023-central-asset-library.md)). A profile can be **exported** as a
  file with a fingerprint of the pack's file names; a file applies to a pack sharing at least 80% of its names
  and shows its effect first.
- **Signals** say which packs need a structure: name sets too big for one card, the same names in several
  folders, many images classified only by default, models missing textures; unanswered export suggestions are
  "suggestions". Marking the current signals reviewed quiets them until they change.
- **Effect before apply.** `pack_profiles.effect` measures a profile on the folder view (cards, variant
  groups, packs, files skipped or reclassified) without saving anything.
- **Variant groups replace the per-record `variants` pair lists** ("change C"; they were 75% of catalog
  bytes and unused). Names that differ only in a last token from a known set (single letters, colors,
  materials, `LOD0`…) in one folder form a group, computed when a folder view is built, O(n). Numbered series
  (`Rock_01…20`) are never variants by default; a `variant_axis` rule can add or remove sets per folder. A set
  larger than 24 stays separate and raises a signal. Only models group. Each variant stays **its own asset**
  (ID, previews, results); the app shows one card with a corner badge and chips, a filter shows the member it
  keeps, and collections hold the selected variant.
- **One description per group by default.** Variants share their representative's description (state
  `shared`; Generate descriptions skips them); search vectors embed it with the variant's own value; the
  inspector labels it as shared. **Generate separate descriptions for each variant** is a per-group switch
  (`separate_descriptions`).
- **Agents: tiers instead of a session** (replaces the setup session of
  [decision 0016](0016-agent-setup.md)). Read tools always answer; apply-and-undo tools act at once, recorded
  as the agent's and undoable; propose tools wait for the owner; run is Blender's check only. Pack tools
  (`list_packs`, `get_pack_outline`, `get_profile`, `propose_profile`, `finish_structure`, `say`) page through
  folders in bounded responses. A proposal whose rules need no scan applies at once with Undo; any other waits
  in the app's **Agent activity** drawer, one per pack (a newer one replaces it).
- **Agent activity** is app-wide: every MCP call becomes a sentence (from the server's call log), with the
  connected client, proposals waiting and Undo; toasts tell an owner who is elsewhere in the app.
- **Add library folder is a wizard**: a names-only quick look (seconds; the tree fills in live), what was
  found and how it was decided (with the folder's own examples), then *Let my agent finish* (a copy-paste
  prompt, the connection, the agent's lines and proposals for this folder, progress, a hint after two quiet
  minutes), *Review myself* or *Later*. The quick look's names are kept as a snapshot so agents can work before
  the first scan (hashing) ends. The wizard offers Make previews at the end and never starts it.
- **Try your agent** (Settings → General, an optional setup step; replaces Check my model, owner-approved
  November 2, 2026): generates tiny valid practice packs on demand, uses the connected agent and reuses the
  Library's discovery, prompt, pack tools, grouped owner review and scans. It checks pack organization and
  import review only. Outcomes come from the resulting scanned structure, not the agent's declaration that
  signals are reviewed. There is no local-model benchmark, model verdict or `model-check` CLI command.
  Practice owns a separate disposable store, activity and caches under `scratch/`; files and test-specific
  data are removed on finish, cancellation or normal app close. Results stay in memory only until dismissed.
  Unexpected-shutdown leftovers are cleaned on the next app launch. Cleanup must wait for in-flight work,
  refuse links, reject expired calls and show failures without claiming deletion succeeded. Practice data
  never enters the permanent library or logs. This explicitly replaces the former requirement to retain
  model-check reports; the agent's external chat history remains under that agent's control.
- Search returns each variant group once; `get_asset` lists the variants and the shared description.
- An asset whose folder becomes excluded is `excluded`, not Missing; including the folder again brings it
  back with its ID.

**Why.** On the owner's 73k-asset library the pair lists made the catalog 1.1 GB (`Car_11_R` listed 427
peers) and the app used 14 GB. Packs ship engine copies, numbered series and color variants that no fixed
heuristic reads right everywhere; the owner builds Assetarium for game developers who use AI agents, and
small local models can pick rules from a closed list when they see paged, bounded views.

**Keep true.** Nothing is written into a pack. Applying a rule never processes anything; scan-applied rules
rescan, view-applied rules rebuild a view. Rules are validated against the vocabulary; a rule that needs a
current suggestion is refused when the suggestion is gone. Variants never merge records.

Updates [decision 0019](0019-source-folders-and-export-variants.md) (its answers become profile rules) and
[decision 0023](0023-central-asset-library.md) (packs gain profiles).
