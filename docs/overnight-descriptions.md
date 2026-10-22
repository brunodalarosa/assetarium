# Overnight asset descriptions

For one source, the app's **Asset processing → Generate descriptions**
does the same work in the background with progress, Cancel and a report
notification ([decision 0008](decisions/0008-optional-descriptions-and-notifications.md)).
This runner remains for unattended runs across the whole library.

In File Explorer, double-click **Generate overnight descriptions.cmd** in
`C:\BrunoOS\Local-Asset-Library` before going to bed. Keep its window open and
leave the computer powered on. The runner temporarily requests that Windows
remain awake while processing; the screen may turn off normally. That request is
released when the runner exits. No permanent power setting is changed.

The launcher now selects **pending descriptions only** across current working
catalog membership, including newly imported packs. Existing usable captions,
review notes/warnings, and actual caption faults are retained. The October 14
background run is limited to `synty-part1`, `craftpix-free-packs`, and
`POLYGON_Generic_SourceFiles_v3`. Its exact selection and progress are saved in
the latest run folder. No unchanged fault retry is requested by this import.

It uses the installed local Qwen caption model, actual existing multi-view renders,
the active v3 prompt, and **10–170-word validation**. It does not scan/import new
assets, render images, download/install anything, or use a cloud model. The caption
and embedding runtimes use their existing locked offline wrappers.

Each selected asset receives at most **one generation attempt per run**. The new
response and any rejection reason are saved under that run before updating
working catalog data. Earlier logs and original asset files remain intact.
Owner correction files and their approval states are preserved. New AI captions
still need accuracy review; passing validation does not prove visual correctness.

The runner then updates description-search vectors and publishes the matching
catalog/index. Existing image vectors and usable captions are protected by a
before/after comparison. Original published snapshots remain available throughout
processing. Failed assets retain explicit faults and usable partial results.

## Next morning

Ask this chat: **Review the latest overnight description run.**

The run pointer is `data/overnight-descriptions/latest.json`. It identifies a run
folder containing:

- `summary.md` — counts, overall status, publication result and failure reasons.
- `summary.json` — complete structured report and run error, if any.
- `attempts/` — new raw responses, metrics, inputs and rejection reasons.
- `outcomes/` — durable per-asset completion/failure checkpoints.
- `original-records/` — previous selected records, including prior fault evidence.
- `worker-*.log` — runtime diagnostics, including model startup failures.
- `worker-fault-*.json` — explicit worker timeout/interruption evidence.
- `index-*.json` — per-batch description-vector results and errors.
- `preservation.json` and storage receipts — protected-data and disk checks.

Published results become available after the run successfully publishes. If
indexing/publication is blocked, completed caption work and logs remain saved for
review; the previous published library remains active. Individual caption failures
do not prevent other successful captions from being published.

## Interruption and failures

Double-click the same launcher again to resume an unfinished run. Completed,
failed and skipped assets in that run are not generated again. A saved response
can be committed after interruption without another generation. An attempt
interrupted before its response was saved becomes an explicit fault instead of
being silently repeated. Descriptions are generated in batches (*Settings →
General → Description batch size*, default 8); `inflight.json` lists the whole
batch, so an interrupted batch records each of its assets as interrupted. If a
batch runs out of GPU memory, the run stops with a message naming the batch size,
nothing is recorded as failed and those assets stay pending; lower the size and
resume.

Once a run has finished, manually launching the script again starts a **new** run
for remaining pending captions. An actual fault retry requires an explicit
owner request and direct invocation without `--pending-only`. Earlier evidence
remains intact. Advanced optional arguments:

```powershell
.\.venv\Scripts\python.exe scripts/overnight-descriptions.py --dry-run
.\.venv\Scripts\python.exe scripts/overnight-descriptions.py --resume RUN_ID
.\.venv\Scripts\python.exe scripts/overnight-descriptions.py --new-run
.\.venv\Scripts\python.exe scripts/overnight-descriptions.py --new-run --pending-only --pack synty-part1 --pack craftpix-free-packs --pack POLYGON_Generic_SourceFiles_v3 --peak-reserve-mib 1024
```

The 180-second progress watchdog stops only the wrapper and descendants created
by this runner. A stalled caption batch is recorded as faulty and processing
continues with the next batch in a fresh worker. One batch is bounded by the
120-second generation limit, inside the watchdog window. A model startup or indexing
failure stops the run with a clear report and leaves remaining work resumable.
No unchanged asset fault is automatically retried within a run. If the launcher
window was closed while a worker remained alive, restarting is blocked until
that worker's current batch finishes; the runner does not kill an unrelated
process. Keep the launcher window open to avoid that situation.

Other catalog writers are excluded while the run owns the operation lease.
Cooperating semantic-search workers yield their GPU lease. Browsing/keyword search
remain available; simultaneous model-based searches may report busy.

## Time, storage and verification

An approved repair run can select only recovered models with `--asset-ids-file`,
pointing to a JSON array of configured asset IDs. This fresh-run allowlist is saved
in the plan and excludes unrelated caption faults. Resume uses the saved selection.
See `docs/texture-repairs.md` for the October 14 texture-repair evidence.

The estimate for 937 newly imported models is **3–6 hours**, based on approximately ten seconds
per historical caption attempt plus indexing/checkpoints. The dry run scales its
estimate to the actual selected count. Current v3 response
lengths, GPU contention and faults can change the actual duration.

No new environment or model copy is introduced. Estimated additional storage is
**200–500 MiB**, with an enforced **1 GiB growth allowance** for the October 14 run and the
approved **10 GiB total project ceiling**. The import and overnight run together
have a 3 GiB growth allowance. Fresh unique-allocation receipts precede
bulk work, follow batches, and surround publication. A projected publication
snapshot is checked before copying it. Exceeding a budget preserves all results
and blocks further processing; no automatic cleanup runs.

The original preparation used synthetic model backends and small generated fixtures.
Ninety-three focused tests were verified, including the full coordinator-to-
publication path and separate caption/index/worker fault reports. Real prepared-
wrapper probes and owned-tree watchdog checks passed. The
actual launcher dry run selected 450, skipped 514, and found no input faults.
The previous real overnight run completed 423 descriptions with 27 caption faults;
its original report remains under `data/overnight-descriptions/c4d82c36a616479088fb614f0372f6ea/`.
Failed and corrected test receipts remain retained under
`data/overnight-descriptions/`.
