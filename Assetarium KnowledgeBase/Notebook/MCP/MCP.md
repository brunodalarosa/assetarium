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
- [Agent practice](Agent%20practice.md): "Try your agent", a disposable import through the connected agent and Library review flow.
- [Agent setup sessions](Agent%20setup%20sessions.md): how an agent can configure an install, and only
  while the user allows it.

## Read first

- Tool contract and client setup: [docs/mcp/README.md](../../../docs/mcp/README.md).
- Agent skills shipped to users: `skills/local-asset-library/` (using the tools) and
  `skills/assetarium-setup/` (setup procedure).
- The worker: [Search embedders](../Search/Search%20embedders.md).
- Decisions: [0029](../../Decisions/0029-agent-trust.md),
  [0036](../../Decisions/0036-collections-and-tags.md), [0031](../../Decisions/0031-setup.md).
