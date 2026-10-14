# Local Asset Library

The library provides read-only inventory, SQLite/FTS5 and semantic search,
technical inspection, multi-view Blender rendering, local visual descriptions,
a Windows app and shared MCP access. Step 8 adds explicitly configured membership,
resumable incremental stages, bounded browsing and atomic catalog/index publication.
See [current operations](docs/library-updates.md) and [progress](docs/progress.md).
Earlier forty-asset pilot measurements and real-agent evidence remain preserved.

The source collection is read only:
`C:\Users\backup pc\Documents\General game assets\playful-lowpoly-asset-packs`.
Generated asset data and runtime caches stay in this repository. Model weights
are shared at `C:\BrunoOS\Local-models`. Play Shapes remains independent.
Local agent clients have additive, backed-up MCP registration.

From this repository in PowerShell:

```powershell
.\scripts\uv.ps1 sync --locked
.\scripts\uv.ps1 run --locked local-assets check-config
.\scripts\uv.ps1 run --locked local-assets doctor
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest --basetemp scratch/pytest-current
```

Python 3.13 is required. The wrapper keeps uv cache, virtual environment, temporary
build files, and Hugging Face/Torch runtime caches inside ignored project folders.
It changes environment variables only in its process. Use it for project commands;
calling a third-party runtime directly can bypass these settings.

Runtime installations share one project-local uv cache and use hard links for
identical immutable dependencies. See [storage guidelines](docs/storage.md) for
accurate disk accounting, cache cleanup and the pilot's storage planning target.

`local-assets` is the consistent CLI entry point. The two checks are read only;
`doctor` checks SQLite FTS5 and NumPy with synthetic in-memory data and checks the
configured Blender executable exists. It does not render or run models.

Copy `config.example.toml` to ignored `config.local.toml` for local overrides:

```powershell
.\scripts\uv.ps1 run --locked local-assets --config config.local.toml check-config
```

Storage names are fixed to ignored `data/`, `cache/`, `logs/`, `scratch/`, and
`.venv/`. `[storage].models` explicitly selects the shared absolute directory
`C:\BrunoOS\Local-models`; `"models"` still supports isolated local fixtures.
Paths inside every storage root must be relative. Parent traversal, overlapping
source/output roots, Windows device/stream paths, and resolved links escaping
a root are rejected.
Future stages must use the boundary API in `config.py`; it is application policy,
not an operating-system sandbox, and does not defend against concurrent link swaps.

SQLite/FTS5 will store records and exact keyword retrieval; NumPy will provide exact
vector similarity. Dependencies are pinned in `pyproject.toml` and `uv.lock`.
No model inference dependencies or weights were installed by step 1.

The shared model folders are `qwen3-vl-2b/89644892e4d85e24eaac8bacfd4f463576704203`
and `embeddinggemma-2/914f7f89142e33e77833254d9c9b90c3cef7303b` directly
under `C:\BrunoOS\Local-models`. Other projects may load these same folders.
This project does not own the shared root or count unrelated models against its
budget. Hugging Face inference caches remain under project `cache/`.
See [model relocation](docs/model-storage.md) for verification and usage.

Continue from [progress](docs/progress.md), [environment evidence](docs/environment.md),
[catalog contract](docs/catalog-contract.md), and the versioned
[plan](docs/plan/PROJECT.md).

Catalog workflow (module invocation also works where console launchers are restricted):

```powershell
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli scan
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli search 'sedan sports'
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli search 'chair rounded'
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli get asset_18db4ca35f9737b123a769899bfc288e
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli pilot
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli verify-source
```

`scan` hashes all source files twice, compares them, verifies extracted ZIP
counterparts, and writes only `data/catalog.sqlite`, `data/reports/` and
`data/evidence/`. It inventories supplied images and parses dependency references;
it does not import models, render or execute embedded scripts. `scan` rebuilds the
step 2 catalog transactionally and refuses to replace later-stage metadata or
owner corrections. That historical scanner is retained; Step 8's coordinator
stages scans and preserves downstream results and owner overlays.

`search` treats input as literal keyword terms joined with AND; it supports camel
case and punctuation-separated names. Default limit is five logical assets,
maximum twenty; output has a 6,000-character cap, including size metadata.
Trimming is explicit. The token estimate is a character heuristic, not an actual
tokenizer count. Results resolve available source paths; complete records are
requested with `get`. Search does not rehash each file, so content staleness needs
`verify-source` or a fresh scan. Missing paths are omitted; stored stale/missing
records are excluded. Search is a filename baseline, not semantic retrieval.

