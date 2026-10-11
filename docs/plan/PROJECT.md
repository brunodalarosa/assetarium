# Local Asset Library

Project proposal and sequential implementation plan, prepared October 11, 2026.

Status: planning only. The implementation repository, catalog, models, and search service have not been created by this plan.

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
- Incremental updates, resumable batch jobs, and stale/deleted-file handling.
- A benchmark comparing search quality, latency, returned context size, and actual agent behavior.
- Local operation documentation and reproducible configuration.

Classification and clustering are an optional extension in step 9. They suggest organization; they never move source assets or replace measured facts.

Out of scope: whole-computer indexing, cloud caption generation, public hosting, a graphical website, automatic game imports, asset editing, automatic collision/LOD generation, fine-tuning, and unattended approval of artistic suitability.

## Proposed implementation choices

Use a small Python package managed by `uv`, SQLite with FTS5 for records and keyword search, and NumPy for exact similarity search over normalized vectors. A collection of this size does not initially need a vector database service. Confirm these choices in step 1 and document a concrete reason before changing them.

Use Blender in background mode for inspecting models and generating previews. Resolve its installed executable explicitly. Use a local vision-language inference backend selected through a small capability test, not the existing coding model merely because it is installed. Prefer a project-managed backend or an additive configuration that preserves the current local agent installation.

Use the documented Python/SentenceTransformers path as the initial candidate for EmbeddingGemma 2 text and image support. An alternative runtime is acceptable only after proving the required modalities and correct embedding output. Serving an embedding endpoint alone does not prove image support.

Pin working dependencies and exact model revisions. Isolate virtual environments, model caches, logs, and data under the new project. Do not install into the existing agent environment or upgrade its Ollama installation as a side effect. A necessary shared-runtime change must be separately explained before execution.

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

Dependency installation and downloads required by an executed prompt are allowed within the project-managed environment. Before a model download, verify its license, official runtime support, size, and expected device requirements. Initial budget: at most 8 GiB of model downloads in total and 20 GiB of project-generated data; larger consumption requires revising the budget with Bruno. Do not download several large candidate models speculatively. Implement estimates/dry runs before a full batch. No cloud API keys or paid services are required.

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
| 8 | Incremental processing and full-library expansion | 7 |
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

## Step 8 — Make updates reliable and process the library

Implement stage-specific hashes, resumable jobs, failure isolation, deletion/rename handling, owner correction overlays, and transactional search-index publication. Test them with copied/synthetic fixtures, not edits to the real source library. Then estimate costs from the pilot and process the full collection within budget.

Schedule GPU workloads conservatively: unload or pause one heavy model before the next stage rather than assuming the caption model, embedding model, coding agent, and Blender fit simultaneously. Provide manual `scan`, `process`, `refresh`, and `status` operations; an always-on watcher is optional.

Done when: reruns skip unchanged work; changed source/texture/prompt/model contracts invalidate the appropriate stages; interruption resumes; deleted assets stop appearing; every candidate is processed or has a visible actionable status.

Prompt: [08-incremental-full-library.md](prompts/08-incremental-full-library.md).

## Step 9 — Optional classification and clustering

Add reviewed category suggestions and exploratory groups of similar assets. Use a small owner-readable taxonomy. Separate identity tags, visual attributes, inferred uses, and technical filters. Preserve manually accepted labels and allow unknown/multiple categories. Evaluate task-specific embedding contracts rather than assuming retrieval vectors are optimal for clustering.

Done when: suggestions and cluster reports are inspectable, stable/versioned enough to compare, and useful on a reviewed sample; no automatic reorganization of source files occurs. Record this step as skipped if Bruno does not choose it; core search can ship without it.

Prompt: [09-classification-and-clustering.md](prompts/09-classification-and-clustering.md).

## Step 10 — Finish operational documentation and handoff

Document installation, local models, startup, scan/process/search workflows, refresh, correction review, recovery, data/model storage, MCP clients, and limitations. Repeat the held-out evaluation after full indexing to detect ranking degradation as the candidate pool grows. Verify the final real-agent workflow again only if integration/index changes justify it.

Done when: another fresh Codex chat can operate the tool from repository documents; evidence supports the release claims; unresolved format/model/client failures and human reviews are listed. This is a local handoff, with no publication or game import.

Prompt: [10-handoff-and-final-validation.md](prompts/10-handoff-and-final-validation.md).

## Final acceptance

- Original packs and Play Shapes remain unchanged.
- Each asset can be traced from search result through preview/description to existing source files and dependencies.
- Duplicate export formats do not crowd out distinct candidates.
- Unsupported/failed assets are visible and never masquerade as inspected assets.
- Real local vision and embedding inference are demonstrated and recorded.
- Owner corrections survive automated refresh.
- Quality and token/context claims are supported by measurements, with the cost of tool schemas and requested images disclosed where available.
- At least one intended agent client has completed a real retrieval task; any second client/model remains marked unverified until tested.
- Pilot and visual-suitability approval remain human decisions.

## Sources and evidence boundaries

Official model documentation: [EmbeddingGemma 2 model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2), [SentenceTransformers inference](https://ai.google.dev/gemma/docs/embeddinggemma/inference-embeddinggemma-with-sentence-transformers). Additional reference: [Unsloth usage guide](https://unsloth.ai/docs/models/embeddinggemma-2).

Client integration: [OpenAI MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [OpenCode MCP documentation](https://opencode.ai/docs/mcp-servers/).

Consult current primary documentation during the relevant stage and record tested versions. This plan is an implementation proposal, not proof of model compatibility, installed software, retrieval quality, artistic approval, or token savings.
