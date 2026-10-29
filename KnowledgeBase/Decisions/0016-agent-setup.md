---
tags: [decision]
decided: 2026-10-25
---
# 0016 — Agent-assisted setup through MCP: session gate, proposals, connection signal

**Decision (owner, October 25, 2026).** An AI agent connected through the existing STDIO MCP
server can set Assetarium up, as a second front end over `setup_core`
([decision 0014](0014-setup-wizard.md)); `setup_agent.py` wraps it and holds no setup rule.
The Welcome page offers two equal paths — **Set up with my agent** and **Set it up yourself** —
and Settings → General offers **Run setup with my agent**.

- **Tools.** `get_setup_status` (read only, always available), `validate_blender`,
  `apply_setup`, `propose_setup` and `finish_setup`, declared with the usual schemas,
  annotations, bounded responses (16,000 characters) and `calls.jsonl` audit lines. The
  server also offers the prompt `set_up_assetarium` and, while setup is not completed, a
  setup hint in its instructions. A new, explicitly user-invoked skill
  `skills/assetarium-setup/` carries the procedure; `skills/local-asset-library` still forbids
  setup work as a side task.
- **Session gate.** Every tool except `get_setup_status` refuses unless a setup session is open
  (`data/library/setup-agent.json`). Only a user gesture opens one: the app's buttons, or on
  Linux (no app, [decision 0013](0013-platform-support.md)) `local-assets setup agent` in an
  interactive terminal (no flag bypasses this). Sessions last **60 minutes** and can be ended
  early. No tool argument opens, extends or skips it. `validate_blender` is gated too because
  it runs a program.
- **What agents apply directly.** Storage budget, processing formats, description batch size,
  descriptions on/off, the description engine and its local model server, and the
  target-engine hint — validated by the same functions as the wizard (the server stays
  loopback-only) and recorded as `set_by: agent`. Choosing the local server returns setup's
  Test connection result, which only lists models. The owner wants agents to find a setup
  that works on the computer in front of them, including a local model server for non-NVIDIA
  GPUs; they run installs with their own shell and only with the user's approval.
- **Proposal rule.** The Blender executable, the one program setup saves, is only proposed:
  `propose_setup` accepts a path `validate_blender` passed in the same server process (file
  named `blender.exe`/`blender`, a regular file; nothing else is ever run) and stores it with
  its file identity. Only the user's **Apply** (app card, or `local-assets setup agent
  proposals`) saves it: Apply re-runs the check in that process, refuses a file that changed,
  keeps the re-render confirmation, and records `set_by: agent, approved_by: user`.
  **Reject** saves nothing. A newer proposal supersedes a pending one. `finish_setup` refuses
  while one is pending.
- **Notices.** Each session raises one `setup_changed` notice listing what the agent changed
  (and that it finished); each pending proposal raises a `setup_proposal` notice that
  disappears when decided. Both lead back to the agent panel. The final review shows who set
  each value; saving it records as the user's only what the user changed.
- **Connection signal.** The server writes `data/mcp/connections/<pid>.json` (pid, start time,
  run id, mode, the client name from its initialize request once known) and removes it on
  exit. The app counts a record as connected only while that process is alive
  (`gpu_queue.process_alive`); stale records are ignored and pruned by the next server. There
  is no network listener, and the app never claims that "the server is running": it does not
  host it.
- **What status reveals.** OS name, GPU names, VRAM and compute capability, free and total disk,
  Blender candidate and configured paths, engine and search readiness with the repo-relative
  commands for what is missing, current settings and who set them, setup and session state,
  proposals and recommendations. Never user names, environment variables, directory listings,
  the project path or asset records. The tool description and the Welcome panel say that a
  cloud model receives it.
- **Degraded mode.** When the configuration does not load, the server still starts and offers
  only `get_setup_status`, which returns the fault, the file and the exact fix; everything else
  is refused and nothing changes.

**Why.** Supporting many environments means setup is not "download and run"; agents with a
shell can resolve what the wizard can only describe. A prompt-injected or over-eager agent is
the central risk, so the guards live in the backend, not the UI ([decision 0011](0011-react-desktop-ui.md)).

**Keep true.** Writes stay behind a session only a user gesture opens; the executable path is
applied only by the user after a fresh check; status reveals only the list above. Setup tools
never add sources, scan, process, generate descriptions, install, download or delete. The gate
protects against tool calls, not against an agent the user gave unrestricted shell access (such
an agent could edit `config.local.toml` itself); say so rather than claiming more. Allowlisting
clients need the new tool names in `enabled_tools`.
