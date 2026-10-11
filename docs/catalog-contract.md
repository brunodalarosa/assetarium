# Catalog contract v1

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
evidence; rendered project-relative previews remain pending. Exact names under
matching `Previews`/`Side`/`Isometric` layouts are associated. Isometric
`_NE/_NW/_SE/_SW` suffixes retain directional view labels. Pack contact sheets,
samples and textures are separate inventory roles, not individual asset renders.

Dependency references are parsed from OBJ/MTL, glTF/GLB JSON and DAE images, with
recursive MTL traversal and per-file parser status/issues. Legitimate parent
references must resolve within the configured source root. Absolute, remote,
reserved-name or escaping references are rejected and never fetched. Binary
FBX/Blend dependency inspection remains pending; parsed references do not imply
complete material/geometry validation. Physical units/scale remain unknown.

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
