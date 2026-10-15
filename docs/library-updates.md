# Library updates and processing

Current workflow: **Settings → Asset sources** controls directories and live
enabled-source membership. The app scans enabled sources on opening, and **Scan**
checks changes during a session. One warning card per source offers **Process
assets**, a processing/publication progress bar, and graceful **Cancel**. Cards
clear after a scan verifies that no actionable work remains and current results
are published. Retained failures appear in **Importing failures report**, a
scrollable list of original model paths, instead of keeping pending cards open.
Generated source information now lives in each directory's `metadata-lal`.
See [asset sources](asset-sources.md) for storage, cancellation and fault rules.

For current command-line operation, `library-batch.py scan` checks enabled sources,
`library-batch.py status` reports their state, and
`library-batch.py process --source KEY` starts processing and automatic publication
for that source. These operations reuse existing offline runtimes. Source settings
replace the historical pack allowlist; the existing storage budget still applies.

## Earlier Step 8 and import workflow (historical)

The prepared Windows app and MCP server share explicitly configured membership,
source/dependency checks, measured filters, ranking and response caps. The approved
contract is `docs/library-membership.json`: thirteen packs, initially 883 logical
assets, maximum 1,901 after the separately approved City Kit and October 14
Synty/CraftPix additions. Changing this file is not owner expansion authorization.
Source packs and shared model revisions remain read only. Step 9 is optional;
no classification or clustering is performed.

The original Step 8 publication contained 883 inspected assets, 514 valid generated
captions and 369 retained caption generation/schema failures. Image retrieval and
usable previews remain available for partial results; new captions still await
review. Actual coverage, resource measurements and verification are recorded in
`docs/step8-verification.json` and `docs/progress.md`.
The City Kit addition publishes 964 assets, with its 81 new descriptions pending;
see `docs/city-kits-import.md` for that import's preservation evidence.
The October 14 Synty/CraftPix addition publishes 1,901 records: 937 new models,
882 indexed preview images from 289 models, and 648 retained texture failures.
See `docs/new-packs-import.md` for the separate fault, preview and preservation
reports. The completed overnight run subsequently published 282 descriptions
(265 CraftPix, 15 Generic, 2 Synty) and their search vectors. The other 655 new
captions retain 648 source/preview blockers and 7 validation failures; no selected
work remains unattempted. Repairs/retries and owner accuracy review are separate
follow-up work, with all original evidence retained.

Double-click `Local Asset Library.vbs`. Opening the app reads the published
catalog/index and existing previews; it never installs, downloads, scans,
processes or loads an inference model. Browse pages contain at most 40 cards.
Thumbnails load near the viewport, with at most three requests in progress.
Selection uses stable asset IDs across pages; filters and keyboard controls remain
available. Processing coverage is separate from the currently published version.

## Manual operations

Run from this repository, using the existing base interpreter:

```powershell
.\.venv\Scripts\python.exe scripts/library-batch.py scan --dry-run
.\.venv\Scripts\python.exe scripts/library-batch.py scan
.\.venv\Scripts\python.exe scripts/library-batch.py process --dry-run
.\.venv\Scripts\python.exe scripts/library-batch.py process --batch-size 50
.\.venv\Scripts\python.exe scripts/library-batch.py refresh --dry-run
.\.venv\Scripts\python.exe scripts/library-batch.py refresh
.\.venv\Scripts\python.exe scripts/library-batch.py status
.\.venv\Scripts\python.exe scripts/library-status.py
```

For the approved City Kit import, leave description generation for a later run:

```powershell
.\.venv\Scripts\python.exe scripts/library-batch.py process --skip-captions --batch-size 25 --peak-reserve-mib 500
```

This runs inspection/renders and available image embeddings, then publishes the
catalog/index. It never starts the caption runtime. Ungenerated descriptions are
`pending`, and their text vectors are deferred without failed jobs or an endless
processing loop. Image embeddings remain usable as partial results. The peak
reserve is checked before processing and enforced after each batch/publication;
it cannot exceed the existing approved budget. Normal processing keeps its
default 2 GiB reserve and includes caption generation. Later explicit caption
processing makes these text inputs eligible automatically; unchanged actual
failures still require owner-authorized retries.

The app exposes Check changes, Scan, Process pending, Publish ready work, Status
and Refresh published view. A started background operation returns immediately;
coverage updates as batches checkpoint. Operation logs/results/faults are under
`data/library/operations/`; detailed stage receipts are under
`data/library/batches/`. Use the coordinator for writes; its operation lease
prevents overlapping GUI/CLI writers. The lower-level CLI stage commands are
internal bounded workers used by that coordinator.

