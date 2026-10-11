# Local Asset Library

Steps 2–4 provide a read-only inventory, SQLite/FTS5 search, a reproducible
40-asset pilot, technical inspection, multi-view Blender renders and local
vision descriptions. Embeddings and MCP integration belong to later steps.

The source collection is read only:
`C:\Users\backup pc\Documents\General game assets\playful-lowpoly-asset-packs`.
Generated files stay in this repository. Play Shapes and existing local agent
installations are independent and unchanged.

From this repository in PowerShell:

```powershell
.\scripts\uv.ps1 sync --locked
.\scripts\uv.ps1 run --locked local-assets check-config
.\scripts\uv.ps1 run --locked local-assets doctor
.\scripts\uv.ps1 run --locked pytest --basetemp scratch/pytest
```

Python 3.13 is required. The wrapper keeps uv cache, virtual environment, temporary
build files, and future Hugging Face/Torch caches inside ignored project folders.
It changes environment variables only in its process. Use it for project commands;
calling a third-party runtime directly can bypass these settings.

`local-assets` is the consistent CLI entry point. The two checks are read only;
`doctor` checks SQLite FTS5 and NumPy with synthetic in-memory data and checks the
configured Blender executable exists. It does not render or run models.

Copy `config.example.toml` to ignored `config.local.toml` for local overrides:

```powershell
.\scripts\uv.ps1 run --locked local-assets --config config.local.toml check-config
```

Storage names are fixed to ignored `data/`, `models/`, `cache/`, `logs/`, `scratch/`,
and `.venv/`. Absolute paths, parent traversal, overlapping source/output roots,
Windows device/stream paths, and resolved links escaping a root are rejected.
Future stages must use the boundary API in `config.py`; it is application policy,
not an operating-system sandbox, and does not defend against concurrent link swaps.

SQLite/FTS5 will store records and exact keyword retrieval; NumPy will provide exact
vector similarity. Dependencies are pinned in `pyproject.toml` and `uv.lock`.
No model inference dependencies or weights are installed by step 1.

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
owner corrections. Refresh/migration support is reserved for step 8.

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
in `runtime/caption/`. Its wrapper directs all caches, weights and temporary
files into this project; existing Ollama/OpenCode stays independent.
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
