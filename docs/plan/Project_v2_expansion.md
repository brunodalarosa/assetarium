# Assetarium v2 expansion

Prepared October 18, 2026. Status: proposed roadmap; implementation has not started under this plan.

## Purpose and authority

Expand Assetarium from a 3D-model catalog into a local catalog for sprites, icons, other 2D images, audio, textures/materials, shaders, and 3D animation clips. Deliver eight bounded milestones, each usable through the Windows app and the shared agent-facing backend.

This document is the expansion reference for Codex, Claude Code, and future agents. It replaces the original numbered prompts, not the existing application. [PROJECT.md](PROJECT.md) remains a historical v1 proposal; its old status, setup instructions, and step numbers are not the expansion workflow. Current implementation evidence lives in [progress.md](../progress.md). Do not infer current completion from either roadmap.

The owner requested this documentation package. Creating it does not approve implementation, dependency installation, model downloads, source enrollment, bulk processing, or a change to an owner-approved decision. Follow the current root [AGENTS.md](../../AGENTS.md), [decisions](../decisions/README.md), [caption policy](../caption-quality.md), and [storage policy](../storage.md). If this proposal conflicts with them, surface the conflict before implementation; do not silently change the policy.

Before implementation, use the two checkpoints in order, recognizing any explicit approval already given for the same unchanged scope:

1. Restate the selected milestone's scope in one sentence, identify inclusions, exclusions, and ambiguities, ask **"Does this scope match what you want?"**, and wait for the owner's answer.
2. Explain changes, ownership, risks, verification, estimated duration, and additional peak/retained disk space with assumptions and uncertainty. Ask **"Is this implementation plan clear, and do you approve proceeding?"**, and wait for the owner's answer.

Read-only investigation may prepare these checkpoints. Reconfirm the affected checkpoint after a material change. Each prompt covers one milestone. Steps 1 and 2 may be bundled only when that combined scope and plan are explicitly approved. Do not proceed automatically to the next step or spawn subagents without authorization. A milestone may require several chats; retain a resumable handoff.

## Paths and ownership

| Item | Location or responsibility |
| --- | --- |
| Existing repository | `C:\BrunoOS\Local-Asset-Library` |
| This reference | `docs/plan/Project_v2_expansion.md` |
| Expansion launch prompts | `docs/plan/prompts/01-asset-foundation.md` through `08-shaders.md` |
| Source originals | Existing configured source roots; read only |
| Source-generated results | The corresponding source's existing `metadata-lal` storage |
| Combined indexes, caches, settings, reports | Existing project-local configured storage |
| Shared model revisions | Configured `[storage].models`, currently `C:\BrunoOS\Local-models` |
| Implementation agent | Scoped implementation, migrations, verification, receipts, and handoff |
| Bruno | Scope/plan approval, representative collections, usability/relevance judgments, and expansion decisions |

Preserve the existing project and neighboring projects. Do not recreate the repository, reset existing work, move originals, edit installed dependency files, or change the separate Ollama/OpenCode setup. These launch prompts are distinct from inference prompts in the repository-root `prompts/` directory; replacing this plan's prompts does not retire runtime caption prompts.

## Verified starting point and limits

Read-only planning inspection on October 18, 2026 found:

- The catalog and processing pipeline are centered on logical 3D models. Inventory recognizes texture and preview images, but generic images are not yet first-class searchable assets. Format-selection settings are also model-oriented.
- The current pipeline has inspection, caption, and embedding stages, with immutable publication generations, source-side generated results, owner overlays, fault records, and shared desktop/MCP retrieval.
- `blender_worker.py` enumerates armatures/actions and explicitly does not play or behaviorally validate them. Enumeration is not animation support.
- Captioning uses `Qwen/Qwen3-VL-2B-Instruct`, pinned in `docs/caption-model.json`. The active adapter consumes actual images. Video support advertised by the publisher has not been validated in Assetarium.
- Embeddings use `google/embeddinggemma-2`, pinned in `docs/embedding-model.json`, with normalized 768-dimensional vectors. `embedding_backend.py` explicitly disables audio using `audio_config=None`; its current contract accepts text and image only.
- The locally stored embedding checkpoint has audio configuration and audio tensors. This suggests that no replacement embedding checkpoint download is needed for audio; it does not prove decoder compatibility or successful audio inference.
- Current image embedding preprocessing rejects dimensions below 16 pixels, composites transparency over fixed gray, and uses a pinned preprocessing contract. Small sprites need deliberate handling.
- Runtime lock and adapter hashes participate in inference fingerprints. A code or dependency change can invalidate contracts even when the model name is unchanged.

