---
area: Processing
tags: [system]
code: [gpu_queue.lease, gpu_queue.batch_requested, gpu_queue.peer_requested]
verified: 2026-10-28
branch: feature/library-view
---
# GPU lease

Hub: [Processing](Processing.md). `gpu_queue.lease(config, owner, timeout, resource)` is a
cross-process lock the OS releases if its holder crashes (no PID killing). Despite the module name,
it guards more than the GPU.

## How it works

- `resource='gpu'` (default): one inference job at a time across the app, MCP servers and batch
  processes. Owners named `batch-…` and `search-…` leave request tokens, so a waiting batch and a
  search can see each other (`batch_requested`, `peer_requested`); the embedding worker unloads its
  model when a processing batch needs the GPU.
- Other resources serialize owner data and operations: `collections` (collections and tags),
  `notifications`, `operations` (CLI scans, recheck), `setup`, `setup_agent`.

## Rules

- **Take the lease before touching the GPU or the shared JSON stores it guards**; don't add a second
  lock for the same data.
- Never terminate another process to get the lease; wait or report that it's busy.

## Related

[Descriptions](Descriptions.md) · [Blender rendering](Blender%20rendering.md) · [Retrieval](../Search/Retrieval.md).
