# Local Asset Library

Project proposal and sequential implementation plan, prepared October 11, 2026; remaining stages revised October 12, 2026.

Status: the pilot backend, agent access and Windows desktop app are implemented. Steps 8–10 remain future work. Consult `C:\BrunoOS\Local-Asset-Library\docs\progress.md` for current evidence, owner decisions and limitations; this plan does not itself authorize full-library processing.

## Purpose

Build a local, searchable catalog of 3D game assets that helps cloud-backed and local agents find suitable candidates quickly and retrieve their real source files. Combine exact search, generated visual descriptions, technical metadata, and EmbeddingGemma 2 representations of descriptions and preview images.

The primary objective is to reduce repeated directory exploration and visual inspection, and reduce the amount of irrelevant information entering an agent's context. Better search quality must be demonstrated on this collection rather than assumed from model benchmarks.

## Paths and ownership

| Item | Location |
| --- | --- |
| This plan and its implementation prompts | `C:\BrunoOS\Plans\Local-Asset-Library` |
| New implementation repository, created in step 1 | `C:\BrunoOS\Local-Asset-Library` |
| Initial asset source, read only | `C:\Users\backup pc\Documents\General game assets\playful-lowpoly-asset-packs` |
| Existing local agent installation, preserve its configuration | `C:\BrunoOS\OpenCode-local-agent` |
| Existing Play Shapes implementation, unchanged by this project | `C:\Users\backup pc\Documents\Codex\play-shapes` |

Bruno owns visual approval, relevance judgments, and the decision to expand the pilot. GPT-6.1 Sol implements the stages. A separate locally running vision-language model writes asset descriptions; EmbeddingGemma 2 generates embeddings. These are different jobs and may use different models.

Do not add files to Play Shapes, move its assets, or modify the source packs. This library is a separate contributor tool, with no runtime dependency in the game.

## Observed starting collection

The folder inspected during planning contains five Kenney packs and three Quaternius packs. Approximately 883 model names were counted within their respective packs. This is a filename-based estimate, not a verified count of unique geometry. Multiple export formats often represent one asset, and some repeated names across packs are different objects.

| Pack | Model names observed | Individual files in a `Previews` directory |
| --- | ---: | ---: |
| Kenney Car Kit | 50 | 50 |
| Kenney City Kit Roads | 95 | 95 |
| Kenney Food Kit | 200 | 200 |
| Kenney Furniture Kit | 140 | 0 |
| Kenney Mini Forest | 22 | 22 |
| Quaternius Ultimate Food Pack | 103 | 0 |
| Quaternius Ultimate House Interior Pack | 123 | 0 |
| Quaternius Ultimate Nature Pack | 150 | 0 |

The preview column does not prove that other thumbnail layouts are absent. Discover them during cataloging. The collection includes GLB, OBJ/MTL, FBX, Blender, DAE, STL, textures, pack previews, and ZIP archives. Exclude archives from the catalog when their extracted contents are already present. Record licensing from supplied evidence and source links; do not invent or infer a license.

Hardware observed earlier in this conversation: RTX 5070 with approximately 12 GB VRAM and Intel Core Ultra 7 265KF. Recheck availability, runtime compatibility, and concurrent GPU use during implementation. Blender was not found on the current shell PATH during planning; that does not establish that it is uninstalled.

## Scope

The first release includes:

- A deterministic inventory and one catalog record per logical asset, with alternate formats grouped conservatively.
- Technical inspection and consistent multi-view previews, without changing originals.
- Local visual descriptions, with observations separated from technical facts and suggested uses.
- Filename/keyword, description, image, and combined retrieval.
- Compact agent-facing search and detail tools, initially using a local command interface and then MCP.
- A local Windows desktop app for browsing, searching and inspecting the same backend records, previews and evidence.
- Incremental updates, resumable batch jobs, and stale/deleted-file handling.
- A benchmark comparing search quality, latency, returned context size, and actual agent behavior.
- Local operation documentation and reproducible configuration.

Classification and clustering are an optional extension in step 9. They suggest organization; they never move source assets or replace measured facts.

Out of scope: whole-computer indexing, cloud caption generation, public hosting, a hosted website, automatic game imports, asset editing, automatic collision/LOD generation, fine-tuning, and unattended approval of artistic suitability.

