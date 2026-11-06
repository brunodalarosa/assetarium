---
area: Processing
tags: [system]
code: [inspection.discover_blender, blender_worker.py, blender_batch_worker.py, render_pool.plan, render_pool.run, render_pool.RECYCLE_AFTER, render_devices.run, render_devices.STEPS, render_math.py, data/library/rendering.json]
verified: 2026-10-28
branch: feature/library-view
---
# Blender rendering

Hub: [Processing](Processing.md). Inspection loads each model in Blender in the background with
scripts disabled, measures it and renders preview views. Start at `incremental.run_inspection`,
`render_pool.py` and `blender_batch_worker.py`. Decision: [0022](../../Decisions/0022-parallel-rendering.md).

## How it works

- Renders run in several **kept-open Blender processes** at once (`render_pool`), on the CPU or a
  GPU backend (`render_devices.BACKENDS`: OPTIX, CUDA, HIP, METAL, ONEAPI). A host is recycled after
  `RECYCLE_AFTER` jobs to bound slow leaks.
- The **speed test** (`render_devices.run`) renders synthetic shapes at 1, 2, 4, 6 and 8 processes
  per device and keeps the fastest. The owner's limits (device, renders at a time, memory) live in
  `data/library/rendering.json`; they only lower the tested count or change the memory allowance,
  and neither may pass the best tested count or the memory free now, so a setting never makes
  rendering slower (`render_pool.plan`).
- `render_pool.plan` budgets memory: a share of free memory, minus headroom, divided by per-process
  memory (measured by the speed test when available).
- Blender is the saved `[tools].blender` in `config.local.toml`. `inspection.discover_blender` finds
  one for processing when none is saved, but the speed test and render pool use the saved one only.

## Rules

- **Don't edit `blender_worker.py` or `render_math.py`** (see [Stage ledger and fingerprints](Stage%20ledger%20and%20fingerprints.md)).
  The batch host wraps the unchanged worker instead.
- Source assets load with script execution off; the workers never write originals.
- Cancel lets running renders finish and saves them; workers are never killed to cancel an operation.
- **One GPU job at a time** across processes, through the [GPU lease](GPU%20lease.md).

## Gotchas

- A discovered but unsaved Blender looked "unchanged" to setup until October 28, 2026, so the speed
  test stayed blocked on a fresh clone; setup now writes a discovered Blender after its check.
- The desktop's launch `Config` is frozen; `config.with_saved_blender` lets the speed test read a
  Blender saved after launch without a restart.

## Related

[Shared texture dependencies](Shared%20texture%20dependencies.md) · [Setup core](../Setup%20and%20Engines/Setup%20core.md).