These are dated findings, not perpetual guarantees. Recheck the relevant files and installed capabilities at the start of each milestone. Do not load models or bulk-scan assets merely to refresh documentation.

## Shared design requirements

### One catalog, type-specific processing

Keep a shared catalog, source registry, publication system, search backend, review system, and dependency resolver. Add a small dispatch boundary for type-specific inspection and previews; do not build a general plugin framework before concrete needs justify it. Reuse SQLite/FTS5, NumPy retrieval, runtime wrappers, and existing UI/MCP services unless an approved plan establishes a reason to change them.

Asset type describes what someone selects. File role describes how a source file is used. A PNG can be a sprite, a standalone texture, or a dependency of a material; extension alone does not establish that role. Preserve generic supported image records when a precise subtype is unknown. Record unsupported content, unresolved grouping, and actual processing faults without guessing a successful classification.

Represent relationships explicitly: alternate export, contains frame/clip, depends on map/rig/include, and variant. One texture may serve several assets without duplicating source bytes. Group only with evidence. Preserve existing IDs; design a versioned identity rule for sub-assets, including source linkage, region/clip identity, and explicit rename/change handling. Do not merge unrelated same-name files.

Keep shared fields stable and put type-specific facts in versioned metadata. Define applicable stages so an audio item does not need Blender and an intentionally optional caption does not appear as an impossible pending job. Agree on schema/status changes at the plan checkpoint; never relabel an actual failed stage as successful or optional after failure.

### Facts, descriptions, and evidence

Separate extracted facts, supplied metadata, AI observations, suggested uses, and owner corrections. Every generated description must cite the actual media inputs and model/prompt versions. A filename, waveform image, model load, or plausible sentence is not evidence that a model inspected an image or listened to audio.

Apply the current caption severity policy to supported description/review workflows. Use `review_note` for minor uncertainty, `warning` for meaningful errors that could mislead selection, and `caption_faulty` only for failed/incomplete or unusable generation. New review findings carry severity, evidence, and reason. Preserve raw responses and owner states. A technically valid output is not owner approval. Any audio/motion extension of the review schema must preserve these distinctions and be reviewed explicitly.

For actual source, decode, dependency, preview, timeout, or runtime faults: mark the affected item/stage faulty, preserve evidence and usable partial results, and move on. No unchanged automatic retries, repairs, guessed replacements, or edits to originals. Fixing application/test defects is allowed normally. Notes, warnings, or pending owner review alone do not require regeneration. Changed embedded content invalidates affected vectors; severity-only changes do not.

### Search and interfaces

Preserve keyword search and saved browsing without model inference. Add asset-type and relevant technical filters to the shared backend, then expose the same semantics in desktop and MCP. Keep result caps, concise defaults, explicit media availability, and bounded detail responses. Do not return all frames or audio segments in a default shortlist.

Measure filename/metadata, description, and direct-media retrieval separately before tuning fusion. Aggregate views, frames, segments, and exports into logical results. A long track or large atlas must not dominate by having more representations. Sub-asset matches should identify their parent and useful coordinates, timestamps, or clip names.

Same dimensionality does not make different models' vectors compatible. Keep a distinct contract/index channel for another embedding model such as CLAP and fuse ranked results. EmbeddingGemma's shared space enables cross-modal comparisons, but useful mixed-type ranking still needs evaluation. Default to clear type filters while measuring mixed results.

