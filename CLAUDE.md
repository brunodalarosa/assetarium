@AGENTS.md

# Claude orientation for Local Asset Library (LAL)

AGENTS.md above is the shared contract for every agent (Codex and Claude): the
two approval checkpoints, UX care, fault handling, caption severity and storage
discipline all apply unchanged. This file only adds orientation. When they
differ, AGENTS.md and the owner's instructions win.

## What LAL is

A local, read-only catalog of 3D game assets (FBX, glTF/GLB, OBJ/MTL, BLEND…)
for agents and a Windows desktop app. It inventories configured asset sources,
inspects and renders them in Blender, writes local visual descriptions
(Qwen3-VL), builds text/image embeddings (EmbeddingGemma 2) and serves bounded
search/detail through a STDIO MCP server and a pywebview/WebView2 desktop app.
Original asset files are never written. Owner: Bruno (visual approval,
relevance judgments, expansion decisions). Being prepared for open source.

## Runtimes — always use the wrappers (PowerShell, from the repo root)

| Wrapper | Environment | Project | Purpose |
| --- | --- | --- | --- |
| `.\scripts\uv.ps1` | `.venv` | `pyproject.toml` | Base CLI, catalog, keyword search, storage report, `library-batch.py` |
| `.\scripts\mcp-runtime.ps1` | `.venv-mcp` | `runtime/mcp` | MCP server, desktop app (pywebview), **full test suite**, GUI verify scripts |
| `.\scripts\caption-runtime.ps1` | `.venv-caption` | `runtime/caption` | Qwen3-VL captioning (Torch cu128, Transformers 4.x) |
| `.\scripts\embedding-runtime.ps1` | `.venv-embedding` | `runtime/embedding` | EmbeddingGemma indexing and semantic search (Transformers 5.x) |

Python 3.13 only. Wrappers keep uv cache, temp, HF/Torch caches inside the
project and set `UV_LINK_MODE=hardlink`. Never `sync`/install or change pins
without covering it at the plan checkpoint; never edit installed packages.
Prefer `--locked --no-sync --offline` for runs.

```powershell
# Full suite (313+ tests, includes real Blender fixtures; takes minutes)
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest --basetemp scratch/pytest-<new-name>
# Targeted
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest tests/test_desktop.py tests/test_sources.py --basetemp scratch/pytest-<new-name>
# Real WebView2 verification with isolated synthetic assets (writes data/gui/<run-name>/report.json)
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/verify-source-browser.py --run-name <unique-name>
# Config/health (read only)
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli check-config
.\scripts\uv.ps1 run --locked python -m local_asset_library.cli doctor
# Storage receipt (base interpreter, new output name each time)
.\.venv\Scripts\python.exe scripts/storage-report.py --output <new-name>.json
```

Use a new `--basetemp` / `--run-name` each time; existing outputs are evidence.
pytest config lives in `pyproject.toml` (`-q -p no:cacheprovider`). Some tests
create Windows junctions and may need sandbox permission. Launch the app with
`Local Asset Library.vbs` (it runs `.venv-mcp\Scripts\pythonw.exe
scripts\asset-desktop.pyw`; startup never installs or runs models).

## Code map (`src/local_asset_library/`)

- **Config and boundaries:** `config.py` (validated storage roots; the only
  path-boundary API, rejects traversal/links escaping roots), `settings.py`
  (app-owned `data/library/settings.json`: processing formats, storage budget),
  `publication.py` (atomic JSON, pinned immutable catalog/index generations).
- **Sources and catalog:** `sources.py` (registry `data/library/sources.json`,
  per-source `metadata-lal/` output, combined read-only catalog, scans),
  `source_operations.py` (durable, cancellable Process-assets operations),
  `source_storage.py`, `source_migration.py`, `source_browser.py`,
  `catalog.py` (inventory, logical-asset grouping, keyword/FTS5 baseline),
  `membership.py` (`docs/library-membership.json`, no full-catalog fallback).
