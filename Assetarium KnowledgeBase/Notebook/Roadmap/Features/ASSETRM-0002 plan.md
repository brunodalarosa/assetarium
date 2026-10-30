---
tags: [roadmap]
id: ASSETRM-0002
type: plan
status: agreed
created: 2026-10-30
code: [sources.py, sources.generated_path, sources.owners, sources.add, catalog.asset_id, catalog.walk_source, image_catalog.py, incremental.inspection_input, incremental.caption_input, incremental.recorded_fingerprint, incremental.EQUIVALENT_WORKERS, image_inspection.inspection_input, hash_cache.py, publication.py, source_operations.py, gpu_queue.py, overnight.py, library_policy.py, src/local_asset_library/blender_worker.py, frontend/src/ui/Shell.tsx, frontend/src/ui/AssetGrid.tsx, frontend/src/pages/Processing.tsx, frontend/src/pages/Settings.tsx, frontend/src/pages/SourceBrowser.tsx]
---
# ASSETRM-0002 plan: Asset library rework

Implementation handoff for [ASSETRM-0002](ASSETRM-0002.md), from a brainstorm with the owner on
October 30, 2026. The binding summary is [decision 0023](../../../Decisions/0023-central-asset-library.md).
Every phase still goes through the **`AGENTS.md` scope-and-plan checkpoint** (scope, duration,
disk, risks) before code changes. Read the [Sources and Catalog hub](../../Sources%20and%20Catalog/Sources%20and%20Catalog.md),
[Sources](../../Sources%20and%20Catalog/Sources.md), [Stage ledger and fingerprints](../../Processing/Stage%20ledger%20and%20fingerprints.md),
decisions 0004, 0006, 0019–0022 and the [Catalog contract](../../../Architecture/Sources%20and%20Catalog/Catalog%20contract.md)
first.

## 1. Owner decisions

