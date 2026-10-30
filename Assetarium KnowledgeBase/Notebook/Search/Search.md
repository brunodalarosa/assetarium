---
area: Search
tags: [hub]
code: [retrieval.SearchEngine, search_policy.py, library_cache.py, hash_cache.py, embedding_backend.py, embedding_cpu.py, search_speed.py]
---
# Search

Assetarium's search capabilities, shared by the desktop app, the owner CLI and the MCP server:
keyword, description, text-to-image, reference image and combined ranking over the published
library. How agents reach it is the [MCP](../MCP/MCP.md) area. Up: [Notebook](../Notebook.md).

## Systems

- [Retrieval](Retrieval.md): `SearchEngine`, channels and fusion, filters, bounded shortlists.
- [Hash reuse and caches](Hash%20reuse%20and%20caches.md): why reads are fast without dropping verification.
- [Search embedders](Search%20embedders.md) *(gap)*: EmbeddingGemma on CUDA or the CPU, the private
  worker, threads and the speed test (`embedding_backend.py`, `embedding_cpu.py`, `search_speed.py`).

## Read first

- [Embedding contract](../../Architecture/Search/Embedding%20contract.md) and the frozen pilot
  evaluation in [`docs/evaluation/`](../../../docs/evaluation/README.md).
- Decisions: [0003](../../Decisions/0003-per-publication-read-caches.md),
  [0004](../../Decisions/0004-stat-identity-hash-reuse.md),
  [0005](../../Decisions/0005-embedding-worker-and-prestart.md),
  [0018](../../Decisions/0018-cpu-search-embedder.md).
