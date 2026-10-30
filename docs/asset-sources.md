# Asset sources

The **Asset sources** tab (the folder icon above Settings in the rail) is where you browse your assets
by place and decide what to process. **Home** is for searching; both share the same cards and the same
inspection panel, and a search result's menu offers **Show in pack** to jump here.

Nothing is ever written into your asset folders. Previews, descriptions and search data live in one
**library store**: by default the ignored `data/library-store/` in the project; another drive can be set
with `[storage].library` in `config.local.toml`. The store counts against the storage budget in
**Settings → General**. Read-only drives, network shares and asset repositories work as library folders.

## Library folders, bundles, packs and folders

**Add library folder** watches a folder. Add the top folder of your collection (for example the folder
that holds all your packs); Assetarium finds the structure inside it:

- A **pack** is the folder closest to the assets that carries pack markers: a license file, a readme, a
  preview image, internet shortcuts or a versioned name such as `Name_1.0_FREE` or `Name 3.7.0`. Without
  markers, the first folder with assets under the library folder is the pack. Publisher names are never
  used. A pack shows its cover (its own preview image), its license file and its counts.
- A folder that holds several packs is a **bundle** (for example `Kenney All-in-1` → `2D assets` →
  `Tiny Dungeon`).
- You correct detection on any folder: **Make this a pack** and **Merge into parent pack** are saved and
  survive rescans, and **Rename** gives a pack a display name. Packs have no tags and are never added to
  collections.

Adding a folder **inside** a library folder is refused as already covered, with **Show it**. Adding a folder
**around** library folders replaces them: their assets keep their IDs, results, collection entries and
your reviews. **Remove…** stops watching a folder; its results stay in the store, and adding the same
folder again restores everything. An unreachable folder (a removed drive) shows **Offline**; its results
and collection entries are kept.

## What is found

Every supported type is always included: 3D models (FBX, glTF/GLB, OBJ, BLEND, STL, DAE) and still images
(PNG, JPEG, WebP, SVG and others). Images are sorted into three kinds, each with the evidence shown:

- **Model textures** belong to a model and are not separate assets: a glTF image, an MTL map, a file name
  inside an FBX, or a texture Blender reported when it inspected the model.
- **Material textures** (`brick_normal.png`, a `Textures` folder, normal-map colors) are browsable and
  found by name; they are not described.
- **2D images**: everything else, for example a pack with no models, icons, sprites and UI.

When the guess is wrong for a folder, **Treat images here as textures** or **as 2D assets** decides for it.

Scans run in the background at startup, after you add a folder and after each change you make. They never
run models or renders. Unchanged files reuse their verified hashes (decision 0004).

## Identity: moves, copies and edits

An asset's ID is assigned once, when it is first seen, and kept by recognizing it:

- A file **moved or renamed** inside your library keeps its ID, its previews and descriptions (found again
  by content), your reviews and its collection entries. Its search data is rebuilt by the next Make previews.
- A **copy** of an asset is a new asset that shares the copied asset's finished results: nothing renders twice.
- A file **edited** in place keeps its ID and needs previews again.
- A file that **vanished** becomes **Missing**: shown faded with when it was last seen, with its results and
  collection entries kept until you choose **Forget missing** on its library folder or pack.

## States on the cards

Each card has one state and a few overlays, shown as labeled icons (never color alone):

| State | Meaning | What you can do |
| --- | --- | --- |
| No previews yet | Found, not processed. 2D images already show their original file | Make previews |
| Search data pending | Previews exist; search data is missing | Make previews |
| Queued / Making previews | In the processing queue / running | Cancel on Asset processing |
| Ready | Previews and search data done | — |
| Blocked | Its next step can't run on this computer (Blender not set up, the search runtime not installed) | **Fix…** shows what to install; it is never offered as something to process |
| Recorded failure | A fault with its evidence | **Copy error**, **Recheck…** (decision 0020) |
| Missing | The file is gone | **Forget missing** |

Overlays: a description warning (review notes are not shown as warnings), the description state when
descriptions are on, how many collections hold it, and **new** since your last visit to that library folder.
Files that are not assets (readmes, HTML, licenses) are listed after the cards, faded, behind **Show other files**.

## Working with the tab

- Click a folder or pack to show its assets and its panel in inspection; click an asset to inspect it.
- **Double-click** any file or folder to show it in Explorer.
- **Ctrl-click** or **Shift-click** picks several cards for Make previews, Generate descriptions or Add to collection.
- Right-click (or Shift+F10, or the menu key) for everything a folder, pack, library folder, asset or file
  offers. Menus only offer what can resolve the shown state.
- Arrow keys move in the tree: Right expands, Left collapses or goes to the parent, Enter shows the folder.
- The header sorts the tree (Name, Recently added, Most without previews, Most assets) and filters the cards
  by type (3D models, Images, Material textures) and status (Has new, Needs previews, Blocked, Failures, Missing).

## Making previews and descriptions

**Make previews** (inspection, preview images and search data, never split) and **Generate descriptions**
(only when descriptions are on in Settings → General) act on a library folder, a pack, a folder or picked
assets. They start at once or wait in line on **Asset processing**:

