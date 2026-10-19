# Windows desktop app — configured library membership

Step 8 extends this same app with bounded pages, lazy thumbnails, manual updates,
resumable processing and versioned catalog/index publication. Current operations,
approved membership/storage limits and worker ownership are documented in
[`../library-updates.md`](../library-updates.md). Historical pilot verification
below remains evidence for the earlier GUI milestone; it is not full-library
coverage or owner approval.

Double-click `C:\BrunoOS\Local-Asset-Library\Local Asset Library.vbs`.
It opens a normal, resizable Windows window without an extra terminal. The
launcher resolves its own directory, so shortcuts and other starting directories
work. It invokes the prepared `.venv-mcp\Scripts\pythonw.exe`; startup never
installs packages, downloads weights or starts rendering/model inference.
It scans enabled asset sources for file changes in the background.

## Using the app

**Settings → Asset sources** adds/removes directories and changes their Enabled
checkboxes. Results refresh live. Source-specific generated information is stored
in each source's `metadata-lal`. See [asset sources](../asset-sources.md).

Click a source name or its **🔍** icon to browse that source inside LAL, including
disabled sources. The scrollable grid loads saved published assets in batches of
forty, with lazy thumbnails and a **Load more assets** keyboard alternative.
Select any card to use the same inspection panel and interactive 3D preview as
the main library. This view has no search controls and does not change Enabled,
scan, process or publish assets. Sources without saved published records explain
that scanning/processing is needed. **Back to asset sources** restores the source
list position and focus; the main library's query and result cards are preserved.
Saved faulty items remain visible with their evidence. An unsupported or faulty
3D source retains the existing image/evidence behavior.

Source browsing uses a registered source's own published membership and generation
through the existing desktop services. Disabled-source inspection is limited to
this explicit source scope; main library/MCP visibility is unchanged. Removed
sources and assets from other sources cannot use that scope. Viewer failures
share the library's retained fault history, and file tickets remain source scoped.
Native verification: `scripts/verify-source-browser.py --run-name <unique-name>`
through the existing MCP runtime, using isolated synthetic assets only.

The library shows one warning card per source needing processing/publication.
**Process assets** performs both (inspection/previews and search vectors; no
descriptions), with a progress bar spanning processing, publication and a final
verification scan. **Cancel** finishes and saves the current asset before stopping.
Descriptions are optional ([decision 0008](../decisions/0008-optional-descriptions-and-notifications.md)):
**Settings → Asset sources → Generate descriptions** runs them per source in the
background, with progress and **Cancel** in the source row and under the bell;
**Cancel** waits for the current batch.
**Settings → General → Description batch size** (1, 2, 4 or 8; default 8) sets
how many assets are described per model call. If a run stops because the GPU
ran out of memory, its report names the batch size; lower it and choose
**Continue**. Finished descriptions are never redone.

The header bell opens **Notifications**: *Descriptions ready to generate* for a
source (actions **Generate descriptions** / **Not now**) and one report per
description run (finished, with failures, cancelled, stopped or interrupted;
**Continue** when descriptions remain, **View source**, dismiss ×). New notices
also appear as a toast for 8 s (paused while hovered or focused). The bell shows
the unread count, or a dot while a run is in progress. Escape or a click outside
closes the panel and marks its notices read. The gear button opens Settings.
Native verification: `scripts/verify-notifications.py --run-name <unique-name>`
(synthetic assets; a stand-in run, no model). The card remains until a scan confirms that no
actionable work remains and current results have been published. Recorded failures
do not trigger pending cards: **Importing failures report** opens a scrollable list
of original asset paths, including disabled sources. Saved attempts distinguish
unchanged failures from new/changed files and unfinished work. The separate Process pending and
Publish ready work buttons have been removed, and so have the manual **Scan** and
**Status** buttons: enabled sources are scanned at startup, and the app watches
cheap file stamps (publication, source status, operation and settings files)
every 1.5 s, reloading library or source data only when one changes. An unchanged
scan rewrites nothing, so it never reloads the open view. Processing never starts
automatically when sources/files are added.

