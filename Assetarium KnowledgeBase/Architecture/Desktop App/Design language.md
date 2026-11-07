---
tags: [architecture]
aliases: [Design principles]
level: system
parent: "[Desktop app design](Desktop%20app%20design.md)"
status: reviewed
code: [frontend/src/ui/ProposalReview.tsx, frontend/src/ui/CommandBlock.tsx, frontend/src/ui/OperationProgress.tsx]
verified:
branch:
---
# Design language

> **Only the owner changes this document.** Agents may propose an edit, then wait for the owner's approval
> before writing it (`AGENTS.md` → Knowledge base). This is the one home of Assetarium's design principles
> (also called "Design principles"); other notes link here and never restate them.

Assetarium's UI and UX follow these named principles. They are **principles, not rules**: a change may depart
from one when it says why. How the UI applies them (tokens, components, icon meanings and concrete rules) is in
the [Design system](../../Notebook/Desktop%20App/Design%20system.md) note. They were first recorded as
[decision 0025](../../Decisions/0025-design-principles.md) (November 1–4, 2026), which keeps the history.

Up: [Desktop app design](Desktop%20app%20design.md) · Where in code: [Design system](../../Notebook/Desktop%20App/Design%20system.md)

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
| Anything a connected agent does (P6) | Runs at once, shown in Agent activity with **Stop** / **Undo** |
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

*(Added November 4, 2026; co-designed and approved by the owner on the PR 21 review. Hiding rule changed by the
owner on November 7, 2026, decision review.)* Assetarium is built for people who want to know everything about a
file, a process or an action. Every asset, queue item and action shows its state and why it is in it: the facts
first, then only the actions that actually resolve it. Nothing is skipped or "nothing to do" without saying why.
Explicit is not verbose: a state chip or one line is always visible, and the reason and actions sit in the
inspector, a tooltip or an expanded row.

- **Hidden, counted once.** A view may leave items out (a format that is off, a description search can't use),
  but never silently: the view says how many it left out, why, and offers **Show** and the action that resolves
  it, in one line. The same rule holds in every view, the Library included, where each folder shows its count.
- First applied to a model whose previews were made from a file in a format that is off (an FBX inspected model
  that also has an OBJ, with FBX off). It used to look Ready while descriptions and search by meaning quietly
  left it out. It became **Format off** (`settings.format_off`) with **Turn FBX on**. Under the hiding rule it
  leaves the views, is counted and is re-inspected from its OBJ on the next Make previews:
  *"15 hidden until previews from OBJ are made · Make previews"* (decision 0030; not built yet).
- Closing the app while work runs says so and asks; the next start says what stopped (decision 0023).

## P6 — Agents first, in the open

*(Added November 7, 2026 by the owner, decision review;
[decision 0029](../../Decisions/0029-agent-trust.md).)* Assetarium is agent-first: a connected agent may do what
the owner can, except the owner-only actions, and does it at once instead of asking. In exchange, everything an
agent does happens in the open.

- **Say it before connecting.** Connecting an agent explains, in one plain sentence, what it may change on its
  own and where to watch, stop, pause or undo it.
- **Show it as it happens.** Agent actions appear in Agent activity and on what they touched, with `Bot` (P2).
  An agent's job in the queue says who started it.
- **Control is always one click away.** Stop, Pause agents and Undo for an agent session are never hidden
  behind a page the user has to find.

## What future work must keep true

- New review flows with several alike decisions group them and commit once, unless the cost table says otherwise.
- A commit reports per item: one failing item is shown with its reason and stays pending; the others are saved.
- New agent-related UI uses `Bot`; no sparkle icons.
- Commands appear only in a `CommandBlock` (or through `Reason`); an action the app can run is a button.
- A new state, skip or exclusion carries its reason and the actions that resolve it; hidden items are counted
  with their reason and **Show** (P5).
- A new agent capability is visible in Agent activity and can be stopped or undone; connecting says what it may do (P6).
