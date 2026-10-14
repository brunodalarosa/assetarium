# Synty and CraftPix import — October 14, 2026

Status: **operation completed and published, with retained source/caption faults**.
The overnight description job **finished on October 14 at 2:57 a.m. New York time**.
Run: `5c64438b6b3a4b43b51987b2d0c90c1a`. Its morning report is
`data/overnight-descriptions/5c64438b6b3a4b43b51987b2d0c90c1a/summary.md`.
The October 14 completion check verified the published catalog/index, all completed
descriptions, preservation, and live description search. There were no worker
interruptions/timeouts, no unattempted selected assets, and no run error.
The final coordinator dry run confirms **zero pending inspection, caption, or
embedding jobs**. The remaining work consists of retained faults and owner review.

## Overnight results and remaining follow-up

Generated, indexed and published **282 new descriptions**: 265 CraftPix, 15 Generic,
and 2 Synty. Current generation: `v_41955003334a482e88d383e9f2c77be4`.
The library contains 1,901 records, 1,219 usable descriptions, and 5,045 image
vectors (6,264 vectors in total). Existing 27 caption failures remain unchanged.

The 655 failed new descriptions comprise **648 existing texture/preview blockers**
and **7 caption-validation failures** among models with usable renders. The 655
new description-index faults concern these same failed assets; they are not an
additional 655 asset failures. No model or asset was automatically retried.

The seven caption failures are `Road_breek_4`, `Grass_002`, `Desert_plant_006`,
`Tree_temp_climate_007`, `Hill_desert_004`, `Tree_Tropic_014`, and `Scythe`.
Their original responses and rejection reasons are preserved. Validation rejected
suggested-use wording, inconsistent unknown-identity certainty, or an invalid
style list. Source/texture repair and failed-caption retries require a separate
explicit owner request. Owner accuracy/artistic review of generated descriptions
and preview appearance remains pending.

Final verification confirms unchanged source hashes, existing records and asset
outputs, owner corrections, previous vectors, and all 5,045 image vectors. Both
published databases passed integrity checks; all 282 completed captions have
published description vectors. Live MCP description search returned new assets
from the final generation. No completion claim is an accuracy/artistic approval.

Final storage receipt: **7.22 GiB total**, with **475.9 MiB measured project growth**
since the pre-import receipt (7,252,277,392 to 7,751,292,776 unique allocated bytes).
This includes retained outputs/evidence and runtime/verification caches; it remains
within the approved 10 GiB total and 3 GiB combined growth allowances.

Published import generation: `v_5e175e64a4bf47a190d44de8c9566cb4`.

| Folder | Registered models | Models with renders | Texture failures |
| --- | ---: | ---: | ---: |
| synty-part1 | 91 | 2 | 89 |
| craftpix-free-packs | 379 | 272 | 107 |
| POLYGON_Generic_SourceFiles_v3 | 467 | 15 | 452 |
| Total | 937 | 289 | 648 |

Generated and indexed **882 views**: 867 front/side/three-quarter images plus 15
top views. Existing 5,100 vectors were unchanged; the pre-caption published index contained
5,982 vectors. The 648 failed models retain unresolved texture reference evidence
and usable geometry measurements. No source repair, texture substitution, or
asset retry occurred. Another 237 Godot-native scene/resource items are listed
separately as unsupported; they are not 237 additional logical models.

All 937 new details and correct pack browse counts were checked through the desktop
backend. Actual MCP keyword search and PNG preview transport passed on the new
published generation. All seven overview sheets (289 three-quarter views) and
six representative front/side/three-quarter views were inspected. Many CraftPix
renders are grey; some Generic collision files retain explicit pink source diffuse
materials without image nodes/dependencies. Intended engine/material appearance
and owner artistic approval remain pending. Color uncertainty alone did not
manufacture an asset/caption fault.

Preservation passed: all 7,008 source entries are unchanged, all 964 existing
records' protected fields and existing vectors are unchanged, and prior asset
outputs/corrections are unchanged. The shared Blender discovery receipt refreshed
normally. The initial preservation harness decoded Unicode with the Windows
locale; explicit UTF-8 reads eliminated its false text/path differences. Both the
initial failed receipt and corrected verification are retained. A presentation
harness snapshot-selection error and a Windows test-fixture path-length error
were also corrected without retrying any assets.

Pre-caption storage receipts measured **7.01 GiB total** and **265.3 MiB import growth**
(7,252,277,392 to 7,530,498,920 unique allocated bytes). This is below both approved
allowances. The 1 GiB overnight allowance also fits the combined 3 GiB growth
budget and 10 GiB total ceiling.

The read-only inventory found 937 model records: 91 in `synty-part1`, 379 in
`craftpix-free-packs`, and 467 in `POLYGON_Generic_SourceFiles_v3`. Approved
membership expands from 964 to 1,901 records. Different files remain separate
identities; similarly named source/Godot exports are not silently merged.

The existing offline workflow inspects each model, generates multi-view 640-pixel
previews, indexes available images, and publishes usable results. Captions are
deferred until these stages and preservation verification finish. Faults and
partial results remain visible, with no original modification or automatic retry.
Godot-native scenes/resources/effects are listed separately as unsupported by
the Blender pipeline in `data/library/new-packs-20261014/unsupported.json`.

Supplied pack README/license evidence is retained without importing an unrelated
collection-wide CC0 claim. `NOT CC0` does not become a CC0 license identifier.
This records local source evidence; it is not legal or owner license approval.

The updated overnight launcher selects pending descriptions and preserves existing
caption faults. The background run targets these three packs, saves one attempt
per selected asset, updates text-search vectors, and publishes ready results.
New generated descriptions and previews await owner accuracy/artistic review.

Storage: 10 GiB approved total ceiling; 3 GiB combined additional allowance,
split into 2 GiB for import/render/index/publication and 1 GiB for overnight work.
No new runtime, model, original copy, or automatic cleanup is introduced.

Evidence is saved under `data/library/new-packs-20261014/`, `data/storage/`,
`data/library/operations/`, and `data/overnight-descriptions/`.
The latest overnight pointer is `data/overnight-descriptions/latest.json`.

Focused synthetic tests: 56 passed, including pending-only pack selection,
retained faults, resumable saved selection, and non-CC0 source evidence.
The pending-only preservation test was extended through actual synthetic text
indexing and passed. No new indexer change was required.

Key evidence:

- `data/library/new-packs-20261014/verification-confirmed.json`
- `data/library/new-packs-20261014/completion-20261014.json`
- `data/library/new-packs-20261014/completion-description-search.json`
- `data/library/new-packs-20261014/completion-pending-check.json`
- `data/storage/new-packs-completion-20261014.json`
- `data/library/new-packs-20261014/access-verification.json`
- `data/library/new-packs-20261014/visual-review.json`
- `data/library/new-packs-20261014/mcp-{search,preview}.json`
- `data/library/new-packs-20261014/unsupported.json`
- `data/library/new-packs-20261014/overnight-dry.log`
- `data/library/new-packs-20261014/overnight-{launch,confirmed}.json`
- `data/storage/new-packs-{before,after}-20261014.json`
- `data/library/operations/75fafc0236fc43b7b7d2c8fc91843fda/`
