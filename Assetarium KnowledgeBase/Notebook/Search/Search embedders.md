---
area: Search
tags: [system]
code: [scripts/asset-worker.py, mcp_server.RemoteBackend, mcp_server.WORKER_SILENCE_SECONDS, mcp_assets.TransientFault, retrieval.indexed_vectors, embedding_backend.py, embedding_cpu.py, search_speed.py]
verified: 2026-11-10
branch: feature/audit-simplify
---
# Search embedders

Hub: [Search](Search.md). The search model (EmbeddingGemma on CUDA, or on the CPU:
[decision 0018](../../Decisions/0018-cpu-search-embedder.md)) runs in a private worker process,
`scripts/asset-worker.py`, started by `mcp_server.RemoteBackend`. This note was decision 0005 until
November 2026; it is a design, so it lives here.

## How it works

- **The worker only returns vectors.** It answers `contract`, `text` and `image` requests. Catalog
  records, file verification, the validated vector matrix (one per index file and contract,
  `retrieval.indexed_vectors`), keyword search and rank fusion run in the calling process.
- The desktop app starts the worker in the background at launch. That loads Python libraries only: no
  model, no GPU lease. The model loads, behind the GPU lease, on the first semantic search. The MCP
  server starts its worker on the first semantic query.
- The worker unloads the model after 10 idle minutes (`IDLE_UNLOAD_SECONDS`), and at once when a
  processing batch or a peer asks for the GPU.
- While busy it sends a heartbeat every 5 s. A worker silent for 90 s (`WORKER_SILENCE_SECONDS`) is
  kept as a fault that needs an explicit retry; a slow first load shows in the status line instead of
  failing.
- Busy-queue and stopped-worker errors are `TransientFault`: they are not kept as per-query faults, so
  the same query works once the GPU is free.
- Keyword search never contacts the worker.

## Rules

- **Do not load the model before a semantic request.** Startup may pre-load libraries only.
- **Do not move ranking or verification into the worker.** It repeated the whole catalog load in a
  second cold process, which is why it was taken out.
- **Keep the worker's stdout protocol-only**: it is private JSON IPC; anything else printed there breaks
  the caller.
- The desktop's presentation lock covers `DesktopService` state only. Settings, library folders, folder
  actions and the `changes()` poll run without it.

## Gotchas

- Why these numbers: a 20 s cold library import plus the old 60 s idle unload made first and occasional
  searches slow, and a single 90 s read timeout could switch semantic search off for the session during
  a slow first load. Heartbeats replaced the timeout.

## Friction and improvements

- **CPU threads and the speed test are not written up here yet** (`search_speed.py`, `embedding_cpu.py`).
  Seen: 2026-11-10

## Related

[Retrieval](Retrieval.md) · [MCP tools](../MCP/MCP%20tools.md). Architecture:
[Embedding contract](../../Architecture/Search/Embedding%20contract.md),
[MCP server](../../Architecture/MCP/MCP%20server.md). Decisions:
[0018](../../Decisions/0018-cpu-search-embedder.md).
