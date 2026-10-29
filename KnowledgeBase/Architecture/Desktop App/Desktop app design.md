---
tags: [architecture]
level: system
parent: "[Architecture](../Architecture.md)"
status: draft
code: [desktop.DesktopBridge, desktop_service.DesktopService, desktop.page_html, frontend/src/ui/Loading.tsx, frontend/src/ui/Activity.tsx, tests/test_ui_encoding.py, scripts/gui_harness.py]
verified:
branch:
---
# Desktop app design

> The Windows desktop app is a pywebview/WebView2 window around the React bundle in `ui/build/`.
> It is a read-mostly presentation layer: every search, filter and availability rule lives in the
> shared backend (`Gateway.call` / `AssetService` / `SearchEngine`), never in the window.

Up: [Architecture](../Architecture.md) · Where in code: [Desktop App](../../Notebook/Desktop%20App/Desktop%20App.md) ·
User guide: [docs/gui/README.md](../../../docs/gui/README.md) · Interactive preview: [3D preview](../../Notebook/Desktop%20App/3D%20preview.md)

Moved from `docs/gui/README.md` on 2026-10-28; not yet re-verified against the code line by line.

## Loading states

One small, consistent language (`frontend/src/ui/Loading.tsx`, `ui/Activity.tsx`, the loading
block of `styles.css`), so a slow answer never looks like an empty or broken view:

- *Ghosts* stand where content of a known shape will appear: asset and collection
  cards, cover tiles and thumbnails, inspection, the open collection's name,
  description and count, source cards and counts in Asset processing and Settings,
  the collection flyout and tags. They share one shimmer clock, so the light crosses
  a grid as one diagonal wave, and enter with a short stagger. Real content
  replaces them in place (cards rise in, images resolve from a soft blur). Ghosts
  appear only after 150 ms and then stay at least 400 ms, so quick loads show
  nothing and slow ones do not flicker. They never imply an outcome: the empty
  states ("No collections yet", "No asset sources yet") appear only after an answer.
- *Refreshing* content stays on screen: while a search replaces results the cards
  dim and a light sheen sweeps across the search bar. Background refreshes
  (agent edits, revisiting a tab) do not dim.
- *Background work* shows as a small pill left of the bell: an orbiting comet, the
  main task ("Opening library", "Preparing search", "Loading search model",
  "Scanning", "Processing 42%", "Describing", "Previews 24") and "+N" for others.
  It appears only after 450 ms of continuous work, morphs as tasks change, and
  turns into a check before leaving. Clicking it lists every task with a progress
  bar (or an indeterminate sweep); source operations open Asset processing at
  that source. It replaced the bell's pulsing dot.
