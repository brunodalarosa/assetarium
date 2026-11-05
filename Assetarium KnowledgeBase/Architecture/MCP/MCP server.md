---
tags: [architecture]
level: system
parent: "[Architecture](../Architecture.md)"
status: draft
code: [mcp_server.py, mcp_assets.py, scripts/asset-mcp.py, scripts/asset-worker.py, scripts/register-mcp.py, scripts/verify-mcp.py, search_policy.py]
verified:
branch:
---
# MCP server

> The STDIO MCP server gives agents bounded, read-only search and detail over the published
> library, plus owner-data writes (collections, tags) and session-gated setup tools. Stdout is
> protocol only; query inference happens in a private embedding worker, and ranking stays in the
> server process.

Up: [Architecture](../Architecture.md) · Where in code: [MCP](../../Notebook/MCP/MCP.md) ·
User guide and tool contract: [docs/mcp/README.md](../../../docs/mcp/README.md)

Moved from `docs/mcp/README.md` on 2026-10-28; not yet re-verified against the code line by line.

## Runtime

MCP SDK **2.3.0**, NumPy **2.3.4** and Pillow **12.1.0** are locked separately
under `runtime/mcp/`. Semantic queries start one persistent private subprocess
using the existing `.venv-embedding`, unchanged model/backend/lock/index
contracts, offline weights and CUDA BF16. The worker only embeds the query text
or reference image; the server verifies, scores and fuses rankings in-process
(decision 0005). Its output is private JSON IPC with progress heartbeats; all
diagnostics use stderr. The MCP server starts the worker on its first semantic
query; only the desktop app pre-starts it. There is no automatic fallback/restart after a failed
worker, model initialization, or unchanged failed query.

## Client registration, preservation and restoration

`scripts/register-mcp.py` performs first registration only: copy original bytes
to ignored `data/mcp/config-backups/<UTC>/`, verify them, add just this server,
compare parsed unrelated settings, check for concurrent edits, then verify the
write. Never rerun it blindly over an existing server entry. Exact setup snippets
are versioned here; `data/mcp/registration.json` records paths, hashes and backups.
Backups can contain private settings and must not be committed or sent to models.

To restore, close the client. Check for later changes before restoring the whole
file. If none exist, copy the exact backup bytes back to the corresponding
receipt path. If later changes exist, remove only this server entry after review
and preserve those later settings. Restart/reconnect the client to load changes.
The existing desktop chat was not treated as having hot-reloaded new tools:
verification used fresh installed CLI sessions with the same active configuration.

## Verification and disclosure

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
& '.\.venv-mcp\Scripts\python.exe' -m pytest tests\test_mcp_assets.py tests\test_retrieval.py tests\test_evaluation.py --basetemp scratch\pytest-mcp-new-run
& '.\.venv-mcp\Scripts\python.exe' scripts\verify-mcp.py --run-name unique-run-name
```

Read previous faults before requesting any repeat. The protocol harness creates
a distinct directory and captures real initialization, tool discovery, both
tools, image decoding/hash, malformed ID/path/filter/cap errors, semantic default
and clean EOF shutdown. This is explicitly **not agent-use evidence**. The
initial harness incorrectly matched a Windows environment-launcher PID to its
child Python PID; original faulty evidence is preserved. The corrected harness
identifies the new audit directory instead.

`scripts/historical/verify-agent-workflow.py codex|opencode` (original development machine only) performs one bounded real-client
selection workflow and saves events/stderr plus final manifest in
`data/exports/<client>-selection.json`. It runs installed clients as verification
targets, without delegation/subagents. It never changes the persistent model or
permission setup. Codex disables other MCPs for that one invocation; OpenCode's
one-run inline permission overlay authorizes exactly the two read-only project
tools. Neither changes unrelated saved configuration. A failed unchanged client
workflow is not automatically retried.

Each server process records returned text size/UTF-8 bytes, estimated tokens,
image bytes/base64 length, errors, full fault evidence and timing under
`data/mcp/runs/<id>/`. Preview PNGs are preserved separately. These are local
evidence writes, not source edits. Tool-schema and full-client token usage are
measured separately; reported client usage includes instructions, prior context,
tool schemas, repeated context and images as accounted by that client. It cannot
be used to claim retrieval-only token savings.


See `docs/mcp/client-results.json`, `owner-review.json`, `preservation.json` and
the [progress journal](../../../docs/history/progress-2026-10.md) for real outcomes and current limitations. Owner labels were
validated and quality recomputed only from saved first-repeat rankings; frozen
step 6 artifacts were preserved. The current session supplies the explicit
bounded pilot decision recorded in those historical receipts. Step 8 received
separate scope and runtime/storage approval; its current contract and coverage
are documented in [Library updates](../Processing/Library%20updates.md) and the progress journal.

## Decisions and history

- Step 7 of the pilot (October 11, 2026) introduced the server; step 8 generalized membership to
  the configured library and pinned each request to one published generation. The historical
  forty-asset pilot approval remains preserved; current operations are in
  [Library updates](../Processing/Library%20updates.md).
- The owner's client decision at the time was **Codex for now**; OpenCode work is on hold until
  the owner asks ([`client-decision.json`](../../../docs/mcp/client-decision.json), [progress journal](../../../docs/history/progress-2026-10.md)).
- `register-mcp.py` discovered and preserved the client registrations on the original
  development machine; `docs/mcp/codex-setup.toml` and `opencode-setup.json` are those recorded
  snippets, not current setup files. Official references read October 11, 2026:
  - [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
  - [OpenCode MCP servers](https://opencode.ai/docs/mcp-servers/)
  - [OpenCode configuration precedence](https://opencode.ai/docs/config/)
  - [MCP server development](https://modelcontextprotocol.io/docs/develop/build-server)
