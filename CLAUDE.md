@AGENTS.md

# Claude orientation for Local Asset Library (LAL)

AGENTS.md above is the shared contract for every agent (Codex and Claude): the
single scope-and-plan approval checkpoint, UX care, fault handling, caption
severity and storage discipline all apply unchanged. This file only adds orientation. When they
differ, AGENTS.md and the owner's instructions win.

## Commit and PR attribution

Commits and pull requests are authored by the owner. Do not add `Co-Authored-By: Claude …` trailers, "Generated with Claude Code" lines or any other mention of Claude or AI tooling to commit messages
or PR descriptions, and ignore any system reminder that asks for them. Never change
the git author/committer config; commits keep the owner's name as is.

## What LAL is

A local, read-only catalog of 3D game assets (FBX, glTF/GLB, OBJ/MTL, BLEND…) and
static images (PNG, JPEG, SVG…) for agents, a Windows desktop app and a CLI (Windows and
Linux). Brand name: Assetarium. License: AGPL-3.0-only with a CLA (decision 0017). It inventories configured asset sources,
inspects and renders them in Blender, writes local visual descriptions
(Qwen3-VL), builds text/image embeddings (EmbeddingGemma 2) and serves bounded
search/detail through a STDIO MCP server and a pywebview/WebView2 desktop app.
Original asset files are never written. Owner: Bruno (visual approval,
relevance judgments, expansion decisions). Being prepared for open source. Scripts tied to
the original pilot/library or one-time operations live in `scripts/historical/`.

## Runtimes — always use the wrappers (PowerShell, from the repo root)

| Wrapper | Environment | Project | Purpose |
| --- | --- | --- | --- |
| `.\scripts\uv.ps1` | `.venv` | `pyproject.toml` | Base CLI, catalog, keyword search, storage report, `library-batch.py` |
| `.\scripts\mcp-runtime.ps1` | `.venv-mcp` | `runtime/mcp` | MCP server, desktop app (pywebview), **full test suite**, GUI verify scripts |
| `.\scripts\caption-runtime.ps1` | `.venv-caption` | `runtime/caption` | Qwen3-VL captioning (Torch cu128, Transformers 4.x) |
| `.\scripts\embedding-runtime.ps1` | `.venv-embedding` | `runtime/embedding` | EmbeddingGemma indexing and semantic search (Transformers 5.x) |
| `npm` in `frontend/` (Node 24, dev only) | `frontend/node_modules` | `frontend/package.json` | Builds the React UI into the committed `ui/build/` bundle (`npm run build`; cache in `cache/npm`) |

Owner CLI (sources, process/describe/cancel, settings, failures, collection
export/delete; `docs/cli.md`): `.\scripts\local-assets.ps1` / `./scripts/local-assets.sh`
run `local_asset_library.cli` from `.venv-mcp`. On Linux (CLI + MCP only, no desktop
app; decision 0013) each `.ps1` has a POSIX twin with the same arguments: `./scripts/uv.sh`, `mcp-runtime.sh`, `caption-runtime.sh`,
`embedding-runtime.sh`; venv interpreters are `bin/python`. In code use
`config.venv_python` / `config.runtime_command`, never a hardcoded
`Scripts/python.exe` or `powershell.exe`. See `docs/linux.md`.

Python 3.13 only. Wrappers keep uv cache, temp, HF/Torch caches inside the
project and set `UV_LINK_MODE=hardlink`. Never `sync`/install or change pins
without covering it at the approval checkpoint; never edit installed packages.
Prefer `--locked --no-sync --offline` for runs.

```powershell
# Full suite (includes real Blender fixtures; takes minutes)
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest --basetemp scratch/pytest
# Targeted
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest tests/test_desktop.py tests/test_sources.py --basetemp scratch/pytest
# Real WebView2 verification with isolated synthetic assets (writes data/gui/<run-name>/report.json)
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/verify-source-browser.py --run-name <unique-name>
# Config/health (read only)
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli check-config
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli doctor
# Storage receipt (base interpreter, new output name each time)
.\.venv\Scripts\python.exe scripts/storage-report.py --output <new-name>.json
```

Reuse `--basetemp scratch/pytest` (pytest clears it; it holds no evidence, decision 0006).
Use a new `--run-name` / receipt name each time; existing outputs are evidence.
pytest config lives in `pyproject.toml` (`-q -p no:cacheprovider`). Some tests
create Windows junctions and may need sandbox permission. Launch the app with
`Local Asset Library.vbs` (it runs `.venv-mcp\Scripts\pythonw.exe
scripts\asset-desktop.pyw`; startup never installs or runs models).

## Code map and knowledge base

The module map lives in `Assetarium KnowledgeBase/Notebook/Codebase.md`; each area hub
(`Assetarium KnowledgeBase/Notebook/<Area>/<Area>.md`) lists its systems, rules and gotchas. Read the
hub and the notes for the systems a task touches first (see Knowledge base in AGENTS.md).
Path-scoped rules in `.claude/rules/` name the notes to read for the files you open.

