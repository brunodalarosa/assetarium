# October 14 texture repairs

Bruno approved repairing the texture/material bindings of the 648 newly imported
models blocked by missing author paths. Originals remain read only; source files
are never rewritten or copied. Repairs use existing supplied textures, exact
filenames within the same subpack, or publisher mesh/material-slot tables. An
ambiguous or absent mapping stays faulty. No substitute textures, geometry repair,
Godot effect reconstruction, or unrelated caption-fault retry is included.

The approved estimate was 6–11 hours and 0.5–1.5 GiB additional storage, with an
enforced 2 GiB repair-growth limit and 10 GiB project ceiling. Existing runtimes,
shared models, and external textures are reused. Reducing preview resolution or
view count would reduce storage; the normal 640-pixel multi-view previews are kept.
No cleanup is performed. Unique allocated bytes are measured before/after bulk
work and during processing under `data/storage/`.

The repair worker changes only the loaded Blender scene. It preserves existing
image color spaces and connections, reconnecting nonconstant supplied albedo alpha
to an otherwise unlinked Principled alpha input. The initial representative ivy
render exposed opaque black card regions; its supplied RGBA alpha range was 0–255.
The initial successful samples and corrected-alpha render evidence are retained.
The common worker and healthy assets' inspection fingerprints stay unchanged.
Changing worker settings alone does not authorize a retry of unchanged faults.

The audit found 599 candidates: 429 Generic, 105 CraftPix, and 65 Synty. The remaining
49 (23 Generic, 2 CraftPix, 24 Synty) have missing or unsupported author mappings.
Candidate counts are not a claim that bulk processing has succeeded. Twelve
representatives passed technical rendering and contact-sheet checks. Owner
accuracy/artistic approval and exact authored engine appearance remain pending.

## Published preview results

Bulk rendering and image indexing are complete. All 594 successful three-quarter
previews were inspected across thirteen final contact sheets.

| Pack | Recovered models | Retained faults |
| --- | ---: | ---: |
| Generic | 424 | 28 |
| CraftPix | 105 | 2 |
| Synty | 65 | 24 |
| Total | 594 | 54 |

The 54 faults comprise 49 unresolved mappings and five preview-quality failures
(four thin walls and one skyline model). Their original evidence and usable
partial results remain. Nineteen recovered models retain pre-existing overlapping
face faults; this operation did not repair geometry. The seven separate new
caption-validation failures and all unrelated caption faults remain excluded.

The published preview generation is `v_1cb1b604c5e2414486029e474bf2eeeb`, with 6,976
image vectors and the previous 1,219 text vectors. The operation added 1,931 image
vectors, including usable partial images. Preservation verification passed for
all original files, unrelated records, old outputs/vectors and owner states.
Live MCP detail returned a repaired preview and verified import bindings; live
image search returned repaired ivy models. Evidence is in `preview-verification.json`
and `live-mcp-{detail,image-search}.json` under the repair evidence folder.

Before descriptions, measured unique allocated project storage was 7.74 GiB,
with approximately 534 MiB growth from the repair baseline. No installation,
original/model copy or cleanup occurred. The recovered-ID description run
`8a5f127aa1fe475a8edeed0c7fd5136f` is running in the background. Its existing
runner updates text search and publishes the completed generation. Final
verification/storage checks automatically follow.

The larger image-vector preservation receipt exposed the Windows reader's old
1 MiB size bound. The reader now has a strict 4 MiB bound, verified with synthetic
large/oversized fixtures and publication tests. A background finalizer watches
this existing run and resumes only finalization if the already-running coordinator
encounters the old limit; it never repeats completed/failed description attempts.
Application-fault evidence is retained separately from asset faults.

`data/texture-repairs/20261014/` contains the full original-record/source/vector
baseline, hash-bound overrides, unresolved findings, per-model one-attempt outcomes,
visual review, storage receipts, and publication/preservation checks. No completed
or failed outcome is automatically repeated on resume. An interrupted intent stays
visible and requires an explicit reviewed repair/retry.

Both desktop and MCP use the corrected dependency paths and preserved provenance.
MCP details provide `texture_overrides` and an import limitation: the FBX itself
still contains its original author paths. Engine imports must apply the supplied
bindings; a successful library render is not proof of an automatic engine import.

Recovered previews are indexed and published first. The descriptions script uses
an explicit recovered-ID allowlist, so the seven separate new caption-validation
faults and older caption faults remain untouched. Each recovered asset receives
one new description attempt; caption severity follows `docs/caption-quality.md`.
The prepared overnight runner preserves evidence, updates text search, and
publishes its completed generation. It can continue in the background.

Useful operations are `scripts/repair-textures.py prepare`, `representatives`,
`bulk`, then `index` in the prepared embedding runtime. The bulk operation requires
a recorded representative technical pass. Description selection is supplied as a
JSON ID array with `scripts/overnight-descriptions.py --asset-ids-file`.
