# Windows desktop app — pilot stage between 7 and 8

Double-click `C:\BrunoOS\Local-Asset-Library\Local Asset Library.vbs`.
It opens a normal, resizable Windows window without an extra terminal. The
launcher resolves its own directory, so shortcuts and other starting directories
work. It invokes the prepared `.venv-mcp\Scripts\pythonw.exe`; startup never
installs packages, downloads weights, scans assets or rebuilds data.

## Using the app

The initial grid contains the approved pilot, with its actual membership and
counts supplied by the backend. The full inventory count is context, not browse
authorization. Names, packs, thumbnails and fault/review flags remain distinct.
Select a card for a larger preview and source/evidence detail. Preview selection
is explicit: a missing or faulty requested view produces a reason, not another
image. Source-format selection verifies that export and shows its original path;
**Copy source path** copies text only.

Enter a description or filename and press **Enter** or **Search**. The default
mode is explicitly `keyword_description`. **Clear** resets query, filters and
mode, restoring full pilot browsing without starting the model. With an empty
query, Enter browses using the selected filters rather than issuing an empty
semantic search. Pack, source format, maximum triangles and rigged filters reuse
the existing verified backend policy. Technical filters require inspected facts
for the requested format; unknowns do not qualify.

**Filters & search options** exposes the existing keyword, description, image,
combined and reference modes. Reference search uses an existing pilot asset ID
and a known view; there is no upload or arbitrary path input. Image-related modes
are requested explicitly. Searches show the same compact shortlist as MCP, up to
five candidates with identical order and shared cap/truncation. Suggestions can
be irrelevant even when the requested object is absent; scores are not confidence
percentages and the app has no universal similarity threshold or semantic fallback.

**Copy search settings** copies the completed search's exact MCP `search_assets`
argument JSON, including explicit mode, filters and limit. It does not copy later
unsent edits. An agent must submit that object against the same catalog/index
version. Full catalog/index/pilot SHA-256 values are available in the footer
description/tooltip and retained verification receipts. Versions are not added
as invalid extra fields to the tool argument object.

Use Tab/Shift+Tab for controls, arrows/Home/End within the grid, Enter/Space to
activate a card, Ctrl+F to focus text search, and Escape to close detail. Controls
have accessible names, live status/error announcements, readable contrast and
visible focus. The layout adapts to narrow windows; details move below the grid.
Basic native keyboard checks and rendered inspection are separate from a full
screen-reader/accessibility audit and Bruno's usability approval.

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

Follow `../storage.md`, including fresh before/after receipts, shared `cache/uv`,
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
script/evaluation; CSP blocks external resources, connections, frames and uploads.
Asset text is inserted as text rather than executable HTML.

Browsing does not load a model. The first semantic query starts one private
existing embedding worker, with offline shared weights at
`C:\BrunoOS\Local-models`. Subsequent searches reuse that worker. MCP and other
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

Actual results, timings, storage and fault receipts are summarized in
`verification.json` and `../progress.md`. Modest actual WebView2 captures are under
`data/gui/final-window/`. Focused checks use synthetic fixtures; no real asset is
damaged and no full preprocessing is repeated. Verification scripts refuse to
overwrite prior runs; select a fresh `--run-name` for a deliberately requested check.

```powershell
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/gui-unit-checks.py --run-name new-unit-run
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/verify-gui.py --run-name new-window-run
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/verify-gui-truncation.py --run-name new-cap-run
```

This stage does not import, edit, refresh, watch, process or expand assets. It does
not add classification, game integration, agent registrations, hosting or cloud
inference. Step 8 remains necessary for reliable incremental updates and full-library
processing, under separate authorization. Bruno's usability, artistic suitability
and comprehensive accessibility review remain separate owner decisions.
