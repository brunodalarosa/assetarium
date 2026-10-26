# Progress

## October 26 — Excluded folders, duplicate export folders, folder variants, branch `feature/cpu-search-embedder`

[Decision 0019](decisions/0019-source-folders-and-export-variants.md), approved at the scope/plan
checkpoint by the user of this checkout.

- **Excluded folders** per source (`source.json` `excluded_folders`; `catalog.excluded_folder`,
  `walk_source` prunes and records `excluded_folder` rows with file counts).
- **Suggestions and answers.** `catalog.export_candidates` (sibling folders with equal sets of
  ≥3 unique model stems) and `group_models` (answers bound to anchor, folders and name-list hash;
  reference identity kept; `confirmed-sibling-export-v1` evidence). `sources.decide_export`,
  `forget_export`, `set_excluded_folders`; status carries `export_suggestions` and
  `excluded_folders`.
- **Variants.** `catalog.file_variants`; `resolved_detail(..., source_variant)` with a stable
  default (rendered file, reference folder, recognized folders); `get_asset` `source_variants` /
  `source_variant`; inspector label.
- **UI and CLI.** Source row section (suggestions, saved answers with Undo, exclusion chips),
  Asset processing line, bridge `source_exclusions` / `source_export` / `source_export_undo`,
  `sources exclude|include|exports`. `ui/build/` rebuilt.
- **Verification.** Full suite 657 passed, 2 skipped (`Real-Blender tests: 5 passed`), with
  `tests/test_source_exports.py` (8 tests). WebView2 `scripts/verify-source-folders.py`
  (`data/gui/source-folders-2026-10-26c/`; the fixture bridge runs scans in-process because the
  fixture project has no runtimes) and `verify-general-settings.py` passed. Real rescans gave
  suggestions for Medieval Weapons (Unity FBX), Low Poly Nature (OBJ + Unity FBX, 3,300 names) and
  Medieval Megapack (Unity FBX); none were answered. MCP `source_variant` checked on a real asset
  (`data/evidence/source-folders-2026-10-26/report.json`).
- **Found, not changed:** `Low Poly Nature - Extended` scans take ~514 s although walking its
  16,504 files takes 4.5 s; the rest is in inventory building or scan merging.

## October 25 — Scan cache size bound, branch `feature/cpu-search-embedder`

`Low Poly Nature - Extended` (16,504 files) showed **Scan fault: Managed manifest exceeds its
bounded size**: its `metadata-lal/library/scan-cache.json` was 5.76 MB and `read_json` caps app
JSON at 4 MiB, so every rescan after the first failed. `read_json(path, limit)` now takes a
caller bound; only the scan cache uses `SCAN_CACHE_LIMIT` (256 MiB, about 750,000 files). New
tests in `tests/test_manifest_bound.py`; full suite 649 passed, 2 skipped (`Real-Blender tests:
5 passed`). The real rescan succeeded in 544 s (full re-hash after the unreadable cache) with
9,900 assets pending and no faults. No storage change.

## October 25 — CPU search embedder and AMD end to end, branch `feature/cpu-search-embedder`

[Decision 0018](decisions/0018-cpu-search-embedder.md), approved at the scope/plan checkpoint by
the user of this checkout (owner review pending before any upstream merge). Machine: Ryzen 9
9950X3D, Radeon RX 6800 16 GB, 31 GB RAM, Windows 11; no NVIDIA GPU.

- **CPU embedder.** `embedding_cpu.py` (same EmbeddingGemma revision, prompts, preprocessing,
  BF16 and normalization; own contract with device, adapter, base-adapter and lock hashes plus
  `hashed_files` for the LF/CRLF rule in `retrieval.recorded_contract`). `search_device` setting
  (`cuda` default, `cpu`) in `settings.py`, chosen in `engines.embedder`/`embedder_contract`; the
  search worker's contract request goes through `engines`. `embedding_backend.py`, caption and
  Blender worker files are byte-identical to `develop`.
- **CPU-only lock.** `runtime/embedding-cpu/` (Torch/torchvision `+cpu`, every other pin equal),
  synced into `.venv-embedding` by the same wrapper; `prepare_embedding_model.py --device cpu`.
- **Fresh installs.** `scripts/record-embedding-capability.py` records the search check from two
  of the library's own previews (sources' working records). The search stage stops with that
  command as its reason while the receipt is missing or for the other device; a dry run counts
  against the receipt's contract (first run, device switch). Stage environments follow the
  settings (`source_operations.stage_runtime`): local-server descriptions run in `.venv-mcp`, CPU
  search uses the CPU lock; the CLI stage command and overnight workers use the same helper.
- **Setup and UI.** Settings → General → Search card; wizard step "Descriptions and search" with
  per-device checklist (`environment_report.search_devices`) and a first-run CPU suggestion
  without NVIDIA BF16; `apply_setup` and `settings set --search-device`; agent panel label.
  `ui/build/` rebuilt.
- **Measured.** CPU probe: 1.10 s per image and 0.033 s per text vector in BF16, cosine ≥ 0.998
  to FP32 (`data/evidence/cpu-embedder-probe-2026-10-25/`). Medieval Weapons pack (64 logical
  assets): previews 209 s; 32 Unity FBX duplicates recorded as import failures (kept, not
  retried); 97 image vectors at 1.13 s each; 32/32 descriptions through llama.cpp b11870 Vulkan on
  the RX 6800 with Qwen3-VL-2B F16 at 3.9 s per asset; MCP search 0.02–0.09 s after a 6.4 s first
  query (`data/evidence/cpu-embedder-e2e-2026-10-25/`).
- **Verification.** Full suite 648 passed, 2 skipped (`Real-Blender tests: 5 passed`), with
  `tests/test_cpu_embedder.py` (10 tests). WebView2: new `verify-search-device.py`
  (`data/gui/search-device-2026-10-25b/`), `verify-general-settings.py`,
  `verify-setup-wizard.py` (readiness check updated for the separate search list;
  `data/gui/setup-wizard-2026-10-25-cpu-r3/`) and `verify-agent-setup.py` passed.
- **Storage.** Receipts `data/storage/2026-10-25-cpu-embedder-before.json` (207,869,096
  allocated bytes) and `…-after.json` (1,463,004,608): the CPU search runtime, base and app
  environments, frontend `node_modules`, evidence. Outside the project: 5.53 GB under `C:\AI`
  (EmbeddingGemma 1.53 GB, Qwen F16 GGUF 4.07 GB, llama.cpp 0.13 GB), 10.8 MB `metadata-lal`.
  `uv cache prune` found nothing to remove; the npm cache (`cache/npm`) is kept for offline rebuilds.

## October 25 — Beta cleanup before sharing the repository, branch `linux-support`

Owner-approved cleanup from the beta audit (all items, internal plumbing included); license
decided by the owner. Nothing in originals, model storage, decision rationale, caption prompts,
evidence or environments was removed; inspection/caption/embedding fingerprints are unchanged.

- **License (decision 0017).** AGPL-3.0-only with a Contributor License Agreement;
  `license = "AGPL-3.0-only"` in `pyproject.toml` (lock unchanged), README section. The CLA text
  is drafted in its own session/branch for owner review.
- **Onboarding.** One MCP setup path: the app's agent panel or `register-mcp.py --snippets-only`
  (now writes ignored `data/mcp/clients/`; no OpenCode default path); tracked `docs/mcp/clients/`
  are neutral examples. README: all eleven MCP tools, 3D + images scope, license, links to the new
  [`status.md`](status.md) and [plans index](next%20version%20plan/README.md); dead
  `plan/PROJECT.md` links fixed. Completed plans/prompts marked historical (handoff header
  corrected). Supersession notes on decisions 0007, 0008 and 0011. Owner machine paths removed
  from instructional docs, CLAUDE.md and the roadmap prompts (historical records keep theirs).
  Startup fault dialog and keep-awake name say Assetarium.
- **Library destination hidden** from the rail until a library browser exists (0011 note).
- **Dead code.** Unused beUI `AnimatedBadge`, unused easing/pointer exports; `ui/build/` rebuilt.
  The KayKit comparison research site moved out of the repository to ignored `data/archive/`.
- **Historical scripts.** 34 pilot/benchmark/one-time/owner-machine scripts moved to
  [`scripts/historical/`](../scripts/historical/README.md) (only the root lookup changed);
  current docs point there.
- **Neutral library policy.** `library_policy.py` replaces `docs/library-membership.json` as the
  live membership/budget default (registered sources; same 10 GiB / 3 GiB numbers). The old
  contract is evidence in `docs/history/`; an older install's own file is still honored. The
  overnight contract now hashes `library_policy.py` (runs started before this change must be
  restarted, as for any code change).
- **Model preparation** checks the shared unique-allocation accounting (`measure_all`) against
  the saved storage budget instead of logical folder sums and historical budget fields.
- **Hash cache.** Synthetic verify scripts use `scratch/hash-cache/` (`isolate_hash_cache`);
  `verify-library-gui.py` builds its fixture in `scratch/`; `scripts/prune-hash-cache.py` drops
  records of missing files. `verify-layout-revamp.py` now uses the shared harness.
- **Local storage.** Receipts in `data/maintenance/`: uncommitted GUI fixture copies retired
  (181 MiB, manifests kept; reports/screenshots kept), inactive WebView profiles (254 MiB),
  bytecode caches (143 MiB), scratch cleanup (96 MiB, 43 folders). `node_modules`, llama.cpp
  tools and the uv cache were kept.
- **Checks.** Full suite 638 passed, 2 skipped, real-Blender 5 passed
  (`data/evidence/beta-cleanup-pytest-r1.txt`); `check-engine-stability.py` against HEAD code:
  0 differences (`data/engines/beta-cleanup-after-2026-10-25.json`); check-config and doctor
  passed. WebView2/STDIO checks passed: `verify-layout-revamp` (`beta-cleanup-layout-r2`),
  `verify-mouse-navigation`, `verify-setup-wizard`, `verify-agent-setup`, `verify-agent-setup-mcp`,
  `smoke-headless` (its embedding fault is the designed one) — log
  `data/evidence/beta-cleanup-verify-r1.txt`. **Open fault, pre-existing:** `verify-library-gui.py
  --synthetic` fails its grid ArrowRight focus check with the HEAD bundle too
  (`beta-cleanup-library-gui-headbundle`); not caused by this cleanup, left for a separate fix.
- **Not done here.** The `LICENSE` text file (needs the official AGPL text downloaded with owner
  permission); pruning `cache/file-hashes.sqlite` (two agent MCP servers held it open — run
  `scripts/prune-hash-cache.py` with clients stopped). Git history still contains earlier
  machine paths. Storage: 8.890 → 8.318 GiB allocated (`data/storage/beta-cleanup-before-20261025.json`,
  `beta-cleanup-after-20261025.json`).

