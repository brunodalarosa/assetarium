---
area: Desktop App
tags: [system]
code: [frontend/src/ui/Inspector.tsx, frontend/src/app/store.ts, settings.INSPECTOR_SECTIONS, settings.save_interface_settings, scripts/verify-inspector-layout.py, blender_worker]
verified: 2026-11-08
branch: develop
---
# Asset inspector

Hub: [Desktop App](Desktop%20App.md). The right sidebar that inspects one asset: `Inspector` in
`frontend/src/ui/Inspector.tsx`. Decision: [0011](../../Decisions/0011-react-desktop-ui.md).

## How it works

- One scroll: header, fault line (only when something is faulty), preview, fact chips, variants or
  collection entry, description, tags, then the collapsible File & license, Geometry (Image for images)
  and Processing record sections.
- Collapsible sections remember their state app-wide in `interface.json` (`inspector_sections`, names in
  `settings.INSPECTOR_SECTIONS`). The boot payload delivers them and `store.setInspectorSection` saves a
  change. All sections are closed by default.

## Gotchas

- **Collapsed content is not in the DOM.** Verify scripts must open a section with
  `lal.setInspectorSection(name, true)` before reading its text. That call persists, so a script that runs
  on the real library restores the previous state afterwards.
- Inspection technical data stores animation clips as `animation_clips` (`blender_worker`); a field called
  `actions` never exists there.

## Related

[Verify harness](Verify%20harness.md), `scripts/verify-inspector-layout.py` (checks layout, remembered
sections and restart). Docs: the inspector section of [docs/gui/README.md](../../../docs/gui/README.md).
