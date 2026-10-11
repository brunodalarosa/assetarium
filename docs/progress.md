# Progress

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
