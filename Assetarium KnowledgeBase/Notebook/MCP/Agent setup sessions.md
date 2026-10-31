---
area: MCP
tags: [system]
code: [setup_agent.agent_change, setup_agent.notice_id, setup_agent.PROPOSAL_STATES, setup_agent.connections, setup_core.py, frontend/src/ui/AgentSetup.tsx, skills/assetarium-setup/SKILL.md, scripts/verify-agent-setup-mcp.py, scripts/verify-agent-setup.py]
verified: 2026-10-31
branch: feature/library-view
---
# Agent setup sessions

Hub: [MCP](MCP.md). An agent can set up Assetarium for the computer it runs on. There is no session
any more ([decision 0024](../../Decisions/0024-pack-profiles-and-variant-groups.md)); the page keeps its
name for links. Start at `setup_agent.py`; it wraps `setup_core`, which holds every setup rule.
Decision: [0016](../../Decisions/0016-agent-setup.md).

## How it works

- Tools are gated by tier, not by a session: read, apply and undo (recorded as the agent's, one
  `setup_changed` notice per day via `notice_id`), propose (the user applies), run (`validate_blender`).
- Values the agent applies are recorded as set by the agent. The Blender path is only ever a
  **proposal** (`PROPOSAL_STATES`: pending, applied, rejected, superseded, failed) that the user
  applies after a fresh check in their own process.
- While running, a server keeps `data/mcp/connections/<pid>.json`; the app shows "connected" only
  while that process is alive. There is no network listener, and the app never hosts the server.
- If the configuration doesn't load, the server starts in `setup_only` mode with `get_setup_status`
  alone, reporting the fault and the exact fix.

## Rules

- **The agent never applies a Blender path itself**, and a file that changed after the check is refused.
- Status sent to the agent includes OS, GPU, free disk and Blender paths, never user names,
  environment variables, folder listings or the project path (it may reach a cloud model).

## Related

[Setup core](../Setup%20and%20Engines/Setup%20core.md) · [MCP tools](MCP%20tools.md).
