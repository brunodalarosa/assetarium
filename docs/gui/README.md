# Windows desktop app (Assetarium)

The desktop app is a React interface ([decision 0011](../../Assetarium%20KnowledgeBase/Decisions/0011-react-desktop-ui.md))
in a native Windows window. This page describes how to use it. How it is built, its runtime
boundaries and its verification are in the knowledge base:
[Desktop app design](../../Assetarium%20KnowledgeBase/Architecture/Desktop%20App/Desktop%20app%20design.md); processing and
publication are in [Library updates](../../Assetarium%20KnowledgeBase/Architecture/Processing/Library%20updates.md).

Double-click `Local Asset Library.vbs` in the checkout.
It opens a normal, resizable Windows window without an extra terminal. The
launcher resolves its own directory, so shortcuts and other starting directories
work. It invokes the prepared `.venv-mcp\Scripts\pythonw.exe`; startup never
installs packages, downloads weights or starts rendering/model inference.
It scans enabled asset sources for file changes in the background.

## Using the app

**Layout.** The left rail has **Back**/**Forward** (view history; a mouse's dedicated back and forward
buttons do the same), **Home**,
**Library**, **Collections** and **Asset processing**, with **Settings** at the
bottom; every icon has a label and a focus/hover tooltip. Library is reserved for
a later version and offers no actions yet. The top bar holds the background
activity indicator (only while something runs), the notifications bell and the
inspection toggle. Asset processing shows a dot while a source needs
processing or an operation runs.

**Collections** ([decision 0012](../../Assetarium%20KnowledgeBase/Decisions/0012-collections-and-tags.md)). The
Collections tab shows every collection as a card (four member covers, name, asset
count, a small "Updated …" date), newest first, with **New collection** and a
search over names, descriptions and what is inside (member names, labels, notes,
tags and descriptions; a card says how many members matched). Clicking a card
opens it; right-click (or the Menu key / Shift+F10) offers **Open** and
**Delete…**. A collection view works like Home: its name appears in
the top bar, larger, with a pencil to rename it in place; the description has its
own pencil; the search bar keeps Home's modes but searches only members, listing
label/notes/tag/name matches first, then the ranked search. **Select** and the
card menu's **Remove from collection…** start a batch selection (like forwarding
messages): cards toggle (Shift-click selects a range, Ctrl+A selects all, Escape
cancels) and one **Remove from collection** removes them with an **Undo** toast
that restores labels and notes. **Export** writes JSON for agents (absolute
original paths), a PNG sample sheet, Markdown with a thumbnails folder or a PDF,
through a Save dialog that opens in `data/exports/collections/`.

Every asset card has a right-click menu: **Inspect**, **Add to a collection ›** and **Show in Explorer**.
**Show in Explorer** (Windows only, decision 0013) opens Explorer with the asset's original file selected: the format open in
the inspector for that asset, otherwise its primary file. The backend resolves the path through the source boundary (the
window only names the asset), nothing is opened or hashed, and a missing original is a visible fault toast without a retry.
The flyout searches collections, ticks those that already hold the asset (choosing
one again removes it, with Undo), and **Create new collection**; typing an unused
name offers **Create “name”**, which creates it and adds the asset in one step.
While any of these menus is open, the window behind it (except the item the menu
came from, which stays sharp and clickable) dims slightly with a light
blur and is shielded: a click outside only closes the menu (it never reaches the
card or button underneath), and right-clicking another card moves the menu there.
The flyout stays open while the pointer crosses gaps toward it; it closes only
after resting about 300 ms on another menu row. The backdrop is still, so the blur
costs nothing measurable (frame timing is recorded by `verify-collections.py`).
Selecting a member in a collection shows its **label** (only in this collection)
and **notes** at the top of inspection, saved automatically as you type (and when you leave the field or the asset). **Tags**
(on the asset itself, shared everywhere) are edited at the end of Overview on any
page. Members whose source was removed stay as **Unavailable** cards with the
reason; disabled or not-yet-published members open through their source. Agent
edits arrive live and raise a notice with **Open collection**. Every deletion
(a collection, removing a source) asks first in a modal with a red confirm button.

**Home and search.** Home is a centred search pill. Type a description or name
and press **Enter** or the arrow button; results compact the search to the top
and show the count, the query, the search mode and the status line (candidates,
seconds, truncation and recorded exclusion faults). Pressing Enter on an empty
search browses the filtered library forty cards at a time with Previous/Next; the
**×** in the pill clears the search and returns Home to its idle state (filters
are kept). The sliders button opens **Filters & search options**: Asset type,
Pack, Source format, Maximum triangles, Rigged, Image transparency, Image size,
Search mode and Shortlist limit, with **Reset** and **Apply filters**. Choosing
**Pilot preview reference** also shows the reference asset and view. Technical
filters require inspected facts for the requested format; unknowns do not
qualify, and image filters match processed 2D images only.

Search modes keep their backend values: **Name + description + image** is
`combined`, the default; **Name + description** is `keyword_description`; then
**Exact keywords**, **Visual description**, **Text → image** and **Pilot preview
reference**. `combined` uses reciprocal rank fusion with image rank weight 3,
keyword and description weight 1 each, `k=60`. Shortlist choices are exactly
**5, 10, 20, 30, 40** (default **20**; MCP's omitted limit remains 5). Both
interfaces share the request-scaled response cap in `../mcp/README.md`.
Suggestions can be irrelevant even when the requested object is absent; scores
are not confidence percentages, and there is no semantic fallback.

**Copy search settings** copies the completed search's exact MCP
`search_assets` arguments (mode, filters, limit), not later unsent edits; agents
must use the same catalog/index versions (shown on Asset processing).

While a search runs, a spinner with a polite **Searching…** announcement appears
in the pill, the arrow button is disabled and earlier cards stay visible. The
status line says when the worker is preparing its runtime or loading the model
(first semantic search only). Repeated identical submissions are ignored; a
different request supersedes the old one, and obsolete completions cannot hide a
newer busy state. Reduced-motion preferences stop the animation.

**Asset inspection.** The right sidebar is only for inspection. Clicking a card
opens it (the card is highlighted); the toggle or **×** hides it and shows it
again with the same selection and tab. With nothing selected it shows **No asset
selected**. Drag the grip (or focus it and use ←/→, Home/End) to resize it
continuously; the width is remembered. Results and inspection scroll
independently. On narrow windows the panel floats over the results.

- **Overview:** the preview, **Source format** and **Preview view**, **Open
  interactive 3D preview**, measured facts, generated observations and suggested
  uses. A missing or faulty requested view produces a reason, not another image.
- **Sources:** the original path with **Copy source path** (text only) and its
  SHA-256, dependencies with their referring source, and license evidence.
- **Evidence:** caption notes and warnings (with the original review evidence),
  recorded faults with full fault/processing evidence, measurement and
  structured-observation evidence, and owner review.

Click the inspection image or **Open interactive 3D preview** to explore the
selected source in place; **Fullscreen** opens the same preview across the
window. Drag to rotate, right-drag to pan, scroll to zoom. The toolbar has Fit,
Reset view, zoom buttons and view presets; Display options add projection,
background, edges, up-axis and navigation. Escape returns from fullscreen;
**Back to image** releases the viewer. See [interactive previews](3d-preview.md).

**2D images** appear with a **2D image** or **SVG image** badge on a checkerboard,
and small-palette art keeps hard pixel edges. Their Overview shows an image
viewer instead of the 3D preview: **Fit**, **1:1**, zoom out/in (12.5–3,200%),
**Background** (checkerboard, light, dark, mid gray; remembered for the session)
and **Hard pixel edges**; with the image focused, `+`, `-`, `0` and `1` work too.
SVGs are re-rendered at the zoom level. Damaged, animated or externally linked
images keep their cards and explain the recorded reason instead of a preview.

**Notifications.** The bell opens a panel over any view: *Descriptions ready to
generate* (**Generate descriptions** / **Not now**) and one report per
description run (**Continue** when descriptions remain, **View in Asset
processing**, or **View report** for stopped, interrupted or failed runs;
dismiss ×). Running description jobs show progress with **Cancel**. New notices
also appear as a toast with the same actions for 8 s (paused while hovered or
focused). The bell shows a dot for unread notices or a running job. Escape or a
click outside closes the panel and marks its notices read.

**Asset processing** lists every source with its import state and optional
descriptions. **Process assets** (offered only when there is pending work or a
scan fault) runs inspection/previews and search vectors, then publishes, with
progress through a final verification scan; **Cancel** finishes and saves the
renders already running first (several run at once, decision 0022). **Settings → General →
Rendering** says what renders now and why ("Now: AMD Radeon RX 6800 (HIP), 2 renders at a time
(fastest in the speed test)") and offers the render device, renders at a time and memory for
rendering (saved with the form; empty memory is automatic). The **Search** card lists **What is
installed** for the chosen device (GPU, search runtime, model weights, search check), with a copyable
command for anything missing and **Check again**; it installs nothing. When search runs on the CPU, the
**Search** card adds **CPU threads for search data** (Automatic = the speed test's choice, or 1 to
every logical thread) with "Now: 24 of 32 threads (…)". Both cards link to the **Speed test** card,
which shows when the test last ran, one line per tested render device, the search-data line (each
tested thread count's seconds per test image and the count chosen, or why it is not tested), and
**Test speed** / **Test again** and **Cancel test** with the test's phase. **Generate descriptions** runs the optional describe
operation per source with progress and **Cancel** (decision 0008); disabled
buttons say why. Run reports open as a dialog; a GPU-memory stop suggests lowering
**Settings → General → Description batch size** (1, 2, 4 or 8; default 8)
before **Continue**. When descriptions are turned off, each source says so (existing
descriptions stay stored and searchable) and offers **Open Settings → General**
instead of **Generate descriptions**; report notices drop **Continue**. The page also
shows the published library (coverage,
catalog/index versions, **Refresh published view**) and the **Importing failures
report**, a list of original asset paths with recorded failures, kept separate
from pending work. A source with recorded failures offers **Recheck failures**: it reruns the
file/dependency check, read only, and a dialog offers **Retry N assets** for failures that came
from that check and pass it now (or **Nothing to retry** with Close); retried assets become pending
for the next **Process assets** ([decision 0020](../../Assetarium%20KnowledgeBase/Decisions/0020-alternate-file-faults-and-recheck.md)).

**Setup** ([decision 0014](../../Assetarium%20KnowledgeBase/Decisions/0014-setup-wizard.md)). A full-window
overlay with a step list (Welcome, Blender, Formats, Storage budget, Descriptions and
search, Batch size, Review and finish; the descriptions step also chooses **Where search
runs**, NVIDIA GPU or CPU, with its own checklist, [decision 0018](../../Assetarium%20KnowledgeBase/Decisions/0018-cpu-search-embedder.md)), **Back** / **Skip step** / **Next**, and **Skip setup**
at any time. It opens by itself only on a genuinely fresh install (no setup record, no
saved settings, no source); otherwise **Settings → General → Run setup** opens it
pre-filled. Nothing is saved until **Save** on the review step, and setup never
downloads, installs, processes or starts a model. *Welcome* shows the system, GPUs
(NVIDIA with VRAM and driver; other adapters by name) and free space. *Blender* lists
discovered executables and **Choose executable…**; **Check Blender** runs the version,
headless-start and importer checks (Cancel stops the probe), says when saving writes
nothing (only for the Blender already saved; a discovered one is always written), and asks to confirm when a change would re-render finished 3D previews.
*Formats* suggests formats per target engine. *Storage budget* explains exactly what is
counted, shows free space and current use (newest receipt or **Measure now**), presets
with a recommendation and a whole-GiB field. *Descriptions* turns them on or off and
chooses the engine — **Built in (Qwen3-VL-2B-Instruct)**, tested, or **Local model
server (experimental)** with address, model and **Test connection** ([description
engines](../description-engines.md)) — with a readiness checklist whose missing items
have copyable commands. *Batch size* (built-in engine only) shows measured speed and
memory and a recommendation for the detected GPU. After saving, each part reports its
own result (a failed Blender write keeps the other settings) and **Go to Asset
sources** leads to the next step. Verification: `scripts/verify-setup-wizard.py
--run-name <unique-name>`.

**Setup with an AI agent** ([decision 0016](../../Assetarium%20KnowledgeBase/Decisions/0016-agent-setup.md)). *Welcome*
offers two equal cards, **Set up with my agent** and **Set it up yourself** (the manual
steps above). The agent card opens a 60-minute setup session — the only way an agent's setup
tools may change anything — and shows the agent panel: the session line with minutes left
and **End access** (or **Open for 60 minutes** once ended); **1 · Add Assetarium to your
agent** with Codex / Claude Code / OpenCode / Other snippets generated for this computer's
folders and **Copy**; **2 · Ask it to set up Assetarium** with **Copy setup prompt**; a
live connection line ("Waiting for an agent to connect…" or "<client> is connected", from
the server's connection record; the app does not host the server and never says it runs);
a privacy note that the agent's model, possibly in the cloud, receives the OS, GPU, free
space and Blender paths; and **What your agent has set**, each value with *Set by agent*,
*Set by you* or *Proposed by agent · approved by you*. A Blender proposal appears as a card
("Your agent proposes: Blender → path, checked as Blender 5.2.2 …") with **Apply** (checks
again, then saves; the re-render confirmation appears when needed) and **Reject**. When the
agent finishes, **Review choices** opens the review step with the saved values and who set
them; **Save** records only what the user changed. Agent changes and proposals raise
notices whose **Review** / **Review proposal** lead back to the panel; a decided proposal's
notice and toast disappear. **Settings → General → Run setup with my agent** opens the same
panel. Verification: `scripts/verify-agent-setup.py --run-name <unique-name>` (a real STDIO
client against an isolated project, light and dark).

**Settings.** *General* has **Appearance** (Match Windows, Light, Dark), **Setup**
(last run, **Run setup**, **Run setup with my agent**), **Blender installation** (a *Saved*,
*Not saved*, *Missing* or *Not found* badge with the path; **Check Blender** and **Change
Blender…** open the wizard's Blender picker with **Save Blender**, the re-render confirmation and
**Keep the saved Blender**; the picker is open by itself while no usable Blender is saved), the storage budget (with the exact
definition of what it counts), formats to process, **Descriptions** (on/off and the
engine, with the local server's address, model and **Test connection**) and the
description batch size (built-in engine only). *Asset
sources* adds directories (**Choose folder…**), and per source shows format
counts, the **Enabled** switch, **Include 2D images** (saves and rescans without
deleting results), **Excluded folders** (pattern chips; adding or removing one rescans),
**Possible duplicate exports** suggestions with **Group as alternate files**, **Exclude extra
folders** and **Keep separate**, saved answers with **Undo**, **Textures not found** with a folder choice, live counts, **Apply** and **Undo** ([decision 0021](../../Assetarium%20KnowledgeBase/Decisions/0021-texture-folder-choice.md))
([decision 0019](../../Assetarium%20KnowledgeBase/Decisions/0019-source-folders-and-export-variants.md)), and **Remove**
(keeps files and saved metadata). The Asset processing card points to unanswered suggestions. Click a source
name or its 🔍 icon to browse that source's saved assets, including disabled
sources, with the same cards and inspection; it loads forty at a time as you
scroll (**Load more assets** is the keyboard alternative) and never scans,
processes or publishes. **Back to asset sources** returns focus to that source.
See [asset sources](../asset-sources.md).

Enabled sources are scanned at startup; the app watches cheap file stamps every
1.5 s and reloads library or source data only when one changes (decision 0002).
Processing never starts automatically.

**Keyboard.** Tab/Shift+Tab move between controls, arrows/Home/End move within
the grid, Enter/Space activate, Ctrl+F focuses search (from any view), and Escape
closes the open panel, then hides inspection. Controls have accessible names,
live status/error announcements and visible focus. Native keyboard checks are
separate from a full screen-reader audit and Bruno's usability approval.

Native verification of the layout itself, in both themes:
`scripts/verify-layout-revamp.py --run-name <unique-name>` (synthetic assets;
screenshots of every handoff state).
