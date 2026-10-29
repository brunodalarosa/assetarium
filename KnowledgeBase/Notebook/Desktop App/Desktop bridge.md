---
area: Desktop App
tags: [system]
code: [desktop.DesktopBridge, desktop.DesktopBridge._present, desktop.DesktopBridge._wait, desktop.create_window, desktop.page_html, desktop_service.DesktopService, frontend/src/app/api.ts, frontend/src/app/store.ts]
verified: 2026-10-28
branch: feature/library-view
---
# Desktop bridge

Hub: [Desktop App](Desktop%20App.md). `desktop.DesktopBridge` is the pywebview `js_api`: every public
method is callable from the page as `window.pywebview.api.<name>`. Types for the page side are in
`frontend/src/app/api.ts`.

## How it works

- pywebview runs bridge methods on its own threads. The bridge owns one asyncio loop on the
  `asset-gateway` thread; methods hand work to it (`_wait` → `run_coroutine_threadsafe`), and
  presentation work runs through `_present` in a worker thread.
- `create_window` / `page_html` inline the built `ui/build/app.css` and `app.js` plus
  `ui/interactive-preview.js` into `ui/index.html`, and apply the saved theme before first paint.
- The launch `Config` is frozen for the window's life; anything saved later (for example Blender) is
  read through helpers such as `config.with_saved_blender`.

## Rules

- **New features follow one shape**: backend logic in the owning module, exposed as a bridge method
  that returns a plain JSON-able dict with `status` / `reason` on faults, then UI in `frontend/src`.
- **The window never sends paths**: bridge methods take asset IDs, source keys and opaque tickets.
- `DesktopService` is read-only presentation; ranking, filtering and availability stay in the shared
  search code ([Retrieval](../Search/Retrieval.md)).
- **Startup never renders or loads a model**; the embedding worker may pre-load its libraries only (decision 0005).

## Related

[Frontend build](Frontend%20build.md) · [Desktop app design](../../Architecture/Desktop%20App/Desktop%20app%20design.md).
