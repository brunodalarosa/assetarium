# Current status

Short, current summary. Detailed dated history, test counts and evidence are in
[`progress.md`](progress.md); binding rules are in [`decisions/`](decisions/README.md).

## What works today

- **Catalog and processing:** register asset sources; startup scans; explicit Process
  assets (Blender inspection and previews, optional Qwen3-VL descriptions, EmbeddingGemma
  vectors); incremental publication with faults kept visible. 3D formats (FBX, glTF/GLB,
  OBJ/MTL, BLEND…) and static images (PNG, JPEG, SVG…).
- **Search:** keyword, description, image and combined search in the desktop app, the
  owner CLI ([`cli.md`](cli.md)) and the STDIO MCP server ([`mcp/README.md`](mcp/README.md)).
- **Desktop app (Windows):** sources, asset processing, search, 3D preview, collections and
  tags, setup wizard, agent-assisted setup.
- **Linux:** CLI + MCP only, no desktop app ([`linux.md`](linux.md), decision 0013).
- **License:** AGPL-3.0-only with a CLA (decision 0017).

## Open work and pending reviews

- Owner visual/copy review of the setup wizard (decision 0014) and the agent setup panel
  (decision 0016), and one run with a real agent on a throwaway project.
- Linux GPU descriptions and semantic search are unverified; macOS is unsupported.
- Linux path policy for case-insensitive references and `\` in MTL files is undecided.
- The **Library** navigation destination is hidden until a library browser is built
  (decision 0011).
- No packaged installer; the app runs from a source checkout.
- Expansion steps 3–8 (sprite sheets, textures, audio, animation clips, shaders) are
  planned but not started ([plans](next%20version%20plan/README.md)).
- The CLA text is being drafted and needs owner (and legal) review before contributions
  are accepted.

## Scripts

Everyday entry points: `local-assets` (`scripts/local-assets.ps1` / `.sh`), `check-config`,
`doctor`, `scripts/smoke-headless.py`, the `scripts/verify-*.py` synthetic checks and the
pytest suite. Tools that reproduce the original pilot, benchmark or one-time migrations
are in [`scripts/historical/`](../scripts/historical/README.md); they need the original
owner's data and are not general tools.
