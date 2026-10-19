# Explicit shared texture paths

Some publisher packs distribute models and shared textures in separate folders.
Their glTF/GLB image URIs can consequently point to a missing location even when
the supplied texture exists elsewhere in the same registered source. The library
does not move originals, copy textures, search other sources, or guess by basename.

After owner authorization, a source can have
`metadata-lal/library/dependency-overrides.json`:

```json
{
  "schema_version": 1,
  "authorization": "Owner approval for this specific repair",
  "sources": {"source/addon/Models/mesh.glb": "SOURCE_SHA256"},
  "paths": {
    "source/addon/Textures/map.png": {
      "path": "source/core/Textures/map.png",
      "sha256": "TEXTURE_SHA256"
    }
  }
}
```

Only a missing glTF image reference from an explicitly listed, unchanged source
file can use a mapping. The mapped texture must be inside the same registered
source, be present in the current inventory, and match its approved hash. Missing,
changed, invalid or escaping mappings remain visible faults. Existing available
references keep their original interpretation.

Scanning records the original missing location and the authorized resolution in
dependency evidence, then creates a source-hash-bound texture repair recipe.
The existing Blender repair worker reloads the supplied images in its temporary
scene. These path-only repairs preserve the model's supplied material and alpha
settings. The existing desktop viewer and agent detail expose the same verified
paths and import overrides. Original GLB bytes remain unchanged, so an external
consumer must apply those supplied mappings when importing the original file.

The manifest does not start rendering or models. Changed inputs become actionable
through the normal processing ledger; unchanged failures are still retained.
Successful stages clear their current stage fault while append-only ledger
history preserves earlier failures. Source-owned caption retries retain their
raw evidence under that source's metadata directory.

## Cartoon City repair, October 18, 2026

The owner approved mapping the four separate model add-ons to the supplied Core
textures, retaining all successful processing, and producing only missing results.
The audit identified 3,467 blocked models, 5,266 missing references, 28 distinct
missing locations and 16 shared texture files. The 310 previously rendered models,
930 previews, 308 usable descriptions and 1,238 vectors are protected.

Receipts, original hashes, prior catalog and ledger, per-asset sample results,
resumable processing logs and final verification belong under
`data/repairs/cartoon-city-20261018/`. The approved growth ceiling is 4 GiB within
the existing 24 GiB library budget; unique allocation receipts also include each
source's generated metadata. Owner appearance and caption approval remain pending.