`pilot` resolves the exact identities in versioned
[pilot-selection.json](docs/pilot-selection.json) and writes
`data/pilot/selection-manifest.json` with IDs, formats, dependencies, supplied
views, hashes, rationale and coverage. No source assets are copied. The manifest
has no wall-clock fields and is byte-for-byte reproducible for unchanged inputs.

See the [catalog summary](docs/catalog-summary.md) and
[inspection report](docs/inspection-report.md) for measured results and limitations.

Inspection workflow:

```powershell
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli inspect --phase representatives --resolution 640 --timeout 180
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli review-sheet --phase representatives
# Open the representative sheet with image tools and inspect materials/framing FIRST.
.\scripts\uv.ps1 run --locked python scripts/record_image_review.py representatives --observations 'Your actual image review findings'
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli inspect --phase pilot --resolution 640 --timeout 180
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli review-sheet --phase pilot
# Open the pilot sheet and inspect it FIRST.
.\scripts\uv.ps1 run --locked python scripts/record_image_review.py pilot --observations 'Your actual image review findings'
.\scripts\uv.ps1 run --locked python scripts/check_inspection.py
```

Blender is discovered from the configured executable, PATH, then installed Windows
locations. A discovered executable must support the required imports and offline
flags; failures remain visible. This machine reuses Blender 5.2.2 LTS. Override its
path with `blender` in local configuration. No installer or automatic download runs.
All Blender user resources, temporary files and outputs are directed into project
storage. Embedded scripts are disabled. Jobs run sequentially with a per-asset
timeout, explicit errors, source/dependency checks, and validated cached results.
Unchanged faulty results are retained without automatic retries. Every kind of
fault is marked with evidence, and the batch moves on. Only use `--retry-faults`
after an explicit request to retry; source repair is outside the batch workflow.
Changing worker code, source/dependencies, runtime or resolution requires a new
representative run and image review before the pilot proceeds.

The original selection manifest is retained. `data/inspection/processed-manifest.json`
adds the actual primary source choice and reason for each asset. Each job directory
contains metadata, source hashes, render settings, images and logs. Supplied
thumbnails remain baseline evidence. Review receipts distinguish technical checks
from pending owner artistic approval. CPU Cycles avoids this machine's observed
GPU renderer crash; imported materials are retained. Exact duplicate faces trigger
a recorded shadow-ray override to avoid self-shadow artifacts, without changing
source geometry. Physical size, author front, animation behavior, and alternate
format equivalence remain unknown or unverified.

Local vision uses a separate `.venv-caption/` environment and dependency lock
in `runtime/caption/`. Its wrapper directs caches and temporary files into this
project; weights use shared model storage. Existing Ollama/OpenCode stays independent.
See [caption contract](docs/caption-contract.md) and
[model evidence](docs/caption-model.json).

```powershell
.\scripts\caption-runtime.ps1 sync --locked --project runtime/caption
.\scripts\caption-runtime.ps1 run --locked --project runtime/caption python scripts/prepare_caption_model.py
.\scripts\caption-runtime.ps1 run --locked --project runtime/caption python scripts/caption_pilot.py smoke
.\scripts\caption-runtime.ps1 run --locked --project runtime/caption python scripts/caption_pilot.py calibration --prompt-version v2
.\scripts\caption-runtime.ps1 run --locked --project runtime/caption python scripts/caption_review_images.py calibration-v2
```

Use `prepare_caption_model.py --verify-only` for existing weights. The download
script checks current exact-revision official metadata, license, remaining
model budget and a real CUDA BF16 kernel before transfer. Inference is offline.
The ten calibration outputs must be viewed with image tools alongside their
text, then recorded with `record_caption_review.py` before running the pilot.
Do not create a receipt just because the process exited successfully.

```powershell
# After actual image/text review; supplied notes document this run's review:
.\scripts\uv.ps1 run --locked python scripts/record_caption_review.py calibration-v2 --notes docs/caption-calibration-v2-review.json --approve-prompt v2
.\scripts\caption-runtime.ps1 run --locked --project runtime/caption python scripts/caption_pilot.py pilot --prompt-version v2
.\scripts\uv.ps1 run --locked python scripts/check_captions.py
```

Review [the pilot captions and real input images](data/captions/review/pilot-v2.html).
Each asset links to its editable owner correction JSON. Change desired visual
fields inside `description`, or replace `suggested_uses`; leave other fields
untouched. Bruno's caption and artistic approval remain pending until his review.
Apply corrections and refresh the sheet without loading the model:

