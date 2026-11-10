---
area: Processing
tags: [system]
code: [processing_queue.py, processing_queue.add, processing_queue.place, processing_queue.MODES, processing_queue.advance, processing_queue.resolve, processing_queue.estimate, processing_queue.claim, processing_queue.release, processing_queue.owner_gone, source_operations.watch_owner, desktop.create_window, processing_queue.failures, folder_view.connect, source_operations.start, source_operations.worker_stage, scripts/source-operation.py, library_view.blockers]
verified: 2026-11-04
branch: feature/library-view
---
# Processing queue

Hub: [Processing](Processing.md). Make previews and Generate descriptions as queue items (decision 0032).
Start at `processing_queue.add` and `processing_queue.advance`.

## How it works

- The queue is `library-store/queue/queue.json`: items (`action`, `scope` = library folder key plus a
  folder path or picked asset IDs, `status`, `stopped_on_close`), `recent`, `paused` and `owner` (the open
  app's `pid`, `closing`, its session `log`). Changes take the `queue` lease (`gpu_queue.lease`).
- `advance` finishes a running item whose operation ended (its outcome goes to `recent`), then starts the
  first waiting item: previews before descriptions, otherwise the owner's order. **The scope is resolved at start**
  (`resolve`, from the folder's up-to-date view, `folder_view.connect(fresh=True)`): assets whose state is `no_previews` (or whose description is `missing`), skipping blocked
  ones. It then calls `source_operations.start` with `asset_ids`, which the operation saves in its state;
  `worker_stage` limits inspection and captions to them (search vectors still cover the whole folder).
- **Description modes** (`MODES`, one named asset only): `retry` resolves a `failed` description and `edited` a
  `complete` one; the default resolves `missing`. `source_operations.start(mode=…)` saves the mode in the operation
  state; `edited` skips the caption stage, needs no description model (allowed with descriptions off) and raises no
  report notice. A waiting item with the same scope is reused, not added twice. `place` tells the inspector whether
  an asset's description work runs, waits (and where), or whose last search update did not finish.
- **Saved edits search does not read yet** (`search_pending` in `queue.json`, `mark_search_pending`): the bridge marks
  the asset before queueing its update, and `_finish_running` clears it only when an `edited` item completes (not for
  an edit saved after that item started). `add` can return `confirm` without queueing (storage budget, no
  measurement); `place` then reports `pending`, so the inspector keeps Update search instead of losing the update.
- `scripts/source-operation.py` calls `advance` when **any** operation ends (scans and speed tests too), so an
  item whose start found its folder busy (`start` returned `busy`) never stalls.
- **The open app owns the queue** (decision 0032, November 4, 2026). `DesktopBridge` calls `claim` at startup
  (previous owner dead without `closing` = a crash: its items go to Recent as `stopped` with the log name) and
  `release` in `_close` (cancel the running item, put it back as `waiting`, mark every item `stopped_on_close`,
  pause, `owner.closing`). `advance` passes the live owner pid to `start(owner=…)`; the worker gets `--owner`
  and `watch_owner` ends it and its process tree (`end_tree`: `taskkill /T` / `killpg`) once that pid is gone,
  calling `owner_gone` first. `create_window`'s `closing` handler returns False while `running_item` exists and
  asks the page (`window.lal.askClose`) from another thread; `stop_and_close` sets `_allow_close` and destroys.
  Work started from a terminal while no app is open has no owner and runs to the end.
- `add` estimates time from recent batch reports (`folders/*/library/batches/<stage>-*.json`) or the
  render speed test, disk from a sample of finished results, and the budget from the newest storage
  receipt (no new measurement). Over `LONG` seconds, past the budget, or `unmeasured` (more than
  `UNMEASURED` assets with no time estimate or no storage receipt) it returns `confirm`; between `QUICK`
  and `LONG` it marks `undo`.

## Rules

- **Blocked work is never queued**: `library_view.blockers` names Blender or the search runtime with its
  fix; `add` refuses a scope with nothing else to do and says why.
- One item runs at a time; the GPU stays one job at a time through the existing leases.
- Removing the running item cancels its operation cleanly (`source_operations.cancel`); nothing is killed.
  Only the owning app going away kills an operation (`watch_owner`).

## Gotchas

- An item whose operation state shows another token is recorded `interrupted`, so a test stand-in for
  `start` must also write the operation state (see `scripts/verify-asset-sources.py`).
- pywebview's `closing` event also fires for `window.destroy()`: scripts that close a window while an item is
  running set `bridge._allow_close = True` first, or the close is cancelled and the dialog shows.

## Related

[Stage ledger and fingerprints](Stage%20ledger%20and%20fingerprints.md) ·
[Sources](../Sources%20and%20Catalog/Sources.md) · [GPU lease](GPU%20lease.md) ·
Decisions: [0034](../../Decisions/0034-rendering.md), [0032](../../Decisions/0032-library-store-and-queue.md).
