# Changelog

All notable changes to Assetarium are listed here. The project follows
[Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- **Asset sources** tab (the folder icon above Settings): browse by place through library folders,
  bundles, packs and folders, with coverage, "+N new", a card state for every asset (no previews
  yet, queued, ready, blocked with its fix, recorded failure, missing), a pack header with its
  cover and license, folder and pack panels, context menus, double-click to Explorer and Show in
  pack from search results (decision 0023).
- Packs are detected from folder structure (license, readme, preview image, versioned names), and
  you can make a folder a pack, merge it into its parent or rename it (`local-assets packs`).
- **Make previews** and **Generate descriptions** on a pack, folder or picked assets go to a
  processing queue: they start at once or wait in line, previews go first, long jobs show an
  estimate and ask first, descriptions can wait for an overnight window, and work left from a
  previous session waits paused (`local-assets previews`, `describe`, `queue`).
- Asset processing shows Running (with a copyable live log), Up next, Blocked (with the fix),
  Recorded failures (by stage and reason) and Recent.
- Every supported type is always included. Images are sorted into model textures (kept with their
  model), material textures and 2D images, with the evidence for each; "Treat images here as
  textures / as 2D assets" corrects a folder (`local-assets library images`).
- 2D images show their original file before any processing.
- Files that move or are renamed keep their ID, previews, descriptions, reviews and collection
  entries; copies share finished previews and descriptions instead of rendering again; vanished
  files are listed as Missing until you forget them (`local-assets forget-missing`).
- `scripts/migrate-library.py` moves existing results into the library store once, with a dry run
  first, without rendering or describing anything again. It prints its progress, and running it again
  after a fault imports the folders that failed and checks unverified ones again.
- Models that borrow textures from a sibling project folder keep them when those folders sit inside one
  library folder, as when separately added folders are joined (decision 0010 amendment).
- Agents get each asset's detected `pack_name` and `pack_path` from `search_assets` and `get_asset`.

- **Settings → General → Blender installation** shows whether a Blender is saved (Saved, Not
  saved, Missing, Not found), checks it on request and changes it with the same choose, check and
  confirm steps as the setup wizard, without running setup again.
- Faster previews: Process assets renders several assets at once in Blender processes that stay
  open between assets, on the CPU or a graphics card (decision 0022). A short speed test on your
  computer (about 2 minutes, synthetic shapes only) picks the faster device and how many renders at
  a time help; it runs on the next Process assets or from **Settings → General → Speed test → Test
  again** (`local-assets rendering test`). You can choose the device, limit renders at a time, and
  set how much memory rendering may use (`local-assets rendering set`); limits never go past the
  fastest tested number or the memory that is free. Finished previews stay valid and are not
  rendered again; cancelling or closing the app finishes the running renders, and a stopped run
  resumes where it left off.
- Search by description and by image can run on the CPU: choose **Where search runs** in
  Settings → General, the setup wizard, `local-assets settings set --search-device cpu` or
  the agent's `apply_setup`. It uses the same EmbeddingGemma model and precision with a
  CPU-only search runtime (`runtime/embedding-cpu`, about 1 GB). Indexing is slower than on an
  NVIDIA GPU; searching feels the same (decision 0018).
- Excluded folders per source (Settings → Asset sources, `local-assets sources exclude|include`):
  a folder name with `*` or a path inside the source; excluded folders are not scanned.
- Duplicate export folder suggestions: sibling folders whose model files have the same names
  (for example `FBX/`, `OBJ/` and `Unity FBX/` copies) are suggested per source, and grouped as
  alternate files of the same assets only when you choose **Group**. You can also keep them
  separate or exclude the extra folders, and undo an answer (decision 0019).
- Grouped files keep their folder as a variant label; `get_asset` lists `source_variants` and
  accepts `source_variant` to pick, for example, the `Unity FBX` file.
- **Textures not found** per source: when models can't find textures that the source holds under
  the exact same name (for example once per render pipeline folder), choose the folder to use and
  whether single copies may be used; Apply repairs every model whose textures all resolve, on the
  next Process assets, without changing originals (decision 0021).
- **Recheck failures** on a source's Asset processing card (and `local-assets recheck`): reruns
  the file check and, after you confirm, retries failures that came from it and pass it now.
- `scripts/record-embedding-capability.py`, the one-time search check on two of your own
  processed assets. Setup lists it, and Process assets names it when it is missing.
- **Settings → General → Search** lists what search needs on the chosen device (GPU, search
  runtime, model weights, search check) with the command for anything missing, and **Check again**.
  `local-assets setup status` lists search on its own, whichever description engine you use.

### Changed

- Nothing is written into asset folders any more: previews, descriptions and search data live in
  one library store (`data/library-store/`, or `[storage].library` in `config.local.toml`), which
  counts against the storage budget. Run `scripts/migrate-library.py` once to move existing
  results (see Asset sources in the docs).
- Library folders replace asset sources: `local-assets library …` replaces `sources …` (still
  accepted). Adding a folder around library folders replaces them and keeps their assets.
- Settings has no Asset sources section and the per-source **Include 2D images** checkbox and
  import format restrictions are gone; the source browser page is replaced by the Asset sources tab.

- Contributor documentation moved into `Assetarium KnowledgeBase/`, an Obsidian vault that also reads on
  GitHub: decisions, current status, contracts, the roadmap and per-area notes. `docs/` keeps the
  user guides; the October 2026 progress journal is frozen in `docs/history/`, and the one-time
  pilot reports were removed (they remain in git history).
- `CLAUDE.md` and `AGENTS.md` no longer describe one computer. Each contributor's hardware, tool
  paths and Linux check setup go in an ignored `MACHINE.local.md`, which agents create when it is
  missing.
- Duplicate export folder suggestions also catch near misses: folders that share at least 90% of
  their model names, such as a `Unity FBX` copy missing a few models or repeating one name in two
  subfolders. The suggestion says which names stay as they are, and Group groups only the shared
  names. Earlier answers and exact suggestions are unchanged.
- Search data on the CPU builds about 25% faster: it uses more CPU threads than one per physical
  core. The speed test picks how many (the fewest within 3% of the fastest), and **Settings →
  General → Search → CPU threads for search data** (`local-assets settings set --search-threads`)
  lets you choose, for example to keep threads free. Vectors are identical at any thread count, so
  existing search data stays valid.
- Descriptions from a local model server no longer need the description runtime
  (`.venv-caption`); only the built-in engine does.
- The setup wizard's descriptions step is now "Descriptions and search".

### Fixed

- Descriptions are no longer rejected for wording alone. A sailing ship's "rigging" is its
  ropes, not a character rig, and phrases such as "designed for use in games" in the
  description are now kept with a review note instead of failing it. The 35 descriptions an
  earlier run rejected this way were accepted from their saved output without running the
  model again.
- Search failed with "Query/index embedding contract mismatch; reindex explicitly" when a source's
  search data was built on a checkout with other line endings (LF vs CRLF) and no search check had
  been recorded on this install. The search code and runtime lock were identical, so search now
  accepts that data without reindexing, and a later search check records the same contract. A
  real code or lock change still requires a reindex.
- Search no longer fails with "Embedding worker exited without result" when the search runtime is
  incomplete. It names the missing packages and the command that installs them, starts no worker,
  and works on the next search once the runtime is installed. A worker that exits names its exit
  code and log file, and a kept worker fault says to restart Assetarium.
- The runtime wrappers (`mcp-runtime`, `caption-runtime`, `embedding-runtime`, `.ps1` and `.sh`)
  refuse `sync`, `run` and other project commands without `--project`. Without it uv installed the
  base project into the runtime's environment and removed the runtime's own packages.
- The setup wizard now saves the Blender it found when none was saved yet. It used to treat a
  discovered Blender as already in use and write nothing, so a fresh install had no saved Blender
  and the speed test stayed blocked ("Set up Blender to test render speed"). The speed test also
  sees a Blender saved after the app started, without a restart. Run setup again (or use Blender
  installation) to save yours.
- One-piece objects such as rocks, pebbles and grass clumps no longer fail their description
  because the model listed no separate parts; shape, colors and style are still required.
  Descriptions that already failed this way stay recorded until you retry them.
- After grouping export folders, a source could ask for **Process assets** forever: its search data
  was all reused, or its recorded failures were kept, but the assets stayed "pending". Processing now
  records those states again; recorded failures show as failed and are still never retried.
- Flat card models (grass and cloud sprites with no thickness) no longer fail with "Empty or
  off-frame preview detected": a view that sees the card edge-on is rendered again turned toward
  its face. Finished previews are unchanged and not rendered again.
- The interactive 3D preview now opens from asset cards inside a collection; it no longer
  reports "Library changed; refresh the inspection card." for assets that preview fine from search.
- After a crash or forced shutdown during processing, Settings → Asset sources showed "No asset
  sources yet" and processing could not resume: a search index left mid-write could not be read
  until something wrote to it. Reads now let SQLite undo the unfinished write first (finished data
  is kept), a source whose data cannot be read shows that on its own card without hiding the
  others, and a source list that fails to load says so instead of claiming there are no sources.

- After grouping export folders, already processed assets stayed "pending" forever: Process assets
  reused their finished previews and descriptions but never marked those stages complete again,
  and Generate descriptions had nothing to start from. Reused results now mark their stage
  complete, and a reuse-only pass runs without starting a model.

- A broken alternate file (for example an OBJ whose texture path points at the pack author's
  computer) no longer fails the whole asset: only that file is marked unusable, with its reason,
  and the asset is rendered from its good file. Healthy assets keep their fingerprints (decision 0020).

- Scans of large sources spent minutes matching every asset against every file (supplied
  previews) and every other asset (name variants); both now look up names directly, with
  identical results. A rescan of a 16,504-file source went from about 8½ minutes to 21 seconds.
- Sources with more than about 12,000 files failed every rescan with "Managed manifest exceeds
  its bounded size": their scan cache outgrew the 4 MiB limit for app JSON files. The scan cache
  now has its own 256 MiB bound; every other file keeps 4 MiB.

- A fresh install could not build search data: the search check only worked with the original
  pilot assets, and the first search stage stopped with "Verified embedding contract missing".

- README: the setup welcome screenshots now show the current page with the
  "Set up with your AI agent" and "Set it up yourself" choices, and the README explains both.

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
