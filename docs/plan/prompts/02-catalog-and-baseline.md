# Step 2 prompt — Catalog assets and establish the keyword baseline

```text
Work in C:\BrunoOS\Local-Asset-Library and implement only step 2. Read applicable AGENTS.md, docs\progress.md, and the scope, catalog contract, and step 2 sections in docs\plan\PROJECT.md. Confirm step 1 actually succeeded. Inspect existing code before choosing file changes. Do not spawn subagents or modify source packs, neighboring installations, or Play Shapes.

Build a deterministic read-only scanner for C:\Users\backup pc\Documents\General game assets\playful-lowpoly-asset-packs. Inventory all packs, formats, dependencies, license/source evidence, individual previews, pack contact sheets, and textures. Exclude ZIP duplicates. Use pack plus source-relative identity for stable asset IDs; group alternate formats conservatively with recorded evidence. Same basenames across packs or unrelated subdirectories are not sufficient proof of equivalence. Preserve variants and expose ambiguous groupings for review.

Persist the catalog in SQLite and add filename/keyword search using FTS5. Check that the actual Python SQLite build supports FTS5; report or solve a real compatibility problem locally instead of silently replacing it. Return compact logical-asset results with IDs and available paths. Do not generate captions or embeddings yet.

Create a reproducible 40-asset pilot across all eight packs. Include food, furniture, vehicles, roads, trees, named variants, repeated names, several formats, dependencies, and assets with missing previews. Save the selection manifest and selection rationale. Write a catalog summary showing logical records, alternate files, ambiguous cases, unsupported candidates, and counts by pack.

Test duplicate names, conservative grouping, deterministic IDs, exclusions, missing dependencies, and valid source-root boundaries using small fixtures. Demonstrate keyword searches against real records. Record source immutability evidence appropriate to the files touched. Update docs\progress.md with commands, actual results, evidence paths, and unresolved cases; make a checked local commit without pushing. Finish with the pilot manifest location and step 3 instructions. Stop before rendering or installing models.
```