Never silently reuse vectors across changed model/runtime/preprocessing contracts. Plan capability checks, compatibility proof or reindexing, atomic publication, peak disk usage, and recovery. Preserve the active usable publication if replacement fails. Desktop and MCP must agree on candidates, filters, source membership, and current publication. For media returned to agents, distinguish an actual delivered image/audio resource from a local path; verify client consumption before claiming the agent saw or heard it.

### Existing decisions remain binding

- **0001:** New entry points use the local-config precedence helpers.
- **0002:** Background startup scans discover changes without model inference or rendering. Preserve cheap change tokens, stable cards, and explicit processing; do not reintroduce heavy polling or obsolete manual Scan/Status controls.
- **0003:** Reuse per-publication read caches. Add necessary list/filter fields to slim records without mutating shared cached objects.
- **0004:** Route runtime hashes through the shared verified-hash mechanism. Fresh byte audits remain fresh; do not introduce another hash cache.
- **0005:** Ranking and verification stay in the caller. Worker startup loads libraries only; semantic requests load the model under the GPU lease. Preserve idle unloading/heartbeats. Audio/video worker operations require an owner-approved amendment to the current text/image request contract.
- **0006:** Retain the active publication plus two older generations and the documented audit retention. Do not broaden cleanup or delete evidence under this roadmap.

## Milestone sequence

| Step | Deliverable | Prerequisites | Prompt |
| --- | --- | --- | --- |
| 1 | Shared asset structure and type-aware stage dispatch | Current implementation review | [01](prompts/01-asset-foundation.md) |
| 2 | Static sprites, icons, and images | 1 | [02](prompts/02-static-2d-images.md) |
| 3 | Sprite sheets, atlases, animated 2D | 2 | [03](prompts/03-sprite-sheets-and-animation.md) |
| 4 | Textures and material sets | 2; builds on 3's relationships where useful | [04](prompts/04-textures-and-materials.md) |
| 5 | Audio playback, metadata, direct audio search | 1 and established search/preview conventions from 2 | [05](prompts/05-audio-playback-and-search.md) |
| 6 | Evaluated audio descriptions | 5 | [06](prompts/06-audio-descriptions.md) |
| 7 | Selectable 3D animation clips | 1 and temporal/sub-asset conventions from 3 | [07](prompts/07-3d-animation-clips.md) |
| 8 | Shader catalog, then one engine preview adapter | 1-2; reuse relevant dependencies/temporal work from 4 and 7 | [08](prompts/08-shaders.md) |

The recommended execution order is 1-8. Dependencies describe actual prerequisites, not permission to run independent work in parallel. Each stage includes its own app/MCP integration and evaluation; these are not postponed to a final integration phase.

### Step 1 - Establish the shared asset structure

Implement the minimum catalog/schema extension for asset types, file roles, relationships, preview capabilities, and applicable stages. Preserve 3D IDs, overlays, successful generated results, source boundaries, and retrieval behavior. Plan identity/schema migrations explicitly; do not use destructive in-place rewriting of active generations.

Use small synthetic records for existing models, one image, one audio item, and parent/child relationships to validate the design. Only enough image dispatch to prove the boundary belongs here; real image-pack processing and the complete image UI belong in step 2. Extend format eligibility, coverage, caches, and API validation only as needed for this foundation.

Done when: existing 3D fixtures and a captured representative baseline still work; synthetic non-model assets no longer require irrelevant model stages; IDs/relationships and unknown metadata survive publication/reload; old catalog compatibility or migration is demonstrated; the next step has a concrete small implementation surface.

### Step 2 - Static sprites, icons, and images

Start with PNG, JPEG, and WebP, subject to verified decoding. Add first-class image records, measured dimensions/alpha, thumbnails, zoom, type filters, source details, and shared retrieval. Handle native-size/pixel-art viewing and transparent art on useful backgrounds. Preserve originals; record any derived display/model-input transformation.

Reuse Qwen3-VL for descriptions from actual images with an image-appropriate prompt, and EmbeddingGemma for direct image and description search. Test tiny sprites, white/black transparent icons, wide art, duplicates, and damaged images. Decide the small-image preprocessing contract explicitly; nearest-neighbor enlargement is a candidate, not a preapproved default. Keep query/index preprocessing compatible and prevent derived backgrounds becoming invented source colors.

