---
tags: [decision]
decided: 2026-10-19
area: Processing
---
# 0010 — Shared dependencies across registered project fragments

**Decision (owner-approved implementation plan, October 19, 2026).** A missing
external glTF/GLB image may resolve to the exact same complete project-relative
path inside another enabled registered source. This supports split exports whose
folders are intended to overlay one shared project layout. Valid local references
and explicit source-owned mappings take precedence. Never match a bare filename,
search arbitrary disk directories, or download dependencies.

Only one content hash may match. Byte-identical duplicates are equivalent and
retained as candidate evidence; differing candidates remain ambiguous faults.
Resolution records retain the original reference/location, referring model hash,
provider source identity, target hash and candidate paths. Texture-only sources
can provide dependencies without being catalogued as models or first processed.

**Keep true.** Ordinary source-file access keeps its original boundaries. Shared
dependency reads use a separate validated API, rechecking enabled source identity,
containment, original model bytes, target bytes and conflicting candidates.
Disabling/removing/replacing a provider or changing its files invalidates reads
and preview tickets; rescanning can establish a new resolution. New/changed
dependencies are new processing inputs; unchanged failures retain their history.

The glTF image adapter rebinds only recorded images in a temporary Blender scene.
It preserves supplied material/alpha settings and uses the unchanged inspection
renderer. The viewer and agent detail receive the same verified bindings. Original
asset bytes are never rewritten, and no shared model or original texture is copied
into a cache. External consumers of originals must honor the returned bindings.

**Fragments inside one library folder.** Split project fragments may also live side by side inside
one library folder, as when separate folders join a library folder added around them
([decision 0032](0032-library-store-and-queue.md)). When
no other library folder has the path, the same path inside a sibling folder of the same library folder is
tried: exactly one folder differs (the fragment's own folder and its sibling), at least a folder and the file
name follow it, and the nearest such level with a match wins. The same single-hash, conflict and validation
rules apply. The inspection key holds these bindings relative to the model and without folder IDs, so a joined
fragment keeps its finished renders.

The path-resolution component is independent of named packs. Additional format
adapters can use its validation, but this decision does not claim processing
support for unimplemented formats or other missing resource kinds.

## Changes

- 2026-10-30: sibling fragments inside one library folder resolve the same way (owner-approved).
- 2026-11-10: that addition is written into the decision text instead of standing as an amendment paragraph; no rule changed.
