# Local Asset Library

Step 2 provides a read-only source inventory, a SQLite catalog, FTS5 filename
search, and a reproducible 40-asset pilot. Rendering, captions, embeddings, GUI,
and MCP integration belong to later steps.

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

See the [measured catalog summary](docs/catalog-summary.md) for grouping policy
and unresolved cases. The next stage is
[step 3: inspect models and render views](docs/plan/prompts/03-inspect-and-render.md).
Use this existing pilot and retain the source/dependency hashes; approve the new
implementation plan, including duration and disk estimates, before proceeding.