| # | Topic | Decision |
| --- | --- | --- |
| D1 | Generated data | **One central library store**; nothing is written into asset folders. It counts against the **Settings storage budget**, the only storage limit (ASSETRM-0003 removes the pilot-era target). |
| D2 | Results | **A cache keyed by inputs** (content, dependencies, settings, code), never by asset ID or path. An asset points to its results. |
| D3 | Identity | **By recognition.** IDs are assigned once at first sight and kept through moves and reorganizations. Existing IDs are kept. |
| D4 | Structure | **Library folders → bundles → packs → folders.** A pack is a light object: a name, a cover, an auto-detected license. No tags, and never in collections (collections are smaller than packs). |
| D5 | Types | **Every supported type is always included.** Images are classified as **model texture**, **material texture** (its own kind in v1) or **2D image**. |
| D6 | Excluded folders | Kept, along with duplicate-export answers (0019) and the texture folder (0021), now attached to packs and folders. |
| D7 | 3D thumbnails | No automatic rendering. A clear **"no previews yet"** card state plus a pack-level **Make previews** action. 2D images display their original file and need no processing to be seen. |
| D8 | Processing levels | **Make previews** (inspection, views and search data, never split) and **Generate descriptions** (only when descriptions are on). |
| D9 | Queue | **Implicit queue**: actions start at once or wait in line, and the scope is resolved when the item starts. **Previews always run ahead of descriptions.** An **overnight** switch holds descriptions until a chosen window. |
| D10 | Confirmation | Under 10 min: starts on a click. 10–30 min: starts, with an **Undo toast**. Over 30 min: a **popover asks first** (estimate: counts, time range, disk, budget). |
| D11 | Missing and offline | An unreachable library folder is **Offline**; vanished files are **Missing**. Results and collection entries are kept until **Forget missing**. Unreferenced results are removed only by an explicit action. |
| D12 | Tabs | **(C)**: Home = search, the **Asset sources** tab = browse by place. One shared grid and inspector; search results offer **Show in pack**. The folder-icon rail item sits above Settings; **Settings → Asset sources is removed**. |
| D13 | Migration | A one-time script **re-keys** existing `metadata-lal/` results into the store (no re-render, no regeneration), merges nested old sources, relinks moved ones (the owner's C → D move). Removing the old folders is a **separate interactive owner-only step**. |
| D14 | Old name | **No hardcoded `metadata-lal`** outside the migration and frozen history; a test enforces it. |
| D15 | Roadmap step 4 | This rework delivers texture recognition as a kind. Afterwards, rewrite [step 4](../../../Architecture/Roadmap/Prompts/04-textures-and-materials.md) to cover only material sets on top of it. |

Still binding: originals are read only; scans never run models; processing starts only from an
owner action; faults keep their evidence and are never retried automatically; changing settings
never deletes results.

## 2. Why this shape (brainstorm record)

- **The problem was identity, not the folder.** Today `catalog.asset_id(pack, identity)` hashes the
  source key and the path inside it, and inspection fingerprints include the asset ID and file
  paths. That one choice is why nested old sources, moved drives and "add a parent folder" each
  needed their own repair mechanism (pack anchors, relink, absorb). Recognition plus input-keyed
  results removes all of them.
- **Rejected: a hidden `.assetarium/` folder in each source** (the first plan). Its only real
  advantage was carrying results along with a pack. The owner rarely moves packs; they **add
  files over time**. Its costs were writes into user folders, no read-only media, cloud-sync bloat
  and nesting.
- **Rejected: a separate thumbnail tier.** KayKit's inspections take a median of about 4 s per
  asset for 3 views, mostly file import and setup. A one-view tier would save little and then be
  redone.
- **Rejected: a start-time picker and an explicit basket.** With two processing levels, actions on
  the tree or grid plus the confirmation thresholds give the same control with less ceremony.
- **Rejected: one merged browser (route B).** Search and browsing are different moods; a shared
  grid stops them from drifting apart.

## 3. Target model

### 3.1 Library store

`[storage].library` in `config.local.toml`; the default is `data/library-store/` (ignored).
Proposed layout (the implementer refines it at the phase 1 checkpoint, reusing `publication.py`
generations and `atomic_json`):

```
library-store/
  library.sqlite            library folders, bundles, packs, assets, file locations, recognition history
  results/<stage>/<kk>/<key>/   inspection and previews, image derivatives, captions (key = input hash)
  ledger.sqlite             stage ledger and history (today each source's jobs.sqlite)
  generations/              published catalog and search index (immutable, decision 0006 retention)
  queue/                    processing queue and run records
  absorbed/<old source id>/ migration evidence (old operation logs, batches, receipts)
```

- `sources.generated_path` (today's resolver from logical `data/...` paths to `metadata-lal`)
  becomes a resolver into the store. **All result access goes through it**, so the earlier
  "logical paths in records" design carries over.
- The storage budget (`library_policy`) measures the store instead of the `metadata-lal` folders.
  The budget help text (`frontend/src/app/format.ts`, `owner_commands.py`) changes with it.

### 3.2 Input-keyed results and the fingerprint redefinition (riskiest part)

The current fingerprints contain location:
- `incremental.inspection_input` hashes `asset_id`, `pack`, `name` and file `path`s
  (source-key-prefixed) together with content hashes, worker hashes and settings.
- `incremental.caption_input` hashes view `path`s, which embed `asset_<id>` folders.
- `image_inspection.inspection_input` hashes the image `path`.

New result keys: **file content hashes, dependency content hashes and their paths relative to the
inspected file, settings and code hashes.** No asset ID, no pack and no absolute or source-prefixed
paths. Relative dependency paths stay in the key because they change what Blender resolves.
Caption keys use view content hashes, not view paths.

**Re-keying, never re-queuing:** for each existing result, the migration recomputes its old
fingerprint from its record (proving it is current, as `recorded_fingerprint` does today), then
computes the new key from the same inputs and files the result under it. A result whose old
fingerprint no longer matches its record is filed as **stale** and stays pending, exactly as it
would today. Phase 1 must prove on a copy of the owner's library that the **pending count after
re-keying equals the pending count before**.

The Blender worker builds its output root from `source_root / "metadata-lal"`, and its hash is
part of the inspection fingerprint. It must take its output root from the job instead. That edit
keeps results only through `incremental.EQUIVALENT_WORKERS`, proven with
`scripts/check-render-stability.py` ([decision 0022](../../../Decisions/0022-parallel-rendering.md)).
Land it in its own commit with the stability receipt. Confirm the batch and repair workers again
during implementation (today they do not contain the literal).

### 3.3 Identity by recognition

- `library.sqlite` holds every asset's ID and its current file locations, content hashes and
  stat identities (seeded from `cache/file-hashes.sqlite`, decision 0004).
- **New asset:** the ID is computed **once** with today's formula (`asset_id(pack, identity)` at
  first sight), then stored and never recomputed. That keeps IDs deterministic for a fresh install
  of the same pack.
- **On each scan:**
  - A file at a known path with a known stat identity is the same asset (no hashing).
  - A new path whose content matches a Missing asset is that asset, **moved**: the ID, results,
    overlays and collections are kept.
  - A new path whose content matches an asset that still exists is a **duplicate**: a new ID that
    shares the cached results through D2.
  - A known path with new content is the same asset, **edited**: its results no longer match, so
    it becomes pending.
  - A vanished path with no match becomes **Missing**.
- Grouped assets (export variants, decision 0019) are recognized by their reference file. Their
  other files follow the group.
- Record the evidence for each recognition (moved, duplicate, edited) in the recognition history,
  so an unexpected identity can be explained.

### 3.4 Library folders, bundles, packs

- A **library folder** is a watched root (today's source registry, `data/library/sources.json`,
  becomes rows in `library.sqlite`). Overlap rules: adding a folder **inside** a library folder is
  refused ("already covered", with Show it). Adding one that **contains** library folders replaces
  them: recognition keeps every ID and result, so this is just a registry change plus a rescan.
- **Pack detection** (structure only, never publisher names; decision 0019's rule):
  - A pack is the folder closest to the assets that carries pack markers (license, readme,
    preview image, `.url` shortcuts, versioned names such as `Name_1.0_FREE` or `Name 3.7.0`).
  - A folder whose children are packs is a **bundle**.
  - Without markers, the first folder under the library folder that contains assets is the pack.
  - Owner overrides **Make this a pack** and **Merge into parent pack** are saved and survive
    rescans.
  - Checked against the owner's library: `Kenney All-in-1` → `2D assets` (a category inside the
    bundle) → `Tiny Dungeon` (a pack); `KayKit_Free_pack` → 13 packs; `Cartoon City Massive
    Pack` → 5 `CCMP_*` parts the owner would merge.
- A **pack object**: display name (editable, defaults to the folder name), cover (the pack's
  preview image if any, else the first processed asset), license evidence (today's nested
  license attachment, `catalog` license rows), counts, last processed, and "+N new since last
  visit". No tags and no collection membership.
- Exclusions, duplicate-export answers and the texture folder move from `source.json` to the pack
  or folder they name. Their meaning is unchanged.

### 3.5 Image classification

Every layer records `{value, basis, evidence}` like `image_catalog.suggested_purpose`, never a
bare fact. Kinds: `model_texture` (a dependency, not a selectable asset), `material_texture` (its
own kind, browsable and searchable by name in v1), `image` (2D asset).

1. **At scan** (no decoding, as `image_catalog` requires):
   - Model references: glTF image URIs, `.mtl` `map_*` lines, ASCII FBX `RelativeFilename` and
     the filename strings in binary FBX. A match means `model_texture`.
   - **Pack prior:** a pack with no models means its images are `image` (with material-name
     images as `material_texture`).
   - Material naming: `_albedo`, `_basecolor`, `_diffuse`, `_normal`/`_nrm`, `_roughness`,
     `_metallic`, `_ao`, `_height`, `_orm`, `_emission`, `_d`/`_n`.
   - Proximity: beside models or sharing a model's stem leans texture. Folder words (`textures`,
     `materials`, `maps` vs `icons`, `sprites`, `ui`, `logos`) and sprite-sheet sidecars count too.
