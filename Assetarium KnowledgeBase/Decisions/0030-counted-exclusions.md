---
tags: [decision]
decided: 2026-11-07
area: Desktop App
replaces: [0008, 0026]
code: [settings.uses, settings.format_off, settings.inspected_path, folder_view.py, retrieval.py, incremental.inspection_input]
---
# 0030 — Left-out items are hidden, counted once

> **Approved by the owner on November 7, 2026** (decision review). Applies Design language P5 "hidden, counted
> once" to the two places that left things out silently. *Not built yet*: see [Today and target](#today-and-target).

**Decision.** When Assetarium leaves something out, it may hide it, but never silently. Every view that leaves
items out shows **one line**: how many, why, **Show**, and the action that resolves it. The same rule holds for
the app's views (Home, search, the Library and each of its folders, the queue) and for agents (MCP responses
carry the same counts and reasons).

## Formats that are off

A format that is off is not used: no previews, descriptions or search from it. Its files stay known.

| Asset | What happens | The line says |
| --- | --- | --- |
| **Every** file in a format that is off (an FBX-only model, FBX off) | Hidden from views, counts, search, agent results and processing | *"120 hidden: FBX is off · Show · Turn FBX on"* |
| Its previews came from an off format, **another of its formats is on** (FBX + OBJ, previews from the FBX) | Hidden as well, and its inspection becomes **pending from the format that is on** (the OBJ). It joins the next Make previews like any pending work; nothing starts by itself. When the OBJ previews exist, it comes back | *"15 hidden until previews from OBJ are made · Make previews"* |

- **Nothing is lost.** The FBX previews stay in the library store, keyed by content
  ([decision 0028](0028-result-identity.md)). Turning FBX back on brings those assets back with their FBX results
  at once, without rendering. Recorded failures are still not retried.
- **Collections** keep a hidden member and mark it "Format off", as before.
- **Image toggles** still cover standalone images only; textures used by 3D models are always read.
- Changing formats is instant (folder views rebuild), never deletes results and never scans again.
- This replaces today's **Format off** chip on shown assets: such an asset is now hidden and counted.

## Descriptions search can't use

Search still finds an asset by its image and name when its description is missing, stale or invalid, so the
asset is not hidden: only the description channel is left out for it. That is no longer silent:

- The search results say it once: *"Descriptions not used for 23 of these results: 20 missing · 3 stale ·
  Generate descriptions"* (no line when there are none). MCP search returns the same counts and reasons.
- It is still **not** an exclusion fault, an import failure or a warning ([decision 0033](0033-descriptions-and-engines.md): descriptions are optional): a
  missing description is optional work, not a problem.

## Today and target

| Rule | Today (2026-11-07) |
| --- | --- |
| Assets with every format off are hidden | Built, but silently: no count line |
| Shown assets with previews from an off format | Visible with a **Format off** chip; they stay out of descriptions and search by meaning and are not re-inspected |
| Re-inspect from the format that is on | *Not built yet* |
| Count line in every view and in MCP | *Not built yet* |
| Search line for descriptions not used | *Not built yet* (the asset's inspector shows its description state today) |

## Keep true

- A view that leaves items out shows the count, the reason, Show and the resolving action. No silent skip.
- Hiding never deletes results; turning a format back on restores its results without rendering.
- Re-inspection caused by a format change is pending work; it never starts by itself.
- Folder views, search, agent results and the queue apply the same format rule (`settings.uses`).

## Changes

- 2026-11-10: a citation of replaced decision 0008 now names decision 0033, which holds that rule; no rule changed.
