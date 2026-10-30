---
area: Setup and Engines
tags: [system]
code: [setup_core.first_run, setup_core.setup_state, setup_core.blender_change, inspection.discover_blender, config.with_saved_blender, frontend/src/ui/SetupWizard.tsx, frontend/src/ui/BlenderPicker.tsx, scripts/verify-setup-wizard.py]
verified: 2026-10-28
branch: feature/library-view
---
# Setup core

Hub: [Setup and Engines](Setup%20and%20Engines.md). `setup_core.py` holds every setup rule as
GUI-free functions: the environment report, Blender discovery and checks, the minimal
`config.local.toml` writer, the first-run rule and `data/library/setup.json` (with who set each
value). The desktop wizard, `local-assets setup` and the agent tools only wrap it. Decision:
[0014](../../Decisions/0014-setup-wizard.md).

## How it works

- **First-run rule** (`first_run`): the wizard opens by itself only when there is no setup record, no
  saved settings and no registered source. A registry that exists but can't be read counts as
  "not fresh".
- Nothing is saved until the review step's **Save**; each part then reports its own result, so a
  failed Blender write keeps the other settings.
- Blender lives in `config.local.toml` (`[tools].blender`); `config.local.toml` overrides
  `config.example.toml` (decision 0001). The tracked example stays neutral.

## Rules

- **Add setup logic to `setup_core`, not to a surface**, so app, CLI and agent stay identical.
- **Changing the saved Blender re-renders finished 3D previews** (its path and mtime are
  inspection fingerprint inputs), so the surfaces ask for confirmation first.
- Only the already saved Blender is "unchanged"; a discovered Blender is written after its check
  (changed 2026-10-28).

## Gotchas

- `inspection.discover_blender` lets processing run without a saved Blender, but the speed test and
  render pool need the saved one, which is how a fresh clone used to end up with a blocked speed test.

## Related

[Agent setup sessions](../MCP/Agent%20setup%20sessions.md) · [Blender rendering](../Processing/Blender%20rendering.md).