2. **When decoded** (previews): normal-map mean color (about 128/128/255), single-channel
   grayscale, seamless edges, cutout alpha.
3. **Inspection:** Blender's texture list overrides any guess for that model's files.
4. **Owner answer:** "Treat images here as textures / as 2D assets" on a folder.

The vision model is not used for this.

### 3.6 States

**Work state (one per asset):** `no previews yet` (pending) · `queued` · `running` · `ready`
(previews and search done) · `blocked` (a prerequisite is missing, such as the search runtime or
Blender, shown with its fix and **never** a process action) · `failed` (recorded fault: Copy
error, Recheck per decision 0020) · `missing` · `excluded`.
**Overlays:** `warning` (a caption warning; review notes are not shown as warnings), `description`
(complete, missing or failed, only when descriptions are on), collections count, `new`.
**Non-asset files** (README, HTML…) are grey and faded.

Derive the states from `sources.import_outcome`, `processing_summary` and `description_state`,
and add `blocked` with its reasons. This fixes the Kenney case (previews done, search stage
cannot run) and the mixed failures-and-pending banner.

### 3.7 No hardcoded `metadata-lal` (D14)

The literal stays only in the migration script (as `LEGACY_METADATA_DIR`), frozen history
(`docs/history/`, `scripts/historical/`), `CHANGELOG.md` and the ASSETRM notes. `.gitignore`
keeps `metadata-lal/` so unmigrated fixtures are never committed. On 2026-10-30 `git grep -c`
found it in 41 tracked files:
- `src` (`sources.py` 12, plus `blender_worker.py`, `config.py`, `catalog.py`, `retrieval.py`,
  `owner_commands.py`, `source_migration.py`)
