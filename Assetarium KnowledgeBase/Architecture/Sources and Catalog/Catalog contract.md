---
tags: [architecture]
parent: "[Architecture](../Architecture.md)"
status: draft
verified:
branch:
level: system
code: [catalog.py, asset_structure.py, image_catalog.py, sources.aggregate]
---
# Catalog contract

Up: [Architecture](../Architecture.md) · Where in code: [Sources and Catalog](../../Notebook/Sources%20and%20Catalog/Sources%20and%20Catalog.md). Moved from `docs/catalog-contract.md` on 2026-10-28; its "step N" sections are the pilot history of the contract.

## Expansion step 1: shared asset foundation

New catalog databases use **SQLite schema 2** (`PRAGMA user_version=2`). Readers
accept schemas 1 and 2 and reject unknown versions. Existing schema-1 catalogs
remain readable without rewriting them. One schema-2 database may retain legacy
JSON records at version 1 alongside explicit media records at version 2.

The `assets`, inventory, FTS5 and membership identities remain unchanged. The
`files` primary key is now `(asset_id, path)`: a parent and its explicit children
can reference the same original file without duplicating bytes. Each asset still
has only one entry for a given path. SQLite/FTS5, NumPy, source binding and the
configured membership boundary are unchanged.

### Record structure and identity

`asset_structure.py` defines the small versioned contract. Missing type fields in
a legacy v1 record mean `model_3d`, including inventoried unsupported model
formats. Reading a legacy record does not add fields to it or mutate a shared
cache. Explicit `upgrade_record` preserves unknown fields and the exact existing
file/dependency lists, outputs, faults, provenance and overlay contents.

| Version-2 field | Contract |
| --- | --- |
| `schema_version` | 2; independent of the SQLite container version |
| `structure_version` | 1; selects these concrete type/stage/capability definitions |
| `asset_type` | `model_3d`, generic `image`, or `audio`. Images are enrolled only in sources that opt in (step 2); their purpose is never guessed from a filename |
| `identity_version` | `asset-v1` for ordinary assets; `subasset-v1` for explicit children |
| `type_metadata` | Object with `version: 1`; unknown fields retained; maximum 32,768 JSON characters |
| `file_roles` | Map covering the record's `files` paths; `primary`, `alternate_export`, `dependency`, or `supplied_preview` |
| `relationships` | Up to 64 entries: `kind` (`alternate_export`, `contains`, `depends_on`, `variant`), target `asset_id`, and nonempty evidence up to 2,048 characters |
| `parent_asset_id`, `subasset` | Required for children; selector contains an explicit `kind` (`frame`, `clip`, `region`) and a stable nonempty `key` of at most 256 characters |

Ordinary model IDs keep the exact algorithm documented below. New ordinary
media assets use that same source/pack-relative identity rule. Changing content
does not change the ID; renames remain deletion plus addition. No new approval,
overlay, or equivalent-export claim is transferred from matching names/bytes.

Child algorithm `subasset-v1` is `asset_` plus the first 32 hex characters of
SHA-256 over compact, sorted-key, UTF-8 JSON:
`["subasset-v1", parent.source_id, parent.pack_id, parent.asset_id, kind, key]`.
Its catalog identity is `@subasset/<child-id>`. A renamed key creates a new ID.
Additional selector evidence is retained; changes enter the child's source
fingerprint, without changing existing model fingerprints. Later frame/clip
adapters must bind their exact region/time/clip inputs before creating vectors.

Candidate validation rejects dangling relationships, self-links, invalid IDs,
missing evidence, duplicate asset IDs and cyclic containment. Parent/child source
and pack must agree; the parent must explicitly contain the child, and child
files must be a subset of its parent's file paths. Relationships do not replace
hash-bound `dependencies`: required maps/includes still need their recorded
paths, hashes and discovery evidence. Unknown type-specific metadata survives
catalog and publication round trips.

