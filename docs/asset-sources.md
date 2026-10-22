# Asset sources

The Windows app opens **Settings → General**. Select **Asset sources** to manage
asset directories. Add a directory using its
folder picker or path field. Every source has an **Enabled** checkbox and a
**Remove** action. Changes apply to browsing, current searches and subsequent
agent requests while the app stays open. Removing or disabling a source preserves
its original files and generated metadata. Re-adding its directory recovers its
saved identity and published results.

## Processing formats

In **Settings → General**, **Formats to process** offers **FBX**, **glTF / GLB**
and **OBJ** checkboxes. All three start enabled. Save applies the selection to
new processing batches in the desktop and command-line processing flows,
including new overnight description runs. A running batch keeps its selection
until the next batch. Unchecking everything pauses processing; scanning,
browsing and existing search results remain available.

Scanning always inventories every supported model format. **Asset sources**
shows logical asset counts for each format, including disabled formats and
other inventoried types such as BLEND. glTF combines `.gltf` and `.glb`; an asset
with both counts once in that group. An asset with alternate formats counts
once under each applicable group, so the counts need not add up to the source's
total asset count. Counts reflect the latest saved scan and remain visible when
a source is disabled.

For a new logical asset, inspection selects an enabled source file using the
existing format preference. Disabled formats and other inventoried types create
no actionable processing work. Alternate formats are not converted or processed
as separate copies of that logical asset. Downstream descriptions and search
data belong to the file actually inspected: disabling that format defers its
unfinished work even if an enabled alternate exists.

Changing these checkboxes does not clean up, regenerate, hide or remove existing
results or search vectors, and does not retry retained failures. Failure evidence
stays in the importing failures report. Saving preferences refreshes pending
indicators from saved inventory without running a scan or starting models.

After upgrading from the single-root version, reopen LAL and reconnect any agent
server connections that were already running. They need to load the new code
once; subsequent source toggles apply live without reconnecting or restarting.

The app scans enabled sources in the background at startup. Enabling a source
also scans it; reopen the app (or toggle the source) to rescan during a session. Scans detect
added, changed and removed files; unchanged files reuse their verified hashes
when file ID, size, modification time and NTFS change time agree. Scans seed the
shared `cache/file-hashes.sqlite` record that searches and detail checks reuse
(decision 0004). The
source's own `metadata-lal` directory is always excluded. Scanning runs no model
inference or rendering. Removed and changed assets are excluded from searches
when discovered; their prior generated evidence is retained.

An unavailable source is recorded in LAL's availability diagnostics, excluded from
searches, and left on disk as-is; other sources still scan. It is never recreated
just to write an error. A later successful scan clears the current availability
warning while retaining the original diagnostic history.

## Descriptions

Descriptions are optional. Assets are searchable by name and image as soon as
they are processed; descriptions add a third signal to the default search, and a
missing, stale or invalid description is skipped without a fault.

Each source in **Settings → Asset sources** shows its description counts
(written · missing · failed) and a **Generate descriptions** button. It is enabled
when the source is enabled, formats are selected, no operation is running for it
and at least one asset with usable renders lacks a description. The run happens
in the background: it writes descriptions in batches (decision 0007), builds their
search vectors and publishes. Its progress and **Cancel** appear in that source
row and under the notification bell. Recorded description failures are kept and
not retried. A cancelled or stopped run still publishes what it finished.

Notifications (bell in the header) report two things: a source that finished
processing with descriptions ready to generate, and the outcome of each
description run. A new notice also shows a short toast. **Not now** hides a
ready notice until more descriptions are missing; closing the panel marks notices
read. They are saved in `data/library/notifications.json`.

## Source cards

The library shows one warning card for each source that needs processing or
publication. Missing or failed descriptions never raise a card: descriptions are
optional extra data ([decision 0008](decisions/0008-optional-descriptions-and-notifications.md)). It remains visible through processing, publication, cancellation
and interruption while actionable work remains. A subsequent scan clears it
when there is no unattempted work and current results have been published.
Recorded failures appear in the importing failures report. Description failures,
caption review notes, warnings and pending owner approval do not count as import
failures.

Click **Process assets** to inspect/render pending assets, create search vectors
and publish usable results for that source. It does not generate descriptions. The progress
bar includes processing, source publication, combined search publication and the
verification scan. Other sources retain their published results. New asset
processing remains an explicit action; adding a source only registers/scans it.
The former **Process pending** and **Publish ready work** buttons are replaced by
this source-specific action.

**Cancel** requests a graceful stop. The worker finishes its current asset in
the current stage, commits its checkpoint, then stops before beginning another
asset. During embedding, all views/channels of the current asset finish together.
An atomic publication already in progress finishes safely. Completed checkpoints
are reused by the next explicit processing action. Workers are never killed to
cancel a source operation. Closing the app requests the same graceful stop for
its outstanding source operations.

Unchanged faulty assets are retained with evidence and skipped, including on a
subsequent **Process assets** click. Other usable assets can finish and publish.
Recorded failures do not keep pending-import cards visible. **Importing failures
report** opens a scrollable list of original asset paths from all configured
sources, including disabled sources. Removed sources retain their metadata but
are excluded from this view. An asset with several source formats lists each
original model path. Usable partial results remain available after publication.

Readiness uses saved stage outcomes, rather than assuming every incomplete stage
has never been attempted. Failed/unsupported stages block dependent work; other
unfinished work stays pending. The caption stage is not part of import readiness;
an embeddings outcome that misses only the description vector counts as complete. Every scan saves each asset's current
file/dependency fingerprint, attempted state and outcome in
`metadata-lal/library/import-status.json`. New or changed inputs become pending;
unchanged failures are retained. Unpublished results still require publication
before their card disappears. Processing is not permission to repair originals
or retry unchanged failures. GPU processing shares the existing
inference lease with semantic search. Browsing and keyword search remain available.

