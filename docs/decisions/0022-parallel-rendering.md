# 0022 — Parallel kept-open renders, render device and speed test

**Decision (user of this checkout, October 26, 2026; for the owner's review before any merge
upstream).** Inspection renders run in several Blender processes at once,
each kept open across assets, on the CPU or a graphics card. A short speed test on the computer picks
the device and how many renders at a time; the owner can limit both, and limits never make rendering
slower.

- **Kept-open Blender.** `blender_batch_worker.py` reads one job file per input line and runs the
  unchanged `blender_worker.main()` in a fresh empty factory session (`read_factory_settings`), so a
  job's results match a new Blender process per asset (pixel-identical previews and identical technical
  metadata, proven by `tests/test_render_pool.py` and `scripts/check-render-stability.py`) while
  Blender's startup is paid once. The host is not part of inspection fingerprints: it only resets and
  calls the worker. A process is recycled after 50 jobs. Texture-repair workers patch the worker module
  at import, so they keep one Blender per job inside the same slots.
- **Faults stay per asset.** A timeout or crash fails only that job, with its log; the slot starts a
  new Blender for the next job, which is not a retry. A result cut off mid-write by an interruption is
  kept as `result.interrupted-*.json` and that asset is rendered again on resume (an unfinished render,
  not an asset fault).
- **Parallel and resumable.** `incremental.process` submits up to N inspections at once; catalog reads
  and writes, ledger checkpoints and progress stay on one thread. Cancel (also what closing the app
  does) stops handing out assets and settles every running render. Every Blender is bound to its
  processing run (a kill-on-close job object on Windows, a parent-death signal on Linux, and its input
  closing), so a killed run never leaves a Blender writing for the resumed one; the run shows as
  interrupted and Process assets resumes, reusing every finished asset.
- **Render device.** The job's `render_device` (absent = CPU) selects a Cycles GPU by backend and id
  (OptiX, CUDA, HIP, Metal, oneAPI). The CPU path keeps the previous settings exactly. The device is
  recorded in `render_settings` (provenance) but is not part of the fingerprint, so switching device
  re-queues nothing. A chosen GPU that is missing or fails to start stops the run with that reason
  (`DeviceUnavailable`, an `EngineStop`): assets stay pending and nothing falls back silently to the CPU.
  GPU renders take the shared GPU lease and wait like the other GPU stages.
- **Proven-equivalent worker edits.** `incremental.EQUIVALENT_WORKERS` maps a `blender_worker.py` hash
  to the hash finished inspections recorded, for edits whose CPU renders are proven identical by
  `scripts/check-render-stability.py`. The render-device edit is the first entry; all 4,708 finished 3D
  inspections kept their fingerprints. Any other edit still re-queues inspections.
- **Speed test.** `render_devices.run` renders four synthetic OBJ shapes (written outside the project,
  never library assets) with the real worker at 640 px, on the CPU and every GPU Blender lists (one entry
  per card, OptiX before CUDA), at 1, 2, 4, 6 and 8 processes. Each step warms every process with one
  untimed render. A device's test stops when a step is not 10% faster, runs 1.5× slower than expected,
  would pass half the logical cores, or would not fit the memory allowance at its measured peak × 1.25.
  A device 3× slower than one already tested is cut off on its first step. The fastest (device,
  processes) pair is saved in `data/library/render-test.json` with every measurement. It runs at the
  start of a Process assets when no test exists for the current Blender or the device list changed,
  and on request (Settings → General → Speed test → **Test again**, `local-assets rendering test`) as a
  cancellable operation that waits for processing.
- **Owner limits** (`data/library/rendering.json`): device (Automatic = fastest tested, CPU or a listed
  GPU), renders at a time (Automatic or 1–8) and memory for rendering (Automatic = 70% of the memory free
  when processing starts, or whole GiB, for example more overnight). The count used is the lowest of the
  tested best for the device, the owner's limit and what fits the allowance; the allowance never passes
  the memory free now minus 1 GiB. Untested counts are never used: after raising the allowance, Test
  again measures higher counts. Before any test the CPU uses one process per 8 cores (at most 4). While
  running, a job waits for a running render whenever free memory drops below 1 GiB; one always runs.

Why: one Blender at a time spent about 1.35 s of each 4.5 s asset starting Blender and left most of a
many-core CPU and the GPU idle. On the owner's machine (Ryzen 9 9950X3D, Radeon RX 6800, 31 GB) real
assets went from 4.5 s to 1.8 s each with kept-open GPU renders 2 at a time (1.4 s with 4, when memory
allows) and to 2.6 s on the CPU 4 at a time; with the CPU limited to 4 threads the GPU was 2.7× faster
than the CPU. Six GPU processes thrashed a machine with 14 GB free, which is why the test and every run
are bounded by measured memory.

Future work must keep: identical CPU results and fingerprints for finished inspections, per-asset
faults, settled renders on cancel, no orphaned Blender after a killed run, no silent device fallback,
and limits that only lower the tested count or change the memory allowance.