### Applicable work and capabilities

Capabilities are derived through `structure(record)` from the versioned type
contract. They describe supported adapters, not successful processing or measured
per-format availability. Actual `processing`, previews, source checks and faults
remain authoritative. Supported image-based types use the existing **image**
vector channel, with no embedding model/runtime/contract change.

| Type | Foundation behavior |
| --- | --- |
| Legacy/current `model_3d` | Existing Blender inspection/previews, optional image descriptions and image/description vectors remain unchanged |
| Generic `image` | Step 2 adapter (see *Static 2D images* below): decoded facts, derived thumbnail/model input, optional descriptions; no Blender or original copy; image vectors use the existing verified backend contract |
| `audio` | Structural/keyword record only; decoding, previews, playback, descriptions and direct audio vectors are explicitly unsupported; no audio inference claim |
| Explicit child | Structural/keyword identity and parent linkage only; slicing/extraction, playback and direct-media vectors remain unsupported until their later adapter |

`not_applicable` is an additional stage state, distinct from `unsupported` and
`failed`. In step 1 the image caption stage was not applicable; step 2 makes it
applicable (see below). Generic inspection/preview/vector stages for audio remain
explicitly unsupported, with evidence that no adapter was attempted. Existing
failures are never relabeled successful or erased by applicability. Failed
description generation remains visible even when its type currently lacks a
description adapter; unsupported unattempted description capabilities are
unavailable rather than runnable missing descriptions.

The PNG proof adapter decodes actual PNG bytes with the existing Pillow runtime,
limits input to 16 MiB and 16 million pixels, verifies source/dependencies before
and after decoding, and keeps width, height and mode separate from model facts.
Its preview references the verified original; it creates no duplicate original
or image conversion. Malformed/stale/missing inputs retain faults and partial
results without unchanged retries. No image input means no successful vector
claim. New image metadata stays available in the slim read cache, while processing
and indexing continue to read fresh full `membership.records`.

The inventory scanner still enrolls only its existing model formats. Explicit
PNG records are an internal foundation boundary, not new source enrollment or
image-pack browsing. Their processing honors the existing empty-format pause;
model format preferences do not select an image subtype. Step 2 must add image
enrollment and its processing preference/UI deliberately.

Decisions 0007-0008 remain binding. Process assets excludes caption generation;
Generate descriptions remains the separate source operation. Missing/failed
model descriptions and description vectors never become import work/failures
when direct image vectors succeeded. Original description failures remain in
detail/source counts; keyword/direct-media search stays usable. Unsupported image,
audio and child description capabilities do not raise a ready notification or
start inference. Existing batching, fingerprints, GPU coordination, resource-stop
handling and notifications are unchanged.

### Migration, publication and recovery

No live-library migration is automatic or required for this foundation. Startup,
list/detail/search and `initialize` do not upgrade catalogs. Fresh candidate
catalogs use SQLite schema 2; normal scans retain unchanged legacy record bytes
and do not regenerate results just to add structure fields.

`catalog_migration.migrate_working_catalog(config, max_additional_bytes)` is an
explicit working-data operation for use under the coordinator's existing writer
lease. It refuses active-generation targets and unknown versions. Before copying,
it requires an explicit budget and free-space reserve of three catalog sizes
plus 64 KiB for the candidate, journal and expansion. It copies through SQLite
backup, converts the child file table and JSON structure, checks relationships,
integrity and foreign keys, verifies that the old working file has not changed,
then replaces only that working catalog. The index, jobs, originals, owner files
and active manifest are untouched. Already-v2 working catalogs are a no-op.
Receipts and failed candidates are retained under the source/project's existing
generated storage (`library/migrations/` and the working catalog directory).
An interrupted switch leaves the old working file and active publication usable;
the retained candidate can be inspected before an explicit retry. No automatic
retry or evidence cleanup is introduced.