Proposed pilot: 30-50 owner-selected images covering sprites, icons, pixel art, UI artwork, and backgrounds. Unknown purpose remains a generic image rather than a guessed subtype. Initially defer authoring formats, SVG, automatic atlas slicing, and animation playback.

Done when: desktop and MCP can find, inspect, and retrieve an unchanged source image; semantic retrieval consumes actual pixels; difficult transparency/size cases are reviewed; image faults retain useful metadata; source selection and existing 3D searches remain correct.

### Step 3 - Sprite sheets, atlases, and animated 2D

Catalog a sheet as a parent asset, even before frame boundaries are known. Add frame regions, sequence order, duration, trim/rotation/pivot information, and animation children only where supplied metadata or explicit owner input establishes them. Select one concrete atlas metadata dialect and a narrow animated-image format for the first approved slice; do not promise every exporter.

Provide frame inspection and play/pause/scrub/loop controls. Store source rectangles/timing as references, not copies of entire packs. Bounded derived crops may support previews/inference; fingerprint them against the sheet and region metadata. Query results aggregate to the appropriate parent/animation and identify a matching frame when useful.

Proposed pilot: about 10 sheets/atlases plus 10 short animations. Verify padding, trimming, rotation, transparency, timing, and changed metadata. Defer guessed slicing, missing-timing invention, and native Aseprite/PSD adapters unless separately scoped.

Done when: a user can select a sheet, inspect known frames, play a defined sequence, and retrieve the original sheet plus frame/animation metadata. Unsupported or ambiguous metadata remains visible without fabricating extraction or playback success.

### Step 4 - Textures and material sets

Support individual texture records and linked material sets. Record resolution, map role, color-space evidence, channel packing, tiling/scale evidence, normal convention, and dependency completeness. Keep unsupported/unknown details explicit. Use manifests or reviewed conventions for grouping; same-stem names alone are tentative evidence.

Generate bounded, reproducible plane/sphere previews for supported mappings, with renderer/version, lighting, geometry, map bindings, and any substitutions stated. Do not silently fill missing required maps or change normal/channel conventions. Preserve usable individual images when assembly fails. Do not feed normal/roughness maps to Qwen as if they directly depict the final surface.

Search appearance using appropriate color maps and assembled previews plus separate metadata. A rendered sample demonstrates that setup, not physical correctness or universal engine compatibility. Proposed pilot: about 20 varied material sets, including incomplete and packed-channel examples. Begin with conventional image-based materials; defer procedural authoring graphs such as Substance until a separate adapter is approved.

Done when: a query such as "stylized cracked stone" finds useful reviewed candidates; a person can inspect maps and assembled appearance; app/MCP return the complete known set and honest unresolved dependencies; originals stay unchanged.

### Step 5 - Audio playback and direct audio search

Start with WAV, OGG, MP3, and FLAC after checking the actual local decoder path. Inspect duration, channel count, sample rate, format, and available supplied loop metadata. Add waveform display, play/pause, seek, volume, and user-controlled loop playback. Do not autoplay audio during browsing. Being able to repeat playback does not prove a seamless game loop.

Enable EmbeddingGemma's audio encoder through a new validated contract and worker operation. Verify actual decoded samples reach inference and that output vectors are finite, normalized, compatible, and meaningful. Model input uses documented mono/16 kHz processing; leave source files and normal listening playback unchanged. Reuse the downloaded checkpoint only after its pinned audio components are verified.

Define separate bounded policies for short SFX and long tracks: timestamped coverage, context/segment limits, aggregation, and matched-passage navigation. Never silently analyze only an introduction or concatenate disjoint excerpts as a single continuous event. Avoid storing full decoded copies of the collection. Preserve stereo originals and document information lost by model preprocessing.

