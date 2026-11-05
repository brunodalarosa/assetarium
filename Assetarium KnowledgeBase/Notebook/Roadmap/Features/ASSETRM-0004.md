---
tags: [roadmap]
id: ASSETRM-0004
type: feature
status: proposed
created: 2026-11-02
code: [store_versions.checked, store_versions.read_versioned, sources._source_settings, notifications.load, desktop.run, mcp_server.main, cli.main, catalog_migration.migrate_working_catalog, library_store.connect, incremental.ledger, result_store._index, retrieval.index_database, incremental.inspection_input, incremental.caption_input, incremental.recorded_fingerprint, incremental.EQUIVALENT_WORKERS, library_migration.rekey, publication.atomic_json, settings.settings_path, processing_queue.load]
---
# ASSETRM-0004

Safe upgrades: users update Assetarium and their processed assets stay recognized and usable.

Source: a read-only migration-readiness audit on 2026-11-02, saved at
`data/evidence/migration-readiness-handoff-2026-11-02.md`. That folder is git-ignored, so this note keeps the
essentials. Nobody runs 0.1.0, so 0.2.0 starts fresh (changelog) and is the first supported baseline.

## Split (owner, 2026-11-05)

Only what 0.2.0 itself must contain gates 0.2.0: an older release can't be taught later to leave newer data alone,
and a release's library can only be frozen when it is cut. The rest needs a second format to be designed against.

| Part | Gate | Covers | State |
|---|---|---|---|
| **0004a** | 0.2.0 | Gap 2 and the JSON files rewritten automatically: refuse a newer version unchanged; the release fixture | Implemented on `feature/pre-v020-polish` |
| **0004b** | the first release that changes a format (likely 0.3.0, audio) | Gaps 1, 4, 5 and the upgrade half of 6: coordinator and lock, back up → migrate → verify → activate, recovery UI, tests across skipped releases | Proposed |

Gap 3 became a release rule (AGENTS.md → Versioning): no fingerprinted worker edit without an equivalence proof.

**0004a in code:** `store_versions.checked` runs before any DDL in `library_store.connect`, `incremental.ledger`,
`result_store._index` and `retrieval.index_database` (an unversioned database is stamped 1, a newer one refused);
`store_versions.read_versioned` / `newer_refused` guard `processing_queue.load`, `sources._source_settings` (and
the other `source.json` reads) and `notifications.load`. Other JSON stayed as it was: collections, tags, settings,
setup and the registry already refused unknown versions; speed tests re-measure; render limits change only on Save;
locks, markers, progress and publication pointers are transient or rebuilt by a rescan.
`scripts/build-release-fixture.py` freezes a scanned sample library (IDs, a collection, a tag; no previews or
descriptions, which need Blender and models); `tests/test_release_fixtures.py` reads every frozen one.

## Problem

The foundations are good: durable asset IDs and recognition, input-keyed results that can be adopted, immutable
publications, a bounded catalog v1→v2 migration and the one-time legacy import. But there is no safe-upgrade
guarantee yet. Keeping old preview files isn't enough if the new version no longer recognizes the asset ID, can't
read its record, or treats completed processing as new work.

| # | Gap | Priority | Evidence |
|---|---|---|---|
| 1 | **No app-wide migration coordinator.** Migrations are separate utilities; desktop, MCP, CLI and workers start without a shared check, lock or ordered route (skipped releases included). | High | `catalog_migration.migrate_working_catalog` documents that startup doesn't call it |
| 2 | **Databases don't enforce schema versions.** Library DB, ledger and result index open any `user_version`; the embedding index resets it to `1`. | High | Synthetic probe: version `999` opened without error in all four |
| 3 | **Code fingerprints invalidate completed work.** An output-neutral code change makes finished work pending again. | High | Synthetic probe: a comment-only edit to the render worker took pending inspections from 0 to 1 |
| 4 | **No whole-upgrade recovery.** Atomic writes protect single operations, but an upgrade spans several stores in different places (library store vs app data: collections, tags, settings, queue). | High | `library.sqlite` alone isn't the whole user state |
| 5 | **JSON formats are inconsistent.** Collections and tags check versions; the queue and settings don't share a policy. | Medium | `processing_queue.load`, settings writer stamps `1` |
| 6 | **Tests don't prove release-to-release upgrades.** Legacy tests rebuild old layouts from current output, not from real release fixtures. | High (release gate) | `tests/test_library_migration.py::legacify` |

## Preservation contract (agree with the owner first)

- Upgrades keep asset IDs and everything that references them (collections, tags, reviews, owner corrections).
- Usable previews and descriptions stay attached to their assets.
- A compatible refactor never turns completed processing into new work. Regeneration, when truly needed, is explicit
  and explained.
- Recorded faults survive and aren't retried automatically.
- Rebuilding the search index is separate from regenerating previews or descriptions.
- A failed or interrupted upgrade leaves a recoverable library and says so.
- An older app refuses a newer format before changing it.
- Original asset files stay read-only.

Binding decisions: [0023](../../../Decisions/0023-central-asset-library.md) (fingerprint changes re-key, never
re-queue) and [0024](../../../Decisions/0024-pack-profiles-and-variant-groups.md). Anything that contradicts them
needs owner agreement and an updated decision.

## Proposed sequence

1. Inventory authoritative vs derived persistent state; pick the baseline and the invariants.
2. Detect supported formats and refuse newer ones before any read or write can change a store.
3. Shared coordinator: exclusive cross-process lock, ordered migration registry, recorded completion, repeatable
   recovery.
4. Back up, stage, verify, then activate across the affected stores. Keep large compatible result files in place.
5. A general result-compatibility policy for fingerprint changes, building on re-keying and `EQUIVALENT_WORKERS`.
6. Upgrade and recovery UI, plus release-fixture tests as a release gate.

User-visible flow: `Check compatibility → block writes → back up → migrate → verify → activate`.

## Done when

- Every persistent format has an explicit version, and newer versions are refused without changes.
- Every entry point goes through one coordinator before normal store access.
- An output-neutral code change leaves completed work completed.
- Small, synthetic, version-pinned fixture libraries from each supported release upgrade directly and across skipped
  releases, including interruption, rerun, low disk space and unsupported-future cases.
- Before implementation: an approved checkpoint naming scope, exclusions, risks, verification, duration and extra disk
  use. The audit didn't estimate those.