Publication validates the complete candidate relationships as well as existing
membership, vector and input checks, copies the matching catalog/index into a new
generation, and atomically switches one active manifest. Failure leaves the prior
active generation intact. Existing request pinning, no-change publication,
per-publication caches and decision-0006 retention remain unchanged. Rollback uses
the retained earlier generation, never an in-place edit of a published database.

Shared desktop/MCP validation accepts the bounded `asset_type` filter, explicit
`png`/`wav` source formats and the `image` still view. Detail metadata exposes the
structure, type facts and relationships under existing response caps; optional
metadata omission remains explicit. Source bytes being usable do not prove clip
extraction, playback or media inference; unsupported audio/child detail states
that limitation. No full image/audio browsing UI is delivered in step 1.

### Static 2D images (expansion step 2)

Step 2 supersedes the PNG proof adapter above; the type table's `image` row now
reads as follows. Images are first-class **generic images** in sources that opt
in, with measured facts, derived display/model inputs, optional descriptions and
the same retrieval as models.

**Enrollment.** `metadata-lal/source.json` may hold `import_types`
(`["model_3d"]` by default, `["model_3d", "image"]` when the owner ticks
**Include 2D images** for that source). Existing sources keep their bytes and
records unchanged. In an image-enabled source the scanner (no decoding) makes
one `image` record per folder + stem, with these files left out as visible
inventory roles: files a model references as a dependency or preview
(`model_dependency_image`), pack `Preview*`/`Sample*` overviews
(`pack_contact_sheet`/`pack_sample`), images in a `texture(s)` folder
(`deferred_texture`, step 4) and images described by an atlas/tileset sidecar
(same-stem `.xml/.json/.atlas/.plist/.tsx/.tmx`, or a `.tsx/.tmx` `<image source>`;
`deferred_sprite_sheet`, step 3). Same folder + stem in several formats are one
asset with `alternate_export` file roles (raster preferred as primary); visual
equivalence is unverified. Identity is the preserved asset-v1 algorithm over
`image:<folder>/<stem>`, so it is independent of the formats present. Byte-identical
files in different assets are recorded as `type_metadata.identical_content`, never
merged. Filename-prefix variant suggestions are not made for images.

**Purpose.** `type_metadata.purpose` is always `generic_image`. A keyword in the
nearest folder name (source path or relative folders: icon(s), tile(s)/tileset,
sprite(s)/character(s), ui/gui/hud/button(s)/cursor(s), background(s)/bg/sky…)
becomes `suggested_purpose` with its basis and evidence. It is a suggestion,
never a filter or fact; no publisher or pack name is consulted (decision 0009).

**Formats.** Raster PNG, JPEG, WebP, BMP, GIF, TGA, TIFF and AVIF are decoded
by the MCP runtime's Pillow 12.1 with the decoder pinned to the extension's
format (a mismatch is a fault). Self-contained SVG is rasterized by `resvg-py`
0.5.0 (MIT; resvg Apache-2.0 OR MIT) in an isolated `python -I` child process
with a 30 s timeout, 8 MiB file cap and 2,048 px render cap; XML entities and any
non-`#`/non-`data:` `href`/`src`/`url()`/`@import` reference are refused before
rendering (resvg would otherwise read absolute local paths). Scripts never run.
An SVG without width/height/viewBox gets a measured content-bounds canvas
(`canvas_basis: content-bounds-v1`). Text elements render with system fonts and
say so. Animated/multi-frame files, external SVG resources and declared entities
are `unsupported` (recorded, not failed); damaged/truncated/oversized files fail
only their asset. DDS/EXR/HDR, PSD/Aseprite, atlas slicing and playback are not
enrolled in step 2.