- One comet spinner remains for small in-place waits (a button's action, a field).
  Faults always replace ghosts with the recorded reason; "Preview pending" and
  "Preview fault" keep their own look and are never shown as loading. Screen
  readers get the same status text as before (`aria-busy`, live regions, hidden
  "Loading …" labels). Reduced motion keeps ghosts static and stops every loop.

Native check: `scripts/verify-loading-states.py --run-name <unique-name>` holds
bridge calls in the page and captures each state in both themes.

## UI text encoding checks

Keep UI source reads and writes explicitly UTF-8; Windows' default Python text
encoding can otherwise corrupt punctuation and icons during edits. Run
`python -m pytest tests/test_ui_encoding.py` through the existing MCP runtime
wrapper. It checks every app-owned UI file and the actual packaged desktop HTML,
including separators, loading ellipses, pagination, accessibility text and icons.
The search, source-navigation and interactive-preview native harnesses also check
DOM text and accessible attributes whenever they capture a screen. The preview
fixture includes accented and non-Latin asset names. The encoding-fix run passed
17 focused tests and 20 native snapshots; evidence is in
`data/gui/encoding-fix-summary.json`. It caught the original corrupted script and
found no remaining corruption in the 189 tracked text files audited.

## Evidence and fault boundaries

Detail separates measured geometry and inspected-file/hash evidence, provisional
generated visual observations, suggested uses, owner caption/artistic review,
license evidence, known dependencies, processing evidence and faults. Live owner
overlays are read without modification; a null suggested-use overlay preserves
generated suggestions. Physical scale remains unknown. Alternate formats remain
uninspected unless the existing evidence says otherwise. Enumerated armatures and
actions do not prove animation behavior; known dependency references do not prove
complete binary/alternate packaging. License unknowns remain explicit.

Historical geometry, texture, caption and preview faults are preserved. Usable
partial assets remain visible. Newly unavailable browse items retain their names,
fault reason and historical evidence, while search keeps its existing exclusions.
Repeated faulty preview requests within the session retain the first fault, and
semantic runtime/query faults never trigger a keyword fallback or worker restart.
Bruno clarified that the no-retry rule applies to asset investigation/export;
app and test-harness issues can be corrected and reverified.

## Runtime and ownership

The app uses pywebview **6.2.1**, pythonnet **3.2.1**, clr-loader **0.3.1** and
their locked supporting packages in the existing MCP environment. Windows also
installed bottle **0.13.4** and proxy-tools **0.1.0**. Existing package versions
were preserved. This PC already provides WebView2 **154.0.4258.62** and .NET
Framework **4.8.09221**. WebView2 is checked explicitly; no legacy renderer is
accepted. No Qt/CEF, another environment, bundled browser or installer was added.

If this environment deliberately needs reconstruction, use the existing wrapper:

```powershell
.\scripts\mcp-runtime.ps1 sync --locked --project runtime/mcp
```

Follow [Storage discipline](../../Notebook/Platform%20and%20Storage/Storage%20discipline.md), including fresh before/after receipts, shared `cache/uv`,
hard links, immutable installed dependencies and cache cleanup after verification.
The launcher never performs this command. See the official
[installation](https://pywebview.flowrl.com/guide/installation),
[threading](https://pywebview.flowrl.com/guide/usage) and
[renderer](https://pywebview.flowrl.com/guide/web_engine.html) documentation.

The shared `Gateway.call`/`AssetService`/`SearchEngine` path handles searches for
both interfaces. `DesktopService` adds read-only browsing and evidence presentation;
it does not implement another ranking, filter, availability or validation policy.
The GUI thread renders local bundled HTML/CSS/JavaScript. An app-owned background
loop handles gateway calls, and source/detail operations run separately from the
serialized GPU queue. Request generations prevent obsolete results or previews
from replacing newer views. The pinned pywebview bridge requires local inline
script/evaluation; CSP blocks external resources, network connections and uploads.
An opaque-origin, scripts-only sandbox frame is allowed for interactive 3D;
its only resources are bundled scripts, data URLs and in-memory blob URLs. It
cannot access the desktop bridge or the parent document. No HTTP listener is added.
Asset text is inserted as text rather than executable HTML.

Browsing does not load a model. The app starts one private embedding worker in
the background when it opens; the worker loads its Python libraries only (no
model, no GPU). The first semantic query loads the model (offline shared weights
in `[storage].models`), and the worker unloads it after ten idle minutes
or when a processing batch needs the GPU. The worker only returns query vectors:
vectors, verification and ranking stay in the app process (decision 0005).
Heartbeats every five seconds separate a slow first load from a stopped worker,
which is retained as a fault after 90 silent seconds. MCP and other
GUI instances have their own workers and can contend for GPU memory. This app
does not manage or terminate unrelated processes. Closing sends EOF to its worker;
if a pending load cannot close in five seconds, only that private Windows process
tree is terminated. Actual idle worker shutdown and pending-load close were checked.

Each window owns a unique browser profile under `cache/gui-webview/<run-id>`.
The closing handler reviews the exact target and all descendants for links before
allowing renderer cleanup. Unexpected links retain the directory. A locked browser
cache cleanup can also leave files; the app records that separately without an
automatic cleanup retry. Browser caches contain no asset evidence. Reports, fault
logs and actual screenshots remain outside them under ignored `data/gui/`.

Startup faults show an error dialog and persist in `data/gui/startup-faults.jsonl`
and `logs/gui.log`. Per-call evidence, timing and lifecycle are under
`data/gui/runs/<run-id>/`; worker diagnostics are in `logs/gui-worker.log`.

## Verification and remaining scope

Caption review now distinguishes minor notes, descriptive warnings and actual
failed/unusable captions. Notes appear in asset detail; warnings have a card
badge. Missing or failed descriptions have no card badge (they are optional);
asset detail explains them and keeps the recorded fault. Original review evidence remains expandable, and source or
preview faults retain their existing presentation. See
[Caption severity](../Processing/Caption%20severity.md) for the shared desktop/agent
classification and verification evidence.

Actual results, timings, storage and fault receipts are summarized in
[`docs/gui/verification.json`](../../../docs/gui/verification.json) and the frozen [progress journal](../../../docs/history/progress-2026-10.md). Modest actual WebView2 captures are under
`data/gui/final-window/`. Focused checks use synthetic fixtures; no real asset is
damaged and no full preprocessing is repeated. Verification scripts refuse to
overwrite prior runs; select a fresh `--run-name` for a deliberately requested check.

```powershell
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/gui-unit-checks.py --run-name new-unit-run
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/verify-gui.py --run-name new-window-run
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/verify-gui-truncation.py --run-name new-cap-run
```

The historical GUI milestone did not expand or process assets. Step 8 now adds
manual scan/process/refresh/status operations under its separate approved contract.
Classification, game integration, new agent registrations, hosting and cloud
inference remain outside scope. Bruno's usability, artistic suitability and
comprehensive accessibility review remain separate owner decisions.

## Focused search-change verification

Run the packaged Windows lifecycle check using existing tooling:

```powershell
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/verify-search-ui.py --run-name unique-search-ui-run
```

This uses small synthetic assets, actual WebView2 and controlled delayed/error
responses. It verifies the packaged UI and shared copied-settings replay without
loading a real model or rerunning relevance evaluation. It preserves screenshots
and reports under `data/gui/`. Reduced-motion styling is checked in the renderer;
it does not change the Windows preference. Owner Windows usability, screen-reader
behavior and search-relevance approval remain separate and pending.