## Proposed implementation choices

Use a small Python package managed by `uv`, SQLite with FTS5 for records and keyword search, and NumPy for exact similarity search over normalized vectors. A collection of this size does not initially need a vector database service. Confirm these choices in step 1 and document a concrete reason before changing them.

Use Blender in background mode for inspecting models and generating previews. Resolve its installed executable explicitly. Use a local vision-language inference backend selected through a small capability test, not the existing coding model merely because it is installed. Prefer a project-managed backend or an additive configuration that preserves the current local agent installation.

Use the documented Python/SentenceTransformers path as the initial candidate for EmbeddingGemma 2 text and image support. An alternative runtime is acceptable only after proving the required modalities and correct embedding output. Serving an embedding endpoint alone does not prove image support.

Pin working dependencies and exact model revisions. Reuse existing project runtime wrappers and separately pinned environments; do not install into the existing agent environment or upgrade Ollama as a side effect. Keep models in configured shared storage, currently `C:\BrunoOS\Local-models`, without duplicate weights. Follow current `AGENTS.md` and `docs/storage.md` for hard-linked dependencies, immutable installed files, receipts and cleanup. Explain any new runtime, pin change or significant storage increase before execution.

Proposed ignored directories: `data/`, `models/`, `cache/`, `logs/`, `scratch/`, `.venv/`. Version source, schemas, configuration examples, prompts, evaluation query definitions, small synthetic fixtures, documentation, and progress records. Do not commit third-party packs, full model weights, or the generated catalog.

### Embedding model contract

EmbeddingGemma 2 has a 270M text configuration and a 440M text-and-image configuration; the documented native output is 768 dimensions and the context limit is 8,192 tokens. Start with full dimensions because this collection is small. Use documented search-query and document formatting. For native inference use BF16 on supported hardware or FP32; avoid FP16. Verify finite values and normalization, and record model revision, modality, prompt, dimension, and preprocessing version with each embedding. A change to that contract invalidates affected vectors. These requirements come from the [Google model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2).

### Catalog record

Each record should contain:

- Stable asset ID, pack ID, source-relative identity, display name, and variant relationships.
- Alternate source formats and primary inspection source; dependencies such as textures and materials.
- Evidence for any format grouping, and unresolved ambiguity rather than speculative merging.
- Content hashes for the source and relevant dependencies; availability/staleness state.
- Technical metadata with extraction method, including local-space bounds and model units. Unknown physical scale remains unknown.
- Preview paths, view labels, render settings/version, and any render issues.
- Description fields: likely object identity, observed colors/shapes/parts/style, distinguishing features, uncertainty, and separately labeled possible uses.
- Provenance: local caption model/revision, prompt version, input view hashes, generation settings, and review/correction state.
- Pack/source/license evidence, without treating generated descriptions as license evidence.
- Embedding contract identifiers, vector references, and stage-specific processing status.

Do not use filename-only IDs globally: two packs can have a `chair` with different geometry. Do not merge same-stem files in unrelated subdirectories without evidence. IDs remain stable for an unchanged source-relative identity; explicitly handle a rename rather than claiming perfect automatic identity preservation.

### Visual inspection policy

Prefer a concise description of roughly 80–150 words plus structured attributes. Require the caption model to inspect real supplied images. Record a failed or unsupported inspection instead of substituting a filename-generated caption.

Render at least front, side, and three-quarter views; add a back/top/detail view when useful. Preserve materials, frame the object consistently, and record the coordinate convention. Use existing thumbnails for a quick baseline, but do not assume a single view is sufficient. Keep the source file unchanged, disable embedded script execution when loading Blender files, and keep all renderer output inside the project workspace.

Technical statements such as triangle count, rigging, animation availability, and dependency completeness come from inspection tools. Visual observations come from the vision model. Suggested gameplay uses are model interpretations and are excluded from the factual description by default. Model-reported confidence is a heuristic, not a calibrated probability.

Separate a reusable asset description from project-specific judgments such as suitability for Play Shapes. Store owner corrections as an overlay that survives regeneration.

