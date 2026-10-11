# Local Asset Library

Step 1 scaffold for a separate, local asset search tool. No inventory, catalog,
rendering, captions, embeddings, GUI, or MCP server has been implemented yet.

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

`local-assets` is the consistent CLI entry point. Both commands are read only;
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
[plan](docs/plan/PROJECT.md). The next stage is
[step 2: catalog and baseline](docs/plan/prompts/02-catalog-and-baseline.md).
