---
tags: [architecture]
level: system
parent: "[Architecture](../Architecture.md)"
status: draft
code: [mcp_server.py, mcp_assets.py, pack_agent.py, setup_agent.py, agent_activity.py, scripts/asset-mcp.py, scripts/asset-worker.py, scripts/register-mcp.py, scripts/verify-mcp.py, search_policy.py]
verified: 2026-11-10
branch: feature/audit-simplify
---
# MCP server

> The STDIO MCP server gives agents bounded search and detail over the published library, owner-data
> writes (collections, tags), pack structure tools and setup tools. Stdout is protocol only; the search
> model runs in a private worker, and ranking stays in the server process. Rewritten on 2026-11-10; the
> pilot-era client trials it used to describe are in git (commit `af02e91`).

Up: [Architecture](../Architecture.md) · Where in code: [MCP](../../Notebook/MCP/MCP.md) ·
User guide and tool contract: [docs/mcp/README.md](../../../docs/mcp/README.md) ·
Binding rules: [0029](../../Decisions/0029-agent-trust.md) (what agents may do),
[0031](../../Decisions/0031-setup.md) (agent setup), [0036](../../Decisions/0036-collections-and-tags.md).

## Shape

```
        agent client
             │  STDIO (JSON-RPC)
             ▼
        scripts/asset-mcp.py
        mcp_server            (1)
             │
             ▼
        mcp_assets.AssetService   (2)
             │
       ┌─────┴──────┐
       ▼            ▼
   SearchEngine   worker      (3)
```

1. `mcp_server` owns the transport, tool listing, the per-run audit log and the worker's lifetime. There is no
   HTTP listener.
2. `AssetService` validates every argument against a closed JSON schema (unknown keys, path-like values and
   out-of-range limits are errors), calls the shared `retrieval.SearchEngine`, and bounds every response.
   The desktop app uses the same service, so both interfaces rank and filter identically.
3. The worker (`scripts/asset-worker.py`, in the search runtime) only turns a query text or a reference image
   into a vector. The server starts it on the first semantic query. Verification, scoring and fusion happen
   in the server ([Search embedders](../../Notebook/Search/Search%20embedders.md)).

## Tools

| Group | Tools | Writes |
| --- | --- | --- |
| Search and detail | `search_assets`, `get_asset` | Nothing |
| Collections and tags | `list_collections`, `get_collection`, `edit_collection`, `tag_assets` | Owner data only; agents cannot delete a collection |
| Pack structure | `list_packs`, `get_pack_outline`, `get_profile`, `propose_profile`, `finish_structure`, `say` | Pack profiles: rules that need no scan apply at once with Undo, others wait for the owner |
| Setup | `get_setup_status`, `validate_blender`, `apply_setup`, `verify_weights`, `propose_setup`, `finish_setup` | Settings, recorded as the agent's and noticed; a Blender path is only proposed |

What an agent may do without asking, what stays the owner's, and how the owner sees and undoes it (Agent
activity, Stop, Pause agents, Undo per session) is [decision 0029](../../Decisions/0029-agent-trust.md).

## Rules the server keeps

- **Each request reads one pinned published generation.** A client connected before an update keeps the old
  behavior until it reconnects.
- **Asset files, library folders and original bytes are read only.** No tool takes an arbitrary path, a URL or
  an upload; a reference search names an asset and one of its known views.
- **No fallbacks.** A failed worker, model load or query is an error the agent sees. It is never answered with
  keyword results instead, and the worker is not restarted behind the agent's back. Busy-queue and
  stopped-worker errors are transient: the same query works once the GPU is free.
- **Responses are bounded** by `search_policy`: limit 1 to 40 (5 when omitted), a character cap that grows with
  the limit, previews only on request. Optional metadata that does not fit is reported as partial; source and
  dependency evidence is never trimmed to make an asset look usable.
- **Asset text is data.** Names, descriptions, license excerpts, labels and notes are returned as content,
  never followed as instructions.
- **Stdout carries only the protocol.** Diagnostics go to stderr.

## Runtime

The server runs in `.venv-mcp` (`runtime/mcp/`: the MCP SDK, NumPy and Pillow, pinned in its lock) and never
imports Torch. Semantic queries use the separate search runtime through the worker, offline, with the model,
lock and index contracts of the [Embedding contract](../Search/Embedding%20contract.md). `scripts/asset-mcp.py`
resolves its own repository and configuration whatever the client's working directory is.

## Evidence each run leaves

Every server process writes `data/mcp/runs/<id>/`: one line per call in `calls.jsonl` (tool, sizes, timing,
errors and full fault evidence) and any preview image it returned. The app's Agent activity drawer reads these
logs, which is how the owner sees what agents did (`agent_activity.py`). They are local evidence, not edits to
assets.

## Connecting a client

The desktop app's **Set up with your AI agent** panel shows the snippet for each client with this checkout's
real paths; `scripts/register-mcp.py --snippets-only` writes the same snippets under ignored
`data/mcp/clients/`. Tracked examples with a placeholder path are in [`docs/mcp/clients/`](../../../docs/mcp/clients/).

`register-mcp.py` without that flag edits a client's configuration file, once: it copies the original bytes to
ignored `data/mcp/config-backups/<UTC>/`, verifies the copy, adds only this server, checks that every other
setting parses the same as before, and records paths and hashes in `data/mcp/registration.json`. Do not rerun
it over an existing entry. Backups can hold private settings: never commit them or send them to a model. To
undo, close the client and either restore the backup (when nothing else changed since) or remove just this
server's entry.

## Verification

```powershell
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest tests/test_mcp_assets.py tests/test_retrieval.py --basetemp scratch/pytest
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/verify-mcp.py --run-name <unique-name>
```

`verify-mcp.py` drives a real STDIO session: initialization, tool discovery, the tools, image decoding and
hash, malformed ID, path, filter and cap errors, and a clean shutdown at EOF. It proves the protocol, **not that
an agent uses the tools well**; that is what "Try your agent" is for
([Agent practice](../../Notebook/MCP/Agent%20practice.md)). `verify-agent-setup-mcp.py` covers the setup tools
on an isolated empty project.
