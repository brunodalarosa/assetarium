# Step 3 prompt — Inspect models and render views

```text
Work in C:\BrunoOS\Local-Asset-Library and implement only step 3. Read applicable AGENTS.md, docs\progress.md, and the visual inspection policy, catalog contract, and step 3 in docs\plan\PROJECT.md. Use the existing 40-asset pilot and catalog. Do not spawn subagents, edit originals, or modify Play Shapes.

Implement a Blender background inspector/renderer. Discover and configure the actual executable. Reuse an installed Blender when compatible. If none is usable, obtain a verified official portable release within the project budget and workspace; never modify a system installation. Capture its version. Disable automatic execution of scripts embedded in Blender files and keep all output inside the project.

Select a primary inspection format per logical asset and record why. Inspect geometry counts, object/mesh count, local-space bounds and unit settings, materials, texture dependencies, armatures, and animation clips. Preserve unknowns and format limitations. Do not imply that an alternate export has features only verified in the chosen source.

Render front, side, and three-quarter views with deterministic framing, neutral lighting/background, preserved materials, and recorded coordinate/render settings. Add detail/back/top views where justified. Detect empty/off-frame renders, missing textures, timeouts, and unsupported imports. Existing thumbnails may be retained as baseline evidence, not silently treated as complete multi-view inspection.

First validate representative GLB, OBJ/MTL, FBX, and Blender cases that exist in the pilot. Inspect the resulting images with image-viewing tools and correct material or framing defects. Then process the remaining pilot with bounded jobs and explicit failures. A successful Blender exit alone is not visual validation.

Test using small fixtures for framing, failure isolation, output boundaries, and inspection metadata. Show actual metadata plus selected real previews; preserve before/after hashes for inspected source/dependency files. Update docs\progress.md with commands, timings, inspected formats, issues, and evidence. Make a checked local commit; do not push. Stop before description generation.
```
