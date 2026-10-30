---
area: Processing
tags: [system]
code: [processing_queue.py, processing_queue.add, processing_queue.advance, processing_queue.resolve, processing_queue.estimate, processing_queue.after_restart, source_operations.start, source_operations.worker_stage, scripts/source-operation.py, library_view.blockers]
verified: 2026-10-30
branch: feature/library-view
---
# Processing queue

Hub: [Processing](Processing.md). Make previews and Generate descriptions as queue items (decision 0023).
Start at `processing_queue.add` and `processing_queue.advance`.

## How it works

- The queue is `library-store/queue/queue.json`: items (`action`, `scope` = library folder key plus a
  folder path or picked asset IDs, `status`), `recent`, `paused` and the `overnight` window. Changes take
  the `queue` lease (`gpu_queue.lease`).
- `advance` finishes a running item whose operation ended (its outcome goes to `recent`), then starts the
  first waiting item: previews before descriptions, otherwise the owner's order; descriptions wait while
  the overnight hold is on and the clock is outside the window. **The scope is resolved at start**
  (`resolve`): assets whose state is `no_previews` (or whose description is `missing`), skipping blocked
  ones. It then calls `source_operations.start` with `asset_ids`, which the operation saves in its state;
  `worker_stage` limits inspection and captions to them (search vectors still cover the whole folder).
- `scripts/source-operation.py` calls `advance` when a process or describe operation ends, so the queue
  moves on without the app. The desktop app calls `after_restart` at startup: waiting items with nothing
  running mean a leftover queue, which is marked paused.
- `add` estimates time from recent batch reports (`folders/*/library/batches/<stage>-*.json`) or the
  render speed test, disk from a sample of finished results, and the budget from the newest storage
  receipt (no new measurement). Over `LONG` seconds or past the budget it returns `confirm`; between
  `QUICK` and `LONG` it marks `undo`.

## Rules

- **Blocked work is never queued**: `library_view.blockers` names Blender or the search runtime with its
  fix; `add` refuses a scope with nothing else to do and says why.
- One item runs at a time; the GPU stays one job at a time through the existing leases.
- Removing the running item cancels its operation cleanly (`source_operations.cancel`); nothing is killed.

## Gotchas

- An item whose operation state shows another token is recorded `interrupted`, so a test stand-in for
  `start` must also write the operation state (see `scripts/verify-asset-sources.py`).

## Related

[Stage ledger and fingerprints](Stage%20ledger%20and%20fingerprints.md) ·
[Sources](../Sources%20and%20Catalog/Sources.md) · [GPU lease](GPU%20lease.md) ·
Decisions: [0022](../../Decisions/0022-parallel-rendering.md), [0023](../../Decisions/0023-central-asset-library.md).