**Inspection** (`image_inspection.py`, adapter `image-inspection-v2`, no Blender)
records `technical`: format, width/height (SVG: canvas units), source mode,
`alpha` (`none` / `binary` cut-out / `partial` soft), visible-pixel coverage and
bounds, colour count (up to 4,096), `size_class` (tiny ≤32, small ≤128,
medium ≤1,024 px, large), aspect and a `pixel_art_candidate` display hint. It
writes bounded derived PNGs under the source's generated data:
`thumbnail.png` (nearest-neighbour integer enlargement for ≤160 px art, else
320 px Lanczos), `display.png` for SVG (1,024 px raster) and `model-input.png`.
`previews` roles: `original` (raster source reference, never copied), `display`,
`thumbnail` and `model_input`, each hash-verified before reuse. The inspection
fingerprint covers source checks, chosen file, the model-input policy, the
pixel-producing code (`image_media.py`, `svg_worker.py`) and the SVG renderer
version (LF/CRLF-tolerant). Editing those two files therefore re-inspects images
and re-queues their vectors and descriptions; scanner rules (`image_catalog.py`)
and orchestration (`image_inspection.py`, whose `VERSION` marks semantic changes)
can change without that cost. A model-input
fault keeps facts and thumbnail, marks previews `partial` and the image vector
`failed` with the reason.

**Model input contract** `image-model-input-b-v1`: Lanczos reduction to fit
1,024 px, then nearest-neighbour integer enlargement until the long edge is at
least 256 px and the short edge at least 32 px (bounded at 4,096 px / 16 MP),
then transparent pixels composited over flat rgb(82,82,82); opaque images get no
backdrop. The derivation (policy, scale, resample, backdrop, sizes and a note that
the backdrop is not a source colour) is stored on the preview. It was chosen by
the preregistered evaluation in `data/verification/image-preprocessing-eval-20261020/`
(candidates a: min 32 px gray; b; c: b with a contrast backdrop) and is pending
owner review. Both unchanged model backends read this file, so
`embedding_backend.py`, `caption_backend.py` and every existing 3D fingerprint
are unchanged; the old <16 px and gray-composite behaviour now only applies to
already-prepared inputs.

**Stages.** Images now have the caption stage (`applicable_stages` returns all
stages). Process assets runs image inspection and image vectors; Generate
descriptions describes images whose model input exists (decisions 0007-0008
unchanged). An unchanged re-enrolled asset resumes from its published record,
and a ledger-complete inspection whose record lost its result is inspected
again instead of being recorded as corrupt output.

## Historical v1 catalog and pilot contracts

Step 2 implements the inventory and keyword portion of this contract in SQLite
schema version 1. SQLite FTS5 and NumPy remain the selected approach. Downstream
fields are nullable/pending; do not interpret them as successful inspection.

One record represents one logical asset, with alternate files grouped only when
evidence supports equivalence. Identity is `(source_id, pack_id, source_relative_identity)`;
the stable asset ID will be a deterministic hash of that tuple, with an explicitly
versioned algorithm in step 2. Filename alone is never global identity. Renames
require explicit handling. Paths are source-relative or project-relative;
resolve them through configured roots before access.

| Field | Contract |
| --- | --- |
| schema_version | Integer 1; migrations must explicitly change it |
| asset_id, source_id, pack_id | Nonempty stable strings; asset ID unique |
| source_relative_identity, display_name | Nonempty strings; identity is not an absolute path |
| variants | Related asset IDs and relationship/evidence; no inferred merging |
| files | Source-relative path, format, SHA-256, availability; primary inspection path names an entry or is null |
| dependencies | Source-relative path, role (texture/material/other), SHA-256 or null if unavailable, status and discovery evidence |
| grouping | Method/version, evidence list, unresolved ambiguities |
| availability | available, stale, missing, or unknown; stale/missing excluded from search by default |
| technical | Nullable counts, rig/animation/dependency facts, local-space bounds, units/unknown scale, extraction tool/version and inspected file hash |
| previews | Project-relative output path, view label, image hash, coordinate convention, render settings/version and issues |
| description | Nullable identity, observed colors/shapes/parts/style/features, uncertainty; suggested uses stored separately |
| caption_provenance | Nullable model/revision, prompt version, input view hashes, generation settings, review/correction state |
| license_evidence | Supplied file/source URL and evidence excerpt/reference, license identifier or unknown; never generated caption evidence |
| embeddings | Contract ID, project-relative vector reference, modality, exact model revision, prompt, dimensions, dtype, normalization and preprocessing version |
| processing | Stage statuses for inventory, inspection, previews, caption, embeddings: pending, running, complete, failed, unsupported; errors retained |
| owner_overlay | Separate versioned corrections/review decisions; regeneration preserves these |
| provenance | Created/updated UTC timestamps and per-stage input/settings fingerprints |