```powershell
.\scripts\uv.ps1 run --locked python scripts/caption_pilot.py review --prompt-version v2
```

AI review is separate technical evidence. Invalid responses, uncertain identity,
review faults and original inspector faults remain visible. Step 4 ends before
[step 5: embeddings](docs/plan/prompts/05-embeddings-and-search.md) and full-library
processing.

## Step 5: pilot embedding search

The original `search 'apple'` command remains the full-catalog filename baseline.
Explicit modes now use configured published membership; the following measurements
record the original forty-asset pilot. See
[embedding contract](docs/embedding-contract.md), [measurement evidence](docs/embedding-evidence.json)
and [progress](docs/progress.md) for versions, faults and limitations.

```powershell
# Install the separately locked environment; runtime caches remain project-local.
.\scripts\embedding-runtime.ps1 sync --locked --project runtime/embedding
# One pinned download, CUDA probe and byte-budget check; use --verify-only once downloaded.
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python scripts/prepare_embedding_model.py
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python scripts/embedding_capability.py
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python -m local_asset_library.cli embed-index

# Keyword needs only the base environment; the three semantic modes need the embedding runtime.
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli search 'apple' --mode keyword
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python -m local_asset_library.cli search 'a boxy orange-red car with wheels' --mode description --rankings-output embeddings/car-description.json
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python -m local_asset_library.cli search 'a red apple with a green leaf' --mode image --rankings-output embeddings/apple-image.json
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python -m local_asset_library.cli search 'a chair with a curved back and flat seat' --mode combined --rankings-output embeddings/chair-combined.json
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python -m local_asset_library.cli search --mode reference --reference 'data/inspection/asset_24e2752dbb26ecd19677091f78243709/fbx/a30ceb622a88a274/three_quarter.png' --rankings-output embeddings/reference-apple.json
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python -m local_asset_library.cli search 'a car with wheels' --mode combined --pack kenney_car-kit --format glb --max-triangles 3000 --rigged no
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli detail asset_24e2752dbb26ecd19677091f78243709 --format fbx
```

Each standard shortlist is capped at five logical assets and 6,000 characters.
Semantic candidates are labeled weak/unvalidated; similarity is not probability.
An optional `--min-similarity` supports explicit negative-query evaluation and
retains unthresholded rankings. It is not a confidence threshold. Full rankings
are saved separately; the default path contains only the last successful search.
Queries never fall back after inference failure. Changed contracts require
capability verification and reindexing. Generated indexes, views and reports
remain project-local; weights use shared storage. No export, full indexing, MCP integration or benchmark
approval is part of this step.

## Agent access (step 7)

Local STDIO MCP tools, setup snippets, restoration instructions and real client
evidence are documented in [docs/mcp/README.md](docs/mcp/README.md).
Codex completed the real prop-selection workflow. OpenCode connected and
received the preview, but its local Qwen workflow timed out and remains
unverified. See [progress](docs/progress.md) for faults and evidence boundaries.

## Windows desktop app

Double-click `C:\BrunoOS\Local-Asset-Library\Local Asset Library.vbs` to browse
the approved pilot and search through the same backend as MCP in a normal,
resizable Windows window. No terminal, installer, model download or processing
step is part of startup. Enter submits; Clear restores browsing. Asset detail
includes explicit views/formats, source-path copying and existing fault/evidence
records. Search settings can be copied as exact MCP argument JSON.

See [desktop usage and runtime ownership](docs/gui/README.md) and
[verification summary](docs/gui/verification.json). This is an additional stage
between steps 7 and 8. Step 8's separately approved update/expansion path is now
documented below; owner usability approval remains pending.
## Current library operations

Step 8 extends the existing Windows app and shared MCP backend to explicitly
configured membership, resumable stages, bounded browsing and atomic publication.
See [library updates](docs/library-updates.md) for manual scan/process/refresh/status,
approved budgets, identity rules, worker coordination and current evidence paths.
Earlier forty-asset results above remain historical pilot evidence.

For owner-started generation of pending captions, double-click
`Generate overnight descriptions.cmd`. Existing caption faults are retained;
an explicit fault retry uses the advanced invocation documented below.
The resumable runner uses the existing
local model and renders, retains prior logs, refreshes description-search data
and publishes ready results. See [overnight instructions](docs/overnight-descriptions.md)
for morning reports, interruption recovery, limits and preparation verification.

The approved October 14 texture/material repairs use supplied textures and
library overrides, preserving original files and fault evidence. Asset handoffs
include the bindings required when importing the unchanged FBX. See
[texture repairs](docs/texture-repairs.md) for current processing and receipts.
