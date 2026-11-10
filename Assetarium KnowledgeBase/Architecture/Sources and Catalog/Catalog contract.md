---
tags: [architecture]
parent: "[Architecture](../Architecture.md)"
status: draft
verified: 2026-11-10
branch: feature/audit-simplify
level: system
code: [catalog.py, asset_structure.py, image_catalog.py, image_kinds.py, image_inspection.py, image_media.py, library_store.recognize, sources.aggregate]
---
# Catalog contract

> What one catalog record is, how an asset gets and keeps its identity, and which fields each stage owns.
> Rewritten on 2026-11-10 as the current contract; the step-by-step history it used to carry is in git
> (commit `af02e91`).

Up: [Architecture](../Architecture.md) · Where in code: [Sources and Catalog](../../Notebook/Sources%20and%20Catalog/Sources%20and%20Catalog.md) ·
Binding rules: [0032](../../Decisions/0032-library-store-and-queue.md) (store, identity),
[0028](../../Decisions/0028-result-identity.md) (result keys), [0027](../../Decisions/0027-saved-catalog-first-and-fast-scan.md) (scans).

## The database

Each library folder has a working `catalog.sqlite` in the library store, and the published library has a
combined one. Both are SQLite with `PRAGMA user_version=2`; readers accept 1 and 2 and refuse anything else.

| Table | Holds |
| --- | --- |
| `assets` | One row per logical asset: its ID and the versioned JSON record |
| `files` | The asset's original files, keyed `(asset_id, path)`, so a parent and its children can share a file |
| `inventory` | Every path the scan found, with its role, status, hash and evidence |
| `metadata` | Source binding, fingerprints, scanner version, scan time |
| `asset_fts` | FTS5 keyword index: file names, split camel-case names, pack names, relative paths |

The Python build must pass an FTS5 create/insert/match probe; no other index is used silently. A scan
compares two complete read-only inventories before it changes working data, merges later-stage results
instead of replacing them, and never overwrites owner corrections. Published catalogs are immutable:
changes go through a new generation.

## One record, one logical asset

Paths are relative to the library folder or the project; they are resolved through configured roots
before any access. Original files are opened for reading only.

| Field | Contract |
| --- | --- |
| `schema_version`, `structure_version` | Record version 2 (1 is still read), structure version 1 |
| `asset_id`, `source_id`, `pack_id` | Stable nonempty strings; the ID is unique |
| `source_relative_identity`, `display_name` | The logical identity inside the pack; never an absolute path |
| `asset_type` | `model_3d`, `image` or `audio`. A record without it is a 3D model |
| `identity_version` | `asset-v1`, or `subasset-v1` for an explicit child |
| `files`, `file_roles` | Path, format, SHA-256, availability; each path is `primary`, `alternate_export`, `dependency` or `supplied_preview` |
| `dependencies` | Path, role (texture, material, other), SHA-256 or null, status and how it was found |
| `relationships` | Up to 64: `alternate_export`, `contains`, `depends_on` or `variant`, a target ID and evidence (at most 2,048 characters) |
| `type_metadata` | `version: 1` plus type facts; unknown fields are kept; at most 32,768 JSON characters |
| `grouping` | Method, evidence and unresolved ambiguities for files grouped into this asset |
| `technical` | Measured facts with the inspected file and its hash; null means unknown, never zero |
| `previews` | Rendered or derived images with view label, hash and settings; supplied previews keep their source |
| `description`, `suggested_uses`, `caption_provenance` | What the description model saw, kept apart from measured facts ([caption contract](../../../docs/caption-contract.md)) |
| `owner_overlay`, `effective_caption` | The owner's corrections, stored apart and merged for display; regeneration keeps them |
| `license_evidence` | Supplied files and excerpts; unknown stays unknown, never guessed |
| `embeddings` | Vector references under the [embedding contract](../Search/Embedding%20contract.md) |
| `processing`, `stage_faults` | A state per stage, with recorded faults |
| `provenance` | Timestamps and each stage's input fingerprint |