Scan stages an inventory and merges downstream results instead of replacing
them. It compares two complete read-only inventories before changing working
data. Dry runs summarize work without inference. Process uses prepared runtime
wrappers with `--locked --no-sync --offline`; no dependencies or weights are
installed. It preserves successful pilot results and existing caption faults.

Process checkpoints each inspection/caption and each vector. Repeat the explicit
operation after interruption to resume running/pending jobs. Completed matching
jobs and unchanged failed/unsupported jobs are retained. New content/contracts
create new stage inputs; changing severity, approval, GUI settings or storage
budgets does not regenerate assets. Caption generation uses one attempt; an
invalid response is recorded as failed without an automatic corrective retry.

An unchanged actual asset fault requires explicit owner authorization for repair
or retry. This coordinator deliberately has no blanket retry-faults switch.
Application/test-harness defects may be fixed normally. Originals and previous
reports are never edited to make a fault disappear.

## Identity, overlays and stage inputs

IDs bind source collection, pack and relative logical identity. Renames are
deletion plus addition; identical bytes or names do not prove identical geometry.
Deleted IDs disappear from active membership/index. Historical jobs, original
results and owner correction files remain retained. No owner approval or overlay
is transferred to a newly renamed ID automatically.

Record a new AI caption review on working membership with the existing writer:

```powershell
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/record_caption_review.py library --notes data/review-input.json
```

Review inputs contain a `scope` and an `assets` object keyed by configured IDs;
each asset uses `findings` with `severity`, `evidence` and `reason` as described in
`docs/caption-quality.md`. The writer verifies canonical results and image hashes,
saves original provenance before changing working metadata, preserves owner states
and never reruns a model. Publish explicitly afterward. Published catalogs are
immutable; old stage writers cannot replace them in place.

Owner correction files remain under `data/captions/corrections/<asset-id>.json`.
Their bytes and owner states survive scan/process. Generated observations,
suggestions and measured facts stay separate. An effective description change
invalidates its text vector; owner approval, notes/warnings and suggested uses
alone do not. Corrupt overlays stay visible and cannot manufacture a successful
caption from failed generation.

Inspection inputs bind selected source/dependencies, actual bytes, resolution,
renderer code and installed Blender identity. Caption inputs bind rendered
pixels/views, model revision, inference backend, runtime lock and prompt. Text
vectors bind effective visual-description content; image vectors bind verified
view inputs. The shared model/runtime/vector contract remains enforced.

## Publication and inference ownership

Processing uses a working catalog/index while search serves an immutable previous
generation. Publish verifies membership, SQLite integrity, vector checksums and
current source/description/view inputs, copies a matching pair into a new
generation, then atomically switches one manifest. Requests pin that generation;
old snapshots remain intact. A no-change publication keeps its version. The app
polls lightweight publication/coverage state, clears obsolete presentation faults
and rejects thumbnail/detail requests for an older version. Live owner overlays
are checked against vectors; changed content requires explicit processing before
publishing again.

Cross-process inference leases serialize batch models and cooperating search
workers. A search worker keeps its model warm for up to sixty idle seconds and
unloads promptly when a batch or another worker requests its lease. Batch inference waits up to 15 seconds; searches wait up to
five seconds, then return a clear busy state. Browse/keyword/detail remain usable.
No unrelated process is stopped. Workers started before this update must be
restarted to participate in the new membership/publication/lease behavior.

## Storage and evidence

The October 14 approved full-library ceiling is 10 GiB unique allocated project storage,
with up to 3 GiB additional peak allocation for the import and overnight run combined.
The import reserves 2 GiB and the overnight run reserves 1 GiB. External read-only originals/shared
weights are excluded. The older 20 GiB allowance is not authorization. Fresh
base-Python receipts precede bulk work, follow each batch and follow final
publication. Processing stops if measured growth exceeds its budget, preserving
all results/evidence. No runtime, model, original asset copy or blanket cleanup
is introduced.

Coverage separates pack membership; inventory/inspection/previews/caption/vector
states; retained partial results; source/stage faults; caption notes/warnings;
and pending AI/owner reviews. Unreviewed new captions have no accuracy approval.
Successful import/inference/retrieval and automated/native GUI checks are
technical evidence, separate from owner relevance, usability, accessibility and
artistic acceptance. Current results and limitations are recorded in
`docs/step8-verification.json` and `docs/progress.md` when delivery completes.

The separately approved October 14 texture repair run has a 2 GiB growth limit
and the same 10 GiB total ceiling. It uses hash-bound library overrides and
publisher material lists; originals and unrelated faults remain unchanged.
See [texture repairs](texture-repairs.md) for scoped operations and evidence.