Proposed pilot: about 40 SFX/ambience clips and 10 BGM tracks, reviewed separately. Compare direct-audio retrieval with filename/metadata search, including silence, very short sounds, long tracks, near matches, and negative queries. No generated audio captions are required yet. If quality is inadequate, record the result and propose a bounded specialist comparison instead of silently changing models.

Done when: audio is useful to browse/play without AI, direct text-to-audio search has actual local evidence, matched segments resolve to one track, GUI/MCP agree, and decoder/search failures preserve usable results.

### Step 6 - Evaluate and add audio descriptions

First conduct a bounded local feasibility study; then integrate only the selected approach within the approved plan. Evaluate sound/music understanding, misleading claims, supported duration, inference cost, Windows/runtime compatibility, GPU use, model storage, and suitability for Assetarium's intended public release. Reverify current publisher terms and exact revisions before any download. Candidate selection is not decided by this roadmap.

Candidates researched October 18:

| Candidate | Planning assessment |
| --- | --- |
| Qwen2.5-Omni-7B | Publisher lists Apache-2.0 and audio/music understanding; memory and any reduced-precision local path need validation. |
| Qwen3-Omni-30B-A3B-Captioner | Designed for arbitrary audio descriptions; original repository reports about 63.4 GB, so not a lightweight default. |
| NVIDIA Audio Flamingo Next Captioner | Relevant speech/sound/music captioning, but publisher specifies noncommercial research use; unsuitable as the default for the intended public release without resolving that constraint. |
| LAION CLAP | A possible specialist retrieval comparison if step 5 is weak; produces embeddings, not captions, and requires a separate model space/channel. |

Descriptions should capture audible events, timbre/texture, rhythm, energy, instrumentation where supported, speech presence, and uncertainty. Separate perceptual mood and suggested uses from measured metadata. Tempo/key are estimates unless supplied/measured with provenance; loop suitability requires evidence. A transcription-only model is insufficient for describing non-speech SFX or instrumental BGM.

Retain segment timestamps, sample coverage, raw responses, generation settings, and review evidence. Compare keyword/direct-audio search with and without caption retrieval on held-out SFX and BGM queries. Keep optional ungenerated captions distinct from failed generation. Do not make audio playback or direct search depend on caption availability.

Done when: a bounded study supports a justified model decision; the approved model produces reviewed descriptions from actual audio; caption retrieval adds demonstrated value or is honestly recorded as not yet justified; faults, warnings, and owner review remain distinct. A failed feasibility study is a documented partial outcome, not implementation completion or permission for unbounded model trials.

### Step 7 - Selectable 3D animation clips

Catalog clips as selectable children of their original source model/animation file. Distinguish authored clips/actions, rig bindings, and unused actions; enumeration alone does not prove playback. Start with a narrowly approved skeletal-animation path in supported glTF/GLB or FBX inputs. Verify duration and timing rather than treating Blender scene defaults as authoring facts.

Provide clip selection and play/pause/scrub/loop controls plus bounded offline previews. Record rig/skeleton references, known bone data, clip range, evaluated timing, root transform/motion measurements, and dependencies. Animation-only files may retain usable metadata when no compatible preview mesh/rig is available; record the preview limitation/fault instead of claiming animated success.

Use ordered timestamped frames/video for descriptions and evaluate motion-aware embeddings before exposing motion-search claims. Qwen video support is a candidate beyond the existing image adapter. EmbeddingGemma's default video sampling is one frame per second, so validate sampling for fast game motions. Single thumbnails or unordered frame averages are insufficient evidence for temporal distinctions such as movement direction.

Proposed pilot: 10-20 clips covering idle, locomotion, jumps, attacks, short actions, root motion, in-place motion, and animation-only cases. Do not automatically retarget, repair rigs, rewrite originals, or claim target-game compatibility. Morph/baked/vertex animation support is a later adapter unless explicitly selected.

Done when: a user can find a motion, play the identified clip, and retrieve the source with clip/rig references; temporal claims have reviewed evidence; unresolved compatibility is visible; existing static 3D behavior remains usable.

### Step 8 - Shader catalog, then one engine preview adapter