- **Processing pipeline:** `incremental.py` (stage ledger, bounded processing,
  publication; driven by `scripts/library-batch.py scan|process|refresh|status`),
  `inspection.py` + `blender_worker.py` + `render_math.py` (Blender in background,
  scripts disabled), `texture_repair.py` + `blender_repair_worker.py`,
  `captions.py` + `caption_backend.py` + `caption_quality.py` + `caption_review.py`,
  `overnight.py` (owner-started caption runs), `library_index.py` +
  `embedding_backend.py` (vectors), `gpu_queue.py` (cross-process GPU lease),
  `maintenance_files.py` (manifest-driven removal of retired generated files).
- **Retrieval and agents:** `library_cache.py` (per-publication slim records and digests; shared, read-only), `retrieval.py` + `search_policy.py` (keyword /
  description / image / combined RRF, bounded shortlists), `mcp_assets.py`
  (`search_assets`, `get_asset` schemas and response caps; no client-supplied
  paths), `mcp_server.py` (STDIO server + isolated `scripts/asset-worker.py`
  embedding worker; stdout is protocol-only), `evaluation.py`.
- **Desktop:** `desktop.py` (`DesktopBridge` = pywebview `js_api`; methods run on
  threads and go through one asyncio gateway loop; `create_window` inlines
  `ui/style.css`, `ui/app.js`, `ui/interactive-preview.js` into `ui/index.html`),
  `desktop_service.py` (read-only presentation), `interactive_preview.py` +
  `ui/viewer.html`/`viewer.js` (sandboxed offline Online3DViewer frame).
- `cli.py` is the `local-assets` entry point; many workflows live in `scripts/`.
- `skills/local-asset-library/SKILL.md` is the agent-facing usage skill for the MCP tools.

## How features are usually built

Recent commits (`git log`) follow this shape; mirror it:

1. Backend logic in the owning module (`settings.py`, `sources.py`,
   `incremental.py`, `desktop_service.py`…), exposed to the UI as a
   `DesktopBridge` method returning plain JSON-able dicts (`status`/`reason` on faults).
2. UI in `ui/app.js`, `ui/index.html`, `ui/style.css` (vanilla JS, no build step).
3. pytest tests in `tests/test_<area>.py`, using synthetic fixtures
   (see `managed` / `ready_source` in `tests/test_sources.py`).
4. A real WebView2 check in `scripts/verify-<feature>.py --run-name` when UI
   behavior changes; keep existing verify scripts passing.
5. Docs: the relevant `docs/*.md` (`docs/gui/README.md`, `docs/asset-sources.md`,
   `docs/library-updates.md`…) and a dated entry at the top of `docs/progress.md`
   with test counts, evidence paths and storage receipts.

## Non-obvious rules

- App-owned UI text must be valid UTF-8 with no mojibake; `tests/test_ui_encoding.py`
  enforces it. Write real characters (`…`, `·`, `→`), not escaped garbage.
- `src/local_asset_library/ui/vendor/**` is upstream, byte-for-byte (`-text`);
  never reformat it. `docs/mcp/*.json` are hash-bound evidence; do not rewrite.
- Generated results belong in each source's `metadata-lal/`; settings, combined
  indexes and evidence stay central under ignored `data/`. Ignored roots:
  `data/ cache/ logs/ scratch/ .venv*/`.
- Inference is offline with no fallbacks; a model/worker failure is a visible fault,
  never a silent substitute. Never start rendering or models at app startup.
- Processing never starts automatically; scans never run models. Changing format
  settings never deletes results or retries faults.
- Shared models live in `C:\BrunoOS\Local-models` (not owned by this project).
  Blender: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`.
- Local overrides go in ignored `config.local.toml` (copy `config.example.toml`).
- Hardware: RTX 5070 (~12 GB VRAM). One GPU job at a time via `gpu_queue`.
- Match the existing dense style: short module docstrings stating the guarantee,
  compact code, few comments that explain *why*.

## Source-of-truth docs

`docs/decisions/` (binding owner decisions, read first) ·
`docs/progress.md` (current state, newest first) · `docs/asset-sources.md` ·
`docs/library-updates.md` · `docs/gui/README.md` · `docs/gui/3d-preview.md` ·
`docs/storage.md` · `docs/caption-quality.md` · `docs/caption-contract.md` ·
`docs/embedding-contract.md` · `docs/catalog-contract.md` · `docs/mcp/README.md` ·
`docs/overnight-descriptions.md` · `docs/plan/PROJECT.md` (historical plan).
