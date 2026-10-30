---
area: Desktop App
tags: [hub]
code: [desktop.DesktopBridge, desktop.create_window, desktop.page_html, desktop_service.py, frontend/src, src/local_asset_library/ui, scripts/gui_harness.py]
---
# Desktop App

The Windows desktop app: a pywebview/WebView2 window, a Python bridge and a React UI built into a
committed bundle. Linux has no desktop app yet (decision 0013). Up: [Notebook](../Notebook.md).

## Systems

- [Desktop bridge](Desktop%20bridge.md): `DesktopBridge`, its gateway loop and the shape of bridge methods.
- [Frontend build](Frontend%20build.md): React source, the committed `ui/build/` bundle, UTF-8 rules.
- [Verify harness](Verify%20harness.md): real WebView2 checks driven through `window.lal`.
- [3D preview](3D%20preview.md): the sandboxed Online 3D Viewer frame.
- [Collections and tags](../../Architecture/Desktop%20App/Collections%20and%20tags.md) *(gap)*:
  `asset_collections.py`, `asset_tags.py`, `collection_export.py`.

## Read first

- [Desktop app design](../../Architecture/Desktop%20App/Desktop%20app%20design.md) (Architecture) and the user guide
  [docs/gui/README.md](../../../docs/gui/README.md).
- Decisions: [0011](../../Decisions/0011-react-desktop-ui.md), [0012](../../Decisions/0012-collections-and-tags.md),
  [0014](../../Decisions/0014-setup-wizard.md).
- `AGENTS.md` → User experience: keep actions clear, never offer an action that can't resolve the
  displayed state, keep pending work and recorded failures apart.