Deliver two slices inside this milestone. **8A** catalogs source code, supplied engine/version/renderer information, parameters, include/texture dependencies, supplied screenshots, and text search. **8B** adds a controlled preview adapter for one engine and shader category. Both slices require their own approved scope/plan if not approved together; do not treat 8A as completion of the preview slice.

Godot canvas shaders are the proposed first preview candidate because of the owner's game work; the engine/category choice remains pending. Distinguish Godot, Unity/HLSL/Shader Graph, Unreal materials, and other shader systems. Extensions alone do not establish compatibility, and a shader is not generally portable between them.

A preview needs a recorded engine build, scene/object, parameter values, textures, lighting where relevant, time sampling, and camera. Use a controlled temporary preview project, approved bounded inputs, and generated results outside originals. Do not execute arbitrary pack projects or their editor/tool scripts. Record compilation/runtime faults and partial static results; do not repair shader source automatically.

Use code/metadata retrieval first, with a distinct validated code-query contract if introduced. Use Qwen for actual rendered appearance and EmbeddingGemma for screenshots/temporal previews after validation. Do not claim behavior based only on plausible code interpretation. Supplied screenshots remain supplied evidence unless linkage to the selected source/setup is established.

Proposed pilot: about 10 shader assets covering static and animated effects plus missing dependencies/compilation failures. Bound preview time, size, and retained video volume. Additional engines, graph exporters, universal conversion, and automatic source fixes are separate work.

Done when: source/dependency search works in both interfaces; at least one approved engine/category renders reproducibly; queries such as "animated water distortion" lead to inspectable effects with explicit requirements; unsupported engines and failed previews remain honest catalog states.

## Verification and completion for every milestone

Before coding, capture only the relevant current baseline. Use small synthetic fixtures for identity, decoding, metadata, migration, dependency boundaries, stage invalidation, and partial-result behavior; use approved original assets by path for representative integration. Do not copy asset packs into fixtures. Run focused checks plus required repository checks appropriate to the change; broaden when changes/failures justify it, not by repeatedly rerunning unrelated expensive inference.

Each handoff must report:

1. Approved scope, what changed, touched components, and remaining exclusions.
2. Actual technical checks and evidence paths, including relevant existing 3D preservation and GUI/MCP parity.
3. Real media/inference demonstrations separately from mocks, schema validity, and model loading.
4. A fixed evaluation sample and held-out queries, with useful top-five matches, negative/near-match behavior, and per-channel comparisons. Agree on relevance criteria before seeing results; do not invent a universal score threshold.
5. Coverage by asset type and stage: success, pending work, unsupported content, actual faults, partial results, caption notes/warnings, and owner-review state.
6. Cold/warm latency where relevant, peak GPU/RAM observations, and unique allocated peak/retained storage with original/model exclusions stated.
7. Owner review still required, known limitations, whether the milestone is technically complete, and the next runnable scope. Do not equate technical completion with owner acceptance.

Update `docs/progress.md` and directly affected contracts/usage docs during implementation, preserving historical receipts. No commit, push, PR, release, or publication of repository changes is authorized by these prompts; follow explicit session instructions and applicable repository policy. Publishing a local catalog generation is a separate application operation within approved processing scope.

## Rough duration and storage assumptions

These are planning estimates, not measurements or approved budgets. Working days include implementation and focused verification; they exclude waiting for owner reviews. Estimates assume the existing Windows app/runtimes remain usable, modest supplied metadata, and small pilots rather than whole-collection processing.

| Step | Rough effort | Generated pilot output allowance, excluding dependencies/models/originals |
| --- | --- | --- |
| 1 | 2-4 working days | Under 50 MiB of new synthetic evidence; existing-index migration copies need separate sizing |
| 2 | 3-5 working days | 50-200 MiB for 30-50 images |
| 3 | 3-5 working days | 100-300 MiB for bounded sheets/animation previews |
| 4 | 4-7 working days | 100-500 MiB for about 20 material sets |
| 5 | 4-7 working days | 50-300 MiB for waveforms, segments/indexes, and evidence; avoid retained full decoded audio |
| 6 | 4-8 working days | 50-200 MiB for pilot results; model/runtime installation is additional and potentially many GiB |
| 7 | 5-9 working days | 200-1,000 MiB for bounded clip previews |
| 8 | 7-14 working days across 8A/8B | 200-1,000 MiB for bounded effect previews; engine installation is additional |

