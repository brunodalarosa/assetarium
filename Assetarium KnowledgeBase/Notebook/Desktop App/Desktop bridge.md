---
area: Desktop App
tags: [system]
code: [desktop.DesktopBridge, desktop.DesktopBridge._present, desktop.DesktopBridge._wait, desktop.create_window, desktop.page_html, desktop_service.DesktopService, frontend/src/app/api.ts, frontend/src/app/store.ts]
verified: 2026-10-31
branch: feature/library-view
---
# Desktop bridge

Hub: [Desktop App](Desktop%20App.md). `desktop.DesktopBridge` is the pywebview `js_api`: every public
method is callable from the page as `window.pywebview.api.<name>`. Types for the page side are in
`frontend/src/app/api.ts`.

## How it works

- pywebview runs bridge methods on its own threads. The bridge owns one asyncio loop on the
  `asset-gateway` thread; methods hand work to it (`_wait` → `run_coroutine_threadsafe`), and
  presentation work runs through `_present` in a worker thread of a pool of eight (`asset-present`).
- `_present(..., shared=True)` marks a read-only call: identical calls in flight (same operation and
  arguments) share one run. `_wait` gives up after 110 s but cannot stop the thread, so without sharing every
  poll used to start one more copy of a slow read.
- `desktop.main` ends with `os._exit` after `_close`: closing never waits for a read still running in the
  pool (the loop drops its executor with `shutdown(wait=False, cancel_futures=True)`).
- `create_window` / `page_html` inline the built `ui/build/app.css` and `app.js` plus
  `ui/interactive-preview.js` into `ui/index.html`, and apply the saved theme before first paint.
- The launch `Config` is frozen for the window's life; anything saved later (for example Blender) is
  read through helpers such as `config.with_saved_blender`.

## Rules

- **Every bridge call is logged once in `_present`** (debug, info when slow, warning when refused; see
  [Session logs](../Platform%20and%20Storage/Session%20logs.md)). Don't add per-method log lines; give a new poll a
  stable name so its repeats collapse.
- **A read the window polls is bounded by its page, not the library**: read folder views or SQL columns
  ([Sources](../Sources%20and%20Catalog/Sources.md) → Folder views), never whole catalogs, and pass
  `shared=True`. A bigger library may mean a longer wait, never more memory.

- **New features follow one shape**: backend logic in the owning module, exposed as a bridge method
  that returns a plain JSON-able dict with `status` / `reason` on faults, then UI in `frontend/src`.
- **The window never sends paths**: bridge methods take asset IDs, source keys and opaque tickets.
- `DesktopService` is read-only presentation; ranking, filtering and availability stay in the shared
  search code ([Retrieval](../Search/Retrieval.md)).
- **Startup never renders or loads a model**; the embedding worker may pre-load its libraries only (decision 0005).
- **The launch scan is the quiet check** (decision 0027): `store.start` calls `source_action('check')`, which starts
  the all-folder scan with `quiet` in `source-operation.json`; `scan_all` adds `changes` (new/changed/removed).
  The activity indicator shows "Checking for changes" for it, `announceCheck` toasts only when something changed,
  and `watchChanges` reloads the tree and the shown folder during scans only when the sources revision moves
  (`onlyScans`); identical answers keep their state, so cards don't re-render. Proof: `scripts/verify-quiet-startup.py`.

## Gotchas

- **Eight bridge names are built at run time.** `sourceApi` in `frontend/src/app/api.ts` calls
  `bridge["source_" + name]` (asset, thumbnail, image_view, reveal and the four `preview_*` calls), so a text
  search for `source_thumbnail` finds no caller, and pytest passes without them. Run a `verify-*.py` check
  before deleting a `DesktopBridge` method.

## Related

[Frontend build](Frontend%20build.md) · [Desktop app design](../../Architecture/Desktop%20App/Desktop%20app%20design.md).
