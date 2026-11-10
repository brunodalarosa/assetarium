---
area: MCP
tags: [system]
code: [setup_agent.status, setup_agent.ask_user, setup_agent.actions, setup_agent.GUIDE, setup_agent.verify_weights, setup_agent.agent_change, setup_agent.notice_id, setup_agent.PROPOSAL_STATES, setup_agent.connections, setup_agent.registrations, setup_core.settings_from_answers, setup_core.confirm_review, setup_core.undo_value, frontend/src/ui/AgentSetup.tsx, frontend/src/ui/SetupReport.tsx, skills/assetarium-setup/SKILL.md, scripts/verify-agent-setup-mcp.py, scripts/verify-agent-setup.py]
verified: 2026-11-01
branch: bugfix/mcp-registration-check
---
# Agent setup sessions

Hub: [MCP](MCP.md). An agent can set up Assetarium for the computer it runs on. There is no session
any more ([decision 0035](../../Decisions/0035-packs-and-variant-groups.md)); the page keeps its
name for links. Start at `setup_agent.py`; it wraps `setup_core`, which holds every setup rule.
Decision: [0031](../../Decisions/0031-setup.md).

## How it works

- **Assetarium leads the conversation.** `status` checks what can be verified (the configured Blender, or the
  first one found, via `setup_core.check_blender`, cached per file identity; runtimes; weights by size) and
  returns `found`, `ask_user` and `GUIDE`. The same guide is in the server instructions and the prompt, since
  not every client has the skill. `actions` orders what is left by `kind`: `user`, `tool` (the agent runs it
  without asking), `install`/`download` (asked one by one, with a size).
- **Answers, not settings.** `apply_setup(answers=…)` goes through `setup_core.settings_from_answers`; derived
  values come back in `implied` with why. The replaced value of each agent change is kept in the setup record
  (`values.<key>.previous`) for the report's Undo (`setup_core.undo_value`).
- **Finishing is the user's.** `finish_setup` sets state `review`; the app opens the report (`SetupReport.tsx`)
  on the next start and when the open panel sees the finish; **Looks good** (`setup_core.confirm_review`) sets
  `completed`.
- Tools are gated by tier, not by a session: read, apply and undo (recorded as the agent's, one
  `setup_changed` notice per day via `notice_id`), propose (the user applies), run (`validate_blender`).
- Values the agent applies are recorded as set by the agent. The Blender path is only ever a
  **proposal** (pending, applied, rejected, superseded or failed) that the user
  applies after a fresh check in their own process.
- While running, a server keeps `data/mcp/connections/<pid>.json`; the app shows "connected" only
  while that process is alive. There is no network listener, and the app never hosts the server.
- If the configuration doesn't load, the server starts in `setup_only` mode with `get_setup_status`
  alone, reporting the fault and the exact fix.
- A client whose entry starts a moved or deleted copy never reaches the server; it only says
  "connection closed". `registrations` reads just the `local_asset_library` entry from the Claude
  Code (user and per-project), Codex and OpenCode settings and judges each one (`ok`, `missing`,
  `other_checkout`, `unrecognized`, `unreadable`) for the app panel, `setup agent check` and
  `doctor`. It never writes them and is never sent to the agent. `LAL_CLIENT_HOME` replaces the
  lookup in tests and verify runs (`tests/conftest.py`), so they never read real settings.

## Rules

- **Weight manifests stay out of the model contracts.** `docs/caption-model.json` and
  `docs/embedding-model.json` bytes feed the overnight contract, the embedding vector identity and the search
  speed test, so the file lists for `verify_weights` live in `docs/*-model-files.json`.
- **Register agents only from the real checkout.** A verify run's panel shows snippets with the
  scratch fixture's paths (`setup_agent.snippets`); one registered at user scope made every agent
  depend on a throwaway folder (`scratch/real-agent-r1`) that later disappeared.
- **The agent never applies a Blender path itself**, and a file that changed after the check is refused.
- Status sent to the agent includes OS, GPU, free disk and Blender paths, never user names,
  environment variables, folder listings or the project path (it may reach a cloud model).

## Related

[Setup core](../Setup%20and%20Engines/Setup%20core.md) · [MCP tools](MCP%20tools.md).
