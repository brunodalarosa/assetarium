---
tags: [decision]
decided: 2026-10-17
status: retired
retired: 2026-11-07
replaced_by: "Notebook/Setup and Engines/Setup core.md"
---
# 0001 — `config.local.toml` overrides the example config (retired)

> **Retired on November 7, 2026.** Still true, but it is a coding convention, not a product decision.
> The rule now lives in [Setup core](../Notebook/Setup%20and%20Engines/Setup%20core.md) → Rules and in
> `CLAUDE.md`. This record is frozen as history.

**Decision.** Runtime entry points load configuration through
`config.load_project_config(root)`: ignored `config.local.toml` when it exists,
otherwise tracked `config.example.toml`. This covers the desktop app, MCP
server, embedding worker, source operations, `library-batch.py` and the CLI
default.

**Why.** The README always documented `config.local.toml` as the local override,
but every entry point hard-coded the example file, so overrides were ignored.

**Keep true.** New entry points use `load_project_config` (or
`project_config_path`). Historical verification scripts may keep their explicit
example path; convert them when they are next touched.