## Storage and identity

Expansion step 1 adds a backward-compatible shared asset structure. Existing
sources/3D IDs and saved results remain unchanged; it does not enroll images or
audio. New candidate catalog databases use schema 2, allowing explicit parent and
child records to share original paths. Old catalogs remain readable without a
startup migration. Generic images, unsupported audio, file roles, relationships
and adapter capabilities are documented in the
[catalog contract](catalog-contract.md#expansion-step-1-shared-asset-foundation).
Expansion step 2 adds image enrollment as a per-source choice: tick **Include
2D images** in *Settings → Asset sources* (stored as `import_types` in that
source's `metadata-lal/source.json`). The source is rescanned; existing results
are never deleted, and an unchanged image that returns later resumes its saved
results. Model textures, previews, pack overview sheets, texture folders and
atlas/tileset sheets stay out of the image assets with a visible inventory role.
**Process assets** measures each image and writes its thumbnail, model input and
image vector; **Generate descriptions** then works for images too. See the
[catalog contract](catalog-contract.md#static-2d-images-expansion-step-2).

The local registry is `data/library/sources.json`. Each source's
`metadata-lal/source.json` stores its persistent identifier and catalog key.
Directories must be separate and must not overlap LAL, shared model storage or
one another. Directory links and metadata directory escapes are rejected.

`metadata-lal` contains its catalog snapshots, working catalog, source inventory,
processing/job history, vector snapshots, inspections, image previews, caption
outputs, owner correction overlays, review classification, source operation logs,
and source-specific historical evidence. Saved `data/...` references in records
are logical references resolved to this directory. This preserves existing asset
identities and vector fingerprints while moving files.

LAL's central catalog and search index are derived combinations of source
publications. Enabling/disabling sources filters the visible membership without
copying model files, rerendering or reindexing. Central application logs, model
capability receipts, runtime caches, shared historical reports and migration/storage
receipts remain application-owned. Mixed-source JSON reports are also partitioned
into each relevant source's historical evidence.

The approved initial migration registers the 13 former top-level asset-pack
directories as enabled sources. Individual result files move within C: with a
per-file hash-checked journal. Original files, result bytes, vector bytes, reviews
and fault evidence are preserved. Migration receipts are under
`data/library/source-migration/`; it refuses automatic repetition.

Storage receipts include unique allocated bytes across the project and all source
metadata directories, deduplicating hard links. They exclude original asset files
and shared model weights. Existing prepared runtimes and offline models are reused.

### Source import restrictions

An explicitly cleaned source can store an `import_formats` list in its
`metadata-lal/source.json`, using the same `fbx`, `gltf`, and `obj` families as
processing preferences. `gltf` includes GLB. This restricts which original models
become catalog entries during future scans; excluded originals remain read only.
Settings shows the source's import restriction beside its format counts.

This is separate from the General processing checkboxes, which retain saved
imports and only select work. Changing those checkboxes does not undo a deliberate
source cleanup. Removing or changing a source import restriction is an explicit
maintenance operation, followed by scanning and processing the restored formats.
Sources without a restriction retain their previous inventory behavior.

Nested source licenses are attached only to assets in the corresponding ancestor
folders, together with applicable collection notes. Internet shortcuts are
documentation rather than license evidence. Full originals and historical
evidence are retained. Equal manifests in sibling `fbx`, `fbx(unity)`, `gltf` and
`obj` export trees can establish a logical export group, preserving subpack and
color namespaces; they do not establish measured geometry equivalence.

The owner-approved KayKit glTF cleanup uses
`scripts/kaykit-gltf-maintenance.py`, with immutable receipts in
`data/library/maintenance/kaykit-gltf-20261016/`. Its phases preserve glTF IDs,
results and vectors, record original hashes, publish the restricted membership,
then remove only manifest-listed generated imports and retired derived
publications. Excluded fault records and their generated evidence are retained
separately. Cleanup refuses links, out-of-root targets and automatic reruns.

## Maintenance commands

From the prepared runtime, `python -m local_asset_library.cli status` reports
source state, and `scan` scans enabled sources. `--asset-source KEY` selects an
individual source. `python scripts/library-batch.py process --source KEY` starts
the same source operation used by the app; it publishes automatically. The
returned operation token identifies its durable log in that source's metadata.

Earlier pilot/import commands and reports in this repository describe their
historical configuration. Current source membership comes from Settings rather
than the historical `docs/library-membership.json` pack list. The existing storage
budget in that file is the default until a user saves a budget in **Settings →
General**. The saved whole-number GiB limit lives in `data/library/settings.json`
and applies to the combined unique allocation of LAL and source metadata. Original
assets and shared models are excluded. Saving does not start or retry processing.
The saved total replaces both historical total and per-operation growth limits;
explicit reserves on legacy command-line jobs still bound those jobs. Processing
reads the setting at its storage checks, including between stages, and preserves
completed work when it stops at the limit. Raise the budget and explicitly choose
**Process assets** to continue pending work. Unchanged asset faults remain skipped.

## Shared project dependencies

Split exports can register their model and shared-texture folders separately.
Missing external glTF/GLB images resolve across enabled sources when the complete
project-relative directory layout matches and all candidates have identical bytes.
The texture source need not contain models. Originals stay read-only; conflicting,
missing, changed or disabled providers remain visible faults. New registrations
with the same convention use this feature automatically during normal scans.
See [shared dependency behavior](dependency-path-overrides.md) and the binding
[capability policy](decisions/0009-general-capabilities.md).
