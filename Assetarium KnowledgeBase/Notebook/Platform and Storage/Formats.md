---
area: Platform and Storage
tags: [system]
code: [settings.uses, settings.used_formats, settings.image_formats, settings.format_key, settings.processing_eligible, folder_view.build, retrieval.matches, frontend/src/ui/FormatToggles.tsx]
verified: 2026-11-01
branch: feature/library-view
---
# Formats

Hub: [Platform and Storage](Platform%20and%20Storage.md). "Formats Assetarium uses" (Settings → General, setup, CLI
`settings set --formats / --image-formats`, agent `apply_setup`): a format that is off does not exist for Assetarium
([decision 0026](../../Decisions/0026-setup-leaves-core-features-working.md)).

## How it works

| Format | Toggle | Can be turned off? |
| --- | --- | --- |
| glTF / GLB | `gltf` (`.glb` counts) | Yes |
| FBX | `fbx` | Yes |
| OBJ | `obj` | Yes |
| PNG, JPEG (`.jpg`), SVG, WebP, TGA, TIFF (`.tif`), BMP, GIF, AVIF | one each (`processing_formats` 3D, `image_formats` images in `settings.json`) | Yes, for **standalone images** |
| Image files used as textures by 3D models | none | **Always on**: textures follow their models, whatever the image toggles say |
| `.blend`, `.dae`, `.stl`, audio and other recognized types without a toggle | none | Always listed (not processed) |

- `settings.uses(kind, extensions, formats)` is the one rule: a `model_3d` or `image` asset is hidden when every
  extension has a toggle and every toggle is off. Textures and kinds without toggles are always used.
- `used_formats(config)` (3D + image toggles that are on) feeds `processing_eligible`, the folder-view stamp and the
  paused state (every format off). `processing_formats` stays 3D-only for `choose_source` and the API.
- Folder views store `hidden` (VERSION 3); the Library, its counts and the queue filter `NOT hidden`; the tree counts
  `hidden` per folder for the "N files in formats you don't use" line. Search and browse pass `used_formats` to
  `retrieval.matches`. Collections keep hidden members with `hidden_by_formats`.

## Rules

- **Hide, never delete**: turning a format off writes nothing but `settings.json`; results stay and come back.
- **New format readers use `used_formats` and `uses`**, never a list of their own.
- A file type gets a toggle only when Assetarium can process it; a toggle that changes nothing is an action that
  cannot resolve the shown state.

## Gotchas

- Changing formats rebuilds folder views (their stamp includes the formats): instant for small folders, a few
  seconds for very large ones.
- Toggles update with a function of the current list (`FormatToggles` `onChange(update)`): two quick clicks computed
  from a stale list used to undo each other.

## Related

[Core features](Core%20features.md) · [Folder views](../Sources%20and%20Catalog/Sources.md) ·
Decisions: [0019](../../Decisions/0019-source-folders-and-export-variants.md), [0026](../../Decisions/0026-setup-leaves-core-features-working.md).