Empty collections indicate no evidence yet. Nullable facts mean unknown, not zero
or false. Technical metadata includes its extraction method; visual observations
are separate from technical facts and suggested uses. Failed image inspection
never falls back to a filename-generated caption.

Implemented SQLite representation: `assets` is keyed by asset ID with uniqueness
on `(source_id, pack_id, identity)` and holds the versioned JSON record. `files`
contains source-file child rows. `inventory` contains every discovered path,
classification/status, hash and archive evidence; `metadata` holds source binding,
fingerprints, scanner version and the scan UTC timestamp. Dependencies, supplied
previews, grouping evidence, license evidence, variant suggestions and future
fields live in each asset's JSON record. `asset_fts` indexes filenames, split
camel-case names, pack names and source-relative identities/paths, linked to IDs.
No generated descriptions or vectors are indexed. `PRAGMA user_version=1`;
unknown versions are rejected. The actual Python build must pass an FTS5
CREATE/INSERT/MATCH probe; no replacement index is silently used.

Asset ID algorithm v1: `asset_` plus the first 32 hexadecimal characters of
SHA-256 over UTF-8 compact JSON `["playful-lowpoly-v1", pack_id, identity]`.
Pack ID is the exact top-level pack directory name. Identity is pack-relative:
the full source path including extension when separate, or
`<export anchor>/@exports/<remaining relative stem>` when sibling-export evidence
permits grouping. Source binding is verified against the configured root when
opening the database. Content changes do not change IDs; path renames or changes
to grouping policy require explicit identity migration, not filename guesses.

Grouping method `sibling-export-manifest-v1` recognizes exact format-folder names,
requires at least two sibling folders with identical complete relative stem sets
and no duplicate keys, and records folders, anchor, matching count and name-set
hash. It removes only the evidenced format-directory segment; deeper namespaces
remain in identity. Other files remain independent, even in the same directory.
Matching names across independent identities are visible review cases. Filename
variant links are explicitly unreviewed suggestions and never merged.

Supplied previews use `source_path` plus source hash, view label and association
evidence; rendered previews use project-relative `path` and recorded settings. Exact names under
matching `Previews`/`Side`/`Isometric` layouts are associated. Isometric
`_NE/_NW/_SE/_SW` suffixes retain directional view labels. Pack contact sheets,
samples and textures are separate inventory roles, not individual asset renders.

Dependency references are parsed from OBJ/MTL, glTF/GLB JSON and DAE images, with
recursive MTL traversal and per-file parser status/issues. Legitimate parent
references must resolve within the configured source root. Absolute, remote,
reserved-name or escaping references are rejected and never fetched. Binary
FBX/Blend dependency inspection remains pending for alternate files not chosen
for step 3; parsed references do not imply complete material/geometry validation.
Physical units/scale remain unknown.

`scan` publishes inventory rows and the logical FTS index in one transaction after
two matching complete source fingerprints. It refuses to overwrite owner overlays
or populated later-stage fields. Incremental updates and downstream migrations
remain step 8 work. Vector arrays and their modality/contracts remain step 5 work.

