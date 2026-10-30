---
tags: [decision]
decided: 2026-10-30
---
# 0023 — Hidden `.assetarium` metadata folder per source, one-time migration, absorbing sources

**Decision (owner, October 30, 2026; [ASSETRM-0002](../Notebook/Roadmap/Features/ASSETRM-0002.md),
plan in [ASSETRM-0002 plan](../Notebook/Roadmap/Features/ASSETRM-0002%20plan.md)).** Everything
Assetarium generates for a source keeps living **inside that source**, in a hidden folder named
**`.assetarium/`**, which replaces `metadata-lal/` (the project's old name). On Windows the folder
also gets the hidden attribute.

- **Why in the source.** The central registry already recognizes sources. The folder is kept for
  what a central store cannot give: identity and results that survive moving the folder (the
  owner's packs moved from drive C to drive D and kept every result), a processed pack that carries
  its previews and descriptions to another install, and remove/re-add without loss. A dot-folder
  is skipped by Godot and Unity and hidden on Linux. Accepted costs: Assetarium writes into asset
  folders (only into `.assetarium/`), read-only media cannot be sources, and cloud-synced folders
  sync the results (Add folder warns). A hybrid (identity in the source, results central) and a
  central-only store were rejected: both lose portability and need a multi-GB move.
- **`source.json` schema 2.** Identity, excluded folders, export answers and the texture folder
  as before. Per-source `import_types` and `import_formats` are dropped (every supported type is
  always included). New `anchors` record absorbed sources.
- **One name in code.** The folder name exists once as a constant, with the legacy name as a
  second constant used only to read, reserve and migrate old folders. No other code, test, script,
  UI text or live doc spells `metadata-lal`, and a test enforces it. The Blender worker gets the
  folder from its job instead of a literal. That edit keeps fingerprints only through
  `incremental.EQUIVALENT_WORKERS`, proven with `scripts/check-render-stability.py`
  ([decision 0022](0022-parallel-rendering.md)).
- **One-time migration** (`scripts/migrate-metadata-folders.py`). It finds every `metadata-lal`
  at any depth under registered, detached and owner-named roots. It converts each folder once (a
  receipt bars reruns for that folder) and merges nested old folders into the roots the owner
  names. It relinks registry entries whose folders moved, matched by the source identity. It shows
  a dry run first and needs an interactive confirmation to apply. It keeps evidence, deletes
  nothing and never edits originals.
- **Absorbing contained sources.** A new root that contains existing sources (in the migration or
  through Add folder) absorbs them through **pack anchors**. The files of an absorbed source keep
  their logical paths under its old key, so asset IDs, fingerprints, previews, descriptions,
  collections and owner edits are unchanged and nothing is reprocessed. Results move by rename,
  an asset ID collision stops that source with a recorded fault, and the rest of the old folder is
  kept as evidence under `absorbed/<id>/`.

**Keep true.** Originals are read only; only `.assetarium/` is written. Evidence files keep their
recorded absolute paths (only file names are read from them). The app never migrates silently: an
unmigrated folder keeps working and shows the command to run. Absorbing never re-identifies an
asset.

Supersedes the folder name in [decision 0019](0019-source-folders-and-export-variants.md) and
[decision 0006](0006-retention.md); their rules are unchanged.
