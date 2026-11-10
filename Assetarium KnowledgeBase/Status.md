---
tags: [hub]
verified: 2026-11-05
branch: release/0.2.0
---
# Current status

Up: [Home](Home.md).

Short, current summary. Detailed dated history, test counts and evidence are in
[`progress-2026-10.md`](../docs/history/progress-2026-10.md) (frozen October 2026 journal); binding rules are in [`decisions/`](Decisions/Decisions.md).

## What works today

- **Catalog and processing:** library folders with packs detected from structure and identity
  by recognition; a central library store (nothing is written into asset folders; decision 0023);
  startup scans; Make previews and Generate descriptions through an implicit queue (Blender
  inspection and previews, optional Qwen3-VL descriptions, EmbeddingGemma vectors); results keyed
  by their inputs; incremental publication with faults kept visible. 3D formats (FBX, glTF/GLB,
  OBJ/MTL, BLEND…) and static images (PNG, JPEG, SVG…), images sorted into model textures,
  material textures and 2D images.
- **Search:** keyword, description, image and combined search in the desktop app, the
  owner CLI ([`cli.md`](../docs/cli.md)) and the STDIO MCP server ([`mcp/README.md`](../docs/mcp/README.md)).
  Description and image search run on an NVIDIA GPU or on the CPU (decision 0018).
- **AMD machines (Windows):** checked end to end on a Radeon RX 6800 with a Ryzen 9 9950X3D:
  descriptions through llama.cpp's Vulkan build (Qwen3-VL-2B F16) and search on the CPU.
- **Desktop app (Windows):** Library tab (browse by library folder, bundle, pack and folder), asset
  processing queue, search, 3D preview, collections and tags, setup wizard, agent-assisted setup,
  agent activity and grouped proposal review.
- **Releases:** 0.2.0 (2026-11-05) is the first supported upgrade baseline; 0.1.0 installs start
  fresh. Data written by a newer Assetarium is refused unchanged (safe upgrades, first part); each release
  freezes a fixture in `tests/fixtures/releases/`.
- **Linux:** CLI + MCP only, no desktop app ([`linux.md`](../docs/linux.md), decision 0013).
- **License:** AGPL-3.0-only with a CLA (decision 0017). The CLA text is revised and published
  ([CLA.md](../CLA.md), [CLA-entity.md](../CLA-entity.md)); contributors sign it as described in
  [CONTRIBUTING.md](../CONTRIBUTING.md).

## Open work and pending reviews

- **Safe upgrades, second part** (store coordinator, backups, recovery UI, skipped-release tests) gates the
  first release that changes a store format, likely 0.3.0 with audio. That release raises the
  format number and ships the migration. 0.1.0 installs are not migrated: the 0.1.0 → store code was removed
  in November 2026.
- **Asset library rework (decision 0023), provisional choices:** a pack without a preview image shows a
  package glyph as its cover; "+N new" resets when you leave a library folder; the 10- and
  30-minute thresholds are constants (`processing_queue.QUICK`, `LONG`). Roadmap step 4 now covers
  material sets only.
- **Owner visual review pending:** queue close/Continue (`verify-queue-close.py`) and the **Format
  off** state (`verify-format-off.py`), from the PR 21 follow-ups. Log retention's Linux path is
  unverified.

  **Later** (parked, not planned): keep running in the system tray with the window closed; "Pause until…";
  audit every hidden or "nothing to do" state against P5; *Make previews again from the OBJ* for a Format off
  model (the catalog re-derives the inspected file on every scan, so it needs its own design); tell agents
  about Format off in `get_asset`; `library_store._remap` maps ID fields directly instead of replacing text.

- Owner visual/copy review of the setup wizard (decision 0014) and the agent setup panel
  (decision 0016), and one run with a real agent on a throwaway project.
- Linux GPU descriptions and semantic search are unverified; macOS is unsupported.
- Linux path policy for case-insensitive references and `\` in MTL files is undecided.
- No packaged installer; the app runs from a source checkout.
- Expansion steps 3–8 (sprite sheets, textures, audio, animation clips, shaders) are
  planned but not started ([Expansion plan](Architecture/Roadmap/Expansion%20plan.md)).

## Scripts

Everyday entry points: `local-assets` (`scripts/local-assets.ps1` / `.sh`), `check-config`,
`doctor`, `scripts/smoke-headless.py`, the `scripts/verify-*.py` synthetic checks and the
pytest suite. The tools that reproduced the original pilot, benchmark and one-time migrations
were removed in November 2026 (they needed the original owner's data and code that no longer
exists); they are in git history at commit `af02e91` under `scripts/historical/`.