Total rough effort is 32-59 working days, approximately 6-12 working weeks. Audio model feasibility, native codecs, animation rig compatibility, and shader setup are the greatest uncertainties. Generated pilot output is on the order of 1-4 GiB across these assumptions; peak usage can be higher because publications, evidence, temporary rendering, and migrations coexist. Do not multiply logical folder sizes to estimate hard-linked dependency storage.

Recalculate every selected milestone from actual samples at its plan checkpoint. Existing full embedding weights appear to include audio; this is not a promise of zero decoder/dependency growth. A new caption model or runtime needs exact download, installed unique allocation, transient peak, and alternatives stated before installation. Do not extrapolate the generated-output allowance to the full collection or treat prior source-specific budgets as expansion approval.

Follow `AGENTS.md` and `docs/storage.md`: use existing wrappers and `cache/uv` hard links, independently pinned runtimes where necessary, and immutable dependency files. Explain any projected growth of at least 500 MiB, another runtime, or crossing the existing pilot target. Save new base-Python `scripts/storage-report.py` receipts under `data/storage/` before/after installations or bulk work, and include source-side generated allocation in combined accounting. Keep shared revisions in configured model storage. Apply documented cache cleanup only after verification; retain fault/evidence/results and approved generations.

## Decisions still open

- Representative source packs and the exact pilot membership for each type.
- Final asset/sub-asset schema and identity rules, with migration costs.
- Tiny-image and transparency preprocessing; first atlas metadata dialect and animated-image format.
- Supported material conventions and how uncertain map assignments are reviewed.
- Audio segmentation/coverage, useful retrieval thresholds judged on the pilot, and whether specialist retrieval is needed.
- Audio caption model, inference precision/hardware/runtime, release suitability, and storage budget.
- First animation format/rig path and motion sampling policy.
- First shader engine/category and the permitted preview setup.

Resolve each at the relevant checkpoint through read-only evidence and owner input where needed. Do not stop unrelated approved work merely because a later milestone has an open decision.

## Explicitly deferred

Automatic game-engine imports, source editing/repair, asset generation, model fine-tuning, universal file conversion, guessed sprite slicing, automatic animation retargeting, procedural material graph interpreters, all-engine shader execution, cloud inference/hosting, and whole-computer indexing. Additional formats are deliberate adapters, not implied support from recognizing their extension. Artistic suitability, seamless audio looping, and target-game compatibility remain reviewable claims with their own evidence.

## Primary references

Consult current primary documentation again during the relevant milestone; publisher support is not proof of local compatibility.

- [EmbeddingGemma 2 model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2): modalities, shared space, precision, selective encoder loading, context limits.
- [EmbeddingGemma multimodal inference](https://ai.google.dev/gemma/docs/embeddinggemma/multimodal-embeddinggemma-with-sentence-transformers): audio input/decoding and video frame sampling.
- [Qwen3-VL-2B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct): current vision model and publisher video capabilities.
- [Qwen2.5-Omni-7B](https://huggingface.co/Qwen/Qwen2.5-Omni-7B): candidate audio/music understanding and publisher terms.
- [Qwen3-Omni Captioner](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Captioner) and [files](https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Captioner/tree/main): specialist captioning candidate and original repository size.
- [Audio Flamingo Next Captioner](https://huggingface.co/nvidia/audio-flamingo-next-captioner-hf): candidate capabilities and noncommercial research restriction.
- [LAION CLAP](https://huggingface.co/laion/larger_clap_music_and_speech): specialist text/audio embeddings, not description generation.
- [glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html): source format structures and animation semantics.
- [Godot shading language](https://docs.godotengine.org/en/stable/tutorials/shaders/shader_reference/shading_language.html): proposed first engine-specific shader path.
