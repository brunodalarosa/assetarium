---
area: Platform and Storage
tags: [hub]
code: [config.venv_python, config.runtime_command, scripts/uv.ps1, scripts/mcp-runtime.ps1, scripts/caption-runtime.ps1, scripts/embedding-runtime.ps1, scripts/storage-report.py, retention.py, scripts/check-caption-classification.py]
---
# Platform and Storage

Python runtimes and wrappers, Windows vs Linux, disk use and what may be deleted.
Up: [Notebook](../Notebook.md).

## Systems

- [Runtimes](Runtimes.md): the four uv environments, their wrappers and how to run tests.
- [Storage discipline](Storage%20discipline.md): receipts, budgets, hard links, `scratch/`.
- [Retention](Retention.md) *(gap)*: superseded generations and launch audits (`retention.py`,
  decision [0006](../../Decisions/0006-retention.md)).
- Linux: CLI + MCP only, no desktop app ([docs/linux.md](../../../docs/linux.md), decision
  [0013](../../Decisions/0013-platform-support.md)).

## Read first

- `AGENTS.md` → Storage discipline (binding for every agent).
- Decisions: [0006](../../Decisions/0006-retention.md), [0010](../../Decisions/0010-shared-project-dependencies.md),
  [0013](../../Decisions/0013-platform-support.md).

## Gotchas

- Links into the vault from outside it must spell the folder `Assetarium%20KnowledgeBase/…`: a
  plain space breaks Markdown links on GitHub. `docs/caption-contract.md` keeps the old
  `KnowledgeBase/` path because `scripts/check-caption-classification.py` hashes its contents.
