---
area: Platform and Storage
tags: [system]
code: [setup_core.save_setup, setup_agent.apply_setup, search_check.record, sources.include_samples, engines.search_readiness, frontend/src/ui/SetupWizard.tsx]
verified: 2026-11-01
branch: feature/library-view
---
# Core features

Hub: [Platform and Storage](Platform%20and%20Storage.md). What must work right after setup, with nothing left for the
user to run ([decision 0026](../../Decisions/0026-setup-leaves-core-features-working.md)). Optional features are in
[Optional features](Optional%20features.md).

## How it works

| Core feature | What it needs | Provided by |
| --- | --- | --- |
| Library (scan, browse, packs) | A library folder | Setup's **Include sample assets** (checked by default), then Add library folder |
| Previews (3D models) | Blender | Setup's Blender step (discovered, checked, saved) |
| Previews (images) | Nothing extra | Always |
| Search by keyword, names, filters | Nothing extra | Always |
| Search by description and image | Search runtime, model weights, the search check | Setup lists runtime and weights with Copy; the **search check** runs after Save, from **Run check**, or by itself in Make previews |
| Agents (MCP) | The MCP server and, when the user wants one, a connected agent | Ready in every install; setup's **Connect your agent** step; agent-assisted setup is connected already |

## Rules

- **Never end setup with a step the user must discover.** If a requirement cannot be met during setup (no library
  yet, a runtime still downloading), the feature fulfils it by itself later.
- An installer or a download can't run inside the app: show it in a `CommandBlock` with Copy (P3), and say what it
  unlocks.
- Adding a core feature means adding its row here and its setup path, in the app wizard, the CLI wizard and the
  agent-assisted setup together.

## Related

[Optional features](Optional%20features.md) · [Formats](Formats.md) · [Runtimes](Runtimes.md) ·
Decisions: [0014](../../Decisions/0014-setup-wizard.md), [0016](../../Decisions/0016-agent-setup.md),
[0026](../../Decisions/0026-setup-leaves-core-features-working.md).
