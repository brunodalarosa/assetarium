# Progress

## October 14 — Separate importing failures from pending work

Added **Importing failures report**, a scrollable list of original model paths
from configured sources, including disabled ones. Saved processing outcomes and
current input fingerprints distinguish retained failures from unattempted work.
Failure-only sources no longer show pending-import cards; unfinished independent
stages, changed files and unpublished results remain actionable. Deferred
descriptions and caption review notes are not reported as import failures.
Deleted assets do not return from older published failure records.

Refreshed all 13 installed source statuses: 150 affected assets, 266 original
model paths and no pending cards. All 1,901 catalog records and 8,742 vector rows
remain identical to the preserved publication. No original asset or generated
result was repaired or retried. Added UX guidance to `AGENTS.md` for the future
open source release, including asking the owner about unclear UX choices.

Actual WebView2 checks cover report navigation, selectable paths, scrollability,
keyboard focus, narrow layout and empty state. Final regression suite: **313
tests passed**, with no failures, errors or skips
(`data/gui/import-failures-tests-final.xml`). Installed-library verification:
`data/gui/source-installed-4c0dfee4dd/report.json`; synthetic UI verification:
`data/gui/source-settings-01bf5c12f0/report.json`. Owner usability approval remains
separate from these technical checks.

Before/after unique-allocation receipts under `data/storage/` record 237,640,504
additional bytes during the measured verification period (about 227 MiB, above
the 50 MB estimate). Retained verification data brings the measured total to
10,127,443,656 bytes (9.43 GiB), below the configured 10 GiB allowance. No runtime,
model installation or original-asset copy was added.

## October 14 — Configurable sources and source-owned metadata

Added **Settings → Asset sources**, live enabled-source membership, background
startup scans, and source cards with **Process assets**, combined processing/
publication progress and graceful cancellation at asset boundaries. Cards clear
only after a scan confirms that current assets are up to date and published.
Separate Process pending/Publish ready work controls are removed.

Migrated the 13 current folders to enabled sources and moved 23,969 individual
generated files into their `metadata-lal` folders. Current published records for
all 1,901 assets, all 8,742 existing vector entries and every original-file receipt
are unchanged. All 5,864 rendered-preview references resolve to source metadata.
Existing processing issues affecting 150 assets remain visible across 11 source
cards; no existing asset was reprocessed, repaired or retried.

Verification: **301 tests passed**, including real Blender rendering into source
metadata; actual WebView2 startup, active-search toggles, busy refresh exclusion,
source cards, progress/cancel and responsive Settings checks passed. A separate
two-cube source verified real cancellation, checkpoint reuse, complete description/
image vectors and processing through publication/verification. It was detached
afterward. A fresh real STDIO server verified migrated PNG delivery and live
disable/re-enable in semantic search. Owner usability/artistic approval is separate.

Windows long-path defects in historical-report copying and storage traversal were
fixed and regression-tested. The original migration fault receipt is preserved;
all 246 missing report copies were subsequently completed without rerunning assets.
An old project-root assumption in caption publication was fixed and verified with
all eight expected vectors on the two-cube check. Temporary QA combined indexes
were removed only after proving that every row/vector remains in authoritative
source snapshots; source outputs, fault records, previews and reports were kept.

Receipts: `data/library/verification/source-preservation.json`,
`data/library/source-migration/report-copies-completion.json`,
`data/library/verification/source-test-cache-cleanup.json`,
`data/gui/source-all-tests-final.xml`, `data/gui/source-settings-ac74562cc7/`,
`data/gui/source-installed-72a58c9c31/`, and source-operation/source-agent reports
under `data/library/verification/`. Existing agent connections running the old
server code require a one-time reconnect after this upgrade.

## October 14 — Synty and CraftPix addition

Published 937 new model records, expanding membership from 964 to 1,901. Generated
882 views for 289 models and indexed all 882 images; 648 models retain unresolved
texture faults and partial geometry evidence. Godot-native resources are listed
separately as unsupported. Existing records, asset outputs, corrections, source
hashes and vectors are preserved. Details, corrected verification harness receipts,
preview review and storage measurements are in [the import report](new-packs-import.md).
The approved overnight description run finished and published 282 new descriptions
and vectors: 265 CraftPix, 15 Generic, and 2 Synty. Its 655 failures comprise the
648 texture/preview blockers plus 7 caption-validation failures. Final generation
is `v_41955003334a482e88d383e9f2c77be4`; preservation, database integrity, and live
description search passed. Storage is 7.22 GiB, within the approved budget.
The operation is complete with retained faults; repairs/retries require a separate
explicit request. New artistic/accuracy approval remains pending.

## Step 1 — completed

Date: October 11, 2026. Scope: repository/scaffold/contracts/environment only.
The first implementation action created `C:\BrunoOS\Local-Asset-Library` and ran
`git init` from `C:\BrunoOS`. Target did not previously exist. No applicable
`AGENTS.md` was found at the drive/workspace/project ancestors; no subagents used.

Copied `PROJECT.md` and all ten prompts into `docs/plan/` without edits. Added a
uv-managed editable Python package, pinned dependency lock, CLI, configuration,
read-only source API, resolved source/output boundaries, ignored local storage,
catalog contract, focused tests, README and environment report. Retained SQLite
FTS5 and NumPy; no deviation. No database or inventory was created.

### Actual commands and results

All project commands below ran from `C:\BrunoOS\Local-Asset-Library`, except the
initial creation/init. Independent tool probes were read only.

| Command / operation | Result |
| --- | --- |
| `New-Item -ItemType Directory -Path C:\BrunoOS\Local-Asset-Library`; `git init C:\BrunoOS\Local-Asset-Library` | Initialized empty repository |
| Read plan/prompt; inspect applicable ancestor guidance | Step 1 scope confirmed; no applicable AGENTS.md found |
| `Copy-Item` plan and prompts into `docs/plan/`; SHA-256 compare all originals/copies | 11 files copied; zero hash mismatches |
| `uv --version`; `python --version`; `git --version`; `Get-Command` tool probes | Versions/paths recorded in environment report |
| `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader` | RTX 5070, 12227 MiB, driver 616.64 |
| `nvidia-smi --query-compute-apps=process_name,used_memory --format=csv,noheader` | No rows; limited concurrency snapshot |
| `Get-CimInstance Win32_Processor`; selected CPU registry value | CIM denied; registry verified Core Ultra 7 265KF |
| Explicit Blender `--version`, Ollama `--version`, OpenCode `--version` | Blender 5.2.2 LTS, Ollama 0.33.3, OpenCode 1.18.29 |
| Selected local config fields; `GET http://127.0.0.1:11434/api/tags` and `/api/ps` | Two Qwen tags; no loaded Ollama models; no credentials printed |
| `uv python list --only-installed` | Managed CPython 3.13.15 discovered; sandbox cache/shim warnings recorded |
| `.\scripts\uv.ps1 sync --python 'C:\Users\backup pc\.local\share\uv\python\cpython-3.13-windows-x86_64-none\python.exe'` | Initial build denied at sandbox TEMP; retry after local TEMP/copy-mode settings passed. Eight packages installed, including local editable package, NumPy 2.3.4 and pytest 8.4.2 |
| `.\scripts\uv.ps1 run --locked local-assets check-config` | Passed with actual source root, read-only true, internal storage valid |
| `.\scripts\uv.ps1 run --locked local-assets doctor` | Passed: SQLite 3.53.1 FTS5 MATCH; NumPy 2.3.4 finite normalization; configured Blender exists |
| `.\scripts\uv.ps1 run --locked pytest --basetemp scratch/pytest` | Final result: 19 passed in 0.13s, zero skips/warnings; includes Windows junction escape checks |
| Module alternatives: `run --locked python -m pytest ...` and `python -m local_asset_library.cli doctor` | Executed inside sandbox; console launchers needed approved execution outside sandbox |
| `git check-ignore data/catalog.sqlite models/weights.bin cache/uv/sample logs/run.log scratch/tmp/sample .venv/Scripts/python.exe config.local.toml` | All seven paths ignored |
| `git status --short --untracked-files=all`; `git diff --cached --check`; staged name review | Reviewed before initial commit; only source/config/docs/tests/lockfile, no assets/catalog/weights/cache/environment |
| `git remote -v` | Empty; no remote configured |
| `git add` explicit scaffold files; `git commit -m "Initialize local asset library scaffold"` | Initial local scaffold commit; obtain its exact ID with `git log -1 --oneline` |

Test coverage: configuration schema/read-only requirement, fixed storage settings,
missing/overlapping source roots, legitimate read-only file access, valid internal
output, absolute/drive-relative/UNC/traversal/Windows device/stream path rejection,
unknown output areas, missing source files, and resolved junction escapes.
All source fixtures and test outputs stayed under ignored `scratch/`.

See [environment.md](environment.md) for evidence and limitations. Sandbox launcher
and link restrictions were resolved for validation by approved execution outside the
sandbox; no shared runtime changes were needed. Earlier deprecation warnings were
fixed before final tests. No model downloads, rendering, asset scanning, remote,
push, or changes to source packs, Play Shapes or Ollama/OpenCode configuration.

### Blockers and next stage

No blocker for step 2. GPU rendering, local vision inference, EmbeddingGemma 2
text/image support, model license/revision/device needs and human visual relevance
remain untested and belong to later stages. Technical checks do not imply owner
visual approval.

Next runnable stage: [step 2 — catalog and baseline](plan/prompts/02-catalog-and-baseline.md).
Start the next chat in this repository and use the versioned plan. Step 2 has not
been implemented: inventory, grouping, 40-asset pilot and keyword baseline remain
pending. No further stage is authorized by this run.

## Step 2 — completed

Date: October 11, 2026. Scope: read-only inventory, evidence-based logical catalog,
40-asset pilot and filename/keyword baseline. No subagents, rendering, models,
captions, embeddings or changes to other projects/installations.

Renamed the user-supplied `AGENTS.md.txt` to `AGENTS.md` on request. Applied its
scope and implementation-plan checkpoints; the user approved both. Also added
the requested duration/additional-disk estimates rule. The approved estimate was
30–60 minutes and 10–30 MB. Observed final scanner runtime: 61.203 seconds
(preceding equivalent catalog run: 81.052 seconds). Implementation/check time is
separate from scanner runtime. Generated `data/` totals 13,187,673 bytes, about
12.6 MiB; retained scratch fixtures total about 2.0 MiB at handoff. Existing
virtual environment/model caches were not replaced; no dependency was added.

### Step 1 revalidation and inspected starting state

Inspected the existing configuration boundary API, CLI, tests, package/lock,
catalog contract, progress and versioned scope/step 2 plan before selecting file
changes. Initial commit `d35ee8f` exists; no remote is configured. Actual doctor
output verifies CPython 3.13.15's SQLite 3.53.1 FTS5 CREATE/INSERT/MATCH, NumPy
2.3.4 and the configured Blender executable. No Blender process was started.

The first test rerun in the sandbox produced 18 passes and one failure because
creating the Windows junction fixture was denied. The permitted rerun under
`scratch/pytest-step1-verified` passed all 19 tests in 0.22 seconds. Step 1 was
therefore confirmed by execution, not its prior progress claim alone. Some
sandbox uv invocations emit `Failed to find real location` for the managed Python
path, but exit successfully using the project environment. No shared interpreter
or neighboring installation was changed to suppress this warning.

### Implementation and actual catalog result

Added `catalog.py`, extended the existing CLI, added 18 catalog tests and the
reproducible real-catalog check utility. The SQLite database has schema version 1,
identity uniqueness, file foreign keys, full inventory rows, versioned structured
records and FTS5. Every scan probes the actual SQLite FTS5 runtime; there was no
compatibility problem and no fallback. Catalog publication and the keyword index
are one transaction; a scan refuses to replace populated later-stage fields or
owner overlays.

Measured inventory: 4,938 files, eight packs, 883 logical records, 2,929 model
files and 2,046 alternate files. No unsupported candidate extension or
unclassified file was found. Inventory includes materials, 13 textures, 1,067
individual views, nine pack contact sheets, three sample images and local
license/source evidence. Furniture has Side and four Isometric views per asset,
despite having no `Previews` directory. None is claimed as a new render or visual
validation. [Catalog summary](catalog-summary.md) contains counts by pack.

