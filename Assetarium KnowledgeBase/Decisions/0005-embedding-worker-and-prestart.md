---
tags: [decision]
decided: 2026-10-17
---
# 0005 — Embedding worker returns vectors; the app pre-starts it

**Decision.**
- `scripts/asset-worker.py` only answers `contract`, `text` and `image`
  requests with a vector. Catalog records, file verification, the validated
  vector matrix (one per index file and contract, `retrieval.indexed_vectors`),
  keyword search and rank fusion run in the calling process
  (`mcp_server.RemoteBackend`).
- The desktop app starts the worker in the background at launch. That loads
  Python libraries only: no model, no GPU lease. The model loads, behind the GPU
  lease, on the first semantic search. "Never start models at startup" still
  holds. The MCP server starts its worker on the first semantic query.
- The worker unloads the model after **10 idle minutes** (was 60 s), and still
  immediately when a processing batch or peer requests the GPU.
- The worker sends heartbeats every 5 s while busy. A worker silent for 90 s is
  retained as a fault (explicit retry required, as before); a slow first load
  is shown in the status line instead of failing.
- Busy-queue and stopped-worker errors (`TransientFault`) are not retained as
  per-query faults, so an identical query works once the GPU is free.
- The presentation lock covers `DesktopService` state only. Settings, sources,
  source actions and the `changes()` poll run without it.
- Keyword search never contacts the worker.

**Why.** The worker repeated the whole catalog load and verification in a second
cold process, and its 20 s cold library import plus 60 s idle unload made first
and occasional searches slow. A single 90 s read timeout could disable semantic
search for the session during a slow first load.

**Keep true.** Do not move ranking or verification back into the worker. Do not
load the model before a semantic request. Keep the worker's stdout protocol-only.
