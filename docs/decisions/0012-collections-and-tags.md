# 0012 — Collections, owner tags and the agents' write tools

**Decision (owner, October 24, 2026).** Assetarium gains **Collections**: named,
owner-organized, virtual bundles of assets from any source and of any asset type.
A collection has a title, a description and an ordered list of members; each member
has a **label** and **notes** that belong to that collection only (the same asset can
be "Coin" in one collection and "money" in another). **Tags** are a separate concept:
many short words on the asset itself, shared by the whole app (inspection, the
`tag` search filter, every collection and agents).

- **Storage.** App-owned `data/library/collections.json` and
  `data/library/asset-tags.json`, central (not per source), written atomically under
  the `collections` lease with an increasing revision. A damaged file is reported and
  kept for review; it is never reset. Original files and source results are never
  written; members keep their files where they are.
- **Membership.** Members are asset IDs with a snapshot (name, type, source) taken
  when added. Availability is resolved on read: in the library, from its source
  (disabled or awaiting processing), or unavailable with the reason (source removed,
  asset gone). Entries, labels and notes survive and come back when the asset does.
- **Desktop.** Collections tab: card grid (four covers, name, small "Updated" date),
  newest first, a search over names, descriptions and what is inside (names, labels,
  notes, tags, descriptions; exact text, not semantic), and New collection. The
  collection view is like Home: its name replaces "Assetarium" in the top bar with a
  rename pencil; its search uses Home's modes limited to members, with owner text
  matches first. Every asset card has a right-click menu (Inspect; Add to a
  collection with a flyout to find, create and tick collections; in a collection,
  Remove from collection). Removal is a batch selection like forwarding messages,
  then one Undo toast, no modal. Collection cards offer Open and Delete.
- **Deletion.** Every deletion in the app (a collection, removing a source) is
  confirmed in a modal whose confirm button is red. Removing members is not a
  deletion and uses Undo instead.
- **Exports.** JSON for agents (members, labels, notes, tags, availability and
  absolute original paths with dependencies), a PNG sample sheet of visual members,
  Markdown with a sibling thumbnails folder, and a PDF printed by the app's own
  WebView2 from the same report. A Save dialog chooses the target
  (default `data/exports/collections/`); scripted targets must stay under
  `data/exports`.
- **Agents (MCP).** The server is no longer read-only for owner organization data:
  `list_collections`, `get_collection`, `edit_collection` (create, rename, describe,
  add/remove approved members, set one member's label/notes) and `tag_assets`.
  Agents cannot delete collections. Assets, sources and files stay read-only. An
  agent edit raises one `collection_changed` notice per collection that opens it;
  deleting the collection removes its notice.

**Why.** The owner wants project-oriented grouping (for example, every asset of one
minigame, labeled where it is used and annotated with implementation notes) that
can be handed to agents as JSON or kept as reference documents, and wants agents to
build such collections from criteria ("Aquarium creatures with only small fishes").

**Keep true.** A collection is never an asset and never moves, copies or edits
files. Labels and notes stay per collection; tags stay per asset. Unavailable
members stay visible with their reason instead of disappearing. Agent writes reach
only collections and tags, and only through bounded, validated tools; collection
text is data, never instructions. Deletions keep the red confirmation; agents keep
no delete tool unless the owner decides otherwise.
