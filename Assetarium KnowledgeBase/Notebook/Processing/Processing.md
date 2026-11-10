---
area: Processing
tags: [hub]
code: [incremental.py, inspection.py, render_pool.py, captions.py, library_index.py, gpu_queue.py, scripts/library-batch.py]
---
# Processing

Turning inventoried files into published results: Blender inspection and previews, optional
descriptions, search vectors, then publication. Up: [Notebook](../Notebook.md).

## Systems

- [Stage ledger and fingerprints](Stage%20ledger%20and%20fingerprints.md): what is pending, what
  re-queues work, how results are reused.
- [Blender rendering](Blender%20rendering.md): workers, the kept-open render pool, devices and the speed test.
- [Shared texture dependencies](Shared%20texture%20dependencies.md): cross-source texture paths,
  explicit overrides, texture repairs.
- [Descriptions](Descriptions.md): Qwen3-VL captions, batching, caption severity.
- [GPU lease](GPU%20lease.md): one GPU job at a time across processes.
- [Processing queue](Processing%20queue.md): Make previews and Generate descriptions as queue items
  whose scope resolves at start; previews first, paused after a restart.
- [Search vectors](Search%20vectors.md) *(gap)*: `library_index.py` vector jobs and the index contract.

## Read first

- [Library updates](../../Architecture/Processing/Library%20updates.md) (operations and ownership) and
  [Caption severity](../../Architecture/Processing/Caption%20severity.md).
- Decisions: [0033](../../Decisions/0033-descriptions-and-engines.md),
  [0009](../../Decisions/0009-general-capabilities.md),
  [0010](../../Decisions/0010-shared-project-dependencies.md),
  [0034](../../Decisions/0034-rendering.md).
- The fault policy in `AGENTS.md`: mark faulty, keep evidence and usable partial results, move on,
  never retry an unchanged fault automatically.