Eight ZIPs were excluded after all 4,929 non-directory members matched extracted
paths by size and SHA-256, without extraction. Grouping requires identical
complete relative-stem manifests in recognized sibling format folders; namespace
segments below the format folder remain significant. Recorded layout evidence is
not geometry verification. 24 repeated-name cases involving 48 records remain
distinct for review. Variant relationships are filename suggestions, never merged.

Parsed 1,617 dependency references with per-file extraction evidence. No
missing/rejected reference or text parser issue was found. FBX/Blender dependency
inspection remains pending for 1,259 files. Supplied CC0 evidence exists in five
Kenney packs and the Quaternius nature pack; food/interior Quaternius packs have
only the separately labeled collection note and source links, without bundled
author-license files. No legal interpretation or online verification was made.

### Commands, actual results and evidence

All commands ran in `C:\BrunoOS\Local-Asset-Library`. Commands below use the existing
isolated wrapper. The module CLI was used to avoid restricted console launchers.

| Command / operation | Actual result / evidence |
| --- | --- |
| `git log -2 --oneline`; `git remote -v`; inspect config/code/plan and source layout | Scaffold commit exists; no remote; eight extracted packs plus ZIP folder |
| `.\scripts\uv.ps1 run --locked python -m local_asset_library.cli doctor` | SQLite 3.53.1 FTS5 true; NumPy finite normalization true; Blender executable exists |
| `.\scripts\uv.ps1 run --locked python -m pytest --basetemp scratch/pytest-step1-verified` (permitted junction creation) | 19 passed in 0.22s |
| `.\scripts\uv.ps1 run --locked python -m local_asset_library.cli scan` | Full real inventory, verified duplicate ZIPs, matching before/after source fingerprints |
| Final `scan` output saved to `data/reports/scan-run-final.json` | 883 records; 61.203s; consecutive equivalent run reproduced the logical fingerprint |
| `.\scripts\uv.ps1 run --locked python -m pytest --basetemp scratch/pytest-step2-checked` (permitted junction creation) | 37 passed in 1.13s, zero skips; 19 existing plus 18 new tests |
| `.\scripts\uv.ps1 run --locked python -m local_asset_library.cli pilot` twice; `Get-FileHash data/pilot/selection-manifest.json -Algorithm SHA256` | 40 distinct assets, five per pack; 130 model files, six formats, 25 with supplied views, 15 without; both manifest hashes identical |
| `search 'apple'`; `search 'sedan sports'`; `search 'chair rounded'`; `search 'road straight barrier'`; `search 'BirchTree Snow'`; `search 'spaceship laser submarine'` | Saved real results in `data/reports/search-*.json`; details below |
| `.\scripts\uv.ps1 run --locked python scripts/check_catalog.py --previous-logical-fingerprint a16245145b67e92b7a50e42c402c0d62412481cc4143f28853ec8935a24390b3` | SQLite integrity `ok`, zero foreign-key issues, 883 unique FTS rows; pilot paths and all returned paths valid; character cap verified; `data/evidence/catalog-checks.json` |
| `.\scripts\uv.ps1 run --locked python -m local_asset_library.cli verify-source` | 4,938 before/after entries; zero changed paths; `data/evidence/source-verification.json` |
| `git diff --check`; explicit staging; `git diff --cached --check`; staged name review; local commit | Only code, tests, instructions, rationale and documentation; no generated catalog, packs, caches, assets or weights; no push |

An attempted one-off diagnostic via piped stdin through the PowerShell wrapper
did not forward the program to Python and entered its console, producing invalid
handle errors. It was interrupted. The same checks were saved in
`scripts/check_catalog.py` and passed via ordinary script invocation. A PowerShell
display-only pipeline syntax error was also corrected; neither failure altered
the catalog or sources. They are not counted as passing checks.

Search uses literal AND terms and splits camel-case names. Actual demonstrations:

| Query | Results | Serialized characters | Estimated tokens (characters/4) |
| --- | --- | ---: | ---: |
| `apple` | `apple`, `apple-half`, `Apple`, `Apple_Green`, four separate logical IDs | 3,161 | 791 |
| `sedan sports` | `sedan-sports` | 929 | 233 |
| `chair rounded` | `chairRounded`, five available formats | 1,302 | 326 |
| `road straight barrier` | three separately retained barrier road variants | 2,658 | 665 |
| `BirchTree Snow` | five separate snow-tree variants | 4,336 | 1,084 |
| `spaceship laser submarine` | zero candidates | 225 | 57 |

These are filename retrieval demonstrations, not human relevance judgments or a
semantic benchmark. Character counts include output metadata, excluding trailing
newline and transport overhead. The labeled token estimate is a heuristic, not a
measured model-token count. Results are capped at 6,000 characters with explicit
truncation; none of these six examples was truncated.

### Reproducibility and source immutability

Source fingerprint (SHA-256 over sorted source-relative path/hash/size inventory):
`4dbf39d53556d225c9aac13330a9cd91a522dbd1ceae8e195e86184389a9095c`.
Final logical-record fingerprint:
`a16245145b67e92b7a50e42c402c0d62412481cc4143f28853ec8935a24390b3`.
Pilot manifest SHA-256 from both runs:
`844d495098a7442e481ac2a3b703f312f38804460d15d353e0a9b116f0f75459`.

`data/evidence/source-baseline.json` records all source paths, content hashes,
sizes and modification times, including ZIPs, models, dependencies and pictures.
`scan-immutability.json` records matching complete inventories before publishing;
`source-verification.json` independently confirms zero changes after pilot/search
work. These checks cover all traversed file bytes and size/mtime, not access times,
ownership metadata or later external changes. Directory links are visible
exclusions, never traversed. No source file was opened for writing, copied,
imported or executed. Fixtures and outputs stayed within ignored project storage.

The reproducible selection and each rationale are versioned in
`docs/pilot-selection.json`. Resolved pilot manifest:
`C:\BrunoOS\Local-Asset-Library\data\pilot\selection-manifest.json`.
`data/evidence/pilot-reproducibility.json` records the two matching byte hashes.
The generated catalog and manifest stay ignored; reproduce them with `scan` and
`pilot`. The database's run timestamp is intentionally separate from deterministic
IDs, logical-record hashes and manifest bytes.

### Unresolved cases and next runnable step

Step 2 has no blocking runtime failure. The 24 name collisions, unverified geometry
equivalence, filename variant suggestions, binary dependencies, two absent bundled
author-license files and 376 missing individual previews remain explicit. No
bounds, counts, physical units, animations, materials or artistic suitability are
claimed as inspected. Search checks current path existence but does not hash files
on every query; content staleness needs verification/rescan until step 8.

Next: execute [step 3 — inspect and render](plan/prompts/03-inspect-and-render.md)
from this repository, after its scope/plan approvals with duration and disk
estimates. Use the existing catalog and 40-asset manifest. Validate representative
GLB, OBJ/MTL, FBX and Blender pilot cases first; disable embedded-script execution,
keep output under project storage, verify materials/framing with image tools and
retain source/dependency hash evidence. Then process the remaining pilot with
explicit failure states. Stop before captions. No step 3 work was started here.

## Step 3 — completed

Date: October 11, 2026. Scope and implementation plan were explicitly approved
before implementation. Read applicable AGENTS.md, progress, the catalog contract,
visual inspection policy and step 3 plan/prompt; inspected existing code first.
Reused the existing SQLite catalog and exact 40-asset pilot. No subagents, source
edits, Play Shapes changes, system installation changes, model downloads,
descriptions or embeddings. The later user request made fault handling permanent:
mark every kind of fault with evidence and move on; do not automatically retry
unchanged faulty items. This is recorded in AGENTS.md and implemented in the runner.

