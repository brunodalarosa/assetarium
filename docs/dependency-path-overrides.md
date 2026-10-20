# Shared texture dependencies and explicit paths

Some publisher packs distribute models and shared textures in separate folders.
Their glTF/GLB image URIs can consequently point to a missing location even when
the supplied texture exists elsewhere in the supplied folders. The library never
moves originals, copies textures, or guesses by basename.

## Automatic shared project layouts

Missing external glTF/GLB images can use a matching complete project-relative path
inside another **enabled registered source**. For example, `Town/Textures/map.png`
in one source can supply that exact missing path in a separately registered model
source. The source folder names do not matter. Texture-only sources work without
model imports or prior processing. No unrelated disk directories are searched.

Healthy local files and explicit mappings win. Conflicting contents at the same
relative path stay ambiguous faults; byte-identical duplicates retain all candidate
evidence. Records retain the original reference/location, model hash, provider ID,
texture hash and resolution method. Disabling/removing a provider, changing bytes,
adding a conflict or restoring the original local file invalidates the resolution
until rescanning. Ordinary source-file boundaries remain strict; a separate checked
dependency API serves rendering, desktop previews and agent retrieval.

Bindings apply to the temporary Blender scene and viewer package. Original model
bytes and material/alpha settings stay intact. External consumers must apply the
returned bindings. Additional resource kinds need a processing adapter; this
feature currently handles external glTF/GLB image references.

See [general capability policy](decisions/0009-general-capabilities.md) and
[shared dependency decision](decisions/0010-shared-project-dependencies.md).

## Explicit mappings within a source

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
