---
tags: [architecture]
parent: "[Architecture](../Architecture.md)"
status: draft
verified: 2026-11-10
branch: feature/audit-simplify
level: macro
code: [sources.py, incremental.py, processing_queue.py, source_operations.py, library_index.py, publication.py, gpu_queue.py, scripts/library-batch.py]
---
# Library updates and processing

> How a file in a library folder becomes a searchable, published asset: scan, queue, stages, publication.
> Rewritten on 2026-11-10 as the current flow; the pilot-era operations and budgets it used to list are in
> git (commit `af02e91`).

Up: [Architecture](../Architecture.md) · Down: [Stage ledger and fingerprints](../../Notebook/Processing/Stage%20ledger%20and%20fingerprints.md),
[Processing queue](../../Notebook/Processing/Processing%20queue.md) · Where in code: [Processing](../../Notebook/Processing/Processing.md) ·
User guide: [Library](../../../docs/asset-sources.md), [CLI](../../../docs/cli.md).

## The flow

```
        library folder (read only)
                  │
                  ▼
        scan: inventory, records       (1)
                  │
                  ▼
        queue: owner or agent asks     (2)
                  │
                  ▼
        inspection and previews        (3)
                  │
                  ▼
        search vectors                 (4)
                  │
                  ▼
        publish a new generation       (5)
                  │
                  ▼
        search, detail, MCP
```

1. **Scan.** Every enabled library folder is scanned in the background at launch and when it is added or
   toggled. A scan stats files, hashes and parses only what changed, recognizes assets it has seen before,
   and never runs Blender or a model ([decision 0027](../../Decisions/0027-saved-catalog-first-and-fast-scan.md)).
2. **Queue.** Processing never starts by itself. **Make previews** and **Generate descriptions** are queue
   items for a library folder, a pack, a folder or picked assets; the scope is resolved when the item starts.
   One item runs at a time, previews before descriptions; closing the app stops the queue and the next start
   offers to continue ([decision 0032](../../Decisions/0032-library-store-and-queue.md)).
3. **Inspection and previews.** 3D models render in parallel kept-open Blender processes
   ([decision 0034](../../Decisions/0034-rendering.md)); images are decoded without Blender
   ([Catalog contract](../Sources%20and%20Catalog/Catalog%20contract.md#images)).
4. **Search vectors.** Each view gets an image vector; a valid description adds a description vector
   ([Embedding contract](../Search/Embedding%20contract.md)).
5. **Publish.** The working catalog and index are verified and copied into a new immutable generation, and
   one manifest switches to it.

**Descriptions are a separate, optional run** (step 2's second item kind): they describe assets whose
previews exist, add description vectors and publish again. A missing or failed description is never import
work or an import failure ([decision 0033](../../Decisions/0033-descriptions-and-engines.md)).

## What decides whether work is pending

Each stage result is keyed by a fingerprint of its inputs, never by a location
([decision 0028](../../Decisions/0028-result-identity.md)):

| Stage | Key covers |
| --- | --- |
| Inspection (3D) | The chosen file and its dependencies by content, render resolution, worker code, Blender identity |
| Inspection (image) | File contents, model-input policy, pixel-producing code |
| Description | The rendered views by content, model revision, backend, runtime lock, prompt |
| Description vector | The effective description text |
| Image vector | The verified view bytes |

- A record whose key already has a finished result adopts it: a duplicate, a moved file or a folder added
  around others renders nothing.
- A finished job with unchanged inputs is kept. So is a **failed or unsupported** one: an unchanged fault is
  never retried by itself. The owner asks for a recheck
  ([decision 0020](../../Decisions/0020-alternate-file-faults-and-recheck.md)).
- New content or a new contract makes a new job. Changing severity, approvals, format toggles, render limits,
  batch size or the storage budget re-queues nothing.
- Each inspection, description and vector is checkpointed as it finishes, so an interrupted run resumes.

## Settings that shape a run

All under **Settings → General**; none deletes results or retries faults.

- **Formats Assetarium uses**: one toggle per 3D and image format. Assets only in formats that are off are
  hidden and counted, and create no work ([decision 0030](../../Decisions/0030-counted-exclusions.md)).
- **Rendering**: the device and how many renders run at once, picked by a short speed test on synthetic
  shapes; the owner's limits never make it slower.
- **Description batch size** (1, 2, 4 or 8; default 8): how many assets share one model call. Running out of
  GPU memory stops the run with that message and leaves the batch pending.
- **Storage budget**: processing asks before it would pass it. It is a limit, not permission to delete.

## Publication and who serves what

Processing writes a working catalog and index while search keeps serving the previous immutable generation.
Publishing checks membership, SQLite integrity, vector checksums and the current file, description and view
inputs, copies the matching pair into a new generation, and switches one manifest atomically. A failure
leaves the previous generation active. Each request pins one generation; a publication that changes nothing
keeps its version. Old generations are pruned by the retention rule
([decision 0006](../../Decisions/0006-retention.md)), and rollback means switching to a kept generation,
never editing a published database.

The owner's description corrections (`data/captions/corrections/<asset-id>.json`) survive scans and
processing byte for byte. A changed effective description invalidates its description vector; approvals,
notes, warnings and suggested uses alone do not.

## One GPU job at a time

`gpu_queue.lease` serializes model work across processes: a processing batch waits a bounded time for the
lease, a search waits five seconds and then answers that the queue is busy. Browsing, keyword search and
detail never need it. The search worker gives up its model as soon as a batch asks
([Search embedders](../../Notebook/Search/Search%20embedders.md)). A second lease keeps two writers (app, CLI,
agent) from running operations on the same library at once.

## Faults

An asset that fails is marked, its reason and evidence are kept, usable partial results stay, and the run
moves on (`AGENTS.md` → Fault handling). Failures are listed under **Recorded failures** on Asset processing,
apart from pending work. Originals and earlier reports are never edited to make a fault disappear.

## From a terminal

The owner CLI (`scripts/local-assets.ps1` / `.sh`) calls the same backend as the app: `previews`, `describe`,
`queue …`, `process`, `cancel` ([CLI](../../../docs/cli.md#processing)). `scripts/library-batch.py`
(`scan`, `process`, `refresh`, `status`, with `--source`, `--dry-run`, `--batch-size`, `--skip-captions`,
`--peak-reserve-mib`) is the coordinator those commands start; it takes storage receipts before and after a
run and stops if growth passes its reserve. Stage reports are written under `library/batches/` and operation
logs under `library/operations/` in each folder's working data. Runs use the prepared runtimes with
`--locked --no-sync --offline`; nothing is installed or downloaded.

Recording an AI review of descriptions uses `scripts/record_caption_review.py`
([Caption severity](Caption%20severity.md)); it never reruns a model.
