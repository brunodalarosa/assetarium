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