Stages are `inventory`, `inspection`, `previews`, `caption` and `embeddings`. A stage is `pending`, `running`,
`complete`, `failed`, `unsupported` or `not_applicable`. Empty lists mean no evidence yet. A failed inspection
never falls back to a description made from the file name.

## Identity

- **The formula.** A new asset's ID is `asset_` plus the first 32 hex characters of SHA-256 over the compact
  UTF-8 JSON `["playful-lowpoly-v1", pack_id, identity]` (`catalog.asset_id`; the constant is a fixed salt, kept
  so existing IDs never change). `identity` is the pack-relative path with its extension, or
  `<anchor>/@exports/<stem>` for evidenced sibling exports, or `image:<folder>/<stem>` for an image.
- **Kept by recognition.** The formula only names an asset the first time it is seen. After that
  `library_store.recognize` keeps the ID through moves, renames inside a folder, and a folder added around
  others, by matching the bytes of the asset's files; every recognition is recorded with its reason. An ID
  therefore need not match its formula. A vanished asset becomes Missing and keeps its record, results and
  collection entries until the owner forgets it.
- **Content changes never change the ID.** Matching names or bytes never transfer an owner approval or a
  correction to another asset.
- **Children.** `subasset-v1` is the same hash over
  `["subasset-v1", source_id, pack_id, parent_asset_id, kind, key]` with `kind` one of `frame`, `clip`, `region`
  and a stable key of at most 256 characters. A child's files are a subset of its parent's, and the parent must
  list it under `contains`. No scanner creates children yet; they are the foundation for sprite sheets.

Validation refuses dangling relationships, self-links, invalid IDs, missing evidence, duplicate IDs and
containment cycles. Relationships never replace hash-bound `dependencies`.

## Grouping files into assets

- `sibling-export-manifest-v1` groups files only when at least two sibling format folders hold the same
  complete set of relative stems with no duplicates. It records the folders, the anchor, the count and a hash of
  the name set. `confirmed-sibling-export-v1` is the same grouping confirmed by the owner for folders the rule
  would not join ([decision 0019](../../Decisions/0019-source-folders-and-export-variants.md)).
- Other files stay separate assets, even in one directory. Geometry equivalence between grouped formats is
  recorded as unverified.
- Variants (same thing in several colors or sizes) are variant groups from the pack's profile, not merged
  records ([decision 0035](../../Decisions/0035-packs-and-variant-groups.md)).
- Pack contact sheets and samples (`pack_contact_sheet`, `pack_sample`) are inventory roles, never assets.

## Dependencies

References are parsed from OBJ/MTL, glTF/GLB JSON and DAE images, with recursive MTL traversal and a parser
status per file; FBX files contribute the image names they mention. A reference must resolve inside the
library folder (or a sibling project layout,
[decision 0010](../../Decisions/0010-shared-project-dependencies.md)). Absolute, remote, reserved-name or
escaping references are refused and never fetched. Parsed references do not prove complete materials or
geometry; Blender's own texture list is added at inspection.

## What each type can do

`asset_structure.structure(record)` derives capabilities from the type. They say which adapters exist, not
that processing succeeded; `processing`, previews and faults stay authoritative.

| Type | Inspection and previews | Descriptions | Search vectors |
| --- | --- | --- | --- |
| `model_3d` | Blender renders | Yes | Image and description |
| `image` | Decoded facts and derived images, no Blender | Yes, except material textures | Image and description |
| `audio` | None | No | None (keyword only) |
| Child (`subasset-v1`) | None yet | No | None (keyword only) |

## 3D inspection fields

- `primary_inspection_path` and `primary_inspection_reason` name the one file that was measured. `technical`
  holds geometry counts, objects and meshes with bounds and transforms, unit settings, used materials, image
  dependencies, armatures and actions, all scoped to `inspected_path`, `inspected_sha256` and `inspected_format`.
  Other formats of the asset stay uninspected.
- `inspection_run` records the stage fingerprint, status, errors, timing and result path. A failed, timed-out or
  unsupported import is its own outcome; the next asset continues and no other file is tried in its place.