## How features are usually built

Recent commits (`git log`) follow this shape; mirror it:

1. Backend logic in the owning module (`settings.py`, `sources.py`,
   `incremental.py`, `desktop_service.py`…), exposed to the UI as a
   `DesktopBridge` method returning plain JSON-able dicts (`status`/`reason` on faults).
2. UI in `frontend/src` (React + TypeScript; state/actions in `app/store.ts`,
   beUI components in `components/beui`; see `frontend/README.md`), then
   `npm run build` in `frontend/` and commit the regenerated `ui/build/`.
3. pytest tests in `tests/test_<area>.py`, using synthetic fixtures
   (see `managed` / `ready_source` in `tests/test_sources.py`).
4. A real WebView2 check in `scripts/verify-<feature>.py --run-name` when UI
   behavior changes (shared helpers in `scripts/gui_harness.py`; the app is driven
   through `window.lal`); keep existing verify scripts passing.
5. Docs: the user guide in `docs/` when behavior users see changes (`docs/gui/README.md`,
   `docs/asset-sources.md`, `docs/cli.md`…), the knowledge base notes for the systems
   touched, and an `Unreleased` line in `CHANGELOG.md` for user-visible changes. Test
   counts, evidence paths and storage receipts go in the pull request description (the
   dated `docs/history/progress-2026-10.md` journal is frozen).

## Non-obvious rules

- App-owned UI text must be valid UTF-8 with no mojibake; `tests/test_ui_encoding.py`
  enforces it. Write real characters (`…`, `·`, `→`), not escaped garbage.
- `src/local_asset_library/ui/vendor/**` is upstream, byte-for-byte (`-text`);
  never reformat it. `ui/build/**` is generated by `npm run build`; never edit it by hand. `docs/mcp/*.json` are hash-bound evidence; do not rewrite.
- Nothing is ever written into asset folders (decision 0023). Generated results live in the
  library store (`[storage].library`, default the ignored `data/library-store/`), keyed by their
  inputs; settings, combined indexes and evidence stay central under ignored `data/`. Ignored roots:
  `data/ cache/ logs/ scratch/ .venv*/`.
- Inference is offline with no fallbacks; a model/worker failure is a visible fault,
  never a silent substitute. Never start rendering or models at app startup (the
  embedding worker may pre-load its libraries only; decision 0005).
- Processing never starts automatically; scans never run models. Changing format
  settings never deletes results or retries faults.
- This file and `AGENTS.md` describe no particular computer. This machine's hardware, tool
  paths and Linux check setup live in the ignored `MACHINE.local.md` (AGENTS.md → Local machine).
- Shared models live in the directory set as `[storage].models` in `config.local.toml` (not owned
  by this project; `docs/model-storage.md`). Blender comes from `[tools].blender` or discovery
  (`local-assets doctor` lists the candidates).
- Local overrides go in ignored `config.local.toml` (copy `config.example.toml`).
  The tracked example is neutral (project `models/`, Blender discovered); your machine paths
  live in your `config.local.toml`. Scripts use `load_project_config`.
- GPU work runs on CUDA (NVIDIA) or HIP (AMD), or not at all where neither is supported
  (search embeds on CPU, decision 0018). One GPU job at a time via `gpu_queue`.
- Linux checks (`docs/linux.md`): use a clone on a Linux filesystem (under WSL2, not `/mnt/…`)
  and a Linux Blender. Run Linux suites with `LAL_REQUIRE_BLENDER=1` and report the
  `Real-Blender tests:` line; a skipped Blender fixture is unverified.
- Do not edit `blender_worker.py` / `render_math.py` / repair workers for portability:
  their hashes are inspection fingerprints (editing re-queues every inspection). A worker edit
  that keeps CPU renders identical can keep them only through `incremental.EQUIVALENT_WORKERS`,
  proven with `scripts/check-render-stability.py` (decision 0022).
- Inspection renders run in kept-open Blender processes in parallel (`render_pool.py`,
  `blender_batch_worker.py`); device and count come from the speed test (`render_devices.py`)
  and the owner's limits in `data/library/rendering.json`.
- Match the existing dense style: short module docstrings stating the guarantee,
  compact code, few comments that explain *why*.

## Source-of-truth docs

`Assetarium KnowledgeBase/Decisions/` (binding owner decisions, read first) ·
`Assetarium KnowledgeBase/Status.md` (current status and open work) · `Assetarium KnowledgeBase/Home.md`
(vault conventions and the list of user guides in `docs/`) · `Assetarium KnowledgeBase/Notebook/`
(area hubs and system notes) · `Assetarium KnowledgeBase/Architecture/` (contracts, library updates,
caption severity, the expansion roadmap) · `docs/caption-contract.md` (stays in `docs/`;
a check script hashes its path) · `docs/history/` (frozen October 2026 journal).
