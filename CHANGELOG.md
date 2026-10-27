# Changelog

All notable changes to Assetarium are listed here. The project follows
[Semantic Versioning](https://semver.org/); the format follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

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

### Changed

- Search data on the CPU builds about 25% faster: it uses more CPU threads than one per physical
  core. The speed test picks how many (the fewest within 3% of the fastest), and **Settings →
  General → Search → CPU threads for search data** (`local-assets settings set --search-threads`)
  lets you choose, for example to keep threads free. Vectors are identical at any thread count, so
  existing search data stays valid.
- Descriptions from a local model server no longer need the description runtime
  (`.venv-caption`); only the built-in engine does.
- The setup wizard's descriptions step is now "Descriptions and search".

### Fixed

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