- `inspection_run.source_faults` keeps faults in the original (kind, object or reference, evidence count, any
  render adjustment) apart from the processing status. A successful render does not clear them. Exact
  duplicate faces, for example, are counted, their shadow rays are turned off in the derived render scene, and
  the adjustment is recorded in `render_settings.shadow_overrides`; the original is untouched.
- Conventions: Blender renders are Z up, with the front at -Y and the side at +X. Real-world size and the author's
  intended axes stay unknown. Armatures and actions are listed, not played.
- A recorded fault on unchanged inputs is never retried on its own; the owner asks for a recheck
  ([decision 0020](../../Decisions/0020-alternate-file-faults-and-recheck.md)).

## Images

Every image is enrolled and classified by layered evidence (`image_kinds`): a **model texture** stays a
dependency of its model, a **material texture** and a **2D image** are assets. Each classification is stored
as `{value, basis, evidence}`; an owner answer on a folder wins over everything except a model reference. The
vision model is never used for this.

- **One record per folder and stem.** The same stem in several formats is one asset with `alternate_export`
  roles (raster preferred as primary). Byte-identical files in different assets are noted in
  `type_metadata.identical_content`, never merged. Images described by an atlas or tileset sidecar
  (`.xml/.json/.atlas/.plist/.tsx/.tmx`) are held back as `deferred_sprite_sheet` until sprite sheets exist.
- **Purpose is a suggestion.** `type_metadata.purpose` is always `generic_image`; a keyword in the nearest
  folder name (icons, tiles, sprites, ui, backgrounds…) becomes `suggested_purpose` with its evidence. No
  publisher or pack name is consulted ([decision 0009](../../Decisions/0009-general-capabilities.md)).
- **Formats.** PNG, JPEG, WebP, BMP, GIF, TGA, TIFF and AVIF are decoded by Pillow with the decoder pinned to
  the extension (a mismatch is a fault), up to 64 MiB and 16 million pixels. Self-contained SVG is rasterized
  by `resvg-py` in an isolated child process with a time limit, an 8 MiB file cap and a 2,048 px render cap;
  entities and any reference that is not `#…` or `data:` are refused before rendering, and scripts never run.
  Animated or multi-frame files and SVG with external resources are `unsupported` (recorded, not failed). A
  damaged file fails only its own asset.
- **Inspection** (`image-inspection-v2`) records format, size, mode, `alpha` (`none`, `binary`, `partial`),
  visible coverage and bounds, colour count (up to 4,096), `size_class` (tiny ≤32, small ≤128, medium ≤1,024 px,
  large) and a `pixel_art_candidate` hint. It writes derived PNGs into the library store: a thumbnail
  (hard-edged enlargement for small art), a display raster for SVG, and the model input. The original is
  referenced, never copied.
- **Model input** `image-model-input-b-v1`: reduce to fit 1,024 px, enlarge with hard edges until the long edge
  is at least 256 px and the short edge 32 px (bounded at 4,096 px and 16 MP), then put transparent pixels on
  flat rgb(82,82,82). Both the description model and the search model read this one file.
- **Fingerprint.** The image inspection key covers the file contents, the model-input policy and the
  pixel-producing code (`image_media.py`, `svg_worker.py`) with the SVG renderer version. Editing those two
  files re-inspects every image and re-queues its vectors and descriptions. Scanner rules (`image_catalog.py`,
  `image_kinds.py`) can change without that cost.

## Descriptions and corrections

`description` holds what the model observed (identity, prose, shape, colors, parts, style, distinguishing
features, uncertainty); `suggested_uses` is a separate interpretation. No technical field is derived from
model text. `caption_provenance` records the model revision and file hashes, device, runtime lock, prompt
version and hash, input view hashes, settings, attempts and review states. The owner's corrections live in
`data/captions/corrections/<asset-id>.json`, survive regeneration byte for byte, and cannot replace measured
facts. Descriptions are optional work, never an import failure
([decision 0033](../../Decisions/0033-descriptions-and-engines.md)).
