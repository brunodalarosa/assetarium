---
tags: [decision]
decided: 2026-11-07
area: Sources and Catalog
replaces: [0023]
code: [library_store.py, result_store.py, library_migration.py, processing_queue.py, sources.py, asset_structure.py]
---
# 0032 — Library store, packs and the processing queue

> **Approved by the owner on November 7, 2026** (decision review). Consolidates the parts of decision 0023
> (October 30, 2026) that [0028](0028-result-identity.md) and [0029](0029-agent-trust.md) did not take over.

**Decision.** Assetarium keeps everything it generates in one central **library store**, never in asset folders.
Assets are light identities that point to results; library folders hold bundles and packs; every supported type
is included; processing runs from one queue.

## Library store

- **Nothing is written into asset folders.** Generated results live in one central library store
  (`[storage].library`, default under the project's ignored `data/`). It counts against the Settings storage
  budget, the only storage limit. Read-only drives, network shares and asset repositories can be library folders.
- How results are keyed and reused: [decision 0028](0028-result-identity.md).
- **An asset is a light identity**: ID, pack, name, owner overlays and reviews, collection membership. It points
  to its results. Duplicates share results; a moved or reorganized file keeps its results; an edited file needs
  processing again.
- **Identity by recognition.** An asset ID is assigned once, when the asset is first seen, and kept through moves
  and reorganizations by recognizing its content (file identity and hash reuse,
  [decision 0028](0028-result-identity.md)). Existing IDs are kept.
- **Missing and offline.** An unreachable library folder is Offline; vanished files are Missing. Their results and
  collection entries are kept until the owner chooses **Forget missing**. Results nothing points to are removed
  only by an explicit owner action.
- **One-time migration.** The old per-folder `metadata-lal/` results were re-keyed into the store without
  re-rendering or regenerating anything. Removing the old folders is a separate, interactive, owner-only step
  after a verified import. No code keeps the old name except the migration.

## Library folders, bundles and packs

- **Library folders** are the watched roots. **Packs** are detected from structure (license, readme, preview,
  `.url` files, versioned names), never from publisher names; the owner can make a folder a pack or merge it into
  its parent pack. A pack is a light object: a name, a cover image and an auto-detected license. Packs have no
  tags and are never added to collections, which are smaller than packs by definition. How a pack's structure is
  corrected: [decision 0035](0035-packs-and-variant-groups.md).
- **Every supported type is always included.** Images are classified as model textures, material textures (a kind
  of their own) or 2D images, by layered evidence (model references, pack contents, names, pixels, inspection) and
  owner folder answers. Which formats are used: [decision 0031](0031-setup.md#formats-assetarium-uses) and
  [decision 0030](0030-counted-exclusions.md).

## Processing queue

- **Make previews** (inspection, views and search data) and **Generate descriptions** act on a pack, folder or
  selection. They start at once or wait in line; their scope is resolved when they start. Previews always go
  ahead of descriptions. Every operation that ends starts the next waiting item.
- **Who starts work:** the owner, or a connected agent ([decision 0029](0029-agent-trust.md)). Nothing starts by
  itself; scans never run models.
- **Size of a job** (for the owner's clicks): under 10 minutes starts at once; 10–30 minutes starts with an Undo
  toast; over 30 minutes asks first, and so does a job of more than 100 assets with no time or storage
  measurement yet.
- **The app owns its queue.** Closing the app while work runs asks first ("Asset processing ongoing"); **Stop &
  close** stops the running item at once. The next start shows "N items stopped when you closed Assetarium ·
  Continue"; nothing resumes by itself. Work the app started never outlives it: if the app crashes, its
  operations stop too, the reason is logged and the items go to Recent with a link to the log. Work queued from a
  terminal while the app is closed runs to the end. There is no overnight hold.

## Why

Results used to live in a `metadata-lal/` folder inside each library folder. One central store lets read-only
drives, network shares and asset repositories be library folders, lets duplicates share results and moved files
keep theirs, and makes the storage budget the only limit.

## Keep true

- Originals are read only; nothing is ever written into an asset folder.
- Scans never run models. Processing starts only from the owner or a connected agent.
- Faults stay visible with their evidence and are never retried automatically.
- Missing results are kept until the owner forgets them; unreferenced results go only by explicit action.
