---
area: Platform and Storage
tags: [system]
code: [config.venv_python, config.runtime_command, scripts/uv.ps1, scripts/uv.sh, scripts/mcp-runtime.ps1, scripts/caption-runtime.ps1, scripts/embedding-runtime.ps1, runtime/mcp, runtime/caption, runtime/embedding, runtime/embedding-cpu, tests/conftest.py, scripts/scratch_links.py]
verified: 2026-10-28
branch: feature/library-view
---
# Runtimes

Hub: [Platform and Storage](Platform%20and%20Storage.md). Python 3.13 only, in separately pinned uv
environments that share one hard-linked cache. Always go through the wrappers in `scripts/`
(PowerShell on Windows, a POSIX twin with the same arguments on Linux).

## How it works

| Wrapper | Environment | Project | Used for |
| --- | --- | --- | --- |
| `uv` | `.venv` | `pyproject.toml` | Base CLI, catalog, keyword search, storage report, `library-batch.py` |
| `mcp-runtime` | `.venv-mcp` | `runtime/mcp` | MCP server, desktop app, **the full test suite**, verify scripts, owner CLI (`local-assets`) |
| `caption-runtime` | `.venv-caption` | `runtime/caption` | Qwen3-VL descriptions (Torch, Transformers 4.x) |
| `embedding-runtime` | `.venv-embedding` | `runtime/embedding`, `runtime/embedding-cpu` | EmbeddingGemma indexing and semantic search (Transformers 5.x) |

- Wrappers keep the uv cache, temp files and Hugging Face/Torch caches inside the project and set
  `UV_LINK_MODE=hardlink`.
- Tests: `.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest --basetemp scratch/pytest`
  (full suite takes minutes and includes real Blender fixtures). On Linux run with
  `LAL_REQUIRE_BLENDER=1` and report the `Real-Blender tests:` line.

## Rules

- **In code, use `config.venv_python` / `config.runtime_command`, never a hardcoded
  `Scripts/python.exe` or `powershell.exe`.**
- **Never `sync`, install or change pins without approval at the plan checkpoint; never edit an
  installed package** (hard links share bytes across environments). Prefer
  `--locked --no-sync --offline` for runs.
- Keep environments separately pinned when compatibility needs it (Transformers 4.x vs 5.x); don't
  merge them to save space.
- Reuse `--basetemp scratch/pytest`; some tests create Windows junctions and may need sandbox permission.

## Gotchas

- The owner CLI runs from `.venv-mcp` (`scripts/local-assets.ps1` / `.sh`), not the base `.venv`.
- A local-server description run uses `.venv-mcp`, so AMD and other GPUs need no caption runtime.

## Related

[Storage discipline](Storage%20discipline.md) · [docs/linux.md](../../../docs/linux.md) · [Codebase](../Codebase.md).
