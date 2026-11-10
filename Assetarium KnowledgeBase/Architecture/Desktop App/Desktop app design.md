---
tags: [architecture]
level: system
parent: "[Architecture](../Architecture.md)"
status: draft
code: [desktop.DesktopBridge, desktop_service.DesktopService, desktop.page_html, mcp_server.Gateway, logs.py, frontend/src/ui/Loading.tsx, frontend/src/ui/Activity.tsx, tests/test_ui_encoding.py, scripts/gui_harness.py]
verified: 2026-11-10
branch: feature/audit-simplify
---
# Desktop app design

> The Windows desktop app is a pywebview/WebView2 window around the React bundle in `ui/build/`. It is a
> presentation layer: every search, filter and availability rule lives in the shared backend, never in the
> window. Rewritten on 2026-11-10; the milestone reports it used to carry are in git (commit `af02e91`).

Up: [Architecture](../Architecture.md) · Where in code: [Desktop App](../../Notebook/Desktop%20App/Desktop%20App.md) ·
User guide: [docs/gui/README.md](../../../docs/gui/README.md) · Interactive preview: [3D preview](../../Notebook/Desktop%20App/3D%20preview.md) ·
Down: [Design language](Design%20language.md) (design principles) ·
Binding rules: [0011](../../Decisions/0011-react-desktop-ui.md) (the React UI),
[0027](../../Decisions/0027-saved-catalog-first-and-fast-scan.md) (startup and change tokens).

## Layers

```
        React UI  (frontend/src → ui/build)
                  │  window.pywebview.api
                  ▼
        DesktopBridge          (1)
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
   DesktopService      owning modules   (2)
        │
        ▼
   Gateway → AssetService → SearchEngine  (3)
```

1. `desktop.DesktopBridge` is the only thing the page can call. Each method returns plain JSON-able data,
   with `status` and `reason` on a fault ([Desktop bridge](../../Notebook/Desktop%20App/Desktop%20bridge.md)).
2. Feature logic stays in its owning module (`sources`, `settings`, `processing_queue`, `asset_collections`…);
   the bridge only forwards. `DesktopService` adds read-only browsing and evidence presentation.
3. Search goes through the same `Gateway`, `AssetService` and `SearchEngine` the MCP server uses. The app has
   no second ranking, filter, availability or validation policy.

## Threads and freshness

- The GUI thread only renders the local bundle. An app-owned background loop handles gateway calls; folder
  and detail operations run apart from the serialized GPU queue.
- The page polls one cheap call, `changes()`, every 1.5 s and reloads only the data whose token changed.
- Every request carries a generation, so a slow answer or preview can never replace a newer view.
- The presentation lock covers `DesktopService` state only; settings, library folders and the poll run
  without it.

## What the page may load

The shell is one local HTML document with the bundle inlined (`desktop.page_html`). Its content security
policy blocks external resources, network connections and uploads; the pinned pywebview bridge needs inline
script. The interactive 3D preview runs in a sandboxed frame with an opaque origin: it gets bundled scripts,
data URLs and in-memory blob URLs only, and cannot reach the bridge or the parent document. Asset text is
inserted as text, never as HTML. There is no HTTP listener.

## Models and the worker

Browsing loads no model. At launch the app starts one private search worker that loads Python libraries
only; the first semantic search loads the model, and it unloads after ten idle minutes or as soon as a
processing batch needs the GPU ([Search embedders](../../Notebook/Search/Search%20embedders.md)). A semantic
runtime or query fault is shown as a fault: never a keyword result in its place, never a silent worker
restart. Closing the window sends EOF to the worker; if a pending load cannot close in five seconds, only
that private process tree is ended. The app never stops processes it did not start.

## Loading states

One small language (`ui/Loading.tsx`, `ui/Activity.tsx`, the loading block of `styles.css`), so a slow answer
never looks like an empty or broken view:

- **Ghosts** stand where content of a known shape will appear (cards, cover tiles, thumbnails, the
  inspector, counts). They share one shimmer clock and are replaced in place. They appear only after 150 ms
  and then stay at least 400 ms, so quick loads show nothing and slow ones do not flicker. They never imply
  an outcome: an empty state appears only after an answer.
- **Refreshing** content stays on screen: while a search replaces results the cards dim and a sheen crosses
  the search bar. Background refreshes (agent edits, revisiting a tab) do not dim.
- **Background work** is a small pill left of the bell with the main task ("Scanning", "Processing 42%",
  "Loading search model") and "+N" for the rest. It appears after 450 ms of continuous work and turns into a
  check before leaving. Clicking it lists every task; a processing task opens Asset processing.
- **One comet spinner** remains for small in-place waits (a button, a field).
- A fault always replaces a ghost with its recorded reason. "Preview pending" and "Preview fault" keep their
  own look and are never shown as loading. Screen readers get the same status (`aria-busy`, live regions);
  reduced motion keeps ghosts static and stops every loop.

## Evidence the detail view keeps apart

Asset detail separates measured geometry (with the inspected file and hash), what the description model
observed, suggested uses, the owner's corrections and review, license evidence, known dependencies and
recorded faults. Physical scale stays unknown; other formats of an asset stay uninspected unless evidence
says otherwise; listed armatures and actions do not prove animation. Usable partial assets stay visible, and
an asset that became unavailable keeps its name, reason and earlier evidence. Description findings follow
[Caption severity](../Processing/Caption%20severity.md): notes in the detail, a badge for warnings, no badge
for a missing or failed optional description.

## Runtime

The app runs in the MCP environment (`runtime/mcp/`: pywebview, pythonnet and clr-loader, pinned in its
lock) on the system WebView2, which is checked explicitly; no other renderer is accepted and no browser is
bundled. Startup never installs anything and never runs a model. Rebuilding the environment is the
wrapper's job (`scripts/mcp-runtime.ps1 sync --locked --project runtime/mcp`), under
[Storage discipline](../../Notebook/Platform%20and%20Storage/Storage%20discipline.md).

## Files the app writes

| Where | What |
| --- | --- |
| `cache/gui-webview/<run-id>/` | The window's browser profile. On close the exact folder is checked for links before it is removed; a locked or unexpected folder is left and recorded, never retried |
| `logs/` | One readable session log per start, shared by every process of that session ([logs](../../../docs/cli.md#logs)) |
| `data/gui/startup-faults.jsonl` | Startup faults, also shown in a dialog |
| `data/gui/runs/<run-id>/` | Per-call evidence and timing, pruned by the retention rule |

Browser profiles hold no evidence. Reports and screenshots from verify scripts go under `data/gui/<run-name>/`.

## Text encoding

App-owned UI text is real UTF-8 (`…`, `·`, `→`), never mojibake. Windows' default text encoding can corrupt
it during an edit, so reads and writes name UTF-8 explicitly. `tests/test_ui_encoding.py` checks every
app-owned UI file and the packaged HTML.

## Verification

Behavior the owner sees is checked in the real WebView2 window with small synthetic assets, through
`window.lal` ([Verify harness](../../Notebook/Desktop%20App/Verify%20harness.md)). Each run takes a new
`--run-name` and refuses to overwrite an earlier one:

```powershell
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/verify-asset-sources.py --run-name <unique-name>
```

These runs are technical evidence. The owner's judgment of usability, look and accessibility is separate and
is never claimed by a passing script.