- `tests` (7 files) and `scripts` (`verify-*` 6, `smoke-headless.py`)
- `frontend/src/app/format.ts`, `README.md`, `CLAUDE.md`, `docs/asset-sources.md`,
  `docs/dependency-path-overrides.md`
- 15 vault pages, including decisions 0006 and 0019

Most of these disappear with the store. The rest switch to the store vocabulary. Enforcement:
`tests/test_metadata_name.py` runs `git ls-files` and fails on the literal outside the allowlist
(including `ui/build/`).

## 4. One-time migration

`scripts/migrate-library.py`, run with the base runtime (`.\scripts\uv.ps1 run --locked python
scripts/migrate-library.py …`, same arguments with `uv.sh`). Model it on `source_migration.py`:
refuse links and out-of-root targets, write receipts, never edit originals.

```
migrate-library.py [--library-folder PATH ...] [--search PATH ...] [--apply]
```

1. **Preflight:** the app and MCP server are not running, no operation is active, and a storage
   receipt is saved (`scripts/storage-report.py --output <new>.json`).
2. **Discover:** deep-search registered and detached source paths, `--library-folder` and
   `--search` for `metadata-lal` at any depth, without following links. Validate each one
   (`source.json` schema 1).
3. **Library folders:** each `--library-folder` becomes one, and everything found under it joins
   it (nested old sources need no special handling under recognition). Old sources under no named
   folder become their own library folder.
4. **Relink moved sources:** match found folders to registry entries by `source.json` `id`. A
   registry path that differs is the C → D case and is corrected. Two folders with the same `id`
   are a conflict, and neither is used. An entry that nothing matches is reported with "pass the
   folder that now contains it with `--search`".
5. **Plan (dry run, the default):** per old folder, the asset count, results to re-key, stale
   results, and what D5 enrolls newly. Images previously off: N images. `import_formats` (KayKit
   `["gltf"]`): N files of other formats, proposed as exclusions where whole folders hold only
   those formats. The plan is saved to `data/library/migration/plan-<utc>.json`.