Use the current `docs/caption-quality.md` contract: minor precision or uncertain details are `review_note`; meaningful identity/color/structural errors that could mislead selection are `warning`; failed/incomplete generation or an unusable description is a caption `fault`. `clear` means no recorded findings, not owner approval. Preserve evidence and owner states. A note or warning does not exclude a usable source, require reprocessing, or invalidate an embedding; an actual change to embedded description content does invalidate affected vectors. New reviews record explicit severity, evidence and rationale; unclassified findings remain warnings. Successful retrieval does not prove every caption detail.

### Retrieval behavior

Support keyword/filename retrieval, semantic description retrieval, text-to-image retrieval, and a combined mode. Keep the channels separately measurable. Initially combine ranked lists using reciprocal rank fusion rather than assuming raw scores from different channels are comparable. Combine multiple views into one asset result so duplicate views and formats cannot occupy the shortlist.

Filter using verified metadata when possible. Exclude unavailable/stale records by default. Similarity is not proof of a match; evaluate negative queries and provide an empty result or explicitly weak candidates when appropriate. Do not invent a universal confidence threshold.

Search returns up to five candidates by default: ID, name, pack, a short excerpt, available formats, preview reference, availability, and a brief indication of matching channels. Detailed metadata and complete dependency paths are requested separately. Use a deterministic character cap plus a clearly labeled token estimate; report actual model token counts only when measurable. Initial target: no more than about 1,500 text tokens per standard shortlist, excluding requested images and transport/tool-schema overhead.

Retrieval means resolving existing source files and dependencies. A separate explicit export command may create a manifest or copy a selected package under `data/exports/`; never automatically copy into Play Shapes or write into source packs.

### Local and cloud agent access

All rendering, caption generation, embedding, and indexing remain local. When a cloud-backed agent requests search results, those returned descriptions and any requested previews enter that model's context. Local computation does not make those returned results private from the chosen cloud model.