Approved planning estimate: 60–120 minutes and 100–400 MB additional storage,
assuming an installed Blender. Reused the actual configured Blender executable
at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`: **5.2.2 LTS**,
build hash `d13f752e3b9c`, September 15, 2026. No portable download was needed.
At the final measurement, inspection outputs plus Blender user/Python cache
storage occupied 35,991,997 bytes (34.32 MiB), including earlier calibration runs
and diagnostics. This is a measured subset, not a claim about the entire project;
fixtures/evidence add a few MB. No model storage was added, within the 20 GiB
generated-data budget.

### Implementation and measured results

Added background inspector/renderer, deterministic framing, bounded sequential
jobs, runtime discovery, project-local Blender resources, source/dependency hash
checks, validated result reuse, technical review receipts, and review sheets.
The CLI now supports `inspect` and `review-sheet`; search handles both supplied
and generated preview roots. Catalog/owner overlays and original selection are
retained. Metadata belongs only to the selected source, never all alternate files.

**40/40 primary files produced metadata and usable derived views; 0 final job
failures. Seven source assets remain explicitly faulty.** Chosen formats: 23 GLB,
15 OBJ/MTL, one FBX and one Blender. Rendered 124 images at 640×640: 40 front,
40 side, 40 three-quarter, four top views for flat roads/Pizza_Burned. Selection
reasons and fault flags: `data/inspection/processed-manifest.json`. All 883 catalog
records still exist; only the 40 pilot records have technical measurements.
Descriptions remain null and embeddings empty for all records.

Real measured examples (evaluated instance vertices / triangles): GLB sedan
3,184 / 2,032 (five mesh objects); OBJ sedan-sports 1,255 / 2,087 (one); FBX apple
71 / 130 (one); Blender BirchTree_1 866 / 1,704 (one). Each has local bounds,
transforms, world bounds, imported units, used materials, texture evidence,
armature/action counts and format limitations. Real-world size and author front
remain unknown; actions are enumerated, not behaviorally tested.

CPU Cycles, 128 samples, fixed seed, CPU denoising, neutral three-light setup and
background, shared orthographic scale and 16% margin. Settings/camera coordinates
are stored with images. Empty/off-frame alpha checks, missing required textures,
timeouts and unsupported imports produce explicit failure states. Script autoexec
is disabled by command flags, preferences and `use_scripts=False` for Blender
files. A fixture containing executable embedded text did not write its marker.
Blender resource paths were checked inside the project. No successful exit alone
is accepted as visual validation.

### Actual commands and timings

Commands below ran from `C:\BrunoOS\Local-Asset-Library`. Python commands use
`.\scripts\uv.ps1 run --locked python` to keep project environment/cache settings.

| Command / check | Actual result |
| --- | --- |
| Installed Blender `--version`, `--help`, import-operator probe | Version/build captured; GLB, OBJ/MTL, FBX and Blender imports usable; offline/autoexec/resource flags verified |
| `python -m local_asset_library.cli inspect --phase representatives --resolution 640 --timeout 180` | Final code: four cases, 12 views, zero job failures, 22.997 s |
| `python -m local_asset_library.cli review-sheet --phase representatives` | Sheet and identity grid map saved; all twelve final images opened with image tools |
| `python scripts/record_image_review.py representatives --observations ...` | Four current stage fingerprints and image hashes recorded as technically reviewed |
| `python -m local_asset_library.cli inspect --phase pilot --resolution 640 --timeout 180` | Final render batch: 40 complete, four representative caches, 124 views, zero job failures, 202.500 s |
| Same pilot command for catalog fault flags / cache validation | 40 cached results, no new render jobs, 1.760 s; final render report retained separately |
| `python -m local_asset_library.cli review-sheet --phase pilot` | Final 40-asset overview opened with image tools; road top and rock diagnostics also viewed |
| `python scripts/record_image_review.py pilot --observations ...` | Technical receipt saved with actual observations; owner artistic approval pending |
| `python -m pytest --basetemp scratch/pytest-step3-final-policy` | **60 passed in 11.68 s**, including three real Blender integration tests |
| `python -m pytest tests/test_inspection.py --basetemp scratch/pytest-step3-fault-policy` | 19 passed in 0.30 s; unchanged faults retained and explicit retry opt-in tested |
| `python scripts/check_inspection.py` | 40 identities/metadata, 124 hashes/foreground checks, 179 source files, SQLite integrity/FKs, 883 FTS rows, unchanged selection, empty descriptions/vectors verified |
| `python -m local_asset_library.cli verify-source` | Full 4,938-file SHA-256/size/mtime comparison: zero changed paths |
| `git diff --check`; staged diff/check; checked local commit | Required before committing; no source packs or generated artifacts staged; no push |

The staged whitespace check found one extra blank line at the end of the new
framing file. It was removed; the source fingerprint changed, so representatives
and the pilot were regenerated and re-reviewed with the final code. The final
cached run retained all 40 results and seven fault flags without rendering again.

Initial focused fixtures and earlier full suites passed before the last fault-rule
change; the 60-test final suite supersedes those results. Existing Windows junction
fixtures require the permitted elevated test invocation; a sandbox run failed to
create its fixture junction, then passed with the required permissions. After the
usage interruption, the console-script invocation reported `uv trampoline failed
to canonicalize script path`; invoking `python -m pytest` passed. The known managed
Python path warning did not stop module commands. Neither issue altered sources.
A checker initially assumed before/after lists had the same number of paths;
the extra FBX texture was accounted for using its original inventory hash, and
the corrected check passed. Failed attempts are not counted as passing checks.

### Faults, image evidence and boundaries

Initial EEVEE jobs crashed in NVIDIA/OpenGL with exit `3221225480`; switching to
CPU Cycles solved the actual local problem without driver/system changes. Initial
bright/noisy calibration images were replaced with corrected neutral lighting,
128 samples and denoising. All four representative formats were re-viewed before
the remaining pilot. Blender extension/cache writes were redirected into project
storage; no neighboring installation was modified.

Flagged overlapping-face counts: ambulance 58, traffic-light 22, burger 78,
burger-cheese-double 156, kitchenFridge 30, rocks-high 156. The rock discrepancy
against its supplied preview was checked with an emission/material diagnostic and
a shadow-disabled diagnostic. Derived renders record disabling shadow rays only
for exact duplicate-face meshes; geometry/materials were not repaired. BirchTree_1
has an unused missing historical `Texture.png`; its active four color materials
do not depend on it. These **seven fault flags remain visible even when a preview
is usable**. No further individual repair is needed. Every fault type follows the
same rule: retain evidence and partial results, move on, and require an explicit
retry request (`--retry-faults`) for unchanged faulty items.

The twelve representative views were inspected individually through their sheet.
The pilot review covers all 40 three-quarter images plus automated checks for
other views, not a claim that every pixel of all 124 views was human-reviewed.
Supplied thumbnails remain baseline evidence. Owner artistic approval remains
pending. Review paths:

- `data/inspection/review/representatives.png` and `representatives-review.json`;
- `data/inspection/review/pilot.png`, `pilot-grid-map.json`, `pilot-review.json`;
- `data/inspection/review/rocks-diagnostic/probe.log`;
- `data/inspection/pilot-final-render-report.json` (202.500-second render batch),
  `pilot-report.json` (latest validated results) and `processed-manifest.json`;
- `data/evidence/step3-catalog-check.json` (actual metadata/searches/faults).

Before/after evidence is saved as `step3-representatives-before/after.json` and
`step3-pilot-before/after.json` under `data/evidence/`. The 178 initially known
pilot source/dependency files match; one additional FBX colormap is verified
against the original catalog inventory, for 179 total. Every imported source and
loaded source texture has per-job before/after hashes. Full independent evidence:
`data/evidence/step3-full-source-verification.json`. No source byte/size/mtime
changes among all 4,938 source files; access times/directory metadata are not
covered. Original pilot hash remains
`844d495098a7442e481ac2a3b703f312f38804460d15d353e0a9b116f0f75459`.
Source fingerprint remains
`4dbf39d53556d225c9aac13330a9cd91a522dbd1ceae8e195e86184389a9095c`.

Actual keyword checks after inspection: `Apple Green` retrieves Apple_Green with
three available formats and a generated project preview; `BirchTree Snow`
retrieves five separate variants, of which only the selected Snow_1 has generated
views; `chair rounded` retains its five available formats and supplied baseline
preview. Search stays compact and never treats the views as separate assets.

### Remaining limitations and next step

DAE alternates are unsupported by this verified runtime and uninspected. Formats
not selected for an asset retain unknown features; packed Blender image state
does not prove original FBX embedding. Physical size, author axes, animation
behavior, alternate equivalence, grouping ambiguities and license unknowns remain
explicit. The 843 non-pilot logical assets are still uninspected. The permanent
fault rule and step 3 completion do not authorize production asset repairs.

Pilot manifest: `C:\BrunoOS\Local-Asset-Library\data\pilot\selection-manifest.json`.
Actual inspection choices/faults:
`C:\BrunoOS\Local-Asset-Library\data\inspection\processed-manifest.json`.
See [inspection report](inspection-report.md) for images and actual measurements.
Next: [step 4 — local visual descriptions](plan/prompts/04-local-visual-descriptions.md).
Confirm its scope/plan with duration and disk estimates; verify one small local
vision model's official license, exact revision, image input, device support and
remaining budget before download. Calibrate on approximately ten varied pilot
assets with actual images before the 40-asset caption batch. No description
generation, embedding or full-library processing was started here.

## Step 4 — technical implementation completed; caption quality limited

Date: October 11, 2026. Scope and implementation plan were explicitly approved
before implementation under AGENTS.md. The approved estimate was 60–100 minutes
and 10–14 GiB additional disk. Only the existing 40-asset pilot was processed.
No subagents, cloud caption API, source/Play Shapes edits, shared runtime upgrade,
embedding work or full-library processing. Owner artistic suitability and final
caption approval remain **pending**.

Read the required model roles, visual inspection policy, catalog contract, step 4
and progress. Selected one model through current official Qwen, Hugging Face
Transformers and PyTorch documentation: **Qwen3-VL-2B-Instruct**, Apache-2.0,
revision `89644892e4d85e24eaac8bacfd4f463576704203`. Verified image/multi-image
support, exact-revision file metadata and device compatibility before transfer.
Before download: no model weights, generated data 49,432,673 bytes, 94.02 GiB
free on C:. A real CUDA BF16 matrix multiplication passed with PyTorch's sm_120
support on the RTX 5070. The one model download totaled **4,266,640,306 bytes**
(3.97 GiB), inside the 8 GiB model budget. No speculative model alternatives
were downloaded. Details and primary links: [caption report](caption-report.md),
[pre-download selection](caption-model.json).

Installed a separate `.venv-caption/` with its own pinned dependency lock:
PyTorch 2.10.0+cu128, torchvision 0.25.0+cu128, Transformers 4.57.6,
Pillow 12.1.0 and isolated caches/model directory. CPython remains 3.13.15.
The base package environment/lock and Ollama/OpenCode were not upgraded.
Inference is offline, local-files-only and disables remote model code. Exact
model file SHA-256 values are verified before loading.

### Implementation and real result

Added a local caption backend, schema validator, one changed corrective retry,
explicit failures, provenance, ten-asset calibration gate and pilot-only runner.
Real generated front/side/three-quarter views are required; all existing top
views are also passed. No filenames, pack names or measured metadata enter the
model prompt. PIL decodes and composites actual image pixels; the processor
must produce finite pixel tensors, image tokens and one grid per input.
Suggested uses are separate. Inspector facts, grouping, license and source
faults are preserved. UTF-8 canonical raw output is retained.

Each caption records revision/file hashes, backend/device, versions/lock hash,
prompt version/hash, view hashes, preprocessing, generation parameters, timing,
tokens, resource measurements, raw attempts and AI/owner review states. Owner
correction files are separate, editable overlays that regeneration preserves
byte-for-byte; effective captions merge them without overwriting raw observations.
Review refresh loads no model. Invalid corrections remain visible rather than
silently replacing measured facts or creating an AI success from failure.

Smoke test distinguished the red-orange car from the red apple with leaf/stem
using six real images, with 588 image tokens each. Responses took 2.127/0.873 s
after 2.808 s loading. AI viewed all 32 calibration input views alongside text.
v1 took 95.155 s; evidence justified v2. Greedy v2 took 107.658 s and remained
repetitive. Preserved it, then used final v2 with seed 0, sampling temperature
0.7/top-p 0.8/top-k 20 and repetition penalty 1.1. Final calibration took
140.767 s, producing ten schema-valid captions with two corrective generations.
No additional caption model was installed. Raw earlier results are retained.

The 40-asset batch took **416.469 s**, reusing ten calibration outputs and making
thirty new jobs. **39 schema-valid captions; one explicit failure** on
road-crossroad after two invalid responses. No fallback caption was invented.
All **124 real input views** were consumed and hash-verified. Final forty assets
include 53 inference attempts totaling **552.784 s** including calibration;
13 assets needed the bounded corrective response. Per-attempt median/p95:
**10.416/12.905 s**. Captions are 60–103 words; input tokens 1,016–1,254 and image
tokens 588–784. Generation settings/token grids are recorded, not estimated.

AI reviewed all 124 input views in ten mosaics alongside the structured text.
**30 of the 39 valid captions have faulty visual claims** recorded separately
from processing success, including wrong bridge identities and unsupported part
counts/material interpretations. These captions are provisional; the model is
technically runnable but unreliable as an authoritative captioner of this pilot.
No source geometry or caption fault was silently repaired. Bruno's final caption
review and artistic suitability are unapproved for every asset. Review artifacts:

- `data/captions/review/pilot-v2.html`: full-size real-view links, captions,
  structured attributes, suggestions, prominent fault flags, correction links,
  measured facts and provenance;
- `docs/caption-calibration-v1-review.json`, `caption-calibration-v2-review.json`,
  `caption-pilot-review.json`: versioned AI review observations;
- `data/captions/calibration-review.json`, `pilot-v2-review.json`: bound technical
  receipts; `data/captions/corrections/`: forty editable pending owner overlays;
- `data/captions/pilot-v2-report.json`, `pilot-v2-resources.json`, `measurements.json`.

### Commands and checks

All commands ran in this repository. Vision commands use
`.\scripts\caption-runtime.ps1 run --locked --project runtime/caption python`;
base checks use `.\scripts\uv.ps1 run --locked python`.

| Operation | Actual result |
| --- | --- |
| `caption-runtime.ps1 sync --project runtime/caption --python <existing managed Python 3.13>` | Separate pinned runtime installed; no shared installation changes |
| Official exact-revision metadata + `scripts/prepare_caption_model.py` | License/size/budget/kernel checked before download; ten files transferred; initial hash helper failed after transfer |
| `scripts/prepare_caption_model.py --verify-only` | Already downloaded files verified by size/SHA-256, including publisher LFS weight hash; 2.294 s; no second model download |
| `scripts/caption_pilot.py smoke` | Actual car/apple image comprehension, response/grid/token/resource evidence |
| `scripts/check_captions.py --before` | Original 883-record noncaption-field baseline saved before generation |
| Calibration v1, greedy v2, final sampled v2 | Actual timings above; same selected model, revised prompt; preceding outputs preserved |
| `scripts/caption_review_images.py`; image tools; `scripts/record_caption_review.py ... --notes ...` | Actual calibration and pilot images/text viewed; hash-bound AI receipts, owner pending |
| `scripts/caption_pilot.py pilot --prompt-version v2` | 39 complete, one failed, ten caches, 124 actual input views |
| `scripts/caption_pilot.py review --prompt-version v2` | Model-free owner overlay publication and review refresh; 30 fault banners |
| `python -m pytest tests/test_captions.py --basetemp scratch/pytest-caption-final-review` | **23 passed in 0.14 s**; malformed/duplicate JSON, wrong types, technical/use leakage, uncertainty contradiction, bounded changed retry, no retry on runtime faults, input hashes/boundaries, measured facts/correction preservation, stale calibration, Unicode and visible/escaped review faults |
| `python tests/caption_runtime_checks.py` in isolated runtime | Real PIL RGBA/gray/RGB/resize verified; empty, escape, mismatch and corrupt image rejected |
| Full test run `python -m pytest --basetemp scratch/pytest-step4-all` before final two review tests | 79 passed, two existing fixture junctions denied by sandbox, 20.89 s |
| Permitted focused Windows boundary-test rerun | Both previously blocked junction tests passed in 0.08 s; final new caption tests separately pass. All 60 preexisting tests and 23 new tests validated across these runs |
| `scripts/check_captions.py` | 883 noncaption records preserved, 39 complete/one failed, 124 hashes/tensors, canonical UTF-8 text, 843 nonpilot pending, SQLite `ok`, zero FK errors, 883 FTS rows and no embeddings |
| `local_asset_library.cli verify-source` after pilot | All 4,938 source files: zero changed SHA-256/size/mtime paths; `data/evidence/step4-full-source-verification.json` |
| `scripts/measure_captions.py` | Actual timing/token/RSS/CUDA/file-byte report, budgets remain positive |
| Whitespace/staged file review and local commit | Only code, runtime lock, prompts, tests and documentation; no generated data/weights/assets or push |

Initial test code used the catalog's stream hash helper with a path; fixed the
adapter helper and verified the downloaded model without downloading again.
Windows-default text decoding caused a review-helper failure and mojibake in a
cached record; helpers now explicitly read UTF-8, restore canonical original
responses, and the checker verifies exact preservation. An initial documentation
patch failed its context check and was reapplied correctly. These attempts are
not counted as passing checks. A one-off review-link check failed from shell
quoting and was replaced by a saved checker; it verified 124 images, 288 existing
local references and 30 visible fault banners. The existing managed-Python path warning remains
nonfatal; no shared interpreter was changed to suppress it.

### Actual resources and remaining work

Pilot peak CUDA allocated/reserved: **4.42/4.84 GiB**; sampled process peak RSS:
**4.54 GiB**, 0.25-second sampling. These are process measurements, not total
machine memory. Final managed file snapshot: **13.00 GiB** including weights,
runtime/cache copies and data, about **12.83 GiB additional**. Remaining model
download budget **4.03 GiB**; remaining conservative generated project allowance
**10.97 GiB**. Exact bytes and accounting limitations are in the caption report.

Step 4 code/technical pilot is complete with visible schema and visual failures.
No further automatic retry or model download is needed. Bruno owns corrections,
final caption review and artistic approval. A later choice of a better caption
model or broader quality evaluation needs a separately authorized scope/budget.
Next numbered stage is [step 5](plan/prompts/05-embeddings-and-search.md), requiring
its own scope/plan approval and actual embedding-model capability checks. No
embedding, full-library processing, remote, push or publication occurred here.

## Step 5 — technical implementation completed; relevance unapproved

Date: October 11, 2026. Bruno approved the separate scope and implementation-plan
checkpoints before edits. Only step 5 implemented. Estimated 60–100 minutes and
7–9 GiB additional storage; measured additional managed files **6.34 GiB** against
the step 4 final snapshot. No subagents, fine-tuning, source edits, caption repair,
neighboring installation changes, benchmark verdict, full indexing or publication.

### Official selection and isolated runtime

Verified current Google [model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2),
[text guide](https://ai.google.dev/gemma/docs/embeddinggemma/inference-embeddinggemma-with-sentence-transformers),
[image guide](https://ai.google.dev/gemma/docs/embeddinggemma/multimodal-embeddinggemma-with-sentence-transformers)
and [publisher model](https://huggingface.co/google/embeddinggemma-2) before download.
Google pages were updated October 6, 2026. Publisher metadata: Apache-2.0, ungated,
exact revision **914f7f89142e33e77833254d9c9b90c3cef7303b**. Selected original
checkpoint; no alternative backend/model speculation. One download: **1,525,787,092
bytes**, thirteen required files, **10.488 s** including verification. Publisher
LFS SHA-256 values and sizes matched; all other runtime files also hash-recorded.
Checkpoint includes audio weights, but only text/vision are loaded. Actual loaded
parameters **438,760,448**, audio config absent and vision present.

Separate `.venv-embedding/` and `runtime/embedding/uv.lock`, CPython **3.13.15**,
SentenceTransformers **6.1.0**, Transformers **5.19.0**, PyTorch **2.10.0+cu128**,
torchvision **0.25.0+cu128**, Pillow **12.1.0**, NumPy **2.3.4**, huggingface-hub
**1.33.0**, psutil **7.2.2**. Base/caption environments and locks unchanged.
Reused only project-local dependency downloads in `cache/uv-caption`; packages
installed into the new environment. A real RTX 5070 CUDA **12.8**, capability
**12.0**, BF16 multiplication passed before weights were transferred. No competing
heavy GPU process was listed before installation or at final verification; none
needed unloading. Models leave GPU memory when their command process exits.

Inference: CUDA BF16, SDPA, TF32 disabled, 768 dimensions, full FP32 normalized
stored vectors; no FP16 or silent hardware/precision fallback. Explicit documented
search/document prefixes and unprefixed image dictionaries. Actual input token
counts/pixel tensor shapes recorded. Local offline files only, no remote model
code/cloud inference. Complete semantic/persistence/filter contract is in
[embedding-contract.md](embedding-contract.md); pinned selection in
[embedding-model.json](embedding-model.json), small versioned actual measurement
summary in [embedding-evidence.json](embedding-evidence.json).

### Actual inference, indexing and retrieval

Capability check consumed real car/apple three-quarter PNGs and real search and
document text. Every output finite, nonzero, normalized and 768-dimensional.
Pixel tensors `[1,2520,768]`, 260 actual processed image input tokens. Text/image
similarity matrix (car/apple queries against car/apple images):
`[[0.796632,0.649857],[0.595636,0.759136]]`; image self-similarities approximately
one, distinct image/text vectors. This proves functioning modalities, not a
benchmark verdict. Standalone runtime checks prove RGB/grayscale/RGBA compositing,
different actual pixels producing different vectors, corrupt image rejection,
over-context text rejection before silent truncation and audio-disabled loading.

Pilot index: **208 finite normalized vectors** for **40 logical assets**:
**39 observation-description documents** and **169 individual supplied/rendered
views**. Norm range **0.9999999404–1.0000001192**. Suggested uses, names/pack text
and technical metadata excluded from description embeddings. Thirty caption visual
faults and all pending owner reviews retained. Road-crossroad's failed caption
remains a visible failed description job, with no invented vector; usable views
remain indexed. No new caption inference or automatic repair/retry performed.

Initial indexing took **22.813 s**, with 204 successes and five precondition
failures. Read-only evidence showed BirchTree_1's missing texture was an inspected
inactive datablock (`required_for_render: false`), so the availability rule was
corrected to preserve usable partial assets while exposing that source fault.
Four new jobs then completed during a **2.225 s** publication; other vectors reused.
The original conservative exclusion report is retained locally. Final unchanged
reindex **1.296 s**, 208 reused successes, one retained failed caption, **no inference**.
Missing/stale required dependencies or recorded source alternates still exclude
the logical asset; inactive missing dependency remains unresolved in detail.

Vectors/jobs publish atomically to separate `data/embeddings/index.sqlite`;
catalog schema/records and original FTS baseline untouched. Every vector binds
model/runtime/prompt/precision/preprocessing/dimension/normalization fingerprints,
input/source hashes, modality/role and vector checksum. Search validates compatible
contracts, current inputs and source/dependency bytes. Corrupt persisted output
or query inference failure is an error; no fallback list or fabricated vectors.
Unchanged failed inference jobs are retained; changed inputs/contracts are explicit
new jobs. Failure statuses/evidence stay separate from usable vector rows.

Separate pilot filename/keyword, observation-semantic, text-to-image and combined
modes plus proven reference-image mode. Normalized exact dot products, maximum
view score per logical asset and reciprocal rank fusion (`k=60`); duplicate views
or formats never take multiple shortlist positions. Pack/format filters use catalog
facts. Triangle/armature filters require the inspected export and exclude unknown
or alternate-format claims. Complete channel rankings, scores, eligible rankings,
stale exclusions and timings are saved separately from compact responses.
Legacy no-mode search and raw `get` remain unchanged; new `detail` resolves selected
source plus all known dependency paths, with unresolved optional faults retained.

### Real query demonstrations and measurements

Standard default five-result responses contain 180-character observation excerpts,
formats, preview reference, availability, channel contributions and fault/review
flags. Hard cap 6,000 serialized characters; token estimates use ceil(characters/4),
not measured model tokenization. Image payloads/transport/schema overhead excluded.

| Actual demonstration | First result / behavior | Warm s | Characters | Estimated tokens |
| --- | --- | ---: | ---: | ---: |
| keyword `apple` | four separate apple/half/Apple/green IDs | 0.573 | 2,825 | 707 |
| description `a boxy orange-red car with wheels` | sedan | 1.060 | 3,353 | 839 |
| image `a red apple with a green leaf` | apple | 1.121 | 3,441 | 861 |
| combined `a chair with a curved back and flat seat` | chairRounded | 1.464 | 3,585 | 897 |
| reference: existing apple three-quarter view | apple, then other distinct assets | 1.122 | 3,510 | 878 |
| combined car, pack/GLB/<=3000 triangles/no armature | four filter-valid assets | 0.336 | 2,838 | 710 |
| keyword `spaceship laser submarine` | no_match, empty | 0.564 | 459 | 115 |
| combined `a realistic purple dragon breathing fire` | five **weak_unvalidated** candidates | 1.456 | 3,395 | 849 |
| same dragon, image mode, explicit evaluation floor 0.95 | no_match, empty; original channel ranking retained | 1.053 | 499 | 125 |

The 0.95 floor only demonstrates an explicit evaluation control, not a chosen
universal threshold. BM25, cosine and RRF scores are not probabilities. Reference
demonstration is self-retrieval of an indexed view, not a held-out quality test.
Candidate ordering above is observational evidence, not human relevance judgment.
No Hit@5/p95 verdict, held-out benchmark or expansion gate evaluated.

Separate five fresh Python processes measured model-cold searches, then one warm
repeat per process. OS filesystem cache was not purged. Model initialization
includes imports/hash verification/loading; first query is timed separately.
Whole-process times include **both** queries and are not single-query latencies.

| Mode | Model init s | First query s | Warm query s | Warm characters |
| --- | ---: | ---: | ---: | ---: |
| keyword | 0 | 0.576 | 0.565 | 2,825 |
| description | 11.549 | 1.790 | 1.082 | 3,540 |
| image | 12.500 | 1.703 | 1.233 | 3,441 |
| combined | 12.943 | 2.090 | 1.635 | 3,574 |
| reference | 12.804 | 1.832 | 1.294 | 3,510 |

The initial post-install capability process took **41.063 s** to initialize; the
final repeated capability process took **13.308 s**. Startup varies; sampled
timings are not guarantees. Peak CUDA allocated about **0.91 GiB**, reserved about
**0.95 GiB**, process RSS about **2.13 GiB**. These are process snapshots/allocator
peaks, not total machine memory or a sampled OS peak RSS measurement.

### Commands, checks and preserved evidence

Commands ran in `C:\BrunoOS\Local-Asset-Library`. Embedding commands use
`.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python`;
base commands use `.\scripts\uv.ps1 run --locked python`.

| Operation | Actual outcome / evidence |
| --- | --- |
| isolated runtime sync with existing managed CPython | locked 45 installed packages; no shared runtime upgrade |
| `scripts/prepare_embedding_model.py` | CUDA kernel, exact revision/license/byte-budget preflight and thirteen verified files; `data/embeddings/model-preflight.json`, `model-download.json` |
| `scripts/embedding_capability.py` | real text, document and image vectors/tensors; `data/embeddings/capability.json` |
| `scripts/embedding_demo.py` | all channels, reference/filter/negative queries, exact sizes/timings and reindex reuse; `demonstrations.json`, `demos/*.json`, `demo-detail.json` |
| `scripts/measure_embedding_search.py` | five fresh processes and warm repeats; `cold-warm-timings.json`, `cold/*.json` |
| `python -m pytest --basetemp scratch/pytest-step5-all` | **106 passed**, two existing Windows junction fixtures denied by sandbox, 70.43 s |
| permitted focused rerun of both existing junction boundary tests | **2 passed in 0.07 s**, no skipped failures |
| final `pytest tests/test_retrieval.py` after live overlay-status fix | **25 passed in 54.37 s** |
| `tests/embedding_runtime_checks.py` in pinned embedding environment | actual PIL/model/context/pixel checks passed; `runtime-checks.json` |
| `scripts/check_captions.py` | 883 records and all noncaption fields preserved, 39/one captions, 124 canonical image hashes, 843 untouched nonpilot records, SQLite/FK/FTS valid |
| `scripts/check_embeddings.py` | all 208 stored vectors/contracts/checksums/unit norms valid, all demo rankings unique/pilot-only, shortlisted sources/dependencies resolve, size/budgets pass; `verification.json` |
| baseline keyword CLI, explicit keyword/combined CLI and `detail --format fbx` | actual outputs and independent ranking files under `data/embeddings/cli-*` |
| `local_asset_library.cli verify-source` | all **4,938** source SHA-256/size/mtime entries unchanged; `data/evidence/step5-full-source-verification.json` |
| `scripts/publish_embedding_evidence.py` | small versioned summary, full generated evidence/weights excluded |
| diff/staged whitespace and file review; local commit | code, locks, tests and documentation only; no remote or push |

New tests cover finite/zero/NaN/Inf/dimension normalization; five incompatible
contract cases; corruption/unit-norm rejection; channel separation, fusion and
duplicate-view aggregation; source/content/preview/owner-correction staleness;
verified filters and alternate-format scope; required versus inactive dependencies;
reference capability/path boundary; compact cap; weak/empty negatives; query error
propagation; failed replacement removing old vectors and no unchanged fault retry.
Synthetic vectors exist only in explicitly named test doubles, never production.

Two development fixture issues (models outside pack layout, then legacy empty
overlay validation) were corrected before the passing tests. The deprecated
SentenceTransformers dimension/tokenize methods were replaced with the current
methods and capability proof rerun with the resulting new contract before indexing.
A byte-exact step 2 response comparison differed because step 3 added preview
paths/root labels; the subsequent comparison excluding those fields confirmed
identical keyword IDs/order/names/formats/source paths. Two documentation patches
missed their context and changed nothing before the correct patch applied.
These failed attempts are not passing checks. The existing managed-Python path
warning remains nonfatal. The step 4 preservation checker says `embeddings:
not_started` about its untouched catalog vector field; step 5 embeddings reside
in the separate verified index, so that legacy label is not a step 5 status.

Final measured model directory **5,792,432,361 bytes**, all managed project areas
**20,773,085,969 bytes**; remaining conservative model budget **2,797,502,231 bytes**
and generated-data/runtime/cache allowance **6,494,182,872 bytes**. Counts include
regular-file logical sizes/cache copies and model metadata, not filesystem blocks.
Model downloads themselves total **5,792,427,398 bytes**, inside the 8 GiB limit;
nonmodel generated storage remains inside 20 GiB. No oversized download approved.

### Remaining limitations and stop boundary

Thirty provisional visual descriptions have recorded faults; one caption failed.
Unknown author axes/physical scale, uninspected alternate formats/dependencies,
grouping/license ambiguities and the unused BirchTree texture fault remain.
Semantic candidates can be unrelated for absent queries even with high cosine;
owner relevance labels and threshold calibration do not exist. Reference images
outside source/project boundaries and CPU/FP32 contracts are unverified here.
Fresh CLI invocations reload the model; same-process API is used for warm timings.
No long-lived server/client integration or automatic incremental scheduler added.

Step 5 technical work is complete. Next numbered stage is step 6 evaluation, with
human judgments and an explicit owner expansion decision. **Stop here:** no
benchmark verdict, full-library embedding, MCP registration, game import, export,
remote, push or publication. Owner caption/artistic/retrieval approval remains pending.

## Step 6 — frozen pilot evaluation (2026-10-11)

**Status: provisional.** Technical evaluation and local artifacts are complete;
the fixed expansion arithmetic passes on model-generated labels. Bruno's
relevance review and explicit pilot decision remain pending. No step 7/client
integration, full indexing, source editing, subagents, new models/dependencies or
push. Scope and implementation-plan checkpoints were explicitly approved.

Read project AGENTS, this progress record, step 6 and retrieval/acceptance rules
in `docs/plan/PROJECT.md`. Prepared **32 text queries** (8 exact, 8 descriptions,
6 style/color/shape/variant, 4 verified formats, 6 negatives), **8 held out**;
**4 reference crops**, two held out. Defined the 17-query natural-language gate
before comparisons. No tuning. Query/criteria/model-label freeze at
**16:17:33 UTC**, before comparative rankings. Prior step 5 demonstrations are
disclosed; holdout is a query split, not unseen assets/training data.

No existing explicit owner relevance judgments found. Inspected actual preview
sheets/source identity/verified formats for all forty assets, excluding evaluated
captions as labeling inputs. Complete graded pool (0–3) is versioned as
`docs/evaluation/labels-provisional.json`; uncertain gray/brown mossy-rock and
white/green snow-tree matches are qualified and explicitly await owner review.
Rank-blind local `data/evaluation/relevance-review.html` was prepared before
rankings; asked Bruno to review its 36 manageable query sections. Every section
has actual images, grade controls, deliberate distractors in pilot order, and
an option to inspect all forty assets. Exporting labels does not approve step 7.

Added `keyword_description` mode via the existing equal-weight RRF k=60. Added
reference evaluation parent-hash exclusions before view aggregation; every crop
differs bytewise from indexed inputs, with all parent-image rows removed. Exact
normalized similarity, source/contract checks, separate full channel rankings,
original full-catalog keyword baseline and existing pilot/index remain intact.

### Measured comparison, provisional quality labels

| Mode | Positive Hit@5 | Natural Hit@5 | Exact successes | Positive nDCG@5 | Negative requests returning candidates | Warm p95 s |
| --- | --- | --- | --- | --- | --- | --- |
| Filename/keyword | 9/26 | 0/17 | 8/8 | 0.3320 | 0/6 | 0.699 |
| Description | 25/26 | 17/17 | 7/8 | 0.9320 | 6/6 | 1.279 |
| Text-to-image | 26/26 | 17/17 | 8/8 | 0.9461 | 6/6 | 1.280 |
| Keyword + description | 26/26 | 17/17 | 8/8 | 0.9704 | 6/6 | 1.327 |
| Full combined | 26/26 | 17/17 | 8/8 | 0.9687 | 6/6 | 1.692 |

**328 successful searches, zero inference failures**: 32 queries × five modes ×
two repeats, plus four references × two repeats. Quality uses the first repeat;
64 warm timing samples per text mode, nearest-rank p95. Held-out natural hits:
keyword 0/4, every semantic comparison 4/4; held-out positive hits 2/6 versus 6/6.
Description-only lacks road-crossroad's failed caption; keyword fusion recovers
that exact request without an invented description. Full fusion adds no natural
or positive Hit@5 over keyword+description in this easy-pilot ceiling sample.

All semantic modes returned **30 weak candidate slots / six negatives**, zero
strong match claims. Weak is counted as false positive, not abstention. Threshold
stayed null; no cutoff calibrated on the held-out set. Verified format/pack
violations: **zero** for all modes and complete channel lists. Filter result
slots checked on first repeat: keyword 1, description 19, image 20,
keyword+description 19, combined 20. No within-shortlist duplicate assets.
Across all text queries (including negatives), unique assets/slots: 10/10,
38/159, 40/160, 39/159, 40/160 respectively; coverage is not useful diversity.

Reference same-asset cross-view recovery: **4/4**, all first-ranked, parent
images excluded. Different useful assets: **3/3 evaluable references hit**,
**4/5** labeled useful different assets returned. Tractor has no useful different
target. Snow-tree crop misses one other birch; crops are correlated synthetic
render evidence, not general photographic similarity proof. Reference warm
median/p95 **1.281/1.352 s**, eight samples.

Fresh-process first-query wall times (one sample/mode, OS disk cache retained):
keyword **0.926 s**, description **13.420 s**, image **13.733 s**,
keyword+description **13.589 s**, combined **14.132 s**, reference **13.441 s**.
Include startup/verified load/first query/token measurement, exclude second query
and shutdown. Warm times include inference, source/preview hashing, ranking and
compact serialization; exclude token measurement/evidence writes. No server or
concurrency performance claim. Text ranking repeats were identical.

Maximum standard shortlist: **3,798 exact characters**, **950** with the named
ceil(characters/4) estimator, **1,252 actual tokens with the pinned EmbeddingGemma
tokenizer**. Tokenizer counts are an explicit surrogate, not Codex/OpenCode
billing/context tokens. Images and transport/tool-schema overhead excluded;
agent integration and actual billing/context savings unmeasured.

Fixed gate applied unchanged: +100 natural Hit@5 percentage points versus the
required +10, zero exact-name successes lost (allowed <=1), zero verified-filter
violations, combined warm p95 **1.691895 s <2 s**. **Conditional arithmetic pass;
overall provisional pending owner labels/decision.** Every natural hit is 5.88
points, held-out natural hit 25 points; queries are curated, not random. Small
sample, partial caption faults and reference correlation limit generalization.

### Runtime, costs and checks

No runtime/model change. CPython **3.13.15**, SentenceTransformers **6.1.0**,
Transformers **5.19.0**, torch **2.10.0+cu128**, torchvision **0.25.0+cu128**,
Pillow **12.1.0**, NumPy **2.3.4**, huggingface-hub **1.33.0**. Model
`google/embeddinggemma-2`, revision
`914f7f89142e33e77833254d9c9b90c3cef7303b`; BF16 CUDA, 768-dimensional finite
FP32 L2-normalized vectors, original prompts/preprocessing/contract unchanged.
Contract fingerprint:
`9ce34abf58dfec06638bc7c221ba74b09f39dfeba7acf90a76dccc4eba2de504`.
Warm benchmark process load **12.635 s**, RSS snapshot **2,275,569,664 bytes**,
CUDA peak allocated/reserved **977,068,544 / 1,017,118,720 bytes**. No competing
heavy-model unload was necessary; no inference fallback or model fine-tuning.

Prior measured costs explicitly retained: captions **53 attempts / 552.784 s**
including calibration; batch **416.469 s**, 39 valid/one failed/30 visual faults.
Embedding initial publication **22.813 s** (204/five precondition failures),
four corrected/reused additions **2.225 s**, 208-vector unchanged reuse **1.296 s**.
No captioning/reindexing in this stage; no invented full-library cost estimate.

| Operation | Verified evidence |
| --- | --- |
| `prepare_evaluation.py`, `label_evaluation.py` | actual image sheets, deterministic crops, complete provisional grades, rank-blind HTML, pre-ranking freeze |
| `benchmark_evaluation.py`, then `--cold` | 328 successful searches plus six fresh processes; both repeats/raw channel rankings hash-bound locally |
| `report_evaluation.py` | saved-ranking arithmetic only; raw counts, nDCG/MRR, split/negative/filter/diversity/context/cost metrics; no inference rerun |
| focused `pytest tests/test_retrieval.py tests/test_evaluation.py --basetemp scratch/pytest-step6` | **32 passed** (27 retrieval, five evaluation); no unrelated suite repetition |
| `verify_evaluation.py` | 328 outputs, **520 channel lists**, all **208** finite normalized vectors/contracts, parent exclusion, **1,444** review image links, source/dependency resolution |
| preservation checks | catalog/index/pilot SHA-256 unchanged; all **4,938 source SHA-256/size/mtime entries unchanged** |
| original no-mode keyword CLI `search apple` | same working four-result baseline; no semantic runtime needed |
| diff/staged checks and local commit | evaluation code, tests, report and frozen artifacts only; no push |

One development test used nonexistent `preview` instead of existing ranking
`input`; corrected before benchmarking, affected test then final focused suite
passed. No production inference failures or affected benchmark reruns. Existing
managed-Python location warning remains nonfatal. Frozen versioned JSON/JSONL
use scoped byte-preserving attributes so future Git checkout conversion cannot invalidate
their byte fingerprints. Staging exposed Windows newline conversion; scoped
CRLF-aware whitespace checks and a staged-blob hash comparison confirm all three
frozen versioned input files retain their exact original bytes.

Managed storage snapshot **20,821,007,204 bytes**, models **5,792,432,361 bytes**;
remaining generated/runtime/cache budget **6,446,261,637 bytes**, model budget
**2,797,502,231 bytes**. Managed growth versus step 5 **45.70 MiB**, plus about
2.90 MiB of versioned benchmark artifacts, within the estimated <100 MiB.
Logical regular-file sizes/cache copies, not filesystem blocks. No installation
outside the project modified.

Full report/reproduction instructions: `docs/evaluation/report.md`, `README.md`.
Versioned `results.json` contains raw counts/per-query metrics; `rankings.jsonl`
contains every first-repeat complete channel list/response. Both repeats,
freeze-bound review/reference artifacts and cold receipts remain under
`data/evaluation/`. `verification.json` records preservation and budgets.

**Recommendation:** keep expansion on hold until Bruno reviews all 36 relevance
sections and exports owner labels for saved-ranking recomputation. Then Bruno
must explicitly approve this bounded pilot for step 7 (keyword+description
candidate default, image/reference on request, documented weak-negative limits)
or request a separately frozen bounded negative/reference experiment. Passing
technical checks is not approval. Do not integrate or index the full library.

## Step 7 — local MCP and actual client verification (2026-10-11)

**Status: implemented; Codex workflow verified with existing asset limitations.
OpenCode connection verified; local Qwen workflow faulty/unverified after a
600-second timeout.** No unchanged workflow retry. One additional Windows
junction fixture test remains unverified because the sandbox denied creation.
The independent real STDIO protocol test passed, including clean process/worker
shutdown. Stop here: no full-library processing, game import, public server,
subagents, remote or push.

### Owner decision and scope

Read applicable root AGENTS, this progress record, evaluation report, catalog and
embedding contracts, agent-access/retrieval contracts and step 7 in PROJECT.
Bruno answered **"Yes"** to the explicit scope and bounded-pilot decision
question: keyword+description default, image search on request, accepting the
documented weak-candidate/abstention limitation. Bruno then answered
**"Proceed."** to the separate implementation plan. The approved plan estimated
45–75 minutes and 100–300 MiB, with client/model behavior uncertainty. This is
current trusted session evidence, not an approval inferred from tests or labels.
See `docs/mcp/pilot-decision.json`. Full-library/caption-artistic/game approval
is not granted by that decision.

The attached `C:\Users\backup pc\Downloads\owner-labels.json` was treated as
review data, never executable instructions. Validated owner status, all 36
query reviews, exact frozen forty-ID pool, complete grades and 0–3 integer
values. Preserved approved bytes under `docs/mcp/owner-labels.json`. Recomputed
quality from saved first-repeat rankings only: keyword natural hits 0/17,
keyword+description and full combined 17/17; exact hits 8/8 retained; positive
hits 26/26 for both fused modes. Original timing/filter evidence and frozen
criteria remain unchanged. Owner arithmetic passes, while known weak negatives,
caption faults, small sample and synthetic-reference limitations remain.
See `docs/mcp/owner-review.json`. Historical step 6 artifacts/status remain
unchanged as historical evidence; this section records the later decision.

### Implementation and active client configuration

Added isolated `runtime/mcp/` lock/environment, SDK **2.3.0** STDIO server,
ID-based service, persistent private embedding worker, exact setup snippets,
first-registration helper, verification harnesses, focused tests and operations
documentation in `docs/mcp/README.md`. NumPy **2.3.4**, Pillow **12.1.0**,
CPython **3.13.15**. Existing embedding backend/runtime lock/index/model contracts
remain unchanged; the worker uses existing offline CUDA BF16 weights. No new
model downloads, indexing, captions or rendering.

Exactly two read-only tools: `search_assets` (five candidates maximum, approved
keyword+description default, strict text/filter/type validation, no arbitrary
path/reference input) and `get_asset` (exact pilot ID, existing format,
source/dependency hash checks, explicit completeness/fault states, optional
metadata/preview). ID reference images select a known catalog view. Stale/missing
sources/dependencies are excluded; roots are resolved before access. Text caps
include size fields: 6,000 characters for search, 16,000 for requested detail.
PNG ImageContent is at most 512×512 and 512 KiB; requested missing/stale views
remain faulty without another-view substitution. Fault evidence and usable
partial outputs persist separately under ignored `data/mcp/runs/`.
Diagnostics are on stderr; client startup invokes Python directly, never an
installer. No public/network server transport was added.

Current official documentation was opened for Codex MCP, OpenCode MCP and
configuration precedence, and the MCP SDK server interface; links are in the MCP
README. Active clients were discovered and registered additively:

| Client | Actual active configuration and result |
| --- | --- |
| Codex CLI **0.162.0-alpha.17.2** | `C:\Users\backup pc\.codex\config.toml`; no CODEX_HOME/project override. Retained `gpt-6.1-sol` and existing node_repl/gimp/blender servers. `codex mcp get local_asset_library --json` resolved the exact new STDIO entry; fresh real CLI workflow used it. Desktop hot-reload was not claimed. |
| OpenCode **1.18.29** | Actual `outputs/opencode.cmd` launcher identifies `C:\BrunoOS\OpenCode-local-agent\outputs\opencode-local.json` plus relocated XDG directories. No additional global configuration file found there. Retained `ollama/qwen3.8:local-agent`, small model, provider/options/model setup and every existing permission. `opencode mcp list` showed this server connected. |

Both original configurations were byte-copied before editing into
`data/mcp/config-backups/20261011T222809658883Z/`. Before/after SHA-256 values,
exact entries and restore paths are in ignored `data/mcp/registration.json` and
versioned `docs/mcp/client-results.json`. Original backups and active parsed
settings were reverified: removing only this new server restores the original
configuration objects exactly. Backups remain local/ignored because they may
contain private settings. Restoration instructions and exact setup snippets are
under `docs/mcp/`; no unrelated configuration was rewritten. Codex disabled
other MCPs only in the verification invocation. OpenCode's one-run inline
permission overlay allowed exactly the two read-only project tools; saved
permissions/model settings were not changed.

### Actual client workflows and returned context

Requested prop: a small stylized red apple with a leaf. Real installed clients
were verification targets; no subtasks/subagents were spawned.

| Evidence | Codex cloud model | OpenCode local Ollama model |
| --- | --- | --- |
| Real tool calls | 3: default search, preview+metadata, inspected FBX detail | 2: default search, preview+metadata |
| Search text characters / heuristic tokens | 3,804 / 951 | 3,802 / 951 |
| All returned tool text characters | 19,385 | 11,759 before timeout |
| Requested preview | 47,759-byte PNG, 63,680 base64 characters | Same PNG attached as `image/png` in completed OpenCode tool event |
| Image inspection | Verified: ImageContent in actual tool event, image-specific observations (squat faceted red-orange body, blocky brown stem, flat mint-green leaf, gray background), manually checked against saved PNG | Unverified: no completed image-specific reasoning/final selection before timeout; attachment receipt alone is not vision proof |
| Source/dependencies | Agent chose inspected FBX; exact manifest source/dependency objects matched actual tool returns and all paths/hashes reverified | Usable detail/known dependencies preserved, but no final agent selection claimed |
| Final artifact | `data/exports/codex-selection.json`, actual agent-produced JSON, verified against returns | `data/exports/opencode-partial-receipt.json`, explicitly a harness preservation receipt, not an agent-produced final selection |
| Overall | Workflow verified; agent retained `status: partial` for caption/scale/dependency-completeness limitations | Faulty workflow timeout at 600 seconds; local selection/vision unverified; no retry |

Codex's manifest is deliberately qualified: apple caption is faulty, physical
scale is unknown, and binary/alternate dependency completeness is not proven.
These limits do not erase the successful real search/preview/format-resolution
workflow. No model/source file was copied into any game/source directory.

Both complete tool definitions together measure **1,816 compact JSON
characters**, excluding initialization/instructions/envelope. Characters/4 is
explicitly heuristic, not client/model tokenizer or billing evidence. Image bytes
and transport/schema overhead are separate from the shortlist target. Actual
Codex whole-session usage: **120,046 input tokens**, **104,576 cached input**,
**1,719 output**, **53 reasoning output** as reported by the client. That includes
instructions, schemas, repeated context and images; it is not retrieval-only
usage or proof of billing savings. OpenCode reported completed-step token counts
only: first step 7,437 input/118 output; second 1,221 input/168 output plus
7,433 cache-read. No final vision-step usage is invented.

Cloud disclosure: Codex's configured cloud model received returned descriptions,
metadata, absolute source/dependency paths and requested PNG content. This
cloud-backed verification chat also received candidate text, inspected the same
PNG and reviewed audit summaries. OpenCode inference used the existing local
localhost Ollama provider; the entire task is not claimed private/local because
its evidence was reviewed here. Full source model binaries and configuration
backups were not returned to these models.

Raw client events, stderr, process outcomes and prompts remain under
`data/mcp/client-runs/`; independent server audits and PNGs under
`data/mcp/runs/`. Versioned `docs/mcp/client-results.json` binds the actual audit,
per-call counts/timing/bytes, usage, configuration backups and workflow status.

### Checks, faults and preservation

| Command / operation | Actual result |
| --- | --- |
| `mcp-runtime.ps1 sync --project runtime/mcp --python <existing CPython>` | Separate locked MCP environment; 37 packages installed; no existing model/runtime lock altered |
| `review-owner-results.py <attached owner-labels.json>` | 36 owner sections validated, saved-ranking arithmetic only, gate pass; separately recorded session approval referenced |
| Initial focused MCP/retrieval/evaluation tests | **59 passed in 90.19 s** |
| Final changed-policy/config boundary tests | **46 passed in 28.56 s; one faulty/unverified junction fixture**: Windows symlink privilege absent and sandbox junction creation denied. No unchanged retry or source repair. |
| `verify-mcp.py --run-name final` | **Pass**: real protocol 2025-11-25 initialization, exact two-tool discovery, 17 calls across successful/malformed inputs, both tools, source/dependency detail, PNG decode/hash/cap, semantic default, clean EOF server/worker exit |
| Real Codex verification | Exit 0, 48.86 s, three actual MCP calls; preview/selection manifest independently verified |
| Real OpenCode verification | Two successful calls; stopped at 600.06 s timeout, final workflow/vision unverified; partial evidence preserved |
| Source/catalog/index/pilot/freeze preservation | All **4,938 SHA-256/size/mtime entries unchanged**; catalog/index/pilot byte hashes unchanged; frozen evaluation verified |
| Active configuration preservation | Exact backup hashes and unchanged unrelated parsed fields reverified for both clients |
| Syntax and whitespace checks | New/updated Python files parsed; diff/staging checks reviewed before local commit |

The first protocol harness had a **test-harness fault**: it matched a Windows
environment-launcher PID to a different Python child PID. All tool checks had
completed and the saved worker lifecycle exited 0, but the lookup raised
StopIteration. Preserved that first faulty report/wire/PNG under
`data/mcp/protocol/`; changed the harness to identify its new audit directory and
kept the final passing run separately under `data/mcp/protocol/final/`. No asset
fault was repaired or silently erased. Other read-only/command preparation
faults (default OpenCode directory probe, SDK v1 API introspection, absent optional
attributes file/output-log directory) are recorded in `docs/mcp/verification.json`.

Managed storage snapshot: **21,108,914,299 bytes** versus prior step 6
20,821,007,204: approximately **274.57 MiB** growth, including environment/cache
copies and tests/evidence. New `.venv-mcp` is **116,535,439 bytes**. Models remain
**5,792,432,361 bytes**; remaining model budget **2,797,502,231 bytes**, generated
budget **6,158,354,542 bytes** at that snapshot. Subsequent small evidence/docs
writes add kilobytes. Logical file sizes, not filesystem blocks. Both project
budgets and approved 100–300 MiB estimate remain satisfied.

Local commit contains only step 7 source, runtime lock, tests, docs, approved
labels and bounded evidence summaries; catalogs/assets/models/environments,
full client transcripts, exports and configuration backups remain ignored.
No push. The next stage is **step 8 only after a new explicit request**. A retry
or repair of the faulty local workflow/junction fixture also requires Bruno's
explicit request under the root fault policy; no repair is implied by this
handoff.

### Bruno's client decision — October 11, 2026

Bruno explicitly chose to **use the verified Codex integration for now** and
asked to register that decision. OpenCode completion is **not required for
current use**; further OpenCode work is on hold until Bruno explicitly requests
it. Its existing timeout, partial results and unverified local image/selection
status remain recorded. This decision authorizes no retry, repair, configuration
change, full-library processing or game import.

Trusted session evidence: "For now I don't care if the OpenCode integration
isn't working, I'll use it with codex for now." Then: "Please register this
decision." The decision is also recorded in `docs/mcp/client-decision.json`.

## Shared model relocation — completed October 11, 2026

Bruno approved moving this project's AI weights directly into
`C:\BrunoOS\Local-models`, with no project-specific parent folder, so other
projects can reuse them. Both scope and the revised implementation plan were
approved before implementation.

Moved `qwen3-vl-2b` and `embeddinggemma-2`, retaining revision subfolders.
All 50 files, including download metadata, match before/after SHA-256 and size;
total 5,792,432,361 bytes. No model files remain in the old project `models/`.
No compatibility links, downloads, source edits, index rebuilds, client config
changes, commits or pushes were needed.

The configuration explicitly selects the shared absolute model root. Only model
storage may be external; source overlap, repository overlap, missing roots,
unsafe child paths and resolved link escapes remain rejected. Runtime wrappers
and the MCP worker keep Hugging Face caches in project `cache/`. Model budget
accounting now includes only this project's two pinned revisions, excluding
other projects and revisions in the shared folder. Backend source files and
inference fingerprints were preserved, so the existing embedding index remains
usable. Documentation describes exact paths and shared usage.

Verification: 76 focused configuration/MCP/retrieval tests passed in 117.36 s;
the previously faulty Windows junction fixture was deliberately excluded and
was not retried. Both models loaded offline from the new location. Embedding
search returned existing apple candidates and retrieved real PNG/source detail;
Qwen consumed a real car image and generated a short description. A fresh MCP
protocol session passed 17 calls, including semantic search, previews, malformed
input checks and clean worker shutdown. Config/doctor checks passed; 47 Python
source/script files parsed and the whitespace check passed.

New evidence: `data/model-relocation/move.json`, `embedding.json`, `caption.json`,
`verification.json`, and `data/mcp/protocol/model-relocation/report.json`.
Original caption, embedding, evaluation and fault evidence was not overwritten.

Preserved faults/limitations: read-only CIM process inventory was denied, so
active process enumeration was unavailable; no locks blocked the actual move.
The initial test command used the base environment without Pillow and failed
collection. A separate verification in the existing MCP environment passed;
no dependency installation or unchanged faulty-environment retry occurred.
The existing managed-Python location warning remained nonfatal. New checks are
technical evidence, not caption quality, game-import or full-library approval.

Usage and exact directories: [shared model storage](model-storage.md).

## Windows desktop GUI — added between steps 7 and 8 (October 11, 2026)

**Implemented and verified; Bruno's usability and comprehensive accessibility
review remain pending. Step 8 was not executed.** Bruno approved scope with
"Yes" and the separate plan with "Proceed". Estimate: 90–150 minutes and
30–150 MiB additional unique allocation, assuming the existing WebView2/.NET
installation and dependency pins remained compatible. No subagents were used.
Bruno subsequently clarified that the no-retry rule applies to asset
investigation/export; app and test-harness issues may be corrected and rechecked.

Launcher: `C:\BrunoOS\Local-Asset-Library\Local Asset Library.vbs`. It invokes
the existing MCP environment's console-free Python from any starting directory.
It opens a normal Windows window; startup does not install, download, scan,
render, caption, re-embed or update any asset data. Usage and ownership:
[desktop guide](gui/README.md); bounded results: [verification summary](gui/verification.json).

Added local bundled HTML/CSS/JavaScript, adaptive thumbnail grid, text search,
verified filters, existing secondary modes and pilot-ID/view reference search.
Details expose explicit views/formats, verified original source path with text
copying, measured facts scoped to the inspected file, generated observations,
suggestions, live owner review, license/dependency evidence and recorded faults.
Physical scale and uninspected alternate capabilities remain unknown. Cards
retain usable partial assets and concise fault flags. Missing views have an
accessible reason and no image substitution.

Search uses the same `Gateway.call`/`AssetService`/`SearchEngine` implementation as
MCP, with explicit `keyword_description` default, five-result maximum and shared
validation, filters, availability checks, rankings and deterministic truncation.
Browsing is a separate read-only backend operation; membership/counts come from
the manifest rather than frontend identities. Exact completed MCP arguments can
be copied; same catalog/index versions are necessary for reproduction. Semantic
results can include irrelevant candidates for absent objects; no confidence
percentage, universal threshold or keyword fallback was added.

The GUI main thread remains free while background source/detail work and one
private persistent embedding worker operate. Browsing starts no model. Request
generations suppress obsolete results. Closing releases only GUI-owned resources,
including the private Windows worker tree if a pending load exceeds the graceful
five-second window. Per-window browser profiles have containment/link review
before cleanup; asset evidence is stored outside those profiles.

Dependencies were added to the existing separately locked MCP environment:
pywebview 6.2.1, pythonnet 3.2.1, clr-loader 0.3.1, bottle 0.13.4 and proxy-tools
0.1.0. Existing installed versions were preserved; no additional runtime, browser
bundle, GPU library copy, weights, model contract or agent registration changed.
This PC's existing WebView2 154.0.4258.62/.NET Framework 4.8.09221 worked. All app
resources and inference remain local; source text is rendered as text, and CSP
blocks external resources/connections.

### Verification and actual measurements

| Check | Result and evidence |
| --- | --- |
| Focused desktop/MCP/retrieval policy checks | **61 passed in 28.02 s**; small synthetic fixtures; `data/gui/unit-final/report.json` |
| Final strict-input desktop refinement | **7 passed in 6.01 s**, including a new malformed-object/source-format case and all desktop regression checks; `data/gui/strict-inputs/report.json` |
| Actual packaged-form → pywebview bridge versus real STDIO MCP | **10 queries, all existing modes**, natural-language/name/filter/absent/reference cases; entire payloads and ordered IDs identical; `data/gui/final-window/report.json` |
| Actual truncation over both transports | Synthetic limit 5 returned the same **one candidate**, `truncated=true`, 3,470 characters; `data/gui/cap-verified/report.json` |
| Pilot browsing | **40 existing three-quarter thumbnails**, no model load; counts/context sourced from backend; full inventory remains 883 records |
| Loading/races/faults | Synthetic older-response suppression, visible runtime errors, explicit truncation, earlier-card retention, no fallback; source/preview partial-fault tests passed |
| Actual interface inspection | Windows window visually inspected; final WebView2 captures reviewed under `data/gui/delivery-images/`; native resizing and narrow layout have no horizontal overflow |
| Native launcher/keyboard | Launched from `C:\BrunoOS`; visible window without terminal; Ctrl+F/text entry, Enter search, Clear browse, Escape/detail-focus return, Right-arrow grid movement, Enter-card activation and Alt+F4 checked |
| Resource lifecycle | GUI and verification-owned MCP idle workers exited **0**; one GUI worker retained across warm queries. Closing a pending first load completed in **5.281 s**, terminating only its private process tree; `data/gui/close-pending.json` |
| Preservation | **4,938 original SHA-256/size/mtime entries unchanged; 989 protected generated/contract files unchanged**, including catalog/index, captions/corrections, previews, pilot, inference backends and other runtime locks; `data/gui/preservation-after.json` |

First GUI semantic search took **27.186 s** in the final protocol comparison
(earlier comparison: 29.518 s); the normally launched native session took **7.998 s**.
These are different local cache/load conditions, not guaranteed cold/warm bounds.
Subsequent default searches in the final comparison took **0.302–0.509 s**;
keyword 0.191 s, image 0.501 s, combined 0.641 s, description 0.496 s and reference
0.748 s. Separate GUI/MCP verification workers both loaded successfully, but
arbitrary simultaneous GPU workloads remain unverified. Other processes were
not changed or terminated.

### Storage, cleanup and retained faults

Fresh base-Python receipts: `data/storage/gui-before.json`, `gui-after-install.json`
and `gui-delivery.json`. Unique allocated project bytes changed from
**5,938,483,904 to 5,978,770,592**: **38.42 MiB additional; 5.568 GiB total**, below
the 6 GiB target. External originals/shared models are excluded. Dependencies
initially added **17.46 MiB**. This delivery snapshot precedes subsequent small
documentation/commit writes; live browser cache usage varies.

After successful runtime verification, cleaned only the exact project-local
`cache/uv` with uv's cache command. It reported 699 cache names / 16.1 MiB removed;
that is not an independently measured unique-allocation saving. Offline desktop
and MCP dependency imports still passed. Preserved synthetic test audits/fault
records/reports before removing only this run's four disposable fixture trees,
after exact containment and link/junction checks. Project allocation decreased
by **119.37 MiB** across those cleanup receipts; see
`data/gui/fixture-cleanup/report.json` and `data/storage/gui-before-fixture-cleanup.json`
/ `gui-after-fixture-cleanup.json`. No historical linked fixtures or generic
system caches were deleted.

Retained initial app/harness faults separately: restricted pre-install report
permission, missing evidence-log folder, SDK error-flag attribute mismatch,
JavaScript `arguments` shadowing, incorrect synthetic truncation keyword,
optional documentation/source probes, source-edit quoting, and initial Windows
inspection-helper approval timeout. Successful corrections/partial results are
recorded in `docs/gui/preparation-faults.json` and distinct `data/gui/` runs.
One browser cache cleanup logged WinError 32 for a locked file; partial cache and
log evidence were retained without automatic cleanup retry. Final native profile
cleanup succeeded. Historical asset/caption/source faults were never repaired,
retried in investigation/export, cleared or silently declared successful.

Existing uncommitted storage/runtime guidance and scripts were preserved. The
checked local commit contains only this GUI work, its pinned desktop additions,
verification helpers/tests and documentation; the README GUI addition is staged
separately from prior storage edits. No push or publication. Full-library
processing, incremental updates, imports, game integration, public hosting,
classification and standalone distribution remain outside this stage. Step 8
still needs separate authorization.

## Caption severity cleanup and future processing rules — October 12, 2026

Bruno approved the caption cleanup scope and implementation plan, then requested
that new asset imports use the same practical caption-processing rules.

The current 40-asset pilot now has **1 actual caption fault, 14 caption warnings,
16 assets with minor review notes and 9 with no recorded findings**. All 32
historical visual findings remain intact. New classification is separately bound
to original caption/provenance/evidence hashes. Minor notes appear in detail;
meaningful errors show warning badges; failed/unusable captions retain faults.
Desktop and agent search/detail use the same classification. Source, preview,
dependency and runtime faults retain their original treatment and evidence.

Updated AGENTS.md and the review writer for future processing: structured
`findings` contain review_note/warning severity, evidence and rationale. Legacy
unclassified findings default to warnings rather than faulty. Future provenance
carries explicit severity, independent of the old pilot classification. New
review pages show the same distinctions. Failed or missing captions cannot be
downgraded by a review note. App/test-harness fixes are outside the asset
investigation/export no-retry rule, reflecting Bruno's earlier clarification.
No actual import, recaptioning, model run, owner approval, ranking change or
full-library expansion was performed. Existing model/schema/runtime pins remain.

Verification: 80 shared desktop/MCP/retrieval/severity tests passed in 111.66 s.
After the future-rules update, 51 focused severity/caption tests passed in 8.80 s,
including an actual review-writer publication on synthetic catalog data; these
counts overlap. The real pilot preserves 990 protected input hashes and all 40
keyword-query rankings. Native WebView2 checks confirmed 40 thumbnails, warning
and fault badges, note/fault detail separation, narrow layout, three representative
real STDIO detail/search payload agreements, and clean closure without a model
worker. Actual browse and note-detail captures were visually inspected.

Evidence and current rules: docs/caption-quality.md,
docs/caption-review-classification.json and
docs/caption-classification-verification.json. Detailed receipts are under
data/caption-classification/ and data/gui/caption-classification/. Original
historical static caption review pages keep their recorded wording.

Storage receipts: data/storage/caption-classification-before.json,
caption-classification-after-checks.json and caption-classification-final.json.
Unique allocated storage: 5,979,705,784 bytes before; 6,015,785,440 bytes with
synthetic checks; 5,982,177,224 bytes after reviewed fixture cleanup (about
5.571 GiB, +2.36 MiB retained). Temporary fixture growth of 34.41 MiB exceeded
the initial 20 MiB estimate; retained growth is below it. Cleanup preserved test
reports, faults and synthetic caption publication evidence. No packages, model
weights, originals, historical evidence or general caches were removed.
Preparation errors and their resolutions are recorded separately in the new
verification receipt. Step 8 expansion and owner usability/artistic decisions
remain separate. Reopen the app and restart existing agent server connections
to load the updated code.

Final processing-rule follow-up also updated summary metrics and the review-page
checker, replacing the assumption that every finding is a faulty caption. New
pages validate severity counts; old pages validate explicitly as historical
without being rewritten. The preserved historical page passed all 124 image and
288 local-reference checks. A fresh UUID receipt was saved under data/evidence;
the original Step 4 check receipt was preserved. Final focused checks: 51 passed
in 8.07 s (data/caption-classification/rules-tests-banner.log), including current
note/warning banner checks. Delivery storage receipt:
data/storage/caption-classification-delivery.json, 5,982,236,432 unique allocated
bytes (+2.41 MiB versus before), still below 6 GiB. These are overlapping focused
rechecks, not additional distinct tests or owner approval.

## Remaining plan and execution-prompt update — October 12, 2026

At Bruno's request, updated PROJECT.md and the Step 8–10 execution prompts in
C:\BrunoOS\Plans\Local-Asset-Library and the repository docs/plan mirror.
The plan now records the implemented GUI milestone, responsive full-library
browsing and shared publication/version behavior in Step 8, optional taxonomy
and clustering presentation in the existing app in Step 9, and desktop/agent
handoff and verification in Step 10. Current caption severity, explicit asset
fault retries, shared runtime/model storage and an approved measured expansion
budget replace conflicting old assumptions. Stage numbering remains unchanged;
Steps 8–10 were not executed and full-library processing was not authorized by
this documentation update. Both copies of all four documents are byte-identical;
Markdown fences and affected prompt references were checked. Receipt:
data/plan-updates/gui-caption-remaining-stages.json. No implementation/runtime,
asset, catalog/index or owner-review data changed.

## Step 8 — reliable updates and expanded backend/GUI (October 12, 2026)

Bruno approved the eight-pack, 883-asset scope and implementation/storage plan,
then approved the corrected 4–6-hour batch estimate and requested completion
without further confirmation. The earlier 1.5–3-hour batch estimate was an
arithmetic error; no bulk processing began before its correction/approval.
No subagents, original-pack/Play Shapes edits, dependency/model installation,
client-registration changes, optional classification or clustering were performed.

Implemented explicit bounded membership, persistent stage/vector checkpoints,
input-specific invalidation, isolated faults, deletion/rename identity rules,
preserved owner overlays and immutable transactional catalog/index generations.
The original forty-asset pilot results/evidence remain preserved. GUI browsing
is paged to forty cards, thumbnails load near the viewport with three-request
concurrency, and selection/filters/keyboard access survive updates. Opening
remains lightweight. Manual scan/process/refresh/status and dry runs are
documented in docs/library-updates.md; current contract is
docs/library-membership.json. GPU leases coordinate owned workers; models unload
for queued peers/batches, while browse/keyword/detail remain available.

Actual membership: **883 assets, eight packs**. Stage coverage: `{"inventory": {"complete": 883}, "inspection": {"complete": 883}, "previews": {"complete": 883}, "caption": {"complete": 514, "failed": 369}, "embeddings": {"complete": 505, "partial": 378}}`.
Vectors: `{"description": 514, "image": 3830}`. Caption quality: `{"clear": 484, "fault": 369, "warning": 14, "review_note": 16}`.
Owner states: `{"pending": 883}`. Per-pack/stage counts, usable partial
results, source faults, pending AI reviews, caption notes/warnings and failures
are separately recorded in docs/step8-verification.json. Failed captions retain
raw canonical attempts and reasons; none were retried or manufactured.

Actual stage batch durations (seconds): `{"caption": 8553.721718200191, "embeddings": 621.7863518999075, "inspection": 5037.390167300124}`. These exclude
some wrapper/model-load, status, storage and publication overhead. Before/after
and per-batch fresh base-Python receipts are under data/storage/step8-*.json.
Peak measured project allocation: **6.397 GiB**;
latest: **6.397 GiB**, excluding external
originals/shared weights, below the approved 8 GiB full-library ceiling.

Verification: synthetic source/dependency changes, deletions, renames, metadata
and vector corruption, interruption/resume, owner overlays, measured-filter
boundaries and input/contract changes. Native 316-asset fixtures checked lazy
pages, detail, keyboard handlers, resizing and a live STDIO/GUI publication
update. Enlarged real GUI and all-mode actual GUI/MCP checks: **passed /
passed**. Full original SHA-256/size/mtime and protected pilot
field/image checks: **passed**, 4938
source entries. No-change processing/publication: **passed**, no
render/caption/embedding inference. Test receipt counts overlap and are not
added as distinct tests. Exact receipts and remaining limits are versioned in
docs/step8-verification.json.

Application/check faults were corrected with their original receipts retained:
native GUI membership lookup and narrow-header overflow; stable SQLite content
comparison for no-change publication; Windows native-library initialization
before the worker input thread; and Windows manifest file-sharing races. These
were application/test defects, not retries/repairs of faulty original assets.
No owner caption/artistic/usability/accessibility approval is granted by these
technical checks. Reopen the app/restart pre-update MCP connections. Checked
local commit only; no push. Step 9 remains optional and unimplemented.

| Pack | Assets | Inspected | Valid captions | Caption failures | Complete / partial index | Notes / warnings | Source faults | Owner pending |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| kenney_car-kit | 50 | 50 | 17 | 33 | 17 / 33 | 2 / 2 | 5 | 50 |
| kenney_city-kit-roads | 95 | 95 | 44 | 51 | 44 / 51 | 2 / 2 | 8 | 95 |
| kenney_food-kit | 200 | 200 | 111 | 89 | 111 / 89 | 3 / 2 | 55 | 200 |
| kenney_furniture-kit | 140 | 140 | 86 | 54 | 77 / 63 | 2 / 1 | 33 | 140 |
| kenney_mini-forest | 22 | 22 | 11 | 11 | 11 / 11 | 1 / 3 | 3 | 22 |
| quaternius_ultimate-food-pack | 103 | 103 | 65 | 38 | 65 / 38 | 3 / 1 | 0 | 103 |
| quaternius_ultimate-house-interior-pack | 123 | 123 | 72 | 51 | 72 / 51 | 1 / 2 | 1 | 123 |
| quaternius_ultimate-nature-pack | 150 | 150 | 108 | 42 | 108 / 42 | 2 / 1 | 1 | 150 |

Bulk coordinator elapsed: **4.27 hours**, within the revised
4–6-hour processing estimate. Measured final query ranges, including startup and
GPU handoffs: `{"gui": {"minimum_seconds": 2.7506359000108205, "maximum_seconds": 13.873629799985792}, "mcp": {"minimum_seconds": 2.786964699975215, "maximum_seconds": 14.27538479998475}}`. Native next-page time was
**0.593 seconds**; the window remained available during search.
The older two-second warm-search target is not met by these enlarged queries.
Original failed application/test receipts remain retained, including the base
runtime without Pillow and an incomplete interruption-status fixture. The
prepared-runtime suite passed 197 tests, and the corrected
interruption-status subset passed separately.

Caption failures are generation/schema failures, distinct from visual review
notes and warnings. Retained attempt evidence contains 322 word-length errors,
46 identity/certainty inconsistencies and two suggested-use errors. Those are
attempt-reason occurrences, including preserved historical pilot attempts,
rather than 370 newly failed assets. The index retains 369 failed description
jobs and 31 failed image jobs separately from its 4,344 successful vectors.
All 883 assets retain usable partial results. Source-fault flags affect 106
assets; detailed evidence contains 137 overlapping-face findings and one missing
texture reference. These faults and their original evidence remain visible.

Measured caption GPU peaks were 4.407 GiB allocated / 4.514 GiB reserved;
embedding peaks were 0.910 / 0.957 GiB. Caption process peak sampled RSS was
4.685 GiB. Leases serialized inference; cooperating owned workers unloaded for
queued peers, and final GUI/MCP verification workers exited cleanly. Final
unique project allocation was 6,868,475,992 bytes (6.397 GiB), about 0.764 GiB
above the before-bulk receipt, below both the approved growth and total limits.
No new runtime, dependency, weight copy, source copy or destructive cleanup
was needed. No further full-library accuracy/owner approval is inferred.

## City Kit addition — October 12, 2026

The separately approved import added City_Kit_Suburban (40 assets) and
City_Kit_Commercial (41), publishing **964 assets across ten packs**. All 81 new
inspection/preview stages completed, producing 252 rendered images and 333
successful image-search vectors including supplied thumbnails. Description
generation was explicitly skipped; all 81 captions and their text vectors remain
eligible for later processing. Existing unchanged caption failures were retained.

The importer now supports `--skip-captions` and a bounded per-run peak reserve.
Ungenerated captions display as pending, and absent text inputs do not create
failed vector jobs or prevent publication. Fifty focused tests passed. Desktop
and actual STDIO MCP access agreed for both new packs; every new asset's detail
and preview was checked. All original source files and existing downstream
results/vectors/owner corrections remained intact; the scan refreshed one older
fence's inventory metadata. Twelve new assets retain overlapping-face source
fault evidence and usable previews, with no new processing failures or repairs.

Unique allocated storage grew by **133.4 MiB**, to **6.610 GiB**, under the
500 MiB import allowance and existing 8 GiB total ceiling. Source assets and
shared models remain external and read only. The complete report, visual review
and preservation/access/storage receipts are linked from
[City Kit import](city-kits-import.md). Owner artistic/physical-scale and
alternate-format equivalence approval remains separate and pending.

## Caption minimum reduced — October 12, 2026

The approved change lowers description validation to **10–170 words**, retaining
the existing identity, uncertainty, field, visual-attribute and prohibited-claim
checks. `prompts/caption-v3.txt` is active for future full-library jobs and permits
concise 10–30-word descriptions for simple assets. Historical v1/v2 prompts and
generation records remain unchanged. Completed captions retain their recorded
prompt version for cache checks; jobs needing new generation use v3 and its
fingerprint. Switching the default prompt does not request regeneration.

All **81 focused tests passed**, including 9/10/59/60/170/171-word boundaries and
completed-v2 cache preservation. A before/after comparison verified **1,809
protected files** unchanged, covering historical prompts, caption records,
corrections, catalog/index files and job ledger. Actual dry-run counts remain
514 completed captions retained, 369 failed captions retained and 81 pending.
No model inference, caption recovery/revalidation, asset processing, catalog
publication or dependency/model installation occurred. Evidence is under
`data/caption-minimum-10/{before,preservation}.json` and `tests.xml`.
Focused synthetic test fixtures and receipts used about 11 MiB of file content,
above the preliminary under-5-MiB estimate; no runtime, model or asset copy was
introduced.

## Manual overnight description runner — October 12, 2026

The approved preparation created **Generate overnight descriptions.cmd** and a
resumable coordinator using the existing locked offline caption/embedding
runtimes. Its real-catalog dry run selects **450** assets (81 pending and 369
caption faults), skips 514 usable captions, and reports no input faults. It uses
the active v3/10–170-word rule. **No real model inference was started.**

Each asset gets at most one generation attempt per run. Saved responses can be
committed after interruption without generating again; interrupted attempts with
no saved response become visible faults. Existing captions, owner corrections,
prior attempt evidence, renders and image vectors are protected. Description-only
indexing and checked catalog/index publication follow generation. Morning reports
separate caption, indexing and worker faults, and link to raw attempts/logs.

The runner owns the catalog operation/GPU leases, temporarily keeps Windows awake,
and applies a 180-second progress watchdog only to its owned wrapper/process tree.
Live orphan workers block unsafe resume. Unique-allocation receipts precede bulk
work, follow batches and surround publication, with a 500 MiB growth limit and the
existing 8 GiB total ceiling. No installation, model/source copy or cleanup runs.

Preparation verified 93 focused tests across the related suite and added
coordinator/report checks, real offline wrappers, owned-tree watchdog behavior,
and the actual launcher dry run. A hash comparison found all **1,809 protected
files unchanged**, including the actual catalog/index, caption records, corrections,
job ledger and historical prompts; all 4,163 existing image vectors remain.
Failed/corrected test receipts remain retained. Estimated actual run time is
1.5–3 hours for current membership; accuracy still requires later review.
See [overnight instructions](overnight-descriptions.md) and
`data/overnight-descriptions/` for preparation evidence and future run reports.

## Approved texture repair run — October 14, 2026

The owner approved repairing the texture/material bindings of the 648 blocked
new models, using supplied textures and library overrides while preserving
originals and prior evidence. The audit found 599 supported candidates (429
Generic, 105 CraftPix, 65 Synty); 49 unresolved mappings stay visibly faulty.
Twelve representatives passed technical rendering/contact-sheet checks, including
an additional supplied-alpha correction for ivy. The finalized focused suite
passed 73 synthetic tests, with additional handoff/retrieval compatibility checks.
Bulk rendering and image indexing finished: 594 recovered models, 49 unresolved
mappings and five retained preview-quality failures. All thirteen final contact
sheets were inspected. Nineteen recovered models retain pre-existing overlapping
face faults. Preservation and live MCP detail/image-search checks passed. The
594-model description run `8a5f127aa1fe475a8edeed0c7fd5136f` is running in the background,
with automatic final publication/verification. No new runtime/model, original copy, geometry repair,
Godot effect reconstruction, or unrelated caption-fault retry is included.

The approved repair allowance is 2 GiB additional unique allocated storage and
the existing 10 GiB total ceiling. Baseline/evidence and current outcomes are in
`data/texture-repairs/20261014/`. Recovered previews are indexed/published first,
then an explicit recovered-ID description run continues in the background. The
completion receipt verifies preservation and separates remaining texture and
caption faults. Owner accuracy/artistic approval remains pending. See
[texture repair instructions](texture-repairs.md).