The initial grid contains a bounded page of the published approved membership, with its actual membership and
counts supplied by the backend. The full inventory count is context, not browse
authorization. Names, packs, thumbnails and fault/review flags remain distinct.
Previous/Next page browse forty cards at a time; existing previews load only near
the viewport. The app shows published coverage separately from processing work.
Select a card for a larger preview and source/evidence detail. Preview selection
is explicit: a missing or faulty requested view produces a reason, not another
image. Source-format selection verifies that export and shows its original path;
**Copy source path** copies text only.

Click the inspection image or **Explore in 3D** to interact with the selected
source directly in the inspection card. **Open fullscreen** opens the same
preview across the LAL window. Drag to rotate, right-drag to pan, and scroll to
zoom. The toolbar provides Fit, Reset view, zoom buttons and standard view
presets; Display options adds perspective/orthographic projection, background,
edges, up-axis and upright/free-orbit navigation. Fullscreen preserves the
loaded model and camera, and Escape returns to the inspection card. Back to
image releases the interactive viewer. See [interactive previews](3d-preview.md)
for format support, limits and verification evidence.

Enter a description or filename and press **Enter** or **Search**. The default
mode is explicitly `combined`. **Clear** resets query, filters and
mode (combined) and shortlist limit (20), restoring paged library browsing without starting the model. With an empty
query, Enter browses using the selected filters rather than issuing an empty
semantic search. Pack, source format, maximum triangles and rigged filters reuse
the existing verified backend policy. Technical filters require inspected facts
for the requested format; unknowns do not qualify.

**Filters & search options** exposes the existing keyword, description, image,
combined and reference modes. Reference search uses an existing library asset ID
and a known view; there is no upload or arbitrary path input. Keyword + description + image (`combined`) is the default. Its reciprocal rank
fusion gives image rank weight 3, keyword and description weight 1 each, with
`k=60`; the explicit Keyword + description mode retains equal weights. Existing
embeddings are reused without reindexing.

Shortlist choices are exactly **5, 10, 20, 30, 40**, with **20** selected on
startup and Clear. The Windows bridge explicitly requests 20 by default; MCP
omitted limits remain 5. Both response layers use the shared request-scaled
character budget documented in `../mcp/README.md`, with identical order and
explicit cap/truncation reporting. Suggestions can
be irrelevant even when the requested object is absent; scores are not confidence
percentages and the app has no universal similarity threshold or semantic fallback.

**Copy search settings** copies the completed search's exact MCP `search_assets`
argument JSON, including explicit mode, filters and limit. It does not copy later
unsent edits. An agent must submit that object against the same catalog/index
version. Full catalog/index/membership SHA-256 values are available in the footer
description/tooltip and retained verification receipts. Versions are not added
as invalid extra fields to the tool argument object.

An indeterminate circle and **Searching…** appear immediately. While the worker
is still preparing its runtime or loading the model (first semantic search only),
the status line says so. Prior cards remain visible until completion.
The Search button is disabled while active and repeated identical submissions
are ignored. A different request supersedes the old one; Clear and a published
view refresh invalidate it. Obsolete completion cannot hide a newer busy state.
Success, empty results and errors end the current busy state. The indicator has
a polite live announcement; reduced-motion preferences stop animation while
keeping the circle and text visible. There are no percentages or automatic retries.

Use Tab/Shift+Tab for controls, arrows/Home/End within the grid, Enter/Space to
activate a card, Ctrl+F to focus text search, and Escape to close detail. Controls
have accessible names, live status/error announcements, readable contrast and
visible focus. The layout adapts to narrow windows; details move below the grid.
Basic native keyboard checks and rendered inspection are separate from a full
screen-reader/accessibility audit and Bruno's usability approval.

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
script/evaluation; CSP blocks external resources, network connections and uploads.
An opaque-origin, scripts-only sandbox frame is allowed for interactive 3D;
its only resources are bundled scripts, data URLs and in-memory blob URLs. It
cannot access the desktop bridge or the parent document. No HTTP listener is added.
Asset text is inserted as text rather than executable HTML.

Browsing does not load a model. The app starts one private embedding worker in
the background when it opens; the worker loads its Python libraries only (no
model, no GPU). The first semantic query loads the model (offline shared weights
at `C:\BrunoOS\Local-models`), and the worker unloads it after ten idle minutes
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
[`../caption-quality.md`](../caption-quality.md) for the shared desktop/agent
classification and verification evidence.

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