6. **Apply (interactive `yes`, no bypass):** create the store, import the registry, packs,
   exclusions and answers, and assets with **their existing IDs**. Re-key every result (§3.2),
   merge the stage ledgers, keep old logs, batches and generations under `absorbed/<id>/` as
   evidence. **Copy, never move**: the old folders stay intact until step 8.
7. **Verify and receipt:** rescan (no models), check that every previously published asset ID is
   present and that the pending count is unchanged (§3.2), then save
   `data/library/migration/<utc>.json` and a storage receipt.
8. **Cleanup (separate command, `migrate-library.py --remove-old`, interactive and owner-only):**
   only for folders whose import receipt verified. It lists each `metadata-lal` with its size and
   removes it on confirmation.

**Once per folder:** a folder named in a receipt is never imported again; later runs only take
folders no receipt names. A fault stops only its own folder, with evidence, and the others
continue.

**C → D findings (checked 2026-10-30):** the only real breakage of a move is a registry path to
the old drive (step 4). The old absolute paths in `job.json`, `blender.log`, `result.json`,
batches, operation logs and `jobs.sqlite` history are evidence and stay unread. The
`technical.textures[].original_path` values (about 1.5k for KayKit) are read only for their file
name (`texture_folders`, `texture_repair`). Stat identities change between drives, so the first
scan re-hashes once. The implementer repeats this survey at the phase 3 checkpoint.

**Before migration, the app** shows one notice with the exact command and keeps working from the
old folders, read only. It never migrates by itself.

## 5. Asset sources tab

### 5.1 Shell and pages

- `Shell.tsx`: add a rail item **Asset sources** (lucide `Folder`) in the bottom group **above
  Settings**. Its dot means **the owner must act**: a folder offline, an unanswered export or
  texture question, files missing, or a migration needed. Pending work keeps its dot on Asset
  processing.
- Retire `SourceBrowser.tsx` (page `source`) and `Settings` → Asset sources (`AssetSources`). If
  General is the only tab left, Settings shows no tab strip. Move every deep link and the
  `RailItem` special case.
- **Shared grid (D12):** the new tab and Home use the same `AssetGrid` and `Inspector`. Search
  results get **Show in pack**, which opens this tab with the asset selected and its folder
  expanded.

### 5.2 Layout

- **Header:** Add library folder · sort (Name · Recently added · Most without previews · Most
  assets · Last processed) · type chips (3D models · Images · Material textures; built from the
  supported-types list, so audio can be added later) · status filter (Has new · Needs previews ·
  Blocked · Failures · Missing).
- **Left:** a virtualized tree of library folders → bundles → packs → folders (**folders only**),
  using the [beUI motion file tree](https://beui.dev/components/motion/file-tree) vendored into
  `frontend/src/components/beui/` (MIT, see `frontend/README.md`). Each row shows a thin
  **coverage bar** ("73% have previews") and **+N new**. A pack row shows its cover thumbnail and
  display name. Offline library folders are dimmed with an "Offline" label.
- **Right:** the shared grid for the selected folder or pack (list view toggle). Cards carry the
  §3.6 icon strip with tooltips (shape and label, never color alone), and "no previews yet" is a
  designed state (format glyph, name, quiet label), not a broken image. Non-asset files come last,
  faded, behind a **Show other files** toggle that is on by default.
- **Pack header** above the grid: cover, name, license, counts, and the main action for the state
  ("312 models without previews · Make previews"). Previews fill in progressively with a soft
  fade-in.
- **Inspector:** an asset → today's inspection panel. A pack or library folder → its panel (name,
  path, license, exclusions, export answers, texture folder, enable/disable, Rescan, Remove,
  Forget missing).
- Animations: expand and collapse, staggered first reveal, preview fade-in; respect
  `prefers-reduced-motion`.
- Empty state: a short illustration with "Point Assetarium at a folder of game assets" and Add
  library folder.

