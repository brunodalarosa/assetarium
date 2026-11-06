---
tags: [decision]
decided: 2026-10-17
---
# 0006 — Retention of superseded generated data

**Decision.**
- **Publications:** keep the active generation plus the **two** newest older
  `v_*` generations, centrally (`data/library/generations`) and in each source's
  `metadata-lal/library/generations`. `work`/scan folders are never touched.
  Combined-publication shortcuts that point at a retired generation are removed,
  so that combination is rebuilt on demand instead of failing as incomplete.
  Runs after every combined publication (`sources.aggregate`); a retention fault
  never fails the publication.
- **Launch audits:** keep the **ten** newest `data/gui/runs` folders; applied in
  the background at each app launch. Other `data/gui` evidence folders and
  `data/mcp/runs` are not touched.
- **Tests:** reuse one `scratch/pytest` basetemp. pytest clears it at the start of
  a run with `shutil.rmtree`, which does not traverse junctions on Python 3.13
  (`tests/test_retention.py`). It holds no evidence.
- **Old scratch folders:** removed only through the explicit two-step
  `scripts/cleanup-scratch.py --plan` (reviewed list) then `--apply PLAN`.
- All removal uses `maintenance_files`: links refused (scratch links are removed
  as links only when they point inside their own folder), every file re-hashed
  just before removal (read-only attributes of immutable publications are lifted
  only after that check), changed files retained as faults, and a receipt under
  `data/maintenance/`.

**Why.** Seventeen old combined generations held about 2.3 GB, and old test and
verification folders about 3.4 GB, with no policy that stopped the growth.

**Keep true.** Never retire the active generation or anything outside these
exact locations. Do not widen retention (fewer generations, other evidence
folders) without the owner. Keep receipts.

> **Since [decision 0023](0023-central-asset-library.md) (October 30, 2026):** the per-source generated folder named
> here is replaced by the central library store; the rules of this decision are unchanged and now apply to
> library folders, packs and folders.
