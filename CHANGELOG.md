# Changelog

All notable changes to Assetarium are listed here. The project follows
[Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- **Agents act freely, in the open** (decision 0029): a connected agent can start Make previews and Generate
  descriptions (`start_processing`; a long job shows its estimate first), and its pack profiles apply at once,
  including rules that rescan. Agent activity has a **Pause agents** switch (agent changes are refused, reads keep
  working, jobs agents queued wait) and lists each agent session with **Undo all** for its tags, collections, pack
  profiles and waiting jobs; anything changed since is kept and named. Jobs an agent started carry its name in
  Asset processing. Connecting an agent now says what it may change on its own. CLI: `local-assets agents
  status|pause|resume|undo` (interactive terminal only). Codex users add `start_processing` to `enabled_tools`.

### Changed

- **Disabled buttons say why**: a greyed-out button can now be focused with Tab and shows its tooltip on hover and
  focus, with the reason it is unavailable where the app knows it (Forward, Rescan on an offline folder, Apply with
  no decisions…). Clicking it still does nothing. The 3D viewer's buttons (Fullscreen, Display options, the view
  switcher) show the same tooltips as the rest of the app, in fullscreen too, instead of the system's.
- **Moving or updating Blender no longer re-renders your 3D assets** (decision 0028): previews are keyed by
  Blender's major version, not where it is installed. A moved, reinstalled or minor-updated Blender (5.1 → 5.5)
  keeps every finished preview, and setup asks to confirm a re-render only for another major version (5.x → 6.x).
  Previews made before keep counting as finished once the app has seen that Blender, so open the app (or scan)
  once after upgrading, before you move Blender.

- **Tooltips everywhere**: every icon button, non-obvious action and informative icon, badge or count shows a
  tooltip on hover and keyboard focus that says what it is or what will happen (the variant count on asset cards,
  queue controls, folder actions, setup steps…). Native browser tooltips are gone outside the 3D viewer; truncated names and
  paths show in full in the same tooltip.
- **Faster startup scans**: a scan reads only files whose content changed since the last scan; an unchanged
  library scans about ten times faster. Each scan writes one summary line to the log (files, changes, seconds
  per phase).
- **Quiet launch check**: at launch the top bar shows "Checking for changes" instead of scan phases; a check that
  finds changes says so in one note ("Library updated · 3 new"), and the Library no longer reloads the shown
  folder while a scan only reports progress.
- **Search by reference** is now called "Similar to an asset" and picks any library asset as the reference; the
  pilot wording is gone from search, filters and CLI help.
- **Asset inspection is one scroll**: the Overview / Sources / Evidence tabs are gone. A fault line comes first
  when something is faulty, then the preview, clickable fact chips (triangles, format, dependency files, rig,
  animation clips, license; measurements taken from another format than the one shown name that format, with a
  warning line under the chips), the description, tags and three collapsible sections (File & license, Geometry or
  Image, Processing record) that stay open or closed as you left them, also after a restart. The always-unknown
  physical scale, the owner review states and the empty "no notes / no faults" lines are no longer shown; agents
  still receive every field through `get_asset`.
- **Live 3D in the inspector**: a model's still shows at once and its live 3D view loads by itself after a quarter
  second and fades in; there is no Open button or Back to image any more. View buttons (3/4 · Front · Side · Top),
  fullscreen and a ⋯ menu sit on the canvas; double-click fits, R resets. Formats the viewer can't open, models over
  16 MiB ("Large model · click to load") and load faults say why over the still. While the inspector shows an
  asset, arrow keys in the results select as they move, and browsing fast loads no viewer for the assets it passes.
- **Edit and generate descriptions from the inspector**: the description section shows one line and one action
  for its state: **Generate description** for one asset, its place in line or that it is being written, the
  failure with **Try again**, **Set up descriptions** when no description model can run, and **Edit** on a
  generated description. An edit corrects the text and, under **More details**, what the asset is and its
  shape, colors, parts, style, distinguishing features and uncertainties; search follows the edit in the
  background (no description model runs for it). An edited description says **Edited** and keeps the generated
  original under **Show original**; editing a description shared by a variant group changes it for all its
  variants. Editing replaces approval: the owner-review and artistic-suitability states are gone from the
  inspector and the **Review** chip from the cards (stored values are kept).