### 5.3 Interaction

Click an asset to inspect it · click a folder or pack to show it · **double-click any file or folder
to show it in Explorer** (`desktop.show_in_explorer`) · Ctrl- or Shift-click for multi-select in
the grid (for queue actions, Add to collection and Exclude) · keyboard: arrows, Enter, Shift+F10 or
the menu key. Use `tree`/`treeitem` and grid roles.

### 5.4 Context menus

| Target | Items |
| --- | --- |
| Asset (one or several) | Inspect · Show in Explorer · Open with default app · Copy path · Add to collection ▸ · Make previews (when missing) · Generate descriptions (descriptions on, missing) · Fix… (blocked) · Copy error, Recheck (failed) · Exclude containing folder |
| Non-asset file | Open · Show in Explorer · Copy path |
| Folder | Make previews · Generate descriptions · Make this a pack · Merge into parent pack · Treat images here as textures / as 2D assets · Exclude folder · Show in Explorer · Copy path · Expand / collapse all · Duplicate-export answer (when suggested) |
| Pack | Make previews · Generate descriptions · Rename · Merge into parent pack · Forget missing · Show in Explorer |
| Excluded folder | Include again · Show in Explorer |
| Library folder | Rescan · Enable / Disable · Show in Explorer · Copy path · Remove… (confirm; results stay in the store) |

Offer only what can resolve the shown state. Never offer Make previews on a ready, blocked or
missing asset.

## 6. Processing

### 6.1 Queue (backend)

- A queue item is `{action: previews | descriptions, scope: pack | folder | asset list, added_utc}`
  in `library-store/queue/`. The **scope is resolved when the item starts**: "whatever in
  Tiny Dungeon still lacks previews".
- Previews items always run before description items (D9). Otherwise items run in the owner's
  order (drag to reorder, remove). One GPU job at a time (`gpu_queue`). Renders keep the parallel
  Blender pool (decision 0022).
- Each item runs through today's durable operations (`source_operations`, `incremental.process`
  with `asset_ids`). Results publish progressively. Cancel stops the current item cleanly.
- **Overnight:** a switch on Up next holds description items until the overnight window, reusing
  `overnight.py`.
- After a restart, a leftover queue is **Paused** with Resume. It never resumes by itself.
- **Estimate:** counts per stage; a time range from the render speed test (`render_devices`,
  `data/library/rendering.json`) and recent ledger durations; description throughput from recent
  caption batches; disk from the median store bytes per processed asset of that type; whether the
  storage budget would be reached. With no history, say "no measurement yet". If only blocked work
  is in scope, the action is disabled and shows the fix.

### 6.2 Confirmation (D10)

Under 10 min: starts on a click. 10–30 min: starts, with a toast "Started · ~18 min · Undo" for a
few seconds. Over 30 min, or when the budget would be reached: a popover with the estimate and
**Make previews (1,240 models)**.

### 6.3 Asset processing tab

**Running** (progress, phase, Cancel, a live log with **copy buttons on errors and warnings**; the
errors come from run records, not only `logs/gui-worker.log`) · **Up next** (reorder, remove,
overnight switch) · **Blocked** (grouped by reason, each with its fix and the count it unblocks) ·
**Recorded failures** (by stage and reason; Copy, Recheck, Show in Asset sources) · **Recent**
(outcome, counts, duration, log). Pending and failures are never in one banner. The global format
checkboxes stay in Settings only as the format preference (`incremental.choose_source`) for
grouped assets.

## 7. CLI, MCP, docs

- **CLI** (`owner_commands.py`):
  - `library add|remove|list` replaces `sources add|remove`; `sources images` goes away.
  - `packs list|rename|merge|split`.
  - `previews PATH|--pack|--asset [--dry-run]` and `describe …` add to the queue. `queue
    list|move|remove|pause|resume`.
  - `forget-missing --pack`.
  - Keep the 0019 and 0021 commands, re-scoped to packs and folders.
  - Update `docs/cli.md`.
