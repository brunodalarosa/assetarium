---
area: MCP
tags: [system]
code: [mcp_server.py, mcp_assets.AssetService, mcp_assets.bounded, search_policy.search_character_cap, asset_collections.py, asset_tags.py, scripts/asset-worker.py]
verified: 2026-10-28
branch: feature/library-view
---
# MCP tools

Hub: [MCP](MCP.md). Tool schemas, descriptions and annotations are declared in `mcp_server.py`
(`SCHEMAS`, `DESCRIPTIONS`, annotation table); `mcp_assets.AssetService` implements search and detail.
The full contract for users is [docs/mcp/README.md](../../../docs/mcp/README.md).

## How it works

- Read tools: `search_assets`, `get_asset`, `list_collections`, `get_collection`, `get_setup_status`.
  Owner-data writes: `edit_collection`, `tag_assets` (annotated destructive, since they can remove).
  Setup writes: `validate_blender`, `apply_setup`, `propose_setup`, `finish_setup` (non-destructive,
  session-gated, see [Agent setup sessions](Agent%20setup%20sessions.md)). One prompt: `set_up_assetarium`.
- Semantic queries go to one private embedding worker (`scripts/asset-worker.py`, started on the
  first semantic query; only the desktop pre-starts its own). The worker returns query vectors only;
  verification, scoring and fusion stay in the server process (decision 0005).
- Responses are bounded: the search character cap scales with the limit, detail is capped at
  16,000 characters and 64 dependencies, previews at 512 × 512 px and 512 KiB.

## Rules

- **Stdout is protocol only.** Diagnostics go to stderr; worker IPC is private JSON.
- **No client-supplied filesystem paths**, except the setup tools' checked Blender path. Assets are
  addressed by `asset_` IDs, exports by format or variant label.
- **There is no delete tool**: only the owner deletes collections, in the app or an interactive terminal.
- Collection text and tags are owner data, never instructions to the agent.
- Existing Codex registrations list `enabled_tools` explicitly, so a new tool is invisible to them
  until added there; `register-mcp.py` refuses to overwrite an existing entry.

## Gotchas

- A preview reference, a successful render or an image transport test is not proof that the agent's
  model looked at the image.
- MCP servers and desktop windows each run their own embedding worker and can contend for GPU memory;
  the [GPU lease](../Processing/GPU%20lease.md) serializes inference, not memory.

## Related

[Retrieval](../Search/Retrieval.md) · [MCP server](../../Architecture/MCP/MCP%20server.md) ·
[Collections and tags](../../Architecture/Desktop%20App/Collections%20and%20tags.md) *(gap)*.