### Removed

- **Pilot-only CLI commands**: `pilot`, `inspect --phase` and `review-sheet`, with their `--selection`, `--phase`,
  `--timeout` and `--retry-faults` options. They only worked on the original 40-asset pilot data. Libraries no
  longer fall back to `data/pilot/selection-manifest.json` when `data/library/membership.json` is missing.
- **Pilot-era and one-time scripts**: `scripts/historical/` and eight one-time check scripts in `scripts/`
  (`publish_embedding_evidence.py`, `summarize-agent-evidence.py`, `preservation-dry-run.py`,
  `verify-source-preservation.py`, `verify-model-relocation.py`, `verify-asset-foundation.py`,
  `verify-library-nochange.py` and the stale `verify-loading-states.py`). They needed the original owner's data
  or code that no longer exists; they stay in git history at commit `af02e91`.
- **Overnight descriptions runner**: `Generate overnight descriptions.cmd`, `scripts/overnight-descriptions.py`
  and its guide. Descriptions run from **Generate descriptions** in the app or `local-assets describe`; run
  folders already under `data/overnight-descriptions/` are left as they are.
- **Migration from 0.1.0**: `scripts/migrate-library.py`, `scripts/check-rekey.py` and the app's "move your
  results" notice. 0.2.0 is a fresh start; a 0.1.0 generated folder inside a library folder is still never
  scanned as assets. Upgrades are supported from 0.2.0 on.
- **Unused code**: the frozen-benchmark arithmetic (`evaluation.py`), the pilot review-page checker
  (`caption_review.py`), the never-called schema 1 → 2 catalog migration (`catalog_migration.py`) and the desktop
  bridge's unused `source_browse` call. Nothing the app, the CLI or the MCP server does changes.

## [0.2.0] — 2026-11-05

**Upgrading from 0.1.0:** start with a fresh library. 0.2.0 changes where results live and doesn't upgrade a 0.1.0
install; add your library folders again and process them. Supported upgrades start from 0.2.0.

### Added

- **Library**: library folders replace asset sources (`local-assets library …`; `sources …` still works). Browse
  by folder, bundle, pack and folder, with a card state for every asset, pack headers, context menus and Show in
  pack from search. Packs are detected from structure (license, readme, preview image, versioned names) and can
  be made, merged or renamed (`local-assets packs`).
- **Recognized files**: moved or renamed files keep their ID, previews, descriptions and collection entries;
  copies share finished results; vanished files show as Missing until you forget them.
- **Image kinds**: images are sorted into model textures, material textures and 2D images, with the evidence;
  a folder can be corrected (`local-assets library images`).
- **Variant groups**: `Car_11_R/G/B` become one card with variant chips and a shared description, unless you
  ask for separate ones (decision 0024).
- **Pack profiles**: a pack says whether it needs a structure and why, with versioned rules, Restore and export
  (`local-assets packs signals|profile|apply|revert|export`).
- **Add library folder wizard**: a quick look at names only, a verdict per pack, then **Let my agent finish**,
  **Review myself** or **Later**.
- **Agents**: guided setup (the agent checks Blender, runtimes and weights itself, the app shows a report with
  Undo and **Looks good**), pack structure tools (`list_packs`, `get_pack_outline`, `get_profile`,
  `propose_profile`, `finish_structure`, `say`), an Agent activity panel, grouped proposal review with one
  **Apply decisions** (decision 0025), **Try your agent** practice packs, a **Connect your agent** setup step,
  and an agent entry check (`setup agent check`, `doctor`).
