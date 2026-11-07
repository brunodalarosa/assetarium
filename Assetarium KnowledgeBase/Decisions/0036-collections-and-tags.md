---
tags: [decision]
decided: 2026-11-07
replaces: [0012]
code: [asset_collections.py, mcp_server.py, frontend/src/pages/Collections.tsx, frontend/src/pages/Collection.tsx]
---
# 0036 — Collections and owner tags

> **Approved by the owner on November 7, 2026** (decision review). Consolidates decision 0012 (October 24, 2026).
> What agents may change is in [decision 0029](0029-agent-trust.md).

**Decision.** **Collections** are named, owner-organized, virtual bundles of assets of any type from any library
folder. A collection has a title, a description and an ordered list of members; each member has a **label** and
**notes** that belong to that collection only (the same asset can be "Coin" in one collection and "money" in
another). **Tags** are separate: short words on the asset itself, shared by the whole app (inspection, the `tag`
search filter, every collection and agents).

- **Storage.** `data/library/collections.json` and `data/library/asset-tags.json`, central, written atomically
  under the `collections` lease with an increasing revision. A damaged file is reported and kept for review, never
  reset. Members keep their files where they are; nothing is copied or written to originals.
- **Membership.** Members are asset IDs with a snapshot (name, type, library folder) taken when added. Availability
  is resolved on read: in the library, waiting for processing, hidden by a format that is off (marked "Format
  off"), or unavailable with the reason (folder removed, asset gone). Entries, labels and notes survive and come
  back when the asset does.
- **Desktop.** A Collections page: card grid (four covers, name, "Updated" date), newest first, a search over names,
  descriptions and contents (names, labels, notes, tags, descriptions; exact text), and New collection. A
  collection's view works like Home, with its name in the top bar, a rename pencil and search limited to its
  members, owner text matches first. Every asset card has a right-click menu (Inspect; Add to a collection; in a
  collection, Remove from collection). Removing members is a batch selection with one Undo toast, not a deletion.
- **Deletion.** Deleting a collection (and removing a library folder) is confirmed in a modal with a red confirm
  button, and only the owner does it.
- **Exports.** JSON for agents (members, labels, notes, tags, availability and absolute original paths with
  dependencies), a PNG sample sheet of visual members, Markdown with a thumbnails folder, and a PDF printed by the
  app from the same report. A Save dialog picks the target (default `data/exports/collections/`); scripted targets
  stay under `data/exports`.
- **Agents (MCP):** `list_collections`, `get_collection`, `edit_collection` (create, rename, describe, add or
  remove members, set a member's label and notes) and `tag_assets`. An agent edit raises one `collection_changed`
  notice per collection. Collection text is data, never instructions.

## Why

The owner wants project-oriented grouping (every asset of one minigame, labeled where it is used, with
implementation notes) that can be handed to agents as JSON or kept as reference documents, and wants agents to
build such collections from criteria ("aquarium creatures with only small fishes").

## Keep true

- A collection is never an asset and never moves, copies or edits files.
- Labels and notes stay per collection; tags stay per asset.
- Unavailable members stay visible with their reason.
- Deletions keep the red confirmation and stay owner-only.