Embedding contract from the plan is provisional until step 5 verifies official
documentation and real inference: full 768 dimensions, finite normalized values,
text/image modality recorded separately, BF16 where supported or FP32, no FP16.
Changes in model revision, formatting, dimensions or preprocessing invalidate
affected vectors. No compatibility or image-support claim is made in step 1.

Preview/description/vector/export paths must be in the allowed project storage
areas. Original pack paths are opened for reading only. License unknowns and
ambiguities remain explicit. No catalog, vector, or third-party asset is committed.

## Step 3 inspection fields

`primary_inspection_path` and `primary_inspection_reason` identify the one measured
source. `technical` contains original/instance-evaluated geometry counts, object
and mesh counts, each mesh's local bounds, transforms and world bounds, imported
unit settings, used materials, image dependencies, armatures, actions and sample
frame. Facts are scoped to `inspected_path`, `inspected_sha256` and
`inspected_format`. Alternate formats remain explicitly uninspected. Packed image
data after import does not prove that an original FBX embeds the image.

`inspection_run` records stage fingerprint, status, errors, timing and result path.
The fingerprint includes worker/framing code hashes, source and known dependencies,
runtime version output and resolution. Successful caches require current source,
dependency and rendered-image hashes. Errors/timeouts/unsupported imports remain
separate outcomes; processing continues with the next asset. No alternative source
is silently substituted after failure. Changed settings invalidate representative
review before the full pilot can proceed.

Rendered `previews` include origin, view label, SHA-256, renderer/settings,
coordinate convention, alpha-mask foreground/boundary checks and a separate image
review receipt. Technical review never implies owner artistic approval. The pilot
review scope is the three-quarter overview plus automated checks for other views;
all three required views of the four representatives are reviewed with image tools.
Existing supplied thumbnails retain their source association and provenance.
Search returns `preview_root` so source and generated preview paths are unambiguous.

Exact duplicate-position faces are counted per evaluated mesh, ignoring winding.
Affected meshes have shadow rays disabled in the derived render scene, with the
count and reason in `render_settings.shadow_overrides`; original geometry and
materials remain untouched. This is a flagged source geometry fault, not a repair
or a claim that the model is ready for production use. Other faulty assets retain
explicit error states and are not repeatedly repaired during a batch.

Unknown author-facing axes and real-world size remain explicit. OBJ coordinates
use negative-Z forward/Y up on import; Blender renders use Z up, canonical front
at -Y and side at +X, elevated 14 degrees. Actions/armatures are enumerated, not
played or behaviorally validated. Original step 2 logical fingerprint describes
the inventory snapshot; later technical fields use their own stage fingerprints.
Descriptions, embeddings, variants, grouping evidence and owner overlays are preserved.

`inspection_run.source_faults` persists the faulty status, kind, affected object
or reference, evidence count and any derived-render adjustment separately from
processing status. Any failed/unsupported outcome or source fault is retained on
unchanged inputs, without automatic retry. An explicit `--retry-faults` request
permits another attempt. This fault rule applies to all fault types, including
new definitions; successful output does not clear source fault flags.

## Step 4 caption fields

`description` stores validated visual identity, prose, shape, colors, parts,
style, distinguishing features and uncertainty. `suggested_uses` is a separate
interpretation list. No technical fields are derived from model text.
`caption_provenance` records exact model revision/file hashes, backend/device,
runtime versions/lock hash, prompt version/hash, original input view hashes,
preprocessing, generation settings, raw attempts/errors/timing, measured token
and resource counts, stage fingerprint and AI/owner review states.

`owner_overlay` mirrors the separate editable JSON file under ignored project
data. `effective_caption` merges it into generated observations without changing
the raw `description`. Corrections cannot replace measured metadata. Existing
overlay files survive regeneration byte-for-byte. Only Bruno can approve final
caption review and artistic suitability. See [caption contract](../../../docs/caption-contract.md).

The SQLite schema version and keyword index remain unchanged. The other 843
logical records retain pending captions; embedding arrays remain empty.
