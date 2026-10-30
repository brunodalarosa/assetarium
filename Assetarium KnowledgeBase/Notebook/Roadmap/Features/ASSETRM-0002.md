---
tags: [roadmap]
id: ASSETRM-0002
type: feature
status: open
created: 2026-10-29
---
# ASSETRM-0002

Brainstorm a rework of the Asset Source management implementation.

## Goal

The owner wants to rebuild how asset sources are managed from the ground up and fix issues
along the way. This task is the **brainstorm**: its output is an agreed design, not code.
Implementation is split into its own tasks afterwards.

## Scope of the brainstorm

- Review the current implementation end to end: `sources.py`, `incremental.py`,
  `desktop_service.py` and the Sources UI, plus the Notebook notes in
  [Sources and Catalog](../../Sources%20and%20Catalog/Sources%20and%20Catalog.md) and the
  decisions that bind it (`Decisions/`).
- Collect the problems to fix with the rebuild. Start from what is already known and add the
  owner's list:
  - A source can show "needs processing" for work its processing run cannot finish, and the
    Process assets action then fails every time. See the Kenney 3D assets case, where previews
    are complete but the search-data stage cannot run because the embedding runtime is not
    installed.
  - Failures and pending work are shown together in one banner, which does not make clear what
    an action will actually resolve ([user experience rules in AGENTS.md](../../../../AGENTS.md)).
  - Errors are hard to find: operation logs can be empty and the real fault lands in
    `logs/gui-worker.log`.
- Decide what stays binding from existing decisions (read-only originals, results in each
  source's `metadata-lal/`, processing never starts automatically, faults kept visible and never
  retried automatically) and what the rebuild may change. A change that contradicts a decision
  needs the owner's approval and an updated decision record.
- Propose the target model: what a source is, its lifecycle (add, scan, process, publish,
  remove), stage/state tracking, how faults and pending work are separated, and how the app,
  CLI and MCP share it.
- Propose how to migrate existing sources and results without reprocessing or losing evidence.

## Out of scope

Writing the new implementation, changing models or the processing pipeline itself, and any
change to original asset files.

## Output

A design note (Architecture doc, `status: draft`, from `_Templates/Architecture Doc.md`) with
the options considered, a recommendation, the migration path, risks, and the follow-up
implementation tasks to add under this roadmap.

## Working on it

The owner drives this one. The agent should interview the owner first about pain points,
priorities and must-keep behavior, offer options with a recommendation, and write nothing until
the direction is agreed. The `AGENTS.md` scope-and-plan checkpoint applies before any
implementation.
