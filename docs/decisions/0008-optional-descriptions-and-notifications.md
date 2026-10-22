# 0008 — Descriptions are optional extra data; notifications report them

**Decision.**
- **Importing never generates descriptions.** **Process assets** runs inspection/
  previews and search vectors (`OPERATION_STAGES['process']`), then publishes.
  Image vectors and the asset name make an asset searchable.
- **A pending or failed description is neither import work nor an import
  failure.** `sources.import_outcome` ignores the caption stage and treats an
  embeddings `partial`/`failed` state as complete when no *image* vector failed
  (`embedding_failures` reads image jobs only). It raises no main-view source
  card and does not appear in **Importing failures report**. Failures are still
  recorded and shown in asset detail and in each source's description counts.
- **Search ignores unusable descriptions silently.** Default `combined` search
  still fuses descriptions. A missing, stale or invalid description leaves only
  the description channel and is not reported as an exclusion fault (app or MCP).
- **Generate descriptions** on *Asset processing* (moved there from
  *Settings → Asset sources* by [decision 0011](0011-react-desktop-ui.md)) starts a per-source
  `describe` operation: caption stage (only assets whose renders are ready,
  `description_state == 'missing'`), then description vectors, then publish. It
  reuses the operation lease, progress, Cancel, storage budget and the batching
  of [decision 0007](0007-batched-description-generation.md). Recorded failures
  are not retried. Cancel, out of GPU memory and storage stops still publish
  finished descriptions.
- **Notifications** (`data/library/notifications.json`, bell + panel + toasts):
  *Descriptions ready to generate* (one per source; raised when processing ends
  with missing descriptions, and once on first launch for existing sources;
  **Not now** stays quiet until more descriptions are missing) and a *report* per
  describe run (finished / with failures / cancelled / stopped / interrupted).
  They arrive with `sources()`; `changes()` stamps the file. Closing the panel
  marks notices read. Notices only offer actions that can change the state;
  report notices lead to Asset processing (**View in Asset processing**, or
  **View report** for stopped, interrupted or failed runs).

**Why.** EmbeddingGemma image and name matching already find assets without
descriptions, while description generation is the slowest stage (a GPU model).
Blocking imports on it, or flagging every missing description as a warning,
hid usable assets behind work that only refines text search.

**Keep true.** Do not add the caption stage back to importing or count
description faults as import failures. A description run never retries
recorded failures without an explicit owner request. Keep notifications to
facts about runs and pending optional work; they never start work by themselves.
