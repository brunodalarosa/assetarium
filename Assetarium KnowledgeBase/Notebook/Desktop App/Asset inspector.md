---
area: Desktop App
tags: [system]
code: [frontend/src/ui/Inspector.tsx, frontend/src/app/store.ts, settings.INSPECTOR_SECTIONS, settings.save_interface_settings, scripts/verify-inspector-layout.py, blender_worker, desktop_service.DesktopService.description_edit, desktop.DesktopBridge.edit_description, scripts/verify-description-edit.py]
verified: 2026-11-09
branch: develop
---
# Asset inspector

Hub: [Desktop App](Desktop%20App.md). The right sidebar that inspects one asset: `Inspector` in
`frontend/src/ui/Inspector.tsx`. Decision: [0011](../../Decisions/0011-react-desktop-ui.md).

## How it works

- One scroll: header, fault line (only when something is faulty), preview, fact chips, variants or
  collection entry, description, tags, then the collapsible File & license, Geometry (Image for images)
  and Processing record sections. A model's preview is the live 3D view ([3D preview](3D%20preview.md)).
- While the inspector shows an asset, arrow keys in a result grid select the card they move to
  (`AssetGrid` `onKeyDown`); with the panel hidden they only move focus.
- **The description section is one line and one action per state** (`description_edit` in the detail payload:
  `none`, `queued`, `running`, `failed`, `generated`, `edited`, `not_set_up`, `unavailable`). Generate and Try
  again queue one asset (`store.describeAsset` → `queue_add` with `asset_ids` and `mode`); Edit saves through
  `DesktopBridge.edit_description` and queues the edit's search update. There is no approval step; the stored
  `caption_review` / `artistic_suitability` values are kept and not shown.
- Actions and the change poll refresh only the description fields (`store.refreshDescription` → `detail.description`),
  never the whole detail: a new `result` would mount the live 3D preview again.
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
sections and restart), `scripts/verify-description-edit.py` (every description state and its action). Docs: the inspector section of [docs/gui/README.md](../../../docs/gui/README.md).
