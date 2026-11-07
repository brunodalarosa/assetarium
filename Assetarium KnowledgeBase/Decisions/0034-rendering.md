---
tags: [decision]
decided: 2026-11-07
replaces: [0022]
code: [render_pool.py, blender_batch_worker.py, render_devices.py, search_speed.py, incremental.process, scripts/check-render-stability.py]
---
# 0034 — Rendering: kept-open Blender in parallel, speed test, owner limits

> **Approved by the owner on November 7, 2026** (decision review). Consolidates decision 0022 (October 26, 2026),
> which had been recorded for the owner's later review. The render device staying out of the key and
> proven-equivalent worker edits are in [decision 0028](0028-result-identity.md) (exceptions E1, E6).

**Decision.** Inspection renders run in several Blender processes at once, each kept open across assets, on the
CPU or a graphics card. A short speed test picks the device and how many renders at a time; the owner can limit
both, and limits never make rendering slower.

## Kept-open, parallel, per-asset faults

- **Kept-open Blender.** `blender_batch_worker.py` reads one job per input line and runs the unchanged
  `blender_worker.main()` in a fresh empty factory session, so results match a new Blender per asset
  (pixel-identical previews, identical technical metadata; `tests/test_render_pool.py`,
  `scripts/check-render-stability.py`) while Blender's startup is paid once. A process is recycled after 50 jobs.
  Texture-repair workers keep one Blender per job inside the same slots.
- **Faults stay per asset.** A timeout or crash fails only that job, with its log; the slot starts a new Blender for
  the next job, which is not a retry. A result cut off by an interruption is kept as `result.interrupted-*.json`
  and that asset is rendered again on resume (an unfinished render, not an asset fault).
- **Parallel and resumable.** `incremental.process` submits up to N inspections at once; catalog writes, ledger
  checkpoints and progress stay on one thread. Cancel (also what closing the app does) stops handing out assets and
  settles every running render. Every Blender is bound to its run (a kill-on-close job object on Windows, a
  parent-death signal on Linux, and its input closing), so a killed run never leaves a Blender writing for the
  resumed one.
- **Edge-on flat models.** A card with no thickness across a camera (grass, cloud sprites) renders empty from that
  side. When a front, side or three-quarter view renders empty and the model is under 1% of its size across that
  camera, the worker renders that view once more turned 35° toward the face, keeps the view's label and records the
  turn (`view_adjustment`). A second empty render fails the asset.

## Device

The job's `render_device` (absent = CPU) selects a Cycles GPU by backend and id (OptiX, CUDA, HIP, Metal, oneAPI);
the CPU path keeps its settings exactly. A chosen GPU that is missing or fails to start stops the run with that
reason (`DeviceUnavailable`): assets stay pending and nothing falls back silently to the CPU. GPU renders take the
shared GPU lease and wait like the other GPU stages.

## Speed test

`render_devices.run` renders four synthetic OBJ shapes (written outside the project, never library assets) with the
real worker at 640 px, on the CPU and every GPU Blender lists, at 1, 2, 4, 6 and 8 processes, each warmed with one
untimed render. A device's test stops when a step is not 10% faster, runs 1.5× slower than expected, would pass
half the logical cores, or would not fit the memory allowance at its measured peak × 1.25; a device 3× slower than
one already tested is cut off on its first step. The fastest (device, processes) pair is saved in
`data/library/render-test.json` with every measurement. It runs at the start of Make previews when no test exists
for the current Blender or the device list changed, and on request (Settings → General → Speed test → **Test
again**, `local-assets rendering test`), cancellable and waiting for processing.

**Search threads.** When search runs on the CPU, the same test times the CPU embedder on six synthetic images at
several thread counts and keeps the fewest threads within 3% of the fastest (`search_speed.py`,
`data/library/search-test.json`). The owner's `search_threads` overrides it. Thread counts never change vectors.

## Owner limits

`data/library/rendering.json`: device (Automatic = fastest tested, the CPU or a listed GPU), renders at a time
(Automatic or 1–8) and memory for rendering (Automatic = 70% of the memory free when processing starts, or whole
GiB). The count used is the lowest of the tested best for the device, the owner's limit and what fits the
allowance; the allowance never passes the memory free now minus 1 GiB. Untested counts are never used. Before any
test the CPU uses one process per 8 cores (at most 4). While running, a job waits whenever free memory drops below
1 GiB; one always runs.

## Why

One Blender at a time spent about 30% of each asset starting Blender and left most of a many-core CPU and the GPU
idle. Measured on the owner's machine, real assets went from 4.5 s to 1.8 s each with kept-open GPU renders two at
a time, and to 2.6 s on the CPU four at a time. Six GPU processes thrashed a machine with 14 GB free, which is why
the test and every run are bounded by measured memory.

## Keep true

- Identical CPU results and keys for finished inspections ([decision 0028](0028-result-identity.md)).
- Per-asset faults, settled renders on cancel, no orphaned Blender after a killed run.
- No silent device fallback.
- Owner limits only lower the tested count or change the memory allowance.
- Do not edit `blender_worker.py`, `render_math.py` or the repair workers except through a proven-equivalent edit.
