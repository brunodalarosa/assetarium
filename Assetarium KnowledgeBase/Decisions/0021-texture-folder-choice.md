---
tags: [decision]
decided: 2026-10-26
---
# 0021 — Owner-chosen texture folder for models whose textures were not found

**Decision (user of this checkout, October 26, 2026; for the owner's review before any merge
upstream).** Packs often ship their textures once per render pipeline (`Textures/PBR`, `URP`,
`HDRP`, `Unreal`) while FBX files name a texture without a usable path. Inspection then records
the texture as missing and the asset fails; the glTF-only path mapping
([dependency path overrides](../../docs/dependency-path-overrides.md)) cannot help FBX, and the existing
texture repair only maps unique matches.

- **Suggestion (read only).** Each scan (`texture_folders.py`) looks at inspected models whose
  required textures are missing and finds files with the **exact same name** in the source. A name
  with one version (one file or byte-identical copies) is unambiguous; a name with several different
  versions needs a folder. Candidate folders are the shallowest folders holding exactly one version
  of each such name, listed with how many models each fixes alone and with single copies, sorted by
  the former. Settings → Asset sources shows the choice; the Asset processing card points to it;
  `local-assets sources textures KEY` lists it.
- **Apply.** The owner picks a folder and whether single copies may be used
  (`source.json` `texture_folder`). The rescan writes a `texture_folder_paths` texture-repair recipe
  (exact paths and hashes, the choice as authorization, `originals_modified: false`) for each model
  whose **every** missing texture resolves, and marks its failed render stages pending; the next
  Process assets renders it once through the existing `blender_repair_worker.py`. Models with any
  unresolved texture keep their recorded failure.
- **Undo / change.** Removing or changing the choice drops its recipes on the rescan; other repair
  kinds are never touched. Nothing is deleted.

**Why.** On the user's `Desert Pack`, 117 FBX models failed with "Missing, rejected or unresolved
texture dependencies"; `Textures/PBR` alone resolves 49, and with the two textures that exist once
(`Textures/Other/GrassAlpha_D.png`, `Textures/URP/Plants/Cactus_AlbedoTransparency.png`) all 117.

**Keep true.** Exact file names only, never similar names. One decision per source, applied only by
the owner. All or nothing per model. Originals and the inspection worker stay unchanged.

> **Since [decision 0023](0023-central-asset-library.md) (October 30, 2026):** the per-source generated folder named
> here is replaced by the central library store; the rules of this decision are unchanged and now apply to
> library folders, packs and folders.
