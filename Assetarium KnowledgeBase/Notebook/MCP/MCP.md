---
area: MCP
tags: [hub]
code: [mcp_server.py, mcp_assets.py, setup_agent.py, scripts/asset-mcp.py, scripts/asset-worker.py, scripts/register-mcp.py, skills/local-asset-library/SKILL.md, skills/assetarium-setup/SKILL.md]
---
# MCP

Assetarium's agent interface: a STDIO MCP server with bounded search and detail tools, owner-data
write tools (collections, tags) and session-gated setup tools. The ranking itself belongs to
[Search](../Search/Search.md). Up: [Notebook](../Notebook.md).

## Systems

- [MCP server](../../Architecture/MCP/MCP%20server.md) (Architecture): runtime, worker, registration,
  verification.
- [MCP tools](MCP%20tools.md): the tool surface, caps and annotations, and what the server never accepts.
- [Agent setup sessions](Agent%20setup%20sessions.md): how an agent can configure an install, and only
  while the user allows it.

## Read first

- Tool contract and client setup: [docs/mcp/README.md](../../../docs/mcp/README.md).
- Agent skills shipped to users: `skills/local-asset-library/` (using the tools) and
  `skills/assetarium-setup/` (setup procedure).
- Decisions: [0005](../../Decisions/0005-embedding-worker-and-prestart.md),
  [0012](../../Decisions/0012-collections-and-tags.md), [0016](../../Decisions/0016-agent-setup.md).
