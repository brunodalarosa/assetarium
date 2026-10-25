# Step 2 measured catalog — October 11, 2026

883 logical records represent 2,929 model files: 883 primary entries and 2,046
alternate files. All 4,938 discovered files have an inventory role and status.
Six model formats exist: OBJ, FBX, GLB, Blender, DAE and STL. glTF JSON is supported
by the scanner but no `.gltf` file exists in this collection. No unsupported model
candidate extension or unclassified file was discovered.

| Pack | Logical records | Model files | Alternates | Assets with individual views | Missing views |
| --- | ---: | ---: | ---: | ---: | ---: |
| Kenney Car Kit | 50 | 150 | 100 | 50 | 0 |
| Kenney City Kit Roads | 95 | 285 | 190 | 95 | 0 |
| Kenney Food Kit | 200 | 600 | 400 | 200 | 0 |
| Kenney Furniture Kit | 140 | 700 | 560 | 140 | 0 |
| Kenney Mini Forest | 22 | 66 | 44 | 22 | 0 |
| Quaternius Ultimate Food Pack | 103 | 309 | 206 | 0 | 103 |
| Quaternius Ultimate House Interior Pack | 123 | 369 | 246 | 0 | 123 |
| Quaternius Ultimate Nature Pack | 150 | 450 | 300 | 0 | 150 |
| Total | 883 | 2,929 | 2,046 | 507 | 376 |

See the machine report for format-specific counts. Furniture supplies 700 images: 140 Side images and 560
directional Isometric images. These are supplied baseline views, not new renders.
Overall there are 1,067 individual images, nine pack contact sheets, three sample
images and 13 texture files. No image was visually validated in step 2.

All eight ZIPs are excluded as verified duplicates: each of their 4,929
non-directory members matched an extracted path by size and SHA-256. No archive
was extracted or modified. Archives with absent/mismatched counterparts would
instead receive a visible review status; synthetic tests exercise this case.

Grouping uses identical complete filename manifests in recognized sibling export
folders, preserving pack and deeper path identity. This is recorded export-layout
evidence, not proof of identical geometry. Every logical asset still has geometry
inspection pending. See [catalog-contract.md](catalog-contract.md) for the exact
algorithm and identity rules.

24 repeated-name cases involve 48 distinct records, retained separately. Twenty-one
names repeat across the food packs; `Fork`, `Knife` and `Spoon` also repeat in the
house-interior pack. For example, Kenney `apple` and Quaternius `Apple` have
different IDs and paths. None of these collisions was merged. Filename-derived
variant relationships remain suggestions, not measured visual facts.

1,617 dependency references were recorded. No missing/rejected dependency or text
parser issue was discovered among those parsed references. The 883 FBX and 376
Blender files still need binary material/dependency inspection in step 3. Embedded
GLB content was not extracted; neither existence nor reference parsing proves
successful import, complete materials, topology, bounds, units or animations.

Five Kenney packs and the Quaternius nature pack contain bundled CC0 license
evidence. The other two Quaternius packs rely on the supplied collection
`README-licenses.txt` claim and source links; no bundled author license was found
there. The catalog labels that note separately from supplied pack files, and does
not treat it as independent web verification or generate legal conclusions.

The technical pilot has five assets per pack, 40 distinct records, 130 model
files, all six observed formats, 25 assets with supplied views and 15 without.
Every pilot asset has an OBJ material reference; texture references are represented
by the four textured Kenney packs. The explicit selection and each rationale are
versioned in [pilot-selection.json](pilot-selection.json). The resolved manifest
is `data/pilot/selection-manifest.json`; its IDs, source/dependency hashes and view
paths are generated without copying assets. It is not a random sample or owner
visual/relevance approval.

Raw machine evidence is kept locally under ignored `data/`:

- `reports/catalog-summary.json`: counts, formats, role inventory, all collisions,
  archive-member verification, dependency issues and limitations.
- `reports/scan-run-final.json`: actual scan result and runtime.
- `evidence/source-baseline.json`: full source path/size/hash/mtime inventory.
- `evidence/scan-immutability.json`: matching full inventories before publication.
- `evidence/source-verification.json`: final comparison after search/pilot checks.
- `reports/search-*.json`: real keyword results and measured character sizes.
- `evidence/pilot-reproducibility.json`: two resolved manifest hashes.
- `evidence/catalog-checks.json`: database integrity, search paths/size,
  logical-record determinism and pilot coverage checks.

No original pack, neighboring installation or Play Shapes file was written. No
renderer, model inference, caption or embedding stage was run.
