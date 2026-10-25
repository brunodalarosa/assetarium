# Step 3 pilot inspection

October 11, 2026. The existing 40-asset pilot across eight packs was inspected.
All 40 primary files produced metadata and views; seven also carry source fault
flags. The catalog still contains 883
logical assets; only the pilot has measured technical fields. Descriptions and
embeddings remain empty. No models were installed or source files changed.

The selected formats are 23 GLB, 15 OBJ/MTL, one FBX and one Blender file. Each asset
has front, side and three-quarter views. Four flat assets also have top views:
road-straight, road-straight-barrier, road-crossroad and Pizza_Burned. Total: 124
640×640 PNGs. Selection and source-choice rationale:
`data/inspection/processed-manifest.json`. The original pilot remains at
`data/pilot/selection-manifest.json` with its original byte hash.

## Actual metadata examples

These are evaluated instance totals for the chosen file at the recorded frame,
not counts inferred from a filename or applied to alternate exports.

| Asset | Inspected format | Objects / mesh objects | Vertices | Triangles | Materials | Armatures / actions |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Kenney sedan | GLB | 5 / 5 | 3,184 | 2,032 | 1 | 0 / 0 |
| Kenney sedan-sports | OBJ | 1 / 1 | 1,255 | 2,087 | 1 | 0 / 0 |
| Kenney apple | FBX | 1 / 1 | 71 | 130 | 1 | 0 / 0 |
| Quaternius BirchTree_1 | Blender | 1 / 1 | 866 | 1,704 | 4 | 0 / 0 |

Sedan world bounds: `(-0.75, -1.25, 0)` to approximately `(0.75, 1.30, 1.30)`.
Birch bounds: approximately `(-0.823, -0.569, -0.006)` to `(0.879, 1.910, 3.568)`.
The three exchange-format examples import with metric scale 1; the Blender tree
has unit system NONE and scale 1. These settings do not prove physical size.
Per-mesh local bounds, transforms, edges, polygons and texture evidence are in the
catalog and each job's `result.json`. Full examples and actual keyword results are
in `data/evidence/step3-catalog-check.json`.

## Images and verification scope

Representative rows below: GLB sedan, OBJ sedan-sports, FBX apple, Blender birch.
Columns: front, side, three-quarter. These twelve images were opened with image
tools and checked for visible materials, complete subjects and framing margins.

![Representative rendered views](C:/BrunoOS/Local-Asset-Library/data/inspection/review/representatives.png)

The full pilot overview was also opened with image tools. Every asset has automated
foreground and frame-edge checks on every view. Additional road-top and rock
diagnostic images were examined individually. Technical image checks and owner
artistic approval are recorded separately; owner approval remains pending.

![Forty pilot three-quarter views](C:/BrunoOS/Local-Asset-Library/data/inspection/review/pilot.png)

## Runtime and reproducibility

Reused `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`:
Blender 5.2.2 LTS, build `d13f752e3b9c`, September 15, 2026. No installation
modified or downloaded. `data/inspection/blender-runtime.json` captures its probe.
Use `blender` in local config to explicitly select another compatible executable.

Factory startup, offline mode and disabled automatic execution are passed on every
job. Blender files additionally open with `use_scripts=False`. All user resource,
extension, temporary and cache paths are redirected into the project and recorded.
Local CLI help and a real embedded-script fixture verified this behavior; see
also the official [directory layout documentation](https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html)
and [open-mainfile API](https://docs.blender.org/api/5.2/bpy.ops.wm.html).

CPU Cycles: 128 samples, seed 0, adaptive sampling off, CPU OpenImageDenoise,
Standard color transform, exposure 0, gamma 1. Three neutral area lights scale
with the bounding sphere. Orthographic framing uses one shared scale and 16%
margin. Imported materials are retained in a separate render scene. Alpha masks
detect empty subjects and frame-edge clipping before compositing a neutral gray
background. Camera positions, rotations, dimensions and settings are persisted.
Reproducibility is for the recorded runtime/settings; cross-version byte equality
is not promised.

Jobs run one at a time with a 180-second bound. Changed inputs are rejected before
processing; cached outputs require current hashes. Successful exit alone is
insufficient: metadata, identity, output boundaries, required views, hashes and
foreground checks must pass. Unsupported formats retain explicit outcomes.
DAE was not imported by this runtime; existing DAE alternates remain uninspected.

## Issues retained

Initial EEVEE jobs crashed in the NVIDIA/OpenGL path (`3221225480`); CPU Cycles
resolved the local compatibility issue. Initial bright/noisy renders were corrected
with neutral lighting and denoising, then viewed again. Diagnostic output remains
in ignored project storage. No graphics driver or system installation was changed.

BirchTree_1 contains an unused historical missing `Texture.png` reference. Its
four active color materials do not use that image. The reference remains a warning;
a missing required material texture would fail the render, as verified by fixtures.

The GLB rocks-high export contains overlapping faces and caused black self-shadow
artifacts compared with its supplied thumbnail. A temporary emission diagnostic
confirmed the palette was present; a shadow-disabled diagnostic confirmed the
artifact. Exact duplicate-position faces are now flagged in metadata and affected
meshes have a recorded shadow-ray override in the derived scene. Materials and
geometry are retained. Faulty sources are marked for review, not repaired; further
asset-specific repair work is outside this step. Probe evidence is retained at
`data/inspection/review/rocks-diagnostic/probe.log`.

Flagged geometry: ambulance (58 overlapping faces), traffic-light (22), burger
(78), burger-cheese-double (156), kitchenFridge (30), rocks-high (156). BirchTree_1
is flagged for its unused missing texture reference. These flags coexist with
usable derived previews; they are not erased by a successful render. The processed
manifest and catalog checker enumerate each faulty asset and its evidence.

The permanent fault rule applies to every kind of fault: mark it, preserve partial
results, and move on. Unchanged faulty results are cached without automatic retry.
`--retry-faults` is an explicit opt-in after a user request. No additional asset
diagnosis or repair is required for batch completion.

Source author front, actual scale, alternate geometry/material equivalence,
animation behavior, license unknowns and artistic suitability remain unresolved.
Supplied thumbnails are retained as baseline evidence, never substituted for the
new multi-view inspection.

## Evidence and next step

Before/after checks cover 178 pilot model/dependency files plus one FBX texture
discovered by Blender and checked against the original full inventory. Evidence:
`data/evidence/step3-pilot-before.json`, `step3-pilot-after.json`, representative
equivalents, per-job source hashes, and `step3-full-source-verification.json`.
Full verification found zero byte/size/mtime changes across all 4,938 source files.
Access times and directory metadata are not covered. All output is project local.

The source fingerprint remains
`4dbf39d53556d225c9aac13330a9cd91a522dbd1ceae8e195e86184389a9095c`;
the original pilot SHA-256 remains
`844d495098a7442e481ac2a3b703f312f38804460d15d353e0a9b116f0f75459`.
SQLite integrity and the 883-row FTS index pass. `Apple Green`, `BirchTree Snow`
and `chair rounded` still retrieve distinct real records with available paths;
generated previews identify their project root explicitly.

Next: step 4 instructions in the original staged plan (`plan/PROJECT.md`, since removed
from the repository; it remains in Git history before commit `6a128ae`). Approve
its scope and implementation plan with time/disk estimates. Verify a small local
vision model's official license, revision, image support, device compatibility and
budget before downloading; test actual images, then describe about ten varied
pilot assets before the full pilot. No description generation has started here.
