---
tags: [decision]
decided: 2026-10-30
---
# 0023 — Central library store, identity by recognition, packs, implicit processing queue

**Decision (owner, October 30, 2026; [ASSETRM-0002](../Notebook/Roadmap/Features/ASSETRM-0002.md),
plan in [ASSETRM-0002 plan](../Notebook/Roadmap/Features/ASSETRM-0002%20plan.md)).**

- **Nothing is written into asset folders.** Generated results move from each source's
  `metadata-lal/` into one central library store (`[storage].library`, default under the
  project's ignored `data/`). It counts against the Settings storage budget, which is the only
  storage limit. Read-only drives, network shares and asset repositories can be library folders.
- **Results are a cache keyed by their inputs** (file content, dependencies, settings, code
  versions), never by asset ID or absolute path. An **asset is a light identity** (ID, pack, name,
  owner overlays and reviews, collection membership) that points to its results. Duplicates share
  results; a moved or reorganized file keeps its results; an edited file needs processing again.
- **Identity by recognition.** An asset ID is assigned once, when the asset is first seen, and kept
  through moves and reorganizations by recognizing its content (stat identity and hash reuse,
  [decision 0004](0004-stat-identity-hash-reuse.md)). Existing IDs are kept.
- **Library folders → bundles → packs.** Library folders are the watched roots. Packs are detected
  from structure (license, readme, preview, `.url` files, versioned names), never from publisher
  names; the owner can make a folder a pack or merge it into its parent pack. A pack is a light
  object: a name, a cover image and an auto-detected license. No tags; packs are never added to
  collections, which are smaller than packs by definition.
- **Every supported type is always included.** Images are classified as model textures, material
  textures (a kind of their own) or 2D images, by layered evidence (model references, pack
  contents, names, pixels, inspection) and owner folder answers.
- **Processing runs from an implicit queue.** "Make previews" (inspection, views and search data)
  and "Generate descriptions" act on a pack, folder or selection. They start at once or wait in
  line, and their scope is resolved when they start. Previews always go ahead of descriptions.
  Jobs estimated under 10 minutes start on a click; 10–30 minutes start with an Undo toast; over
  30 minutes ask first. Descriptions can be held for an overnight window. A queue left over after
  a restart is shown as paused and never resumes by itself.
- **Missing and offline.** An unreachable library folder is Offline; vanished files are Missing.
  Their results and collection entries are kept until the owner chooses "Forget missing". Results
  nothing points to are removed only by an explicit action.
- **One-time migration.** Existing `metadata-lal/` results are re-keyed into the store without
  re-rendering or regenerating anything. Removing the old folders is a separate, interactive,
  owner-only step after a verified import. No code keeps the old name except the migration.

**Keep true.** Originals are read only. Scans never run models. Processing starts only from an
owner action. Faults stay visible with their evidence and are never retried automatically. A
fingerprint-definition change must re-key existing results, never re-queue them.

Replaces the per-source `metadata-lal/` folder of [decision 0006](0006-retention.md) and
[decision 0019](0019-source-folders-and-export-variants.md) (their rules are unchanged, now
attached to packs and folders) and per-source image enrollment
([Catalog contract](../Architecture/Sources%20and%20Catalog/Catalog%20contract.md)).
