---
tags: [roadmap]
id: ASSETRM-0003
type: bug
status: open
created: 2026-10-30
---
# ASSETRM-0003

Remove pilot-era rules and wording that still steer agents and contributors.

## Problem

The 40-asset pilot is over, but its rules live on in agent instructions and live docs and still
influence decisions. Example: `AGENTS.md` → Storage discipline sets a "6 GiB pilot target" for
project storage, while the real limit is the owner's **Storage budget** in Settings
(`library_policy`, `save_general_settings`), which overrides it. `git grep -il pilot` also finds
it in `CLAUDE.md`, `Status.md`, Notebook notes (Storage discipline, Retrieval, Search, Codebase),
Architecture docs (Catalog contract, Embedding contract, MCP server, Caption severity, Library
updates, the Expansion plan and its prompts), `docs/gui/README.md` and `docs/mcp/README.md`.

## Done when

- `AGENTS.md` and `CLAUDE.md` state current rules only. The storage section points to the
  Settings storage budget instead of a pilot target.
- Live docs and vault notes describe the current library, not the pilot. Where a pilot fact is
  still a valid record (a measurement, evaluation evidence), it is labeled as history.
- Untouched: frozen and hash-bound evidence (`docs/history/`, `docs/evaluation/`, `docs/mcp/*.json`,
  `docs/caption-contract.md`, the `docs/*.json` receipts), the decision records (their text is the
  record; at most a "superseded" note, with owner approval), and code that still reads pilot data
  (for example `mcp_server.pilot_records`). Code renames are a separate task.
- `CHANGELOG.md` is unchanged unless user-facing text changes.
