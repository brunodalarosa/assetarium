# Catalog contract v1

This is a schema contract for subsequent stages, not a populated catalog or an
implemented database migration. SQLite with FTS5 and NumPy remain the selected
approach. Step 2 creates the database and keyword index. Do not interpret unknown
fields or pending stages as successful inspection.

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

Planned SQLite representation: assets keyed by asset ID with uniqueness on the
identity tuple; source files/dependencies/previews as child rows; versioned structured
payloads for technical/description/provenance/owner overlay; contracts and stage
states retain explicit fingerprints. FTS5 contains searchable names and approved
factual descriptions linked to asset IDs. Vector arrays live in ignored `data/`
with an asset/view mapping and embedding contract fingerprint. This representation
is a proposal until step 2 implements and tests its migration.

Embedding contract from the plan is provisional until step 5 verifies official
documentation and real inference: full 768 dimensions, finite normalized values,
text/image modality recorded separately, BF16 where supported or FP32, no FP16.
Changes in model revision, formatting, dimensions or preprocessing invalidate
affected vectors. No compatibility or image-support claim is made in step 1.

Preview/description/vector/export paths must be in the allowed project storage
areas. Original pack paths are opened for reading only. License unknowns and
ambiguities remain explicit. No catalog, vector, or third-party asset is committed.