- **MCP** stays read only. Payloads gain `pack` and lose `import_types` and `import_formats`. Do
  not rewrite the hash-bound `docs/mcp/*.json`: raise any contract change at the checkpoint.
- **Docs:** rewrite `docs/asset-sources.md` (library folders, packs, migration). Update
  `docs/gui/README.md` and add `CHANGELOG.md` `Unreleased` entries. In the vault, update Sources,
  the Sources and Catalog hub, Stage ledger and fingerprints, Storage discipline and the Catalog
  contract enrollment section, and add "folder replaced by decision 0023" notes to decisions 0006,
  0019 and 0021.
- **Roadmap step 4** is rewritten after delivery (D15).

## 8. Phases (one PR each into `develop`)

| Phase | Content | Done when |
| --- | --- | --- |
| 1 Input-keyed results | §3.2 new keys, re-key routine, worker output-root edit with the `EQUIVALENT_WORKERS` proof, store resolver behind `generated_path` | On a **copy** of the owner's library: the pending count is unchanged after re-keying, nothing re-renders, duplicates share results; `check-render-stability.py` receipt; full suite green with the real-Blender line |
| 2 Recognition and store | §3.1, §3.3, library folders replace the source registry, Missing/Offline, `test_metadata_name.py` | Tests for move, duplicate, edit, vanish and a contained-folder add (IDs, overlays and collections kept); budget measures the store |
| 3 Migration | §4 | Synthetic fixtures: nested old sources, a moved source relinked by `id`, a duplicate `id` refused, `import_formats`, images off, a rerun refused, a fault isolated, links refused, cleanup refused before verification. The owner reviews the dry run on the real library before `--apply`. Storage receipts before and after |
| 4 Packs and classification | §3.4, §3.5, pack overrides, settings moved to packs and folders | Fixtures shaped like Kenney All-in-1, KayKit and CCMP; texture classifier tests per layer (glTF, OBJ, FBX references, no-model pack, names, pixels) |
| 5 Asset sources tab | §5, shared grid, Show in pack, Settings tab and SourceBrowser removed, `npm run build` | `scripts/verify-asset-sources.py --run-name …` (WebView2); existing verify scripts updated (`verify-source-folders`, `verify-image-browser`, `verify-show-in-explorer`, …) and passing; `test_ui_encoding.py` |
| 6 Queue and Processing tab | §6 | Tests: scope resolved at start, previews before descriptions, overnight hold, paused after a restart, thresholds, blocked-only scope disabled, estimate with and without history; `scripts/verify-processing-queue.py` |
| 7 CLI and docs | §7, ASSETRM-0003 if not done yet | Help and docs match; CHANGELOG |

Phase 1 is first because it is the riskiest. Order: 1 → 2 → 3, then 4, 5 (needs 4) and 6 (needs
2), then 7.

## 9. Risks and open points

- **Re-keying correctness** (§3.2): a wrong key silently re-queues thousands of renders and
  descriptions, or worse, attaches results to the wrong file. Prove it on a copy of the library;
  compare per-asset result sets before and after; refuse to apply if any count differs.
- **Recognition mistakes:** two different files with the same content are a duplicate by
  definition, which is fine. Moved and edited at once becomes a new asset plus a Missing one, which
  is acceptable and recoverable with Forget missing.
- **Store size on the project drive:** the store can be pointed at another drive with
  `[storage].library`; the budget warns before a job would exceed it.
- **Classification errors** flood or hide images. The pack prior and model references cover most
  cases; folder answers fix the rest. Report the counts per kind after a scan, so surprises show.
- **Tree and grid scale:** Kenney-sized libraries have tens of thousands of files. Precompute
  roll-ups and coverage at scan and publish time; virtualize both panes.
- **Open for the owner at phase checkpoints:**
  - The pack-cover fallback when a pack ships no preview image.
  - Whether "+N new" resets on visit or on processing.
  - Whether the 10-minute and 30-minute thresholds should be settings.
