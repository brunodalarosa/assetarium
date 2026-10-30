---
tags: [hub]
verified: 2026-10-30
branch: feature/library-view
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
- **Desktop app (Windows):** Asset sources tab (browse by place), asset processing queue, search,
  3D preview, collections and tags, setup wizard, agent-assisted setup.
- **Linux:** CLI + MCP only, no desktop app ([`linux.md`](../docs/linux.md), decision 0013).
- **License:** AGPL-3.0-only with a CLA (decision 0017). The CLA text is revised and published
  ([CLA.md](../CLA.md), [CLA-entity.md](../CLA-entity.md)); contributors sign it as described in
  [CONTRIBUTING.md](../CONTRIBUTING.md).

## Open work and pending reviews

- **ASSETRM-0002 (decision 0023) is implemented on `feature/library-view`.** The owner runs the
  one-time migration (`scripts/migrate-library.py`: dry run, `--apply`, later `--remove-old`) and
  reviews the Asset sources tab and the queue. Open points from the plan, decided provisionally:
  a pack without a preview image shows a package glyph as its cover; "+N new" resets when you
  leave a library folder; the 10- and 30-minute thresholds are constants
  (`processing_queue.QUICK`, `LONG`). Roadmap step 4 now covers material sets only.

- Owner visual/copy review of the setup wizard (decision 0014) and the agent setup panel
  (decision 0016), and one run with a real agent on a throwaway project.
- Linux GPU descriptions and semantic search are unverified; macOS is unsupported.
- Linux path policy for case-insensitive references and `\` in MTL files is undecided.
- The **Library** navigation destination is hidden until a library browser is built
  (decision 0011).
- No packaged installer; the app runs from a source checkout.
- Expansion steps 3–8 (sprite sheets, textures, audio, animation clips, shaders) are
  planned but not started ([Expansion plan](Architecture/Roadmap/Expansion%20plan.md)).

## Scripts

Everyday entry points: `local-assets` (`scripts/local-assets.ps1` / `.sh`), `check-config`,
`doctor`, `scripts/smoke-headless.py`, the `scripts/verify-*.py` synthetic checks and the
pytest suite. Tools that reproduce the original pilot, benchmark or one-time migrations
are in [`scripts/historical/`](../scripts/historical/README.md); they need the original
owner's data and are not general tools.
