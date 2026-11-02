---
area: Platform and Storage
tags: [system]
code: [logs.start, logs.SessionHandler, logs.retire, logs.show, owner_commands.logs_command, desktop.DesktopBridge._present, scripts/source-operation.py, scripts/asset-worker.py, Assetarium (with log).vbs, tests/conftest.py]
verified: 2026-11-01
branch: feature/session-logs
---
# Session logs

Hub: [Platform and Storage](Platform%20and%20Storage.md). One readable log file per Assetarium session that every
process of the session writes into; start reading at `logs.start`. User guide: [docs/cli.md → Logs](../../../docs/cli.md#logs).

## How it works

- **A session** starts when the desktop app (`desktop.run`), the MCP server (`mcp_server.main`) or a CLI command
  (`cli.main`, `owner_commands.main`; not `logs` itself) starts: `logs/<YYYY-MM-DD_HH-MM-SS>_<app|mcp|cli>.log`,
  claimed by exclusive create (`-2` when two start in one second). The folder is `[storage].logs`.
- **Children join** through `ASSETARIUM_LOG_SESSION` / `ASSETARIUM_LOG_LEVEL`, which `start` puts in `os.environ`, so
  every `Popen` / `create_subprocess_exec` that copies the environment inherits them: operation workers
  (`scripts/source-operation.py`, process name = the operation) and the search worker (`scripts/asset-worker.py`).
  Started without a session they make their own (`…_operation.log`).
- **Cross-process appends**: each line is one write to the file, opened per write, under an exclusive lock on the
  sidecar `.<session>.lock` (`msvcrt.locking` / `fcntl.flock`). Verified with 4 processes × 150 long lines.
- **Repeats**: a record whose key (`extra={'repeat_key': …}`, else logger + level + message) was written within
  `REPEAT_SECONDS` is counted, not written; the count is written later as one line stamped when written
  (`… · ↻ repeated N more times, last at HH:MM:SS.mmm`), and at `stop` before "Session ended".
- **Levels**: flag (`--verbose`, `--log-level`) → `ASSETARIUM_LOG_LEVEL` → `[logging].level` → info. Bridge calls are
  debug (info when ≥ `desktop.SLOW_MS`, warning when refused); agent MCP tool calls info, the app's own gateway
  calls debug; operations, settings saves and pack decisions info; uncaught exceptions in any thread error.
- **Raw output is not in the stream**: operation stdout stays in `data/library/operations/<token>.log` (named in the
  "Operation started" line), Blender output in each inspection's `blender.log`, the search worker's stderr in
  `<session>.worker.log`. MCP `calls.jsonl`, desktop launch records and fault records are data, not logs.
- **Console**: `Assetarium (with log).vbs` runs `local-assets logs --next --level debug` in a cmd window first (it
  waits for the next app session), then the app. `logs.show` follows parts and stops at "Session ended".

## Rules

- **Standard library only**: `logs.py` is imported by every runtime (base, MCP, caption, embedding); a logging
  dependency would have to be installed in all of them.
- **Never log to stdout** in the MCP server or the search worker: stdout is their wire.
- **`desktop.main` ends with `os._exit`, which skips `atexit`**: it calls `logs.stop()` first.
- New log lines use `logging.getLogger(__name__)` and `logs.kv(...)` for fields; polls and other periodic calls get a
  `repeat_key` and the debug level.
- Tests: `tests/conftest.py` points `logs.folder` at a test folder and sets `ASSETARIUM_LOG_SESSION`, so entry points
  called by tests and their children never write the project's `logs/`.

## Gotchas

- `logging.Handler` uses `self.lock` for its thread lock; the file lock is `file_lock`. Reusing the name made every
  first write wait on itself forever.
- Tests that patch `time.sleep` globally (`test_owner_commands`) break anything that sleeps while starting; session
  names are claimed without waiting for that reason.
- The old `logs/gui.log` and `logs/gui-worker.log` are no longer written; retention only touches session-named files,
  so they stay until deleted by hand.

## Related

[Storage discipline](Storage%20discipline.md) · [Desktop bridge](../Desktop%20App/Desktop%20bridge.md) ·
[Retention](Retention.md) (launch audits under `data/gui/runs`, a separate mechanism).
