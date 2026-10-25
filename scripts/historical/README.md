# Historical scripts

These scripts reproduce earlier milestones or performed one-time operations on the
original development machine. They are kept so recorded evidence stays reproducible and
explainable. **They are not general tools:** most need the original 40-asset pilot, the
883-asset step 8 library, named asset packs, fixed dates or fixed run paths. Do not run
them on a new install, and never rerun the one-time operations (several refuse reruns).

Moved here from `scripts/` on October 25, 2026 without behavior changes (only the
repository-root lookup, now `parents[2]`). Older documents and receipts cite them under
their earlier `scripts/<name>` paths.

| Group | Scripts |
| --- | --- |
| One-time migrations and repairs | `migrate-sources.py`, `complete-source-report-copies.py`, `reduce-storage.py`, `retry-storage-links.py` (loads `reduce-storage.py`), `relocate-models.ps1`, `cleanup-gui-checks.py`, `cleanup-source-check-projections.py`, `finish-texture-repair-descriptions.py`, `kaykit-gltf-maintenance.py`, `repair-textures.py`, `verify-texture-repairs.py`, `verify-kaykit-gltf.py` |
| 40-asset caption pilot | `caption_pilot.py`, `caption_review_images.py`, `caption_review_text.py`, `check_caption_review.py`, `check_catalog.py`, `check_inspection.py`, `check_captions.py`, `check_embeddings.py` |
| Frozen search benchmark ([`docs/evaluation/`](../../docs/evaluation/README.md)) | `prepare_evaluation.py`, `label_evaluation.py`, `benchmark_evaluation.py`, `report_evaluation.py`, `review-owner-results.py`, `verify_evaluation.py`, `embedding_capability.py`, `embedding_demo.py` |
| Image pilot (October 20, 2026) | `image-pilot.py`, `image-pilot-describe.py`, `image-preprocessing-eval.py`, `image-pilot-search-eval.py` |
| Step 8 delivery report | `report-library-delivery.py` |
| Real installed-client check (original machine's Codex/OpenCode) | `verify-agent-workflow.py` |

Current tools: `local-assets` (`scripts/local-assets.ps1` / `.sh`), `check-config`,
`doctor`, `scripts/smoke-headless.py`, `scripts/cleanup-scratch.py`,
`scripts/prune-hash-cache.py`, the synthetic `scripts/verify-*.py` checks and the pytest
suite.