- What an item covers is decided when it starts: "whatever in this pack still lacks previews".
- Previews always run before descriptions; otherwise items run in your order (move or remove them in **Up next**).
- One job at a time; renders use the parallel Blender processes of decision 0022.
- Under about 10 minutes a job starts on the click. From 10 to 30 minutes it starts with an **Undo** toast.
  Longer jobs, or jobs that would reach the storage budget, ask first with an estimate (counts, a time range,
  disk). The estimate comes from the render speed test and recent runs; without either it says
  "no measurement yet".
- **Hold descriptions for overnight** keeps description jobs waiting until the window (22:00–07:00 by default).
- Queued work left over when the app closed shows as **Paused** with **Resume**. It never resumes by itself.
- Each finished job starts the next one, with or without the app open.

**Asset processing** shows **Running** (progress, Cancel, a live log with copy buttons on errors and
warnings), **Up next**, **Blocked** (by reason, with the fix and how many assets it unblocks), **Recorded
failures** (by stage and reason, with Copy, Recheck and Show in Asset sources) and **Recent**. Pending work
and failures are never mixed in one message.

Cancel requests a graceful stop: the current asset finishes, its checkpoint is saved, and nothing else
starts. Unchanged faults are kept with their evidence and skipped; they are never retried automatically.

## Processing formats

**Settings → General → Formats to process** (FBX, glTF/GLB, OBJ) chooses which file of a grouped asset is
inspected when several formats exist. Unchecking everything pauses processing; browsing and search keep working.
Changing formats never deletes results or retries faults.

## Descriptions

Descriptions are optional (decision 0008). Assets are searchable by name and image as soon as their previews
are made; descriptions add a third signal. Description runs write in batches (decision 0007), build their
search vectors and publish. Recorded description failures are kept and not retried; a cancelled run still
publishes what it finished. Notifications (the bell) report descriptions ready to generate and each run's outcome.

## Excluded folders and duplicate export folders (decision 0019)

**Exclude folder** (menu or panel; `library exclude KEY PATTERN`) skips a folder: a name with `*` (`Unity*`) or
a path inside the library folder (`Models/Unity FBX`). Excluded folders are listed in the tree, faded, with
**Include again**. Their files are not hashed and cannot be textures for other models.

Each scan compares sibling folders by the names of their model files. Equal or nearly equal sets (an engine
copy missing a few models) become a suggestion in the library folder's panel: **Group as alternate files**
(each copy joins the reference folder's asset, keeping its ID and results), **Exclude extra folders** or
**Keep separate**. Answers can be undone.

## Texture folder for models missing textures (decision 0021)

When inspected models can't find textures their files name and the library has files with those exact names,
the library folder's panel shows **Textures not found** with candidate folders (`Textures/PBR`, `URP`, …) and
how many models each fixes. **Apply** writes a texture-repair recipe for those models; Make previews then
renders them once with the mapped files. **Undo** removes the choice. Originals never change.

## Shared project dependencies

Split exports can be separate library folders. Missing external glTF/GLB images resolve across enabled
library folders when the project-relative layout matches and all candidates have identical bytes. See
[shared dependency behavior](dependency-path-overrides.md) and
[decision 0009](../Assetarium%20KnowledgeBase/Decisions/0009-general-capabilities.md).

## Storage budget

The storage budget in **Settings → General** (10 GiB until you save one) caps Assetarium's own disk use:
the project folder and the library store, counting hard-linked files once. Original assets and shared models
don't count. Jobs measure before they start and between stages; at the budget they stop and keep finished work.

## Moving results into the library store

An install from before the library store kept results in a generated folder inside each source. Until they
are moved, the app shows a notice with the command and keeps showing your last published search, read only.
Close the app and MCP servers, then run (base runtime; same arguments with `./scripts/uv.sh` on Linux):

```powershell
.\scripts\uv.ps1 run --locked python scripts/migrate-library.py --library-folder "D:\Game Assets"
```

This **dry run** finds every old folder at any depth (`--search PATH` adds places to look, for example a drive
your library moved to) and writes a plan to `data/library/migration/plan-<time>.json`: assets and finished
results per folder, sources relinked after a move (matched by their saved identity), folders whose identity
two copies share (refused), images newly included and, for sources that imported only some formats, the
folders proposed as exclusions so nothing new floods in. Review it, then add `--apply`:

- It asks for a typed `yes` (no bypass), checks the app and MCP servers are closed, and saves storage receipts
  before and after.
- Results are copied, never moved: immutable files are hard-linked on the same drive. Each finished result is
  re-keyed by its inputs, so **nothing renders or is described again**; a result that was already out of date
  stays pending, as before.
- Every asset keeps its ID. Old sources inside a `--library-folder` become part of it.
- It rescans without models and checks that every published asset is present and nothing newly pending, then
  writes `data/library/migration/<time>.json`. A fault stops only its own folder. A folder is imported once.

`--remove-old` then deletes the old generated folders whose import a receipt verified, asking for each one.

How library folders, recognition and the store work internally is in the knowledge base:
[Sources](../Assetarium%20KnowledgeBase/Notebook/Sources%20and%20Catalog/Sources.md).
