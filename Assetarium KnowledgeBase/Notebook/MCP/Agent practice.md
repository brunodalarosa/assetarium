---
area: MCP
tags: [system]
code: [agent_practice.py, agent_practice_assets.generate, agent_practice.action, agent_practice.tool, agent_practice.checks, agent_practice.recover, transient.work, mcp_server.Gateway.call, desktop.DesktopBridge.practice_action, frontend/src/ui/TryAgent.tsx, frontend/src/ui/AddFolderWizard.tsx, scripts/verify-agent-practice.py]
verified: 2026-11-02
branch: feature/try-your-agent
---
# Agent practice

Hub: [MCP](MCP.md). **Try your agent** replaces the removed local-model benchmark. Binding:
[decision 0035](../../Decisions/0035-packs-and-variant-groups.md).

## How it works

- The generator (`agent_practice_assets.generate`, also exposed by `scripts/generate-agent-practice.py`)
  creates tiny valid OBJ/PNG packs from scratch. No original assets, Blender, model or download is needed.
- The desktop and separate MCP processes share a UUID-scoped session under `scratch/agent-practice/`.
  Its assets and store are separate from the permanent library. The existing wizard reuses discovery,
  handoff, grouped proposal review and pack progress; practice progress counts verified outcomes.
- `Gateway.call` routes practice folder keys to `agent_practice.tool`, which validates and executes the
  same pack tools. Unscoped pack calls on that connection follow the last practice key; an explicitly
  named ordinary library folder restores normal routing. Expired keys are refused, never treated as
  ordinary sources. `say` accepts an optional `library_folder` so practice speech can be explicitly scoped.
- The same `sources.scan_source` and `sources.aggregate` run on small generated files inside the session
  lock. `transient.work` excludes these calls from permanent session logs and the shared hash cache;
  folder views build synchronously there, so deletion cannot race a background rebuild.
- `checks` reads the real scanned working catalog and resulting pack/card structure. Marking signals
  reviewed does not pass missing organization outcomes. Proposals needing review are never auto-approved.
- Completion, cancellation and normal app close mark the session closing before deleting it, after
  in-flight work exits. Cleanup reviews containment and refuses any symlink/junction. A failure stays
  visible and can be explicitly retried. Startup recovery removes only abandoned sessions, not live ones.
- Results are returned into UI memory; no product report is saved. The final screen retains unresolved
  outcomes, waiting-proposal counts and refused-call reasons until dismissed. External agent chat history
  is outside Assetarium's cleanup.

## Verification

`tests/test_agent_practice.py` covers outcomes, actual STDIO calls from a separate process, owner review,
late calls, cancellation, recovery, cleanup failure, hash/log isolation and app shutdown. The real desktop
check is `scripts/verify-agent-practice.py`; its screenshots/reports are development evidence under `data/gui/`,
separate from the disposable product session.