- **Processing queue**: Make previews and Generate descriptions on a pack, folder or selection; previews first,
  estimates, and ask-first for long or large jobs (`local-assets previews`, `describe`, `queue`). Asset
  processing shows Running, Up next, Blocked, Recorded failures and Recent, with measured progress.
- **Parallel rendering** in kept-open Blender processes on the CPU or a GPU, sized by a short speed test and
  your limits (`local-assets rendering`, decision 0022).
- **Formats Assetarium uses**: a toggle per 3D and image format; assets in formats that are off are hidden,
  never deleted, and a model previewed from an off format says so (decision 0026).
- **CPU search**: the same EmbeddingGemma model on the CPU (`runtime/embedding-cpu`, about 1 GB), with a thread
  count chosen by a speed test (decision 0018).
- **Search works after setup**: a search check on built-in samples (a cube, a pyramid, a sphere), and a search
  readiness panel in Settings → General with **Check again** (`local-assets setup search-check`, `setup status`).
- Excluded folders, duplicate export folder suggestions with **Group** (decision 0019), a texture folder choice
  for **Textures not found** (decision 0021) and **Recheck failures** (`local-assets recheck`, decision 0020).
- **Session logs**: one readable log per app, MCP or CLI run in `logs/` (`local-assets logs`,
  `Assetarium (with log).vbs`).
- **Blender installation** panel in Settings → General, and **Copy** on every command the app asks you to run.
- **Newer data is left alone**: data written by a newer Assetarium is refused and left unchanged.

### Changed

- Nothing is written into asset folders: results live in one library store (`data/library-store/`, or
  `[storage].library`), keyed by their inputs (decision 0023).
- Every supported type is always included; Settings loses the Asset sources section, **Include 2D images** and
  import format limits.
- A connected agent may apply setup values at any time (labeled *Set by agent*); the Blender path stays a
  proposal (decision 0024).
- Descriptions from a local model server no longer need `.venv-caption`; setup's step is "Descriptions and search".
- The runtime wrappers refuse project commands without `--project`.
- Contributor docs moved to the `Assetarium KnowledgeBase/` vault; `docs/` keeps user guides; machine details
  go in an ignored `MACHINE.local.md`.

### Fixed

- Large libraries: a 73,000-asset folder opens in about a second, and a 16,504-file rescan takes 21 seconds
  instead of 8½ minutes. Sources over about 12,000 files no longer fail their rescan.
- A crash mid-write no longer hides every source.
- Descriptions are no longer rejected for wording alone or for one-piece objects with no listed parts.
- Flat card models no longer fail with an empty preview; a broken alternate file fails only that file.
- Assets no longer stay "pending" after grouping export folders, and Make previews no longer offers work it
  then refuses.
- Search: no "contract mismatch" from LF/CRLF checkouts, a clear message for an incomplete search runtime, and
  fresh installs can build search data.
- 3D and image viewing use the right data revision everywhere, and the 3D preview opens from collections.
- Show in Explorer selects files with spaces, commas or Unicode in their paths.
- Setup saves the Blender it found, so the speed test is no longer blocked.

## [0.1.0] — 2026-10-25

First public release.

### Added

- Windows desktop app: asset sources, startup scans, explicit asset processing with
  progress and cancellation, search, 3D viewer, image viewer, collections and tags,
  notifications, light and dark themes.
- 3D inspection and previews in Blender (FBX, glTF/GLB, OBJ); 2D image catalog (PNG, JPEG,
  WebP, GIF, BMP, TGA, TIFF, AVIF, SVG).
- Optional local AI descriptions (Qwen3-VL-2B, or an experimental OpenAI-compatible local
  model server) and appearance/image search (EmbeddingGemma).
- Keyword, description, image and combined search with bounded results.
- Collection exports: JSON, Markdown, PNG sample sheet and printable report.
- Setup wizard in the app and the terminal, and agent-assisted setup.
- STDIO MCP server with search, asset detail, collection, tag and setup tools.
- Owner command line for Windows and Linux; Linux supports the command line and MCP server.