Use a local STDIO MCP server with a small interface, initially `search_assets` and `get_asset`. A preview may be returned as an image/resource only after verifying that the client can consume it; a path alone does not prove that a remote agent can view the file. Local MCP support is documented for [OpenAI clients](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and [OpenCode](https://opencode.ai/docs/mcp-servers/). Hosted cloud environments require a separately verified access path. Do not expose this service publicly to solve that limitation.

## Execution instructions

Run one numbered prompt at a time using GPT-6.1 Sol. Start step 1 from `C:\BrunoOS`; subsequent steps use `C:\BrunoOS\Local-Asset-Library` as the workspace. Each prompt is a standalone file in this plan's `prompts/` directory.

Step 1 must first create the new folder and initialize it as a Git repository. If a populated directory or repository already exists at the target, inspect it and report the conflict before changing it. Never reset or delete it.

Copy this plan and its prompt files into `docs/plan/` during step 1. Subsequent work refers to that versioned copy. Maintain `docs/progress.md` with step status, actual commands, outputs, model/runtime versions, evidence paths, blockers, and the next runnable step. Never claim a step passed from source code alone. Keep implementation changes in local commits after appropriate checks, without a remote, push, or publication unless separately requested. Do not spawn subagents by default.

Dependency installation and downloads required by an approved stage use the existing runtime wrappers and storage rules. Before a model download, verify its license, official runtime support, size and device requirements. The original 8 GiB model/20 GiB generated-data planning allowances are historical estimates, not blanket expansion approval. The current target is below 6 GiB of unique allocated pilot project storage, excluding external assets and shared models. Step 8 must estimate and obtain an approved full-library storage/runtime budget from measured pilot costs; do not treat the pilot target as a full-library cap. A projected increase of 500 MiB or more, another runtime or exceeding the pilot target must be explained at the required plan checkpoint. Save fresh base-Python storage receipts before and after installations or bulk processing; count unique allocated bytes, not summed folder sizes. Reuse shared weights and read-only originals. No cloud API keys or paid services are required.

### Sequence and deliverables

| Step | Result | Depends on |
| --- | --- | --- |
| 1 | New Git repository, scaffold, contracts, environment report | Nothing |
| 2 | Inventory, logical asset catalog, 40-asset pilot, keyword baseline | 1 |
| 3 | Technical inspector and multi-view renderer | 2 |
| 4 | Validated local vision model and rich descriptions | 3 |
| 5 | EmbeddingGemma 2 text/image indexing and combined search | 4 |
| 6 | Retrieval benchmark and owner decision on expansion | 5 |
| 7 | Local MCP tools and real agent retrieval verification | 6 approved |
| GUI milestone | Windows desktop pilot app and shared caption severity, implemented between steps 7 and 8 | 7 |
| 8 | Reliable updates, full-library backend and responsive GUI expansion | 7 and existing GUI |
| 9 | Optional category suggestions and clustering | 8 |
| 10 | Operational handoff and final acceptance report | 8; 9 if selected |

## Step 1 — Create the folder and Git repository

Create `C:\BrunoOS\Local-Asset-Library` and initialize Git before creating implementation files. Copy the plan, establish the isolated Python package, configuration examples, schema contracts, ignore rules, focused tests, and progress log. Discover hardware, installed tools, Blender, and local model runtimes without mutating existing installations.

Done when: the repository is new, runnable, and contains an initial local scaffold commit; source-pack paths are configured as read only; environment evidence distinguishes verified, missing, and untested capabilities.

Prompt: [01-create-repository.md](prompts/01-create-repository.md).

## Step 2 — Catalog assets and establish the baseline

Inventory the source packs; distinguish per-asset previews, pack sheets, textures, and archives. Group equivalent export formats conservatively. Create a deterministic pilot of 40 assets across all eight packs, with named variants, duplicate names, texture dependencies, existing previews, and missing previews represented. Build filename/keyword retrieval before captions or embeddings.

Done when: all discovered candidates have a catalog status; grouping evidence and unresolved cases are visible; pilot selection is reproducible; basic search returns original paths without altering sources.

Prompt: [02-catalog-and-baseline.md](prompts/02-catalog-and-baseline.md).

## Step 3 — Inspect models and render views

Build a batch Blender inspector and renderer. Prefer an existing portable model representation where practical, but record which file was actually inspected. Validate materials, framing, visibility, and scale conventions on several formats. Never infer that technical facts from one format apply to every alternate export without recording the limitation.

Done when: representative files have valid metadata and usable views; pilot assets are processed or have explicit error states; texture/format failures are distinguishable from successful renders; originals remain unchanged.

Prompt: [03-inspect-and-render.md](prompts/03-inspect-and-render.md).

## Step 4 — Generate local visual descriptions

Select a locally runnable vision-language model through official documentation and a small actual image test. Keep description generation separate from the embedding model. Calibrate the prompt on approximately ten representative assets, then generate structured descriptions for the pilot. Produce a visual review sheet linking descriptions to their inputs.

Done when: image inputs are actually consumed; output follows the schema; uncertain identity is recorded; technical facts are not hallucinated into the visual description; model/prompt provenance is reproducible. Owner visual review remains distinct from technical validation.

Prompt: [04-local-visual-descriptions.md](prompts/04-local-visual-descriptions.md).

## Step 5 — Embed and search

Implement EmbeddingGemma 2 text and image inference according to the model contract. Build separate keyword, description, and image channels, followed by rank fusion. Index pilot records and previews, with stage/contract fingerprints and a compact search interface. Provide reference-image querying where runtime support is verified.

Done when: real finite normalized embeddings are stored; query/index contracts match; each channel can be tested separately; results resolve to logical asset IDs; no code path fabricates embeddings after inference failure.

Prompt: [05-embeddings-and-search.md](prompts/05-embeddings-and-search.md).

## Step 6 — Evaluate before scaling

Prepare at least 24 evaluation queries: exact names, natural descriptions, shape/color/style requests, format filters, similar assets, and at least four absent/negative requests. Keep a held-out subset for final evaluation. Add a small set of reference-image queries. Human relevance judgments must be recorded before viewing competing rankings; unreviewed judgments are explicitly provisional.

Compare keyword baseline, description-only, image-only, and combined retrieval on the same pilot. Measure Hit@5 and ranked relevance where labels exist, unique-asset diversity, false positives on negatives, cold/warm latency, preprocessing cost, and returned context size. Also compare keyword-plus-description retrieval to the full image-enabled approach to reveal whether vision embeddings add enough value.

Proposed expansion gate: combined retrieval improves Hit@5 on the labeled natural-language subset by at least 10 percentage points over keyword search, without losing more than one exact-name success or bypassing verified filters. Target warm search p95 below two seconds on this machine. These are project acceptance targets, not guaranteed model performance. Publish raw counts because a small pilot has limited statistical power. If the baseline is already strong, report that ceiling and let Bruno decide whether other measured benefits justify expansion.

Done when: a reproducible report exists with real/provisional evidence separated. The step ends awaiting Bruno's explicit pilot decision. Do not manufacture approval or proceed to full indexing merely because tests pass.

Prompt: [06-pilot-evaluation.md](prompts/06-pilot-evaluation.md).

## Step 7 — Connect agents through local MCP

After pilot approval, expose read-only search and detail tools. Enforce source-root boundaries, compact defaults, valid IDs, dependency availability, and client-compatible preview delivery. Executing the step 7 prompt authorizes additive registration of this local server in the intended Codex and OpenCode clients; preserve all unrelated configuration and save a restorable copy before editing.

Run a real agent task: find a requested prop, inspect its preview, resolve a usable format and dependencies, and produce a selection manifest. Evaluate cloud-backed and local model behavior separately when both are available. A direct MCP transport test is not evidence that an agent actually used the tool.

Done when: the intended client has performed the workflow; result size is measured; unavailable clients remain explicitly unverified; no pack or game project was modified.

Prompt: [07-agent-mcp-integration.md](prompts/07-agent-mcp-integration.md).

## Implemented GUI milestone — between steps 7 and 8

The Windows app launches through `C:\BrunoOS\Local-Asset-Library\Local Asset Library.vbs` and reuses the existing MCP runtime and shared retrieval backend. It supplies read-only pilot browsing, search, explicit preview/source-format selection, source-path copying and evidence detail. Browse membership/counts come from the backend; the inventory count does not imply full-library availability. Startup does not install, download, scan, process or load inference models. Search shares MCP ranking/filter/cap behavior; backend membership still explicitly enforces forty assets.

Use repository `docs/gui/README.md`, `docs/gui/verification.json`, `docs/caption-quality.md` and `docs/caption-classification-verification.json` as the current contracts/evidence. Automated/native GUI checks remain separate from Bruno's usability and artistic approval. Preserve the existing app rather than introducing another frontend, runtime or retrieval policy.

## Step 8 — Make updates reliable and expand the backend and GUI

Implement stage-specific hashes, resumable jobs, failure isolation, deletion/rename handling, persistent owner corrections and transactional catalog/index publication. Generalize the shared forty-asset membership contract to explicitly configured library membership; do not simply remove guards. Preserve source boundaries, measured filters, logical-asset grouping and shared GUI/MCP retrieval semantics. Test with small synthetic fixtures and existing read-only paths; do not copy original assets into test trees or damage the source library.

Add bounded/paged browsing and lazy thumbnails for the larger library, retaining stable selection, filters, keyboard access and responsive detail/search. Publish catalog/index changes consistently so an open GUI or agent connection does not mix incompatible versions; surface changed/stale state and invalidate presentation caches appropriately. Show current processing/coverage status in the app. Keep manual `scan`, `process`, `refresh` and `status` operations with dry runs; an always-on watcher is optional. Opening the app must remain lightweight and must not start batch processing.

Separate completed work, caption notes/warnings, actual stage failures, unsupported formats and owner-review states. Preserve usable partial results and original evidence. Resume unfinished/interrupted work without automatically retrying unchanged faulty items; retries/repairs of actual asset faults need explicit authorization. Review severity alone must not rerender, recaption or re-embed assets. Changing an effective description invalidates only its affected embedding input; owner approval or severity alone does not.

Estimate full-library runtime, peak/retained unique allocated storage and GPU use from measured pilot costs, and confirm the full-batch scope/budget approval before processing. Follow current storage rules and save fresh before/after bulk receipts. Coordinate batch GPU work with GUI/MCP workers: pause/unload or queue competing workloads rather than killing unrelated processes or assuming they all fit. Process in resumable batches within the approved budget. Preserve active search during publication or give a clear bounded unavailable state.

Done when: no-change refresh skips unchanged work; appropriate contract/content changes invalidate only affected stages; interruption resumes without fault retries; deleted assets disappear and renames follow documented identity rules; the expanded library is browseable without eager loading of every preview; GUI/MCP agree on candidates, ordering, filters and truncation against the same version; every candidate has coverage/status with notes and warnings separate from operational failure. Full processing and owner acceptance remain evidence-backed decisions.

Prompt: [08-incremental-full-library.md](prompts/08-incremental-full-library.md).

## Step 9 — Optional classification and clustering in the existing GUI

Add reviewed category suggestions and exploratory groups using a small owner-readable taxonomy. Separate identity tags, visible attributes, inferred uses and measured filters. Preserve manually accepted labels and allow unknown/multiple categories. Treat generated captions as provisional observations: meaningful caption warnings must not silently become accepted categories. Use reviewed descriptions and image evidence where needed; keep label evidence and review state explicit.

Display suggestions and groups in the existing app with member previews, representative assets, outliers and suggested/accepted/unknown states. Keep browsing bounded and the extension independently disableable. Do not alter core search ranking/filter contracts, automatically approve labels, rewrite source descriptions to fit categories or reorganize original files. Evaluate task-specific embedding contracts rather than assuming retrieval vectors are optimal for clustering; explain any additional runtime/model/storage cost in the approved plan.

Done when: suggestions and groups are inspectable in the GUI, versioned enough to compare and useful on a modest reviewed sample; unknown handling, caption-warning effects and preservation of accepted labels are demonstrated; search remains usable with the extension disabled. Record this step as skipped if Bruno does not choose it; Step 10 and core search can proceed without it.

Prompt: [09-classification-and-clustering.md](prompts/09-classification-and-clustering.md).

## Step 10 — Finish desktop/agent operational documentation and handoff

Document the exact working installation, local/shared models, Windows launcher/prerequisites, startup/shutdown, GUI browsing/search/detail/source-path copying, processing status, scan/process/refresh operations, corrections, interruption recovery, storage/cleanup, MCP clients and limitations. Explain source faults, caption faults, warnings, minor notes and owner review separately. Cover reopening the app or restarting agent connections after code updates. GUI startup must remain independent of installation and batch processing.

Repeat held-out retrieval evaluation after full indexing to detect ranking degradation as the pool grows. Verify GUI/MCP agreement on the expanded collection and meaningful GUI behavior: bounded browsing/lazy previews, loading/error states, keyboard controls, resizing, updates/publication and shutdown of owned workers. Repeat real-agent tasks only where index/integration changes justify them. Keep automated checks, actual rendered/native inspection, actual agent use and Bruno's usability/artistic approval distinct.

Done when: another fresh Codex chat can operate both interfaces from repository documents; acceptance requirements map to current evidence; measured coverage, storage and operating costs are reported; unresolved failures, warnings and human reviews remain visible. This is a local handoff, with no publication or game import, and no claim of full-library completion if Step 8 has not passed.

Prompt: [10-handoff-and-final-validation.md](prompts/10-handoff-and-final-validation.md).

## Final acceptance

- Original packs and Play Shapes remain unchanged.
- Each asset can be traced from search result through preview/description to existing source files and dependencies.
- Duplicate export formats do not crowd out distinct candidates.
- Actual failed/unsupported stages remain visible with preserved partial results; caption warnings/notes are not counted as processing failures or used to discard usable sources.
- The Windows app browses the configured processed library responsively and shares search semantics with MCP; startup never triggers installation or batch work.
- Real local vision and embedding inference are demonstrated and recorded.
- Owner corrections, accepted labels and caption review evidence survive refresh; severity-only changes do not trigger inference or embedding work.
- Fresh storage receipts and measured full-library costs satisfy the approved expansion budget.
- Quality and token/context claims are supported by measurements, with the cost of tool schemas and requested images disclosed where available.
- At least one intended agent client has completed a real retrieval task; any second client/model remains marked unverified until tested.
- Pilot and visual-suitability approval remain human decisions.

## Sources and evidence boundaries

Official model documentation: [EmbeddingGemma 2 model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2), [SentenceTransformers inference](https://ai.google.dev/gemma/docs/embeddinggemma/inference-embeddinggemma-with-sentence-transformers). Additional reference: [Unsloth usage guide](https://unsloth.ai/docs/models/embeddinggemma-2).

Client integration: [OpenAI MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [OpenCode MCP documentation](https://opencode.ai/docs/mcp-servers/).

Consult current primary documentation during the relevant stage and record tested versions. This plan is an implementation proposal, not proof of model compatibility, installed software, retrieval quality, artistic approval, or token savings.
