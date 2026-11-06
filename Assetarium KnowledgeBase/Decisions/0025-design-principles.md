---
tags: [decision]
decided: 2026-11-01
---
# 0025 — Design principles: decide many, commit once; the robot means agents (superseded)

> **Superseded on November 6, 2026 by the [Design language](../Architecture/Desktop%20App/Design%20language.md)**,
> the one home of the design principles, which only the owner changes. This record is frozen as the history of
> how P1–P5 were decided; read and cite the Design language instead.

**Decision (owner, November 1, 2026; co-designed in a brainstorm, approved for implementation).** Assetarium's
UI and UX follow named design principles. They are **principles, not rules**: a change may depart from one when
it says why. The component catalog and icon meanings that apply them live in the
[Design system](../Notebook/Desktop%20App/Design%20system.md) note.

## P1 — Decide many, commit once, see the outcome

When decisions are alike, let people decide them together and commit them once, after seeing what will happen.

- **Group by signature.** Suggestions with the same kind of rule and the same effect (the same folder inside
  each pack, the same target) are one group, even when their full paths differ. A group can still be decided
  per member. What only one item has stays on its own, so differences stand out.
- **Stage, preview, commit.** Choosing Accept / Reject saves nothing; a preview measures the staged decisions,
  and one Apply saves them all and runs any follow-up work (a scan) **once**.
- **Pick the pattern by cost** (the exceptions):

| What the action does | Pattern |
| --- | --- |
| Cheap and undoable (tags, labels, agent rules that need no scan) | Apply at once, offer **Undo** |
| Costly or coupled (rescans, renders, reprocessing) | Stage, preview, commit once |
| Irreversible (owner-only deletions) | One at a time, never batched |

- **Notices group too**: several alike events arriving together make one notice, not one each.

First applied to agent pack proposals: a library folder's waiting proposals are one grouped review with one
**Apply decisions** button and one scan (`pack_agent.preview` / `commit`, `ProposalReview.tsx`). Why: one
Apply per pack rescanned the folder each time and blocked the next Apply ("Wait for this library folder's
operation to finish"), and near-identical cards hid the one rule that differed.

## P2 — One visual sign for agents

The `Bot` (robot) icon means **an external agent did this or can do it** — and nothing else. Local models
(descriptions, embeddings) are ordinary processing and do not get it. Sparkles are not used anywhere: they read
as generic "AI" and copy another product's identity. "New since your last visit" is a dot.

## P3 — Run it, don't type it

*(Added November 1, 2026.)* Nobody types a command by hand.

1. **Prefer a button that does the work.** When the app can run something itself, it offers the action (for example
   **Run check** for the search check) instead of a command.
2. **When a command can't be avoided** (installs and syncs that can't run inside the app), it is shown in a
   `CommandBlock` with **Copy**, never inline in a sentence. Backend text that carries a command is shown through
   `Reason`, which splits the command into its own block; `tests/test_command_blocks.py` keeps the pattern in step
   with the backend's messages.

## P4 — Make progress measurable

*(Added November 2, 2026; co-designed and approved by the owner.)* Long operations show their current phase
and one compact numeric measure without requiring hover. Hover or keyboard focus reveals further detail:
completed / total, remaining work, the unit being counted and separate successful and faulty outcomes.

- A known total uses a count or percentage. Label phase progress as phase progress, never whole-operation completion.
- When the total is unknown, show measured work so far and say the total is still being discovered; use an
  indeterminate indicator. Do not manufacture a percentage or perform another scan just to count files.
- Saving or finalizing stays visibly active until it finishes, even after every counted item has been checked.
- Asset processing, background activity and notifications present the same measurements consistently.

## P5 — No silent states

*(Added November 4, 2026; co-designed and approved by the owner on the PR 21 review.)* Assetarium is built for
people who want to know everything about a file, a process or an action. Every asset, queue item and action shows
its state and why it is in it: the facts first, then only the actions that actually resolve it. Nothing is
skipped, hidden or "nothing to do" without saying why. Explicit is not verbose: a state chip or one line is
always visible, and the reason and actions sit in the inspector, a tooltip or an expanded row.

- First applied to a model shown in the Library whose previews were made from a file in a format that is off
  (an FBX inspected model that also has an OBJ, with FBX off). It used to look Ready while descriptions and search
  by meaning quietly left it out. It is now **Format off** (`settings.format_off`, the folder view's `format_off`
  state) with the reason and **Turn FBX on** in the inspector.
- Closing the app while work runs says so and asks; the next start says what stopped (decision 0023).

## What future work must keep true

- New review flows with several alike decisions group them and commit once, unless the cost table says otherwise.
- A commit reports per item: one failing item is shown with its reason and stays pending; the others are saved.
- New agent-related UI uses `Bot`; no sparkle icons.
- Commands appear only in a `CommandBlock` (or through `Reason`); an action the app can run is a button.
- A new state, skip or exclusion carries its reason and the actions that resolve it (P5).