## October 25 — Consistent loading states, branch `linux-support`

Approved in chat: one elegant loading language across the app, with skeleton ghosts for content of a
known shape, an inline sheen for refreshing content and a top-bar indicator for background work that
includes preview loading. No mockup step (owner's choice). Frontend only; see
[docs/gui/README.md → Loading states](gui/README.md).

- **Ghosts.** `frontend/src/ui/Loading.tsx`: `Skeleton` (one shared shimmer clock plus a per-element
  offset, so a grid shimmers as one diagonal wave), `useShownWhile` (shown after 150 ms, kept at least
  400 ms), asset/collection card and inspector ghosts. Used by the asset grids (Home, collection,
  source browser with a ghost row while more load), the Collections tab (which used to look empty
  until its first answer), cover tiles and thumbnails, inspection, the open collection's name,
  description and count, Asset processing (counts, coverage, source cards, failures summary),
  Settings → Asset sources, the collection flyout and tags. Empty states now wait for an answer
  (`sourcesLoaded`), so "No asset sources yet" no longer flashes at startup. Cards and pages enter
  with a short stagger/fade; thumbnails resolve from a blur.
- **Refreshing.** Searches dim the cards they will replace and sweep a sheen across the search bar
  (Home, a collection, the Collections tab); background refreshes do not dim. The spinner is now
  a single comet ring.
- **Background activity.** `frontend/src/ui/Activity.tsx`: a pill left of the bell for startup,
  search preparation/model loading (desktop `changes.worker`), source scans/processing/descriptions
  with progress, and queued previews (`state.previews`); a list on click, source rows open Asset
  processing at that source, a check before it leaves. It replaced the bell's pulsing dot.
- **Fix found by the checks.** The source Enabled switch now shows the click at once
  (`sourceAction("enabled")` patches the shown source before the reload corrects it); before, a
  second click during the reload repeated the first choice, which made `verify-source-ui.py` flaky
  with the new rendering.
- **Checks.** `tests/test_ui_encoding.py` + `tests/test_desktop.py`: 77 passed. New
  `scripts/verify-loading-states.py` (real WebView2, synthetic, bridge calls held in the page,
  light/dark screenshots, quick-load no-flash, activity-panel fit and reduced-motion checks) passed:
  `data/gui/loading-loading-states-20261025-122030/`. Earlier attempts in the same family are kept
  (test-script fixes, plus an activity panel whose rows overflowed it, fixed in the UI).
  Existing WebView2 checks passed with this work (the folder prefix `loading-` is this work's run
  naming): `search-ui`, `collections`, `layout-revamp` (`…-20261025-121519`), `notifications`
  (`…-122030`), `library-gui` (`…-121813`, real library), `source-ui` twice
  (`data/gui/source-settings-bd86b1b306`, `-84063ab021`), `general-settings`
  (`data/gui/general-settings-a2c0d8a4ce`); `image-browser`, `mouse-navigation`, `show-in-explorer`
  (`…-120143`, on an earlier build of this work). `search-ui` first failed because the minifier merged
  the spinner's reduced-motion rule into the new one; the rule now stands apart.
  `verify-source-browser.py`'s narrow-overflow assertion fails when it runs right after the
  real-library `verify-library-gui.py`, on the original code too (`data/gui/loading-library-gui-20261025-121246` then
  `loading-source-browser-20261025-121246`, both on stashed original code); it passes on its own
  (`data/gui/loading-baseline-source-browser` original, `loading-source-browser-rerun1` this work). That is a pre-existing resize race, left as is.
  Full suite not rerun (frontend-only change). No storage receipt: no dependencies or models;
  `ui/build/` grew about 18 KiB.
- **Owner tweaks after trying it.** The top bar no longer shows the "Assetarium" label outside a
  collection, and Home's search hint reads "Search your whole asset library".

## October 25 — Mouse back/forward buttons, branch `linux-support`

Approved in chat: a mouse's dedicated back (button 3) and forward (button 4) buttons act like the
rail's Back/Forward arrows; no remapping support, no setting.

- **UI.** `useGlobalKeys` in `frontend/src/App.tsx` listens for `mouseup` of buttons 3/4, calls
  `goBack`/`goForward` and suppresses the web view's default; ignored while setup is open or a
  3D preview is fullscreen. `ui/build/` rebuilt.
- **Verification.** `scripts/verify-mouse-navigation.py` (real WebView2, synthetic source, no
  model) passed: `data/gui/mouse-navigation-1/verification.json`. `tests/test_ui_encoding.py` and
  `tests/test_desktop.py`: 75 passed. Not run on the Linux web view; the DOM button numbers are
  the same there but unverified. No dependency or storage change (bundle only).

## October 25 — Show in Explorer asset menu action, branch `linux-support`

Approved in chat: the menu item reveals the format open in the inspector, otherwise the primary
file; Windows only for now (decision 0013).

- **Backend.** `DesktopService.reveal` locates the original through `config.source_file` (no
  hashing, no client path); `DesktopBridge.reveal` / `source_reveal` launch
  `explorer.exe /select,<path>` through `desktop.show_in_explorer` (no shell; refuses off Windows).
  `SourceBrowser` routes `reveal` to its own source.
- **UI.** **Show in Explorer** in the asset menu of the library, source and collection grids;
  a fault shows a toast. `ui/build/` rebuilt.
- **Checks.** Three new tests in `tests/test_source_browser.py`; targeted suites
  (`test_desktop`, `test_source_browser`, `test_collections`, `test_ui_encoding`) 97 passed.
  Real WebView2: `scripts/verify-show-in-explorer.py` (`data/gui/show-in-explorer-v2`, passed; Explorer
  stubbed, `-v1` kept as the first attempt, which asserted before the worker thread ran) and
  `verify-collections.py` (`data/gui/collections-show-in-explorer-regression`, passed). Full suite
  not rerun. No storage receipt (no dependencies or models; `ui/build/` grew about 1 KiB).

## October 25 — Agent-assisted setup through MCP (milestone 3), branch `linux-support`

The owner approved the milestone 3 checkpoint in chat on October 25 with every recommended
default, then corrected one: `apply_setup` also takes the description engine and its local
model server, so agents can find a setup that works on the computer in front of them. Built
on `linux-support` (not a separate branch) and committed there at the owner's request; not
pushed. See [decision 0016](decisions/0016-agent-setup.md).

- **Backend.** `setup_agent.py` wraps `setup_core`: setup session in
  `data/library/setup-agent.json` (60 minutes; opened only by the app's buttons or an
  interactive `local-assets setup agent`), Blender proposals (pending / applied / rejected /
  superseded / failed; Apply re-checks in the applying process and refuses a changed file),
  bounded status, client snippets, and connection records `data/mcp/connections/<pid>.json`
  that count only while the process is alive. New lease resource `setup_agent`. Notices
  `setup_changed` (one per session) and `setup_proposal` (removed when decided).
- **MCP.** Tools `get_setup_status`, `validate_blender`, `apply_setup`, `propose_setup`,
  `finish_setup` (schemas in `mcp_assets.SCHEMAS`, per-tool annotations, 16,000-character
  cap, `calls.jsonl`); refusals are `{"status": "refused"}`. Prompt `set_up_assetarium`
  (SDK 2.3.0 `on_list_prompts` / `on_get_prompt`) and a setup hint in the instructions until
  setup is completed. A configuration that does not load now starts a setup-only server
  whose one tool returns the fault, the file and the exact fix (it used to exit).
- **App.** Welcome offers **Set up with my agent** and **Set it up yourself** as equal cards
  (its footer is gone); the agent panel shows the session countdown and End access,
  per-client snippets, Copy setup prompt, the live connection line, the privacy note, values
  with *Set by agent* / *Set by you* / *Proposed by agent · approved by you*, the proposal
  card and Review choices; the review saves as the user's only what the user changed.
  **Settings → General → Run setup with my agent**. A notice's toast now disappears when its
  notice does, so a decided proposal never keeps a Review button.
- **CLI, skills, snippets.** `local-assets setup agent | agent proposals | agent end`
  (interactive only). New user-invoked skill `skills/assetarium-setup/`; the
  `local-asset-library` skill no longer hardcodes this machine's root. `register-mcp.py
  --snippets-only` writes `docs/mcp/clients/` (every tool in `enabled_tools`,
  `tool_timeout_sec = 180`); `codex-setup.toml` / `opencode-setup.json` are left as recorded.
  **The owner's existing Codex config needs the five setup tool names added to
  `enabled_tools`.**
- **Tests.** **613 passed, 2 skipped → 630 passed, 2 skipped**; real-Blender tests 5 ran.
  New `tests/test_setup_agent.py` (16): schemas/annotations, every write refused without a
  session and after expiry (injected clock), apply validation and attribution, proposal
  pending → reject → apply, changed file refused, unconfirmed re-render keeps it pending,
  `validate_blender` refuses other programs without running them, degraded mode and `main()`,
  connection create / client name / stale pid, bounded status that omits the project path and
  environment, instructions hint, snippets, interactive-only CLI, damaged record kept.
  `test_collections.py`'s write-tool set now includes the setup writes.
- **Linux.** WSL2 Ubuntu 24.04, `LAL_REQUIRE_BLENDER=1`, from a separate worktree
  `~/lal-m3` (the `~/lal` clone's own uncommitted files were left alone): **631 passed,
  1 skipped**, real-Blender tests 5 ran (`/home/bruno/blender-5.2.2-linux-x64/blender`).
- **Real STDIO.** `scripts/verify-agent-setup-mcp.py` passed 32 checks on an isolated
  project on Windows (`r4`) and Linux (`linux-r2`): setup-only server on a broken config,
  full flow with real Blender 5.2.2, propose → reject → apply, finish, audit lines, clean
  exits. Kept as evidence: r1 (discovered Blender needed no approval), r2 (script syntax),
  r3 (passed, but with a weak path check) and `linux-r1`, which found that check's weakness:
  the fixture's missing Blender sat inside the project and Windows JSON escaping hid the
  match. Status itself revealed only that configured Blender path, as designed; the fixture
  and the pytest check now compare raw and escaped forms. Reports: `data/mcp/agent-setup/`.
- **Real WebView2.** `scripts/verify-agent-setup.py --run-name agent-setup-r5` passed 17
  checks with a real STDIO client against the fixture: both paths, session opened by the
  click, waiting → connected with the client name, live values with attribution, notices,
  proposal card reject and apply (real Blender re-check), finish → review, a review edit saved
  as the user's while others keep *Set by agent*, End access refuses the next write,
  disconnect returns to waiting, manual path, Settings button. 14 screenshots (7 views, light
  and dark) in `data/gui/agent-setup-r5/`; r1–r4 kept (client never listed tools; badge
  selector; footer duplicate and stale toast found in review, both fixed). Existing scripts
  still pass: setup-wizard (its Welcome checks now expect the two cards), layout-revamp,
  search-ui, notifications, collections (`agent-regress-*-r1`) and general-settings.
- **Storage.** No dependency or model change. Receipt
  `data/storage/agent-setup-after-2026-10-25.json`: 9,753,672,200 allocated bytes (the
  milestone 2 receipt was 9,846,622,248; the reusable pytest folder was mid-rebuild). New
  evidence and fixtures are about 50 MB; still above the 6 GiB pilot target as before.
- **Awaiting the owner.** Visual and copy review of the panel, card and notices; one real
  agent (Codex or Claude Code) following `assetarium-setup` on a throwaway project root,
  recorded honestly. Limit stated in the decision: the session gate protects against tool
  calls, not against an agent given unrestricted shell access.

## October 25 — Setup Wizard v1 and inference ports and adapters (milestone 2), branch `linux-support`

The owner approved the combined checkpoint in chat on October 25 with every recommended
default: the wizard in the desktop app (built from the app's components) plus a terminal
version, ports and adapters for inference only, an experimental loopback local-server
engine as the route to AMD, and the llama.cpp Vulkan + Qwen3-VL-2B GGUF downloads for a
real check. See [decision 0014](decisions/0014-setup-wizard.md),
[decision 0015](decisions/0015-description-engines.md) and
[description engines](description-engines.md). Committed on `linux-support`; not pushed.

- **Setup.** `setup_core.py` (GUI-free rules) → `DesktopBridge` (`setup_state`,
  `setup_environment`, `setup_blender`, `setup_check_blender`, `setup_cancel_blender`,
  `setup_storage_use`, `setup_check_server`, `save_setup`, `skip_setup`,
  `choose_blender_executable`) → `frontend/src/ui/SetupWizard.tsx` (full-window overlay; the
  app behind it is `inert`), and `local-assets setup | setup status | setup blender
  check|set | setup skip`. Opens by itself only on a fresh install; Settings → General gets
  **Setup** (Run setup) and **Descriptions** (on/off, engine, server, Test connection); the
  budget help now states exactly what is counted.
- **`descriptions_enabled`** enforced in `source_operations` (refused; a running run stops
  after its batch), `incremental.process`, overnight runs and notifications; Asset
  processing shows the off state with **Open Settings → General**. Nothing is deleted or
  re-queued.
- **Ports and adapters.** `description_engines.py`, `engines.py` (single composition root:
  source operations, CLI, overnight script and the embedding worker switched to it),
  `engine_transformers.py`, `engine_server.py`. `caption_backend.py`, `caption_batching.py`
  and `embedding_backend.py` are byte-identical. A read-only dry run of the owner's 20
  sources before and after (`scripts/check-engine-stability.py`,
  `data/engines/before-engines-2026-10-25.json` vs `after-final-2026-10-25.json`): **no
  differences** in pending counts, pending IDs or completed-description fingerprints.
- **P0 first launch.** `tests/test_first_launch.py`: an empty project with the shipped
  example config starts every bridge view, the gateway and the page with no fault, writes no
  settings and opens setup. Fixed what the probe exposed: the startup scan with no sources
  started a worker (now `idle`), and a missing `.venv` failed with `[WinError 2]` (now names
  `uv.ps1 sync --locked`).
- **Real local-server check.** llama.cpp b11870 Vulkan x64 (SHA-256 matches GitHub) in
  `cache/tools/`; official `Qwen/Qwen3-VL-2B-Instruct-GGUF` at `52d6c8f…` (Q8_0 + mmproj F16,
  SHA-256 match publisher LFS) in `C:\BrunoOS\Local-models\qwen3-vl-2b-gguf\`. Through the
  ordinary caption stage on the RTX 5070 via Vulkan: `data/engines/llama-vulkan-r2/` 3/3
  valid descriptions (apple → “fruit”, crate → “cube”, tree → “tree”) in 7.1 s with
  `server-v1` provenance. r1 kept as evidence: the fixture's placeholder prompts produced 3
  invalid outputs, correctly recorded as failures and not retried.
  Receipt: `data/engines/llama-cpp-check-2026-10-25/downloads.json`.
- **Tests.** Baseline **574 passed, 2 skipped** → **613 passed, 2 skipped**; real-Blender
  tests **5 ran** (one new: the setup check against Blender 5.2.2). New files
  `test_setup_core.py` (18), `test_engines.py` (9, in-process fake OpenAI server),
  `test_descriptions_off.py` (7), `test_first_launch.py` (2), plus a CLI test. Three memory
  tests now expect the port's `MemoryLimitError`; one exact settings dict gained the new keys.
- **Real WebView2.** `scripts/verify-setup-wizard.py --run-name wizard-v1-r4` passed (fresh
  phase 22 checks, existing-install phase 8): auto-open only when fresh, focus to each step
  title, arrow keys in radio cards, failing and passing Blender checks, engine hints, skip and
  un-skip, Measure now, Test connection against a fake server (no generation), batch step
  “Not needed” for a server, Save writes `settings.json` + `setup.json` only, Skip setup,
  narrow window, Run setup pre-fills, re-render confirmation enforced, descriptions off hides
  Generate descriptions and the backend refuses it. 32 screenshots (16 views in light and dark) under
  `data/gui/wizard-v1-r4/`; r1–r3 kept (harness fixes: fixture lacked
  `scripts/storage-report.py`; an over-broad `inert` check). Existing scripts still pass:
  layout-revamp, search-ui, source-browser, notifications, collections (`wizard-regress-*-r1`)
  and general-settings.
- **Storage.** `data/storage/wizard-engines-before-2026-10-25.json` →
  `wizard-engines-after-2026-10-25.json`: **+146.6 MiB unique** (llama.cpp 100 MiB in
  `cache/tools`, GUI evidence, scratch fixtures). The 2.65 GB of GGUF files are in the shared
  models folder, outside the project. No Python dependency, runtime or lock changed.
- **Unverified / not done.** Any AMD GPU; Ollama and LM Studio; real keystrokes (keyboard
  was checked with dispatched events and focus); the native Choose executable… dialog; the
  setup wizard on Linux (no desktop app there; `local-assets setup` covers it, not run on
  Linux this session). `embedding_capability.py` still uses this project's pilot asset IDs,
  so a fresh install cannot record the search capability receipt (follow-up). **Owner
  visual and copy review is pending.**

## October 24 — Owner CLI on Windows and Linux; Linux v1 is CLI + MCP, branch `linux-support`

The owner decided in chat that Linux v1 is CLI-only (no desktop app; the Qt
milestone 1B plan is deferred) and approved the owner CLI with the recommended
defaults, asking that it work natively in Windows PowerShell too. See
[decision 0013](decisions/0013-platform-support.md) (updated) and
[Command line](cli.md). Nothing is committed or pushed.

- **Commands** (`owner_commands.py`, routed from `cli.py`; `process --stage` and the
  read commands keep their parser): `sources list|add|remove|enable|disable|images`,
  `process|describe --asset-source KEY [--follow]`, `cancel`, `settings show|set`,
  `failures`, `collections list|export|delete`, `--json` everywhere. Each wraps the
  backend call the desktop makes. `scripts/local-assets.ps1` / `.sh` run the CLI from
  the `mcp` environment (Pillow for PNG/Markdown exports); the base `uv` route works
  for everything else and explains that. `process` streams progress; Ctrl+C cancels
  safely, a second Ctrl+C stops watching. Source operations start in their own
  session off Windows, so a closed terminal or Ctrl+C never kills the work.
- **Owner-only deletions (tightened from the approved plan).** `sources remove` and
  `collections delete` need an interactive terminal and a typed `yes`, with **no
  `--yes`**: an agent with shell access must not delete (decision 0012). Replacing an
  existing export asks the same way; `--output` stays under `data/exports`.
- **Shared export code.** `collection_export.write_export` / `member_thumbnails` now
  serve both the desktop (`DesktopBridge._export`; PDF still printed by WebView2) and
  the CLI.
- **Tests.** Full suite Windows **574 passed, 2 skipped** (the file-symlink skip and
  the POSIX-only sleep test); Linux **575 passed, 1 skipped** (Windows junction);
  real-Blender tests 4 ran on each. New `tests/test_owner_commands.py` (7): routing,
  settings round trip and validation, sources enable/disable/images rescans,
  progress with Ctrl+C cancel-then-detach, finished-operation report, deletions
  refused without a terminal and confirmed with one, exports under `data/exports`.
- **End to end (CLI + STDIO MCP only).** `scripts/smoke-headless.py` now builds an
  isolated project under `scratch/smoke/<run>` (code copied, `.venv` hard-linked,
  `.venv-mcp` linked, nothing installed; the owner's library is untouched — its
  `sources.json` was last written October 23) and drives the wrapper: settings,
  sources add/list/disable/enable/images, process with real Blender (the unlinked
  embedding stage is recorded as a fault), refresh, failures, MCP `search_assets` /
  `get_asset` / `edit_collection`, collection export json/md/png, and the refused
  delete/remove. Passed natively on Windows (`data/smoke/cli-windows-r3/`; r1 and r2
  kept: a linked `.venv` was correctly refused by the storage boundary, then the
  fixture lacked `docs/library-membership.json`) and on Linux
  (`data/linux/cli-2026-10-24/smoke/cli-linux-r1/`). Real Ctrl+C on Linux (SIGINT to
  the CLI's process group): operation `cancelled`, 3 of 8 assets kept, nothing
  interrupted (`data/linux/cli-2026-10-24/sigint-check.txt`). Read-only commands also
  ran against the owner's real library in PowerShell.
- **Real WebView2:** `verify-collections.py --run-name cli-export-collections-r1`
  passed 22 checks including JSON/PNG/Markdown/PDF exports.
- **Storage.** `data/storage/cli-v1-after-2026-10-24.json`: **+22.1 MiB unique** since
  `linux-support-after-2026-10-24.json` (8.876 GiB; smoke projects under `scratch/`
  and GUI evidence). No dependency or model change.
- **Unverified.** A real Ctrl+C keystroke and closing the terminal on Windows (the
  child runs with its own hidden console; logic covered by tests); describe and the
  GPU path on Linux; PDF export from the CLI (desktop only).
- **Next step.** Owner review of the branch; the L6 case-matching policy question.

## October 24 — Linux support, milestone 1A (headless core), branch `linux-support`

The owner approved the 1A checkpoint in chat on October 24 with every recommended
default (WSL2 Ubuntu 24.04, no platform-marker or lockfile change, no CI, the
Blender worker shim, Windows reserved-name policy everywhere, scripts on
`load_project_config`, an ignored `config.local.toml`). See
[decision 0013](decisions/0013-platform-support.md) and [Linux](linux.md). Nothing
is committed or pushed; owner review is pending.

- **Portability.** `config.venv_python` and `config.runtime_command` replace the
  hardcoded `Scripts/python.exe` and `powershell.exe … -runtime.ps1` launches (MCP
  embedding worker, Process assets stages, CLI `process`, `library-batch.py`,
  overnight runs, `repair-textures.py`, `library_test_wire.py`); Windows paths and
  commands are unchanged (tests). New `scripts/uv.sh`, `mcp-runtime.sh`,
  `caption-runtime.sh`, `embedding-runtime.sh` (`*.sh eol=lf`).
- **Blender.** `inspection.blender_candidates` (configured, `PATH`, Program Files on
  Windows; `/usr/bin`, `/usr/local/bin`, `/snap/bin`, `/opt/blender*`, `~/blender*`
  elsewhere) never runs Blender and is listed by `doctor`. Off Windows Blender's
  `HOME`/`XDG_*`/`TMPDIR` are isolated in `scratch/`, and launches add
  `--python-expr` mapping `os.path.isreserved` to `ntpath`: Blender 5.2's Linux Python
  lacks it and every render failed, but the worker scripts are fingerprint inputs and
  stay byte-identical.
- **Real Linux bugs fixed** (not in the handoff): `os.path.isreserved` is Windows-only
  (config, sources and worker path checks crashed; now `ntpath.isreserved`, same
  policy); stage launches used PowerShell; `process_alive` treated an exited,
  unreaped child (zombie) as alive, hiding crashed operations (now reads
  `/proc/<pid>/stat`, never reaps); `storage-report.py` counted POSIX venv
  interpreter symlinks as faults (now `excluded_file_links`, Windows unchanged);
  `keep_awake` was a silent no-op (now `systemd-inhibit`, or a printed note).
- **Configuration.** `config.example.toml` is neutral (`models = "models"`, Blender
  discovered). The owner's ignored `config.local.toml` is a byte copy of the previous
  example; with it `check-config`, `doctor`, a headless `DesktopBridge` and the real
  STDIO server (`search_assets`, `get_asset`) load as before, and inspection dry runs
  show 0 pending on five processed sources (Blender path string and fingerprints
  unchanged). 45 scripts/helpers moved to `load_project_config`;
  `migrate-sources.py` (one-time, refuses reruns) keeps its explicit path. The
  overnight contract hashes the example, so an overnight run started before this
  change does not resume under its old contract.
- **Tests.** Windows baseline before editing: **562 passed, 1 skipped** (file
  symlinks unavailable). After: **567 passed, 2 skipped** — the same skip plus the new
  POSIX-only sleep-prevention test; no baseline test newly skipped or failing.
  Linux (WSL2 Ubuntu 24.04, glibc 2.39, ext4, Blender 5.2.2, `LAL_REQUIRE_BLENDER=1`):
  **568 passed, 1 skipped** (Windows junction boundary, already marked); the first
  Linux run (before L7) was 566 passed, 1 skipped with no failures. Real-Blender
  tests: **4 ran and passed on each platform** (new summary line). New tests: per-OS
  helper paths, neutral example, byte-identical Windows Blender command, discovery
  without execution, zombie liveness keeping the exit code, sleep-prevention notes.
- **Linux acceptance.** `uv.sh sync --locked` and `mcp-runtime.sh sync --locked`
  created both environments from the unchanged locks; `check-config`/`doctor` pass and
  find Blender. `scripts/smoke-headless.py --run-name linux-smoke-r1` passed: Process
  assets with real Blender rendered 6 previews, originals unchanged, the STDIO server
  answered keyword `search_assets` and `get_asset`. The image-vector stage is recorded
  as **not verified** (no embedding runtime: `uv run --no-sync` creates an empty
  `.venv-embedding` and the stage fails on `import numpy`; the same happens on Windows
  without that runtime — follow-up for setup readiness). `register-mcp.py` (portable
  venv, `--opencode-config`) registered a Linux entry with a throwaway `CODEX_HOME`
  and the server started from it. L7 probes: flock lease exclusive across processes,
  atomic replace with an open reader, identity change despite restored mtime.
- **Path semantics (L6, investigation only).** `scripts/investigate-path-semantics.py`
  on both platforms (`data/platform/l6-windows-r2/`, Linux copies below). Windows
  resolves every case/separator variant. Linux: wrong-case MTL/glTF texture references
  and case-ambiguous names are visible faults (scan `missing`, render failed);
  reserved names and `:` are rejected on both; FBX wrong-case textures resolve in
  Blender; glTF backslash URIs work. Two Linux gaps: a `map_Kd` path with `\` is
  available to the scan but Blender's OBJ importer cannot open it (render fault), and a
  wrong-case `mtllib` renders untextured and reports inspection complete while the scan
  records the MTL missing. **Policy question for the owner** (no behavior changed).
- **Evidence.** `data/linux/1a-2026-10-24/` (pytest first/final, L7 probes,
  `platform/l6-linux-r1` with an invalid flat-triangle fixture kept as evidence and
  `l6-linux-r2`, `smoke/linux-smoke-r1`, registration receipt, Linux storage receipts).
- **Storage.** Windows receipts `data/storage/linux-support-before-2026-10-24.json` →
  `linux-support-after-2026-10-24.json`: **−3.2 MiB unique** (8.858 → 8.855 GiB; the
  reused `scratch/pytest` shrank; still above the 6 GiB target as before). WSL disk
  on C: (outside the project): `ext4.vhdx` 4.51 GiB; 3.3 GiB used in the distro
  (Ubuntu, apt libraries, uv, Python 3.13, the clone with base and `mcp`
  environments: 0.46 GB unique, Blender 1.2 GiB unpacked; tarball removed).
- **Unverified.** GPU path on Linux (captions, embeddings, semantic/image search,
  image vectors); the Linux desktop app (1B); the owner's real Windows-authored packs
  on a case-sensitive filesystem; native Linux versus WSL2; distributions other than
  Ubuntu 24.04; overnight runs on Linux; `systemd-inhibit` with a real login session.
  No real-WebView2 script was run: `desktop.py` and the frontend are unchanged.
- **Next step.** Owner review of the branch and the L6 policy question; then the
  milestone 1B checkpoint (Linux desktop with the Qt backend).

## October 24 — Menu origin stays sharp; label and notes autosave

Owner-approved follow-up: the item a menu was opened from (asset card, collection
card or Export button) is no longer dimmed or blurred. The shield is now the window
minus the item's rounded outline (`clip-path: path(evenodd, …)`, 2 px margin); clicks
inside the hole reach the item, and a `ResizeObserver` moves the hole when the layout
underneath changes (verification caught a stale hole after the inspection panel
closed). Verification also exposed a real save gap: label and notes saved only on
blur, and Chromium can drop focus without a blur event, losing the edit. They now
also save 700 ms after typing stops and when the asset changes or the panel closes;
a save finishing mid-typing never overwrites the field.

- **Real WebView2:** `verify-collections.py` adds origin-hole hit tests, hole-follows-
  layout and autosave-while-typing checks; four consecutive passes
  (`data/gui/autosave-r1`…`r4`) and a final pass (`data/gui/origin-final-collections`).
  Earlier runs `origin-hole-r1`…`r21` are kept as evidence of the diagnosis.
  layout-revamp, search-ui, source-browser and notifications passed;
  `test_ui_encoding.py` + `test_collections.py`: 71 passed.

## October 24 — Context-menu miss-click protection (Collections follow-up)

The owner reported that clicks meant for a collection in the "Add to a collection"
flyout often landed on the asset card underneath, and approved this fix in chat.
Cause: leaving the menu row started a 260 ms close timer that crossing the gap
never cancelled, so a slow move lost the flyout; outside clicks also reached the
page. Now the flyout closes only after resting ~300 ms on another menu row, entering
it cancels any pending close, and an invisible bridge covers the gap. A shield under
every open menu dims (8% light, 20% dark) with a 1.5 px blur, swallows the outside
click and moves the menu when another card is right-clicked. The collection search
heading no longer flickers during background refreshes.

- **Real WebView2:** `verify-collections.py` gained gap/hover-intent, hit-testing,
  swallowed-click, right-click-move and frame-timing checks; passed twice
  (`data/gui/shield-final-collections2/`, `…3/`). Menu opening with the blur: mean
  7.8 ms, max 8.5 ms per frame, none over 25 ms; dim only: same. Regression:
  layout-revamp, search-ui, source-browser and notifications passed
  (`data/gui/shield-final-*`). The first final run failed on the heading flicker
  that is now fixed. `test_ui_encoding.py` and `test_collections.py`: 71 passed.

## October 24 — Collections, owner tags and agent collection tools, branch `collections`

The owner approved the scope in this chat on October 24 (labels per collection and
tags per asset as distinct concepts, WhatsApp-style batch removal, a search on the
Collections tab, red confirmations for every deletion, agents may create and edit but
not delete) and asked for the recommended defaults elsewhere. See
[decision 0012](decisions/0012-collections-and-tags.md). Owner usability review is
pending; nothing is pushed and no PR is open.

- **Backend.** `asset_collections.py` (create/rename/describe/add/remove/restore/
  set label and notes, summaries with content search, detail with availability:
  library, `source_only` or `unavailable` with the reason), `asset_tags.py`
  (app-wide tags), `collection_export.py` (JSON with absolute original paths and
  dependencies, PNG sample sheet, Markdown with thumbnails, printable report). Both
  stores are app-owned files in `data/library/` under a new `collections` lease;
  damaged files are reported and kept. Search and browse accept `collection` and
  `tag` filters. Agent edits raise one `collection_changed` notice per collection.
- **MCP.** New `list_collections`, `get_collection` (paged), `edit_collection`
  (no delete) and `tag_assets`; write tools are annotated non-read-only and
  destructive. `get_asset` adds `tags` and `collections`. Server instructions and
  `skills/local-asset-library/SKILL.md` explain that a collection is a bundle, not an
  asset. `docs/mcp/codex-setup.toml` and `register-mcp.py` list the new tools; the
  owner's existing Codex entry needs those names added to `enabled_tools` by hand.
- **Desktop.** Collections tab (cards with four covers and an Updated date, search
  over names and contents, New collection, right-click Open/Delete); collection view
  (name with rename pencil in the top bar, editable description, member-only search
  with owner text first, Select/Export, batch removal bar with Undo); one shared
  beUI context menu for every asset card (Inspect, Add to a collection flyout with
  find/create/tick, Remove from collection in a collection); inspection shows the
  collection label/notes and app-wide tags; red confirmation modal for deleting a
  collection and for removing a source; PDF printed by the app's WebView2.
  Internal "result grid" types in the store were renamed (`GridId`, `gridApi`) so
  "collection" means only the new feature; `window.lal` names used by verify
  scripts are unchanged. Bundle: 626 KB JS, 147 KB CSS.
- **Tests:** full suite **560 passed, 1 skipped** (188 s) before the last two
  collection tests were added; `tests/test_collections.py` now has 12 tests (store,
  undo order, availability after disable/remove, source-browser members, search and
  browse scoping, Collections-tab search, tags, damaged files, concurrent writers,
  agent tools without delete, exports and escaping, the desktop bridge round trip
  including keyword search inside a collection without loading a model).
- **Real WebView2:** new `scripts/verify-collections.py` passed 16 checks with 22
  screenshots (`data/gui/collections-r6/`), including the WebView2 PDF, the agent
  notice, unavailable members, red confirmations, dark theme and a narrow window.
  Earlier runs r1–r4 failed on test timing and one real bug (a member whose
  availability changed kept its old card) that was fixed; they are kept as evidence.
  All ported verify scripts still pass (`data/gui/col-regress-*`): layout-revamp,
  search-ui, source-ui, source-browser, notifications, general-settings,
  image-browser, interactive-preview, gui-truncation, library-gui `--synthetic`.
  Not run: scripts that read the installed library or load the GPU model.
- **Storage.** Receipts `data/storage/collections-before-2026-10-24.json` →
  `collections-after-2026-10-24.json`: **+64.6 MiB unique** (8.401 → 8.464 GiB,
  still above the 6 GiB pilot target as before). About 41 MiB is new GUI evidence
  and 21 MiB synthetic verification fixtures under `scratch/`; code and bundle are
  about 1 MiB. No dependency, runtime or model change.

## October 22 — Assetarium layout revamp (React UI), branch `layout-revamp`

The owner approved the scope in this chat on October 21: rebuild the desktop UI in
React to the Assetarium Figma handoff (`data/gui/figma-reference/`, light and dark
frames), preferring beUI components, with dark mode and **no suggestion chips**
(an owner correction over the mockup). Owner visual review is pending; nothing is
pushed and no PR is open. See [decision 0011](decisions/0011-react-desktop-ui.md).

- **Stack.** `frontend/` (React 19, TypeScript, Vite 8, Tailwind 4, motion 14,
  Lucide, Geist inlined as `data:` fonts). `npm run build` writes the committed
  `src/local_asset_library/ui/build/` (568 KB JS, 141 KB CSS); `create_window`
  inlines it, so launches never need Node. The old `ui/app.js`/`style.css` are
  removed; `ui/interactive-preview.js` and the sandboxed viewer are unchanged.
  The CSP gains only `font-src data:`. beUI sources are copied with their MIT notice.
- **Layout.** Rail with view history (Back/Forward), Home, Library and Collections
  (placeholders), Asset processing and Settings. Home: centred search, filters
  panel (nine filters, Reset/Apply, reference fields). Right sidebar: inspection
  only, resizable (remembered), hide/show keeps selection and tab, Overview /
  Sources / Evidence, floats over results on narrow windows. Notifications panel
  over any view; toasts share its actions.
- **Asset processing** (new page): per-source Process assets / Generate
  descriptions with progress and Cancel, run reports, published-library status and
  Refresh, and the importing failures report. Processing notices lead there,
  focused on their source; **View report** opens the run report.
- **Settings:** Appearance (Match Windows / Light / Dark), general settings, asset
  sources (Enabled switch, Include 2D images, browse, remove).
- **Backend (small):** `settings.interface_settings`/`save_interface_settings`
  (app-owned `data/library/interface.json`, separate from budget validation),
  `DesktopBridge.interface_settings`/`save_interface_settings`, the theme resolved
  before first paint (`desktop.page_html`, Windows app-theme registry read), and
  measured card facts (`format`, `triangles`, `width`, `height`) on thumbnails.
- **Tests:** full suite **546 passed, 1 skipped** (173 s). New tests cover
  interface preferences, damaged preference files, the themed packaged shell, card
  facts and the bridge round trip; the encoding test now covers `frontend/src` and
  the bundle.
- **Real WebView2:** new `scripts/verify-layout-revamp.py` passed 19 checks with
  21 screenshots in both themes (`data/gui/layout-revamp-final-20261022/`).
  Every DOM-coupled verify script was ported to the new UI through
  `scripts/gui_harness.py` and `window.lal`, keeping its checks, and passed:
  search-ui, general-settings, notifications, source-ui, source-browser,
  image-browser, library-gui `--synthetic`, interactive-preview, gui-truncation,
  and, read-only on the installed library, kaykit-gltf, gui `--render-only
  --caption-classification` and source-installed-ui (5,785 assets, 17 sources).
  Not run: `verify-gui.py` full mode (loads the GPU embedding model). The
  interactive-preview fullscreen focus check failed once and then passed twice;
  source-installed-ui failed once while the cold startup scan exceeded 90 s.
- **Storage.** Receipts `data/storage/layout-revamp-before-20261021.json` →
  `layout-revamp-after-20261022.json`: **+200.8 MiB unique** (8.205 → 8.401 GiB;
  the project was already above the 6 GiB pilot target). Mostly
  `frontend/node_modules` (133 MiB) and new GUI evidence (57 MiB). The npm
  download cache was cleaned (251 MiB → 0.1 MiB).

## October 20 — Expansion step 2: static 2D images technically complete

The owner approved step 2 in this chat, with these choices: per-source image opt-in
with folder-name purpose *suggestions*; SVG support (added by the owner, via
`resvg-py`); preprocessing chosen by Claude from a preregistered evaluation and
recorded for owner review; a three-folder Kenney pilot; descriptions for a fixed
40-image evaluation set only. Owner visual, relevance and description approval
remain pending. No commit, push or PR; step 3 not started.

- **Enrollment.** *Settings → Asset sources → Include 2D images* (per source,
  `import_types` in `metadata-lal/source.json`). The scanner (`image_catalog.py`, no
  decoding) makes one generic `image` record per folder + stem. Model dependencies
  and previews, pack `Preview`/`Sample` sheets, texture folders and
  atlas/tileset sheets stay out with visible inventory roles. Byte-identical
  copies are recorded, never merged. The purpose is always `generic_image`; a
  nearest folder keyword is only a suggestion. An unchanged image that returns after
  the setting is switched off/on resumes its published record.
- **Formats.** PNG, JPEG, WebP, BMP, GIF, TGA, TIFF and AVIF are decoded with
  Pillow 12.1, verified locally in every runtime, with the decoder pinned to the extension.
  Self-contained SVG renders with **`resvg-py==0.5.0`** (MIT; resvg Apache-2.0 OR
  MIT), added to `runtime/mcp` only (one 1.2 MiB wheel, no dependencies; +2.7 MiB
  installed) in an isolated 30 s child process. External `href`/`url()`/`@import`
  and XML entities are refused first; a probe showed resvg would otherwise read absolute local
  image paths. SVGs without a declared canvas get measured content bounds.
  Animated or multi-frame files are recorded `unsupported`; damaged files fail only
  their own asset.
- **Processing** (`image_inspection.py`, no Blender) measures size, alpha kind and
  coverage, colours, size class and aspect, plus a pixel-art display hint. It writes
  a thumbnail, an SVG display raster and a **model input** (`image-model-input-b-v1`:
  nearest-neighbour enlargement to at least 256 px, transparent pixels on flat
  rgb(82,82,82)). Both unchanged backends read that file, so `embedding_backend.py`,
  `caption_backend.py`, `caption_batching.py` and every 3D fingerprint stay byte-identical.
  The <16 px rejection no longer applies to tiny sprites. Only `image_media.py` and
  `svg_worker.py` are fingerprinted, so editing scanner rules never re-queues work.
- **Descriptions** use the new versioned prompt `prompts/caption-image-v1.txt`.
  A model batch never mixes 3D and 2D prompts; batching, GPU-memory stops,
  per-asset outcomes and notifications follow decisions 0007-0008.
- **Search and interfaces.** New `transparent` and `size_class` filters plus all
  image formats in shared validation; desktop and MCP agree. An image reference
  query uses the same model input as the index. MCP `get_asset` returns the original
  pixels as PNG with alpha kept; art under 256 px is enlarged with hard edges and
  says so. App: type badges, a mid-gray checkerboard (white and black icons both
  visible), and an image viewer with Fit / 1:1 / zoom / backgrounds / hard pixel
  edges (SVG re-rendered at the zoom level). Image detail lists facts, purpose,
  copies, the derivation and faults.

**Pilot** (read-only originals; Kenney All-in-1 3.7.0): `Icons/Game Icons/PNG`
(420 white and black transparent icons, 1x/2x), `2D assets/Tiny Dungeon/Tiles` (132
16-px tiles) and `Icons/Board Game Icons/Vector/Icons` (255 SVGs without declared
size). Process assets ran through the app's own operation path:
- Run 1: **807 images, 0 failures**, in 160 / 100 / 280 s.
- Run 2: the fingerprint narrowing reprocessed all 807, demonstrating invalidation.
- Run 3: unchanged; no inspection or vector work, about 50 s per source of runtime
  startup and no-change publication.

Rasters inspect at about 43 ms each, SVGs at about 0.6 s, and image vectors take
about 0.11 s each at 0.98 GB peak GPU memory. Each source raised one *Descriptions
ready to generate* notice; none started work.

**Preprocessing evaluation** (`data/verification/image-preprocessing-eval-20261020/`).
Thirty held-out queries were labeled before any result: Tiny Dungeon tiles from a
viewed contact sheet, icons from filenames the image channel never sees. Image-channel
MRR@10 was a 0.919, **b 0.911**, c 0.928. The preregistered rule (prefer b within
0.02 of the best) chose **b**. Candidate c (contrast backdrop) did better on tiny
tiles (0.909 vs 0.864), which is worth the owner's review.

**Descriptions (40-image set, real Qwen3-VL).** 39 valid, 1 recorded invalid
(empty `parts` for a plain floor tile; not retried), at about 1.4 s per image and
5.9 GB peak GPU memory. The AI review (Claude, against the viewed model-input pixels) recorded 54
findings and **no caption faults**:
- **Systematic:** the gray model-input backdrop is described as an asset colour or
  background in most icon descriptions (warning).
- **Identity errors (warnings):** white trophy → robot, blue potion and barrel →
  human figure, vial → microphone, axe → sword, chest → book, SVG bow/sword → "X".

An offline benchmark of a firmer wording barely helped (33/38 vs 35/39 still
mention gray or a background). The leakage comes from the opaque input, so changing
it needs an input-side decision; image-v1 remains active.

**Per-channel retrieval** (`data/verification/image-pilot-search-eval-20261020/`,
807 images, same labels):

| Channel | MRR@10 | Success@5 |
| --- | --- | --- |
| Filename keyword | 0.333 | 0.333 |
| Image | 0.911 | 0.967 |
| Description (39 described images only) | 0.796 | 0.900 |
| Combined (default) | 0.967 | 0.967 |

On the described subset, image (0.923) still beats description. Warm queries take
0.24 s; a cold model load takes 7.3 s. Real STDIO MCP and desktop agree on six
image queries plus a 3D query (`data/gui/image-search-agreement-20261020/`).
"blue potion icon" ranks the blue potion tile first, and the delivered MCP
ImageContent decodes to a 256×256 RGBA PNG whose SHA-256 matches the payload. That proves client delivery, not
any particular agent's visual inspection.

**3D preservation.** Read-only stage dry runs with the original code (git worktree
at `6a128ae`) and the new code are **identical for all 15 3D sources**: pending
work, retained results, pending IDs and embedding outcomes
(`data/verification/image-pilot-20261020/preservation-*.json`). Editing
`incremental.py` changes the overnight code contract; none was active.

Verification:
- Full suite **498 tests: 497 passed, 1 skipped** (privileged file symlink), 153 s
  (`data/verification/image-pilot-20261020/pytest-full.xml`). New tests are in
  `tests/test_images.py`; step 1 foundation tests were updated for applicable image descriptions.
- WebView2 `verify-image-browser.py` passed 9 checks
  (`data/gui/image-browser-20261020g/`); earlier attempts a–f retain the harness
  and UX defects found and fixed.
- `verify-source-browser`, `verify-notifications`, `verify-source-ui` and
  `verify-general-settings` still pass.

Harness and UX fixes made along the way:
- Lazy thumbnails needed scrolling in the check.
- The light checkerboard hid white icons.
- A damaged image showed "no substitute" and claimed pixel search; it now names the fault.
- Switching images off and on dropped processed images; returning assets now resume.

**Storage** (unique allocation; originals and shared models excluded):
- Project: 8,485,596,984 → 8,694,134,016 bytes after the pilot (+208.5 MB). This
  includes about 100 MB in the three retained publications, 24 MB of evaluation
  inputs and an 18 MB uv download cache kept for offline reinstalls (prune found
  no unused entries). A 22 MB baseline worktree was then removed.
- The final receipt (8,854,949,656 bytes) also counts reusable `scratch/pytest`
  and runtime temp.
- Pilot sources' generated data: 92.9 MB, including superseded run-1 derived
  images (a cleanup target, not removed).
- Receipts: `data/storage/step2-images-{before,before-pilot,after-pilot,final}-20261020.json`
  and `step2-images-pilot-sources-20261020.json`.

Known limitations:
- Pilot source keys are folder names ("PNG", "Tiles", "Icons"); source naming is
  existing behaviour.
- No license file sits inside the pilot folders (license evidence: unknown).
- Qwen3-VL 2B is weak on 16-px pixel art.

Next runnable scope:
- Owner review of pilot visuals, relevance labels, preprocessing choice b vs c,
  and the backdrop-leakage remedy for descriptions.
- Then `docs/next version plan/prompts/03-sprite-sheets-and-animation.md` with its
  own approval; the deferred sprite sheets already have visible inventory roles.

## October 19 — Shared project dependencies are a general processing capability

The owner approved a global fix and restoration plan with a 4 GiB growth ceiling
within the configured 24 GiB library budget. [Decision 0009](decisions/0009-general-capabilities.md)
requires every fix/capability to be reusable and independent of named sources;
[decision 0010](decisions/0010-shared-project-dependencies.md) defines shared paths.

`dependency_resolution.py` recognizes missing external glTF/GLB images at the same
complete project-relative path in another enabled source, including texture-only
providers without a model catalog. Healthy local files and explicit mappings win.
Different matching contents remain ambiguous; equivalent copies retain evidence.
Separate dependency reads verify the referring model, provider identity, contents,
enabled state, path containment and current conflicts. Ordinary source-file access
keeps its original restrictions. Rendering, byte audits, retrieval and interactive
preview use these verified bindings; originals and material/alpha settings remain
unchanged. The existing renderer and legacy repair worker remain byte-identical.

The live audit found 3,467 blocked models among 3,468 imported models: 5,266 missing
references all matched 16 supplied textures. Their bytes match the inventory;
no missing file was found for those failures. The same folder convention now works
without pack-specific mappings or code. Representative verification passed for
17 real models covering all 16 textures, including static renders, agent detail
with previews, four source keyword queries and a native WebView2 textured preview.
Owner appearance/selection approval remains pending.

The regression suite passed **488 tests**, with one privileged file-symlink case
skipped; Windows directory-junction boundaries passed separately. An earlier
restricted run retained five Windows permission failures, then passed with normal
permissions. Final combined-inventory/audit integration checks are recorded beside
that full run (**124 passed**, one file-symlink case skipped; overlapping counts
are not added). Disabled-consumer browsing compatibility is verified separately.
UI harness pagination/publication selection faults were corrected
with their earlier evidence retained; they were not asset processing faults.

At the owner's request, bulk restoration was **gracefully stopped** after the
current asset, with **128 of 3,467 targets rendered** and **3,339 remaining**.
No new processing failures were recorded. The first source's completed partial
results were published; no source processing operation remains active. Image
indexing for the newly rendered results has not started. Normal **Process assets**
can resume the remaining stages overnight and reuses completed inspections.

The stopped restoration is checkpointed under `data/verification/shared-dependencies/`:
`before.json` records 7,028 original hashes and 24,901 prior generated file hashes;
`plan.json`, sample reports, `api-report.json`, `ui-working-publication/report.json`,
regression XML, `processing.log`, `embedding.log` and `run.json` retain evidence.
The run reuses successful stages, preserves historical failures, generates no
descriptions and installs no runtimes/models. Unique allocation receipts cover
the project and source metadata. Full restoration/preservation completion must
be checked after a resumed run; this intentional stop is not full restoration.

## October 18 — Expansion step 1: shared asset foundation technically complete

The owner approved step 1's scope and implementation plan in this chat. This is
the expansion workflow in `docs/next version plan/`, independent of the historical
v1 step numbers. Owner acceptance remains pending; step 2 has not started.

- New candidate catalogs use SQLite schema 2, with `(asset_id, path)` file keys
  so parent/child records share originals. Readers retain v1 compatibility. No
  live catalog was migrated or republished for this work.
- `asset_structure.py` defines versioned model/image/audio types, explicit file
  roles, preview capabilities, stage applicability and relationships. Existing
  ordinary IDs stay identical; deterministic child IDs bind parent/source and an
  explicit stable selector. Unknown metadata and original evidence survive round
  trips. Candidate validation rejects broken parent/source links and relationships.
- An explicit working-copy migration sizes its reserve before copying, validates
  the candidate, switches only the working DB and retains failure receipts and
  candidates. Active-generation targets are refused. Tests cover budget refusal,
  successful migration, unchanged model fingerprints and interrupted replacement.
- The bounded PNG proof adapter decodes actual tiny synthetic images without
  Blender or original/image copies. Malformed inputs, decoder limits and changed
  or missing dependencies retain isolated faults and partial results. Audio and
  child extraction/playback/inference remain explicitly unsupported. Image
  captioning and real image-source enrollment belong to step 2.
- Shared GUI/MCP services expose type filters, bounded structure/relationship
  metadata, an image still view and type-aware preview defaults. Unsupported
  adapters report unsupported previews. No complete image browsing UI was added.
- Process assets still excludes captions. Missing/failed model descriptions with
  successful image vectors stay outside import work/failures, while description
  failure detail/counts and search fallback remain. Unsupported description
  capabilities do not generate ready notifications or start work. Existing
  batching, fingerprints, caches, worker ownership, GPU coordination, startup
  scanning and retention decisions remain intact.

Verification: **469 passed** in **205.23 seconds**, including **20** foundation
cases and existing synthetic/Blender/Windows link regression checks. The final
API subset also passed before the added decoder-limit case; these overlapping
counts are not added together. Eight enabled real sources passed read-only
keyword/type-filter queries through both desktop and MCP services, without a
model. Synthetic direct-image vectors demonstrate plumbing, not real semantic
relevance. Native UI/owner acceptance and new-media inference are not claimed.

The first preservation comparison passed for **2,985** publication, job,
settings and owner-correction files across the ten registered sources, plus
source/inspection/caption/description fingerprints in eleven representative
scopes (combined plus each source). The combined publication held **2,926**
assets. During the final recheck, **five Cartoon City sources appeared
concurrently**, changing `sources.json` and `asset-sources.json`. Those changes
were preserved. The final comparison records them explicitly: **2,983 original
files**, all baseline catalog counts and all sampled fingerprints still match.
Those five new sources are outside this step's validation; the final raw
whole-scope comparison therefore reports a difference rather than an unchanged
whole library.

Measured final unique allocation for the dedicated evidence/read cache and the
reusable regression directory was **169,885,176 bytes (about 162 MiB)**, within
the approved 100–250 MiB estimate. Of that, **2,933,048 bytes (about 2.8 MiB)**
belong to dedicated reports/read cache and **166,952,128 bytes** to reusable
synthetic regression fixtures. Continuous peak was not sampled, and this is not
a fresh whole-library storage audit or accounting for concurrent source work.
No dependency/runtime/model installation, original copy, bulk processing or
unrelated cleanup was performed. Existing runtime wrappers and retention apply.
Changing orchestration files changes the existing overnight plan code contract;
pre-update plans remain subject to that contract's normal validation.

Early verification faults were corrected with their evidence retained: two
compatibility defects, an initially nonmatching synthetic search fixture, and a
Windows helper stdin issue. The restricted link check passed with normal Windows
permissions. The final preservation helper records newly registered sources
without creating missing catalogs or starting work.

Evidence and reproducible commands: [foundation verification](asset-foundation-verification.json),
`data/verification/asset-foundation/`, `scripts/verify-asset-foundation.py`, and
`data/storage/asset-foundation-*-20261018.json`. The current structure, migration,
publication and recovery contract is in [catalog contract](catalog-contract.md).
The existing planning-document moves were preserved. No commit, push or PR.

Next runnable scope: `docs/next version plan/prompts/02-static-2d-images.md`, with
its own approval for representative images, enrollment, image preferences,
captioning/preprocessing contracts and full browsing. Later audio/clip adapters
remain separate milestones.

## October 18 — Descriptions are optional; Generate descriptions and notifications

Name and image search already find assets without descriptions, so descriptions
are now extra data ([decision 0008](decisions/0008-optional-descriptions-and-notifications.md)).

- **Import:** Process assets runs inspection/previews and search vectors only.
  `sources.import_outcome` ignores the caption stage; a missing or failed
  description raises no source card and is not in Importing failures report
  (`embedding_failures` now reads image-vector jobs only).
- **Search:** default `combined` still uses descriptions; a missing, stale or
  invalid description silently leaves only its channel (app and MCP faults).
- **Generate descriptions** per source in Settings → Asset sources: written ·
  missing · failed counts, a background `describe` operation (caption stage for
  assets with ready renders, description vectors, publish), progress and Cancel.
  Recorded failures are not retried; cancel and machine stops still publish.
- **Notifications:** header bell with unread count, panel and toasts;
  *Descriptions ready to generate* (after processing, and once for existing
  sources) and one report per description run. Saved in
  `data/library/notifications.json`, served with `sources()`, stamped by `changes()`.
- Settings is now a gear icon button. Cards no longer show badges for missing or
  failed descriptions; asset detail explains them.

Verification: full suite **449 passed** (13 new tests in `tests/test_notifications.py`
and `tests/test_sources.py`; updated import/budget tests for two-stage processing).
New WebView2 check `scripts/verify-notifications.py` passed
(`data/gui/notifications-2026-10-18f/`, synthetic assets, stand-in run, no model);
`verify-source-ui.py` (`data/gui/source-settings-83f29fa205/`),
`verify-general-settings.py` (`data/gui/general-settings-0b268c2d03/`) and
`verify-source-browser.py` (`data/gui/optional-descriptions-source-browser-2026-10-18/`)
passed. Read-only status of all 15 registered sources before/after
(`data/evidence/descriptions-optional-2026-10-18/`): no `needs_processing` change;
recorded import failures fall where they were only description failures
(e.g. KayKit 5→0, Cartoon City 45→0) and real faults remain (furniture-kit 15
image-vector, synty 24 preview); no enabled source has missing descriptions, so
no ready notice is seeded today. Real runtimes:
`verify-source-operation.py --describe` passed
(`data/library/verification/source-operation-b97673af4f22427ab2ae4664f2b9093c.json`):
Process assets published 2 cubes with 6 image vectors and 2 missing descriptions
(0 failures); Generate descriptions wrote, indexed and published both in 125 s and
reported `complete`. The script now writes its cubes in a selected format (the
saved settings process glTF only, so its OBJ cubes were skipped in a first run)
and dismisses its own notices after detaching its source. Added
storage about 17 MB of GUI evidence and scratch fixtures; no installs or models.
Editing `incremental.py` changes the overnight code contract (no run was active).

## October 18 — Code and lock line endings no longer re-queue finished work

Follow-up to the prompt fix below. The caption, inspection and embedding
fingerprints also hash raw bytes of `caption_backend.py`, `caption_batching.py`,
`runtime/caption/uv.lock`, `blender_worker.py`, `render_math.py`,
`blender_repair_worker.py`, `embedding_backend.py` and `runtime/embedding/uv.lock`.
They are all LF today, but `core.autocrlf=true` and no `.gitattributes` rule cover
them, so the next checkout that touches one (or a fresh Windows clone) writes CRLF.
That would have re-queued every finished description and inspection, and stopped
semantic search and indexing until a capability run and a full re-embed.

- `incremental.recorded_fingerprint`: when a ledger fingerprint differs from the
  current one, the LF and CRLF forms of those files are tried (at most 8
  combinations, only on a mismatch); a combination that reproduces the stored
  fingerprint keeps it. `process()` and overnight publication pass the recorded value.
- `retrieval.recorded_contract`: the embedding adapter and runtime-lock hashes keep
  the values in `data/embeddings/capability.json` when they differ only by line
  endings; used by search, `index_pilot` and `index_library`.
- `publication.line_ending_hashes`: stored/LF/CRLF hashes, cached per file identity.
- No existing fingerprint changed and no hashed file was edited. New results still
  hash current bytes. Any other byte change still re-queues (or is a contract change).
  `.gitattributes` is unchanged (owner choice).

Verification: full suite **436 passed** (with the uncommitted batching,
dependency-override and prompt work present); two new tests flip each file
LF→CRLF→LF, then make a real change; both fail with the tolerance disabled.
Read-only dry runs (inspection, caption, embeddings) on all 9 enabled sources were
identical before and after (all 0 pending except Cartoon City's 7,430 embeddings;
retained complete/failed unchanged). Read-only simulation of a CRLF checkout of all
the files against the real ledgers: 11,635 complete inspection/caption rows, all
would have been re-queued by raw bytes and all are kept; the embedding contract of
every source is kept. Evidence: `data/evidence/eol-fingerprints-2026-10-18/`. No storage
receipt (no installation or bulk processing). Editing `incremental.py`,
`overnight.py` and `library_index.py` changes the overnight code contract, so an
overnight run planned before this change would refuse to continue (none was active).

## October 18 — Prompt line endings no longer re-queue finished descriptions

Process assets would have regenerated 80 finished KayKit_Free_pack descriptions
(prompt v4, made by `scripts/kaykit-gltf-maintenance.py` on October 16) while
the source card showed nothing pending. Cause: the fingerprint hashed
`prompts/caption-v4.txt` as raw bytes. The descriptions were made from the LF
file (`06cda9b4…`); the checkout of `main` on October 17 21:16 rewrote it as CRLF
(`81e3e9d3…`, `core.autocrlf=true`). The text and what the model reads are
identical (every stored attempt's text digest matches the current file).

- `incremental.prompt_hash`: a completed caption keeps its recorded
  `prompt_sha256` when the prompt file differs from it only by LF/CRLF. All other
  fingerprints stay byte-identical; a real wording change still re-queues.
- No description, ledger row or catalog record was rewritten.

Verification: full suite **434 passed** (with the uncommitted batching and
dependency-override work present); one new test flips LF→CRLF→LF and then
changes wording. Caption dry run on all 9 enabled sources: KayKit 80 pending →
0 (1487 retained complete); every other source's pending/retained counts are
unchanged. No storage receipt (no installation or bulk processing).
Not covered: other hashed inputs (`caption_backend.py`, `uv.lock`,
`caption_batching.py`, inspection and embedding inputs) still hash raw bytes.

## October 18 — Batched description generation

Descriptions were the bottleneck: about 9.3 s per asset with the GPU only ~41%
busy (27 tokens/s, per-token overhead). A read-only benchmark on 20 rendered
Cartoon City assets (`scripts/benchmark-caption-batching.py`,
`data/evidence/caption-batch-benchmark/batching-2026-10-18a/`) measured 9.24 / 5.29 /
3.00 / 2.22 s per asset at batch 1 / 2 / 4 / 8 (4.2× at 8), 79 of 80 valid
outputs, 6.4 GB peak GPU memory, and exact reproduction of all 20 stored
descriptions at batch 1. The owner reviewed the batched outputs and approved
adopting them ([decision 0007](decisions/0007-batched-description-generation.md)).

- New `caption_batching.py` generates several assets per call with the unchanged
  model, prompt, images and sampling. `caption_backend.py` is untouched.
- Process assets (`incremental.process`) and overnight runs use it. Each asset is
  still validated, saved, published and checkpointed alone; one invalid output
  fails only that asset. Overnight `inflight.json` lists the whole batch.
- *Settings → General → Description batch size*: 1 / 2 / 4 / 8, default 8.
- Out of GPU memory stops with a message naming the batch size; the batch stays
  pending and no fault is recorded. The source card shows the reason.
- Cancel finishes the current batch, and its wording says so.
- Completed descriptions keep the fingerprint of the mode they were made with
  (`generation_mode`, default `sequential`); new ones record `batched-v1` and
  `batch` provenance.

Verification: full suite **424 passed** on this change alone (433 with the
separate, uncommitted dependency-override work present); 21 new test cases cover
settings, batching, fingerprints, out-of-memory, cancel, overnight and the
desktop bridge. Read-only
dry runs on all 9 enabled sources were identical before and after the change
(pending counts, pending asset lists and retained complete/failed counts;
Cartoon City 2,874 pending / 892 complete / 11 failed, KayKit 80 pending). The
production module on 10 real assets (`data/evidence/caption-batch-benchmark/pipeline-batch8-2026-10-18b/`):
14.9 s for a batch of 8, 9/10 valid (the invalid output was rejected by the
existing technical-claim rule), 6.4 GB peak. WebView2: `verify-general-settings.py`
passed (`data/gui/general-settings-b9eabaf119/`) and `verify-source-browser.py`
passed (`data/gui/batching-source-browser-2026-10-18/`). Added storage under
1.2 MB; no installs, environments or model copies. Retiring the legacy
pilot/calibration runner and the KayKit maintenance script are separate owner
tasks.

## October 18 — Cartoon City shared texture paths repaired; missing results running

The owner approved repairing the split Godot pack while reusing successful work.
Its four model add-ons referenced textures at nonexistent merged-pack locations;
5,266 missing references across 3,467 models map to 16 supplied Core textures.
Explicit source/hash-bound mappings now feed the existing texture repair worker,
interactive preview and agent handoff without moving or copying original assets.
The scanner retains these recipes across unchanged rescans. Successful stages
clear current faults while retaining ledger history; source-owned caption retry
evidence now uses the source metadata root correctly.

All 19 representatives rendered successfully, covering every mapped texture and
each affected add-on. The installed WebView2 check opened `Ambulance_2_B` with a
rendered image and a textured 3D viewer (2,708 triangles, five meshes, four
materials). Preservation passed for 7,657 originals, 2,480 prior per-asset output
files, 310 rendered models, 308 usable descriptions, 1,238 vectors, and the other
sources' active publications. The mutable Blender discovery receipt is reported
separately. Prior catalog, ledger, verification attempts and faults are retained.

The background run is generating the remaining 3,448 missing previews, followed
by missing descriptions and search data; it retains unchanged failures and reuses
existing results. The two independent unusable captions have one authorized retry.
It saves cancellation/resume checkpoints and will publish and verify final
results. The 4 GiB growth cap and existing 24 GiB library budget remain enforced.
The latest sample publication used 10,828,577,496 unique allocated bytes, a
568,874,096-byte increase from the combined-source baseline. Owner visual and
caption approval remain pending; bulk completion is not yet claimed.

Evidence: `data/repairs/cartoon-city-20261018/` (live `report.md`, sample and final
verification, actual UI captures, preserved originals/results hashes and logs),
`data/storage/sources-cartoon-city-*.json`, and
`docs/dependency-path-overrides.md`. Regression suite: 410 passed; follow-up
caption/mapping checks: 22 passed; final mapping checks: nine passed. Windows
link/process tests passed with normal permissions after sandbox-only restrictions.

## October 18 — `verify-gui.py` updated for the paged library

The legacy real WebView2 + STDIO MCP agreement check still assumed the 40-asset
pilot (all members on one page, every thumbnail loaded, Clear restoring the full
pilot). It now expects one browse page (`min(40, members)`), waits for the
visible-only thumbnail queue to settle, finds `apple` and caption-severity
examples across all browse pages, and loads `config.load_project_config`
(decision 0001). App behavior is unchanged.

Full mode passed (`data/gui/verify-gui-paged-20261018/report.json`): ten
packaged-form searches (combined, keyword, filtered, description, image and
reference) exactly match real STDIO MCP payloads, order and truncation with the
actual model; keyboard, native resize, synthetic race/truncation/error checks,
clipboard and local-only resources pass; the pre-started GUI worker closed with
exit code 0. Searches took about 5 s each because the GUI and MCP workers
alternate on the GPU lease. Render-only mode passed
(`data/gui/verify-gui-paged-render-20261018/report.json`).

## October 17 — Performance phase 4: retention and footprint

Phase 4 of the optimization plan ([decision 0006](decisions/0006-retention.md)).

- New `retention.py`: after every combined publication, keep the active
  generation plus the two newest older `v_*` generations centrally and in each
  source (`work`/scan folders untouched); stale combined-publication shortcuts
  go with their generation and are rebuilt on demand. Each app launch keeps the
  ten newest `data/gui/runs` audits. Faults never fail a publication; receipts
  are written under `data/maintenance/`.
- `maintenance_files` now uses Windows long-path syntax (trees over 260
  characters), validates each directory once per operation, and can lift the
  read-only attribute of immutable publications only after re-verifying bytes.
  The link test now uses a real junction.
- New two-step `scripts/cleanup-scratch.py --plan` / `--apply PLAN` removed old
  pytest/verification folders from `scratch/`; links were removed as links and
  only when they pointed inside their own folder. Runtime temp, Blender,
  download and unclassified folders, scripts and logs were kept. Tests now reuse
  `--basetemp scratch/pytest` (pytest's cleanup does not traverse junctions,
  covered by `tests/test_retention.py`).

Cleanup (receipts in `data/maintenance/`): 13 superseded central generations
(1.67 GB; a first pass retained 21 read-only files as faults, removed after the
read-only fix), 48 launch audits (7 MB), and 164 reviewed scratch folders in three
passes (1.34 GB, then 0.05 GB, then 2.09 GB after the read-only and long-path
fixes; no remaining faults). Each later plan was checked to be a subset of the
first reviewed plan. Source generations were already within the limit. Storage
receipts: `data/storage/perf-before-phase4-20261017.json` → `perf-after-phase4-20261017.json`:
allocated 11.74 → **7.05 GiB** (−4.69 GiB), files 547,093 → 102,944. Against the
session start (`perf-before-20261017.json`, 10.51 GiB) the project is 3.46 GiB smaller.

Verification: **403 tests passed** (`scratch/pytest`); WebView2 checks passed:
`data/gui/source-installed-9c12240acf/report.json` (10 launch audits retained),
`data/gui/perf-p4-source-browser`, `data/gui/source-settings-9fec3080c6/report.json`.
Final read-only receipt `data/benchmarks/perf-phase4-20261017.json` matches phase 3
(warm summary 0.14 s, browse 0.03 s, keyword 0.58 s, stub combined 2.1 s).
Earlier phase entries cite `scratch/pytest-perf-*` folders that this cleanup
removed; their pass counts remain recorded here. No original asset or generated
asset result was modified, retried or reprocessed.

## October 17 — Performance phase 3: embedding-only worker and pre-start

Phase 3 of the optimization plan ([decision 0005](decisions/0005-embedding-worker-and-prestart.md)).

- The private worker now only returns query vectors (`contract`, `text`,
  `image`); verification, the validated vector matrix (built once per index and
  contract), keyword search and fusion run in the app or MCP server process.
- The desktop app pre-starts the worker at launch (libraries only, no model or
  GPU lease; ready in about 4.5 s). The model loads on the first semantic search
  (about 3 s) and unloads after 10 idle minutes (was 60 s) or when a batch needs
  the GPU. Heartbeats separate a slow load from a stopped worker; the status
  line shows "Loading the search model". Busy-queue and stopped-worker errors
  are no longer retained as per-query faults.
- The presentation lock covers presentation state only; settings, source and
  change polls run concurrently. Owner overlays are parsed once per file stat;
  file identity, source and output paths are memoized per request; containment
  uses a normalized string check equivalent to `Path.is_relative_to`.

Read-only receipt `data/benchmarks/perf-phase3-20261017.json` versus baseline:
stub combined search 19.5 → 2.1 s; keyword 7.0 → 0.54 s; summary 3.9 → 0.18 s;
browse 1.2 → 0.13 s. Real model through the desktop bridge (single app): first
combined search including model load 8.0 s, then about 3 s; keyword 0.9 s.
Installed-library startup (`data/gui/source-installed-8eece65ba1/report.json`):
one summary load, eight thumbnails in 2.5 s total (10.9 s after phase 2), no
model requested.

New `scripts/verify-search-agreement.py`: real STDIO MCP and desktop bridge,
both with the actual worker and model, returned identical candidates for six
queries across combined, keyword, description and image modes
(`data/gui/perf-p3-search-agreement/report.json`). Two concurrent workers share
the GPU lease, so they reload the model alternately (about 5 s per search in that
check). The legacy `verify-gui.py` still assumes the 40-asset pilot (all cards
and thumbnails on one page) and was not run.

Verification: **398 tests passed** (`scratch/pytest-perf-p3-full`), including
new `tests/test_worker_gateway.py`; WebView2 checks passed:
`data/gui/perf-p3-source-browser`, `data/gui/perf-p3-search-ui`,
`data/gui/perf-p3-library-gui`, `data/gui/source-settings-2a38ffd209/report.json`,
`data/gui/source-installed-8eece65ba1/report.json`. Verification scripts now
assert that no model was requested instead of that no worker process exists.
No original asset or generated result was modified, retried or reprocessed.

## October 17 — Performance phase 2: hash reuse by file identity

Phase 2 of the optimization plan ([decision 0004](decisions/0004-stat-identity-hash-reuse.md)).

- `verified_hash` reuses recorded hashes while a file's identity (size,
  modification time, NTFS ChangeTime, file ID) is unchanged, through one shared
  record `cache/file-hashes.sqlite` (5.9 MB for the current library) that scans
  seed. ChangeTime replaces Python's Windows `st_ctime` (creation time), so a
  same-size edit with a restored modification time is still detected; the
  existing regression test for that case passes unchanged.
- Removal checks and the storage/preservation/model-relocation audits re-read
  bytes (`fresh=True`, `hash_cache.require_fresh()`).
- Source-directory validation, storage roots, registry/ownership reads and
  directory resolution run once per pinned request; link leaves are still
  resolved and escapes rejected.
- Card thumbnails show the verified preview only (no source re-verification),
  cached by preview identity at 320 px with a fast PNG encode. Detail and agent
  `get_asset` behavior is unchanged.

Read-only receipt `data/benchmarks/perf-phase2-final-20261017.json` (versus the
baseline): keyword search 7.0 → 0.92 s; stub combined search 19.5 → 4.0 s;
summary 3.9 → 0.24 s; browse 1.2 → 0.04 s; 12 thumbnails 1.3 → 0.27 s; detail
0.135 → 0.069 s. The one-time first run after upgrading re-hashes files whose
identity format changed.

Verification: **394 tests passed** (`scratch/pytest-perf-p2-full`), including new
`tests/test_hash_cache.py`; WebView2 checks passed:
`data/gui/perf-p2-source-browser/verification.json`, `data/gui/perf-p2-search-ui/report.json`,
`data/gui/perf-p2-library-gui`, `data/gui/source-settings-7c56837bfa/report.json`,
`data/gui/source-installed-b135ae32ee/report.json`. Startup thumbnails still wait
behind the shared presentation lock; phase 3 narrows it. No original asset or
generated result was modified, retried or reprocessed.

## October 17 — Performance phase 1: startup and read caches

Phase 1 of the owner-approved optimization plan (decisions
[0001](decisions/0001-config-local-precedence.md)–[0003](decisions/0003-per-publication-read-caches.md),
new `docs/decisions/` directory referenced from `AGENTS.md`).

- Read paths reuse per-publication slim records (`library_cache.py`) instead of
  re-parsing 3,393 catalog records (125 MB JSON) per call; processing still reads
  fresh full records. Publication digests are computed once per file stat.
- Startup loads the library summary once (was three or more times). One stat-only
  `changes()` poll (about 30 ms) replaces the 1.5 s source poll and the 20 s
  summary poll. Unchanged scans rewrite no status, import, ownership or scan-cache
  file, so the launch scan no longer reloads the view. Source actions no longer
  cancel visible thumbnail loading.
- Manual **Scan** and **Status** buttons removed (startup scan and change
  detection cover them). The MCP SDK loads on first search, not at startup.
- `config.local.toml` now overrides `config.example.toml` in every runtime entry
  point (`config.load_project_config`).

Read-only receipts `data/benchmarks/perf-baseline-20261017.json` →
`perf-phase1-20261017.json` (2,080 members, warm file cache): desktop import
0.46 → 0.13 s; summary 3.9 → 1.0 s (2.1 s first build); browse page 1.2 → 0.17 s;
keyword search 7.0 → 4.8 s; stub combined search 19.5 → 17.0 s (search is
addressed in phases 2–3). Installed-library WebView2 startup check
`data/gui/source-installed-59d7f14638/report.json`: one summary load (3.0 s), one
browse (0.16 s), no Scan/Status buttons, startup scan complete, no model loaded.
The installed check now derives member/source/warning expectations from the live
registry instead of stale hard-coded counts.

Verification: **389 tests passed** (`scratch/pytest-perf-p1-full`); WebView2
checks passed: `data/gui/perf-p1-source-browser/verification.json`,
`data/gui/perf-p1-search-ui/report.json`, `data/gui/perf-p1-library-gui`,
`data/gui/source-settings-5f124c855a/report.json`. Storage receipts
`data/storage/perf-before-20261017.json` → `perf-phase1-20261017.json`: +284 MB
allocated, almost entirely new pytest/verification folders (cleanup is phase 4).
No original asset or generated result was modified, retried or reprocessed.

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

Next runnable stage: step 2 — catalog and baseline.
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

Next: execute step 3 — inspect and render
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
Next: step 4 — local visual descriptions.
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
Next numbered stage is step 5, requiring
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
