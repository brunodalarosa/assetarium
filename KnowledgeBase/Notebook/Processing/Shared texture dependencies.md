---
area: Processing
tags: [system]
code: [dependency_resolution.py, dependency_overrides.py, texture_repair.validate_recipe, texture_folders.py, blender_repair_worker.py, blender_shared_dependency_worker.py]
verified: 2026-10-28
branch: feature/library-view
---
# Shared texture dependencies

Hub: [Processing](Processing.md). Models whose texture references point somewhere missing can still
render with the right textures, without touching originals. Three mechanisms, from automatic to
owner-chosen: shared project layouts across sources (`dependency_resolution.py`), explicit per-source
overrides (`dependency_overrides.py`), and the owner's texture-folder choice (`texture_folders.py`).
User guide: [Shared texture dependencies](../../../docs/dependency-path-overrides.md).

## How it works

- Each mechanism produces a **source-hash-bound texture repair recipe** (`texture_repair`). Processing
  then renders with `blender_shared_dependency_worker.py` or `blender_repair_worker.py`, which bind
  the images in the temporary Blender scene only and call the unchanged inspection renderer.
- The repair worker's hash joins the inspection fingerprint, so a changed recipe or worker re-renders
  only the affected models.
- The desktop viewer and `get_asset` expose the same verified paths and bindings; external consumers
  must apply those bindings when importing the original file.

## Rules

- **Never guess by basename, never copy or move textures, never edit model bytes or material/alpha settings.**
- Conflicting bytes at the same relative path stay an ambiguous fault; disabling a provider source,
  changing bytes or restoring the original local file invalidates a resolution until the next scan.
- Shared layouts are a general capability (decisions [0009](../../Decisions/0009-general-capabilities.md),
  [0010](../../Decisions/0010-shared-project-dependencies.md)): any new registration with the same
  layout gets it automatically. The texture-folder choice is all or nothing per model, exact names
  only ([0021](../../Decisions/0021-texture-folder-choice.md)).

## Gotchas

- Only external glTF/GLB image references are handled today; other resource kinds need a processing adapter.
- History: the Cartoon City repair (October 18, 2026) mapped four model add-ons to the pack's Core
  textures: 3,467 blocked models, 5,266 missing references, 16 shared texture files. Receipts live in
  the owner's `data/repairs/cartoon-city-20261018/`. It is why shared layouts became a general feature.

## Related

[Blender rendering](Blender%20rendering.md) · [Sources](../Sources%20and%20Catalog/Sources.md).
