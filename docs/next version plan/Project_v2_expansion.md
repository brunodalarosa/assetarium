# Assetarium v2 expansion

Prepared October 18, 2026. Status: step 1 approved and technically complete;
owner acceptance remains pending. Steps 2–8 remain proposed. See
[current evidence](../asset-foundation-verification.json) and [progress](../progress.md).

## Purpose and authority

Expand Assetarium from a 3D-model catalog into a local catalog for sprites, icons, other 2D images, audio, textures/materials, shaders, and 3D animation clips. Deliver eight bounded milestones, each usable through the Windows app and the shared agent-facing backend.

This document is the expansion reference for Codex, Claude Code, and future agents. It replaces the original numbered prompts, not the existing application. Earlier v1 proposals, setup instructions, and step numbers are historical context rather than the expansion workflow. Current implementation evidence lives in [progress.md](../progress.md). Do not infer current completion from this roadmap.

The owner requested this documentation package. Creating it does not approve implementation, dependency installation, model downloads, source enrollment, bulk processing, or a change to an owner-approved decision. Follow the current root [AGENTS.md](../../AGENTS.md), [decisions](../decisions/README.md), [caption policy](../caption-quality.md), and [storage policy](../storage.md). If this proposal conflicts with them, surface the conflict before implementation; do not silently change the policy.

Before implementation, confirm scope and implementation plan together in one checkpoint, recognizing any explicit approval already given for the same unchanged scope and plan:

Restate the selected milestone's scope in one sentence, identify inclusions, exclusions, and ambiguities, then explain changes, ownership, risks, verification, estimated duration, and additional peak/retained disk space with assumptions and significant uncertainty. Ask **"Do this scope and implementation plan match what you want, and do you approve proceeding?"**, then stop and wait for the owner's answer. Do not edit implementation files before explicit approval.

Read-only investigation may prepare this checkpoint. Confirm it again if the scope or plan changes materially. Each prompt covers one milestone. Expansion steps 1 and 2 may be bundled only when that combined scope and plan are explicitly approved. Do not proceed automatically to the next step or spawn subagents without authorization. A milestone may require several chats; retain a resumable handoff.

## Paths and ownership

| Item | Location or responsibility |
| --- | --- |
| Existing repository | `C:\BrunoOS\Local-Asset-Library` |
| This reference | `docs/next version plan/Project_v2_expansion.md` |
| Expansion launch prompts | `docs/next version plan/prompts/01-asset-foundation.md` through `08-shaders.md` |
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
- The current pipeline has inspection, caption, and embedding stages, with immutable publication generations, source-side generated results, owner overlays, fault records, and shared desktop/MCP retrieval. Under decisions 0007-0008, **Process assets** performs inspection/previews and image search vectors, then publishes; optional **Generate descriptions** separately batches missing descriptions, builds description vectors, then publishes. Importing never generates descriptions.
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

Keep shared fields stable and put type-specific facts in versioned metadata. Define applicable stages so an audio item does not need Blender. Descriptions are optional extra data: missing descriptions are optional work, and failed descriptions retain their actual failure state without becoming import work or import failures. Agree on schema/status changes at the scope/plan checkpoint; never erase an actual failure or relabel it successful. New media types must validate their own direct-media search path rather than assuming the existing image-vector path accepts audio or video.

### Optional descriptions and notifications

Preserve the separation in [decision 0008](../decisions/0008-optional-descriptions-and-notifications.md). **Process assets** prepares usable assets and their applicable direct-media vectors, then publishes without caption generation. For existing image-based processing, only image-vector failures affect the embedding part of the import outcome; an overall embedding `partial`/`failed` state caused only by description vectors does not make the import incomplete. Asset names and image vectors already enable search without descriptions. Extend this separation to new types through their approved stage contracts.

**Generate descriptions** in **Settings → Asset sources** is a separate per-source `describe` operation. It processes assets with ready renders and `description_state == 'missing'`, then builds description vectors and publishes. Reuse the operation lease, progress, Cancel, storage budget, and current batching. New audio/temporal adapters must validate their own input-readiness and inference contracts before extending this operation. Recorded failures are never retried without an explicit owner request. Cancel, GPU-memory stops, and storage stops still publish completed descriptions.

Keep missing/failed descriptions out of main-view source cards and **Importing failures report**. Preserve failures in asset detail and each source's description counts. Default `combined` search still uses valid descriptions; a missing, stale, or invalid description silently removes only the description channel, without excluding the asset or reporting an exclusion fault in desktop or MCP. Source/dependency/media faults remain subject to the normal fault policy.

Reuse the existing notification bell, panel, toasts, and `data/library/notifications.json`: one **Descriptions ready to generate** notice per source after processing leaves missing descriptions, plus the first-launch notice for existing sources; **Not now** stays quiet until more descriptions are missing. Record a report per describe run (finished / with failures / cancelled / stopped / interrupted). Notices arrive with `sources()` and the file participates in `changes()`; closing the panel marks notices read. Offer only actions that can change the displayed state. Notifications report facts and optional work; they never start processing themselves.

For existing Qwen image descriptions, preserve [decision 0007](../decisions/0007-batched-description-generation.md): reuse `caption_batching.py`, left padding, and the pinned model/revision/prompt/input preparation/sampling/seed, 1,100-token limit, and 120-second generation limit. **Settings → General → Description batch size** offers 1, 2, 4, or 8 (default 8), stored as `caption_batch_size` in `data/library/settings.json`. Each asset is validated, saved, published, and checkpointed individually. Invalid inputs/outputs fail only their asset; a batch-wide runtime fault fails its assets without retry.

Out of GPU memory during description generation is a machine limit, not an asset fault: stop, tell the user to lower the batch size, and leave unfinished assets pending without recording them failed or automatically retrying a smaller batch. Cancel waits for the current batch. Overnight `inflight.json` lists all batch members; interruption records each as interrupted without regenerating it in that run. Keep existing description fingerprints and recorded generation modes (`sequential` when absent); new batched outputs record `generation_mode: batched-v1` and batch size/assets/position. Batch size is provenance only and never re-queues results. Batched wording can depend on the other assets in that batch, so exact wording on a rerun is not guaranteed. Do not change `caption_backend.py` or invalidate existing sequential descriptions without explicit approval. New image-specific prompts and future audio/video generation require separately validated contracts; the current image batch sizes and settings are not proof of support for another model or modality.

### Facts, descriptions, and evidence

Separate extracted facts, supplied metadata, AI observations, suggested uses, and owner corrections. Every generated description must cite the actual media inputs and model/prompt versions. A filename, waveform image, model load, or plausible sentence is not evidence that a model inspected an image or listened to audio.

Apply the current caption severity policy to supported description/review workflows. Use `review_note` for minor uncertainty, `warning` for meaningful errors that could mislead selection, and `caption_faulty` only for failed/incomplete or unusable generation. New review findings carry severity, evidence, and reason. Preserve raw responses and owner states. A technically valid output is not owner approval. Any audio/motion extension of the review schema must preserve these distinctions and be reviewed explicitly.

For actual source, decode, dependency, preview, timeout, or runtime faults: mark the affected item/stage faulty, preserve evidence and usable partial results, and move on. Description GPU-memory exhaustion follows the machine-limit handling above. Failed descriptions remain optional-data failures, separately visible without becoming import failures. No unchanged automatic retries, repairs, guessed replacements, or edits to originals. Fixing application/test defects is allowed normally. Notes, warnings, or pending owner review alone do not require regeneration. Changed embedded content invalidates affected vectors; severity-only changes do not.

### Search and interfaces

Preserve keyword search and saved browsing without model inference. Add asset-type and relevant technical filters to the shared backend, then expose the same semantics in desktop and MCP. Keep result caps, concise defaults, explicit media availability, and bounded detail responses. Do not return all frames or audio segments in a default shortlist.

Measure filename/metadata, description, and direct-media retrieval separately before tuning fusion. Aggregate views, frames, segments, and exports into logical results. A long track or large atlas must not dominate by having more representations. Sub-asset matches should identify their parent and useful coordinates, timestamps, or clip names.

Same dimensionality does not make different models' vectors compatible. Keep a distinct contract/index channel for another embedding model such as CLAP and fuse ranked results. EmbeddingGemma's shared space enables cross-modal comparisons, but useful mixed-type ranking still needs evaluation. Default to clear type filters while measuring mixed results.

Never silently reuse vectors across changed model/runtime/preprocessing contracts. Plan capability checks, compatibility proof or reindexing, atomic publication, peak disk usage, and recovery. Preserve the active usable publication if replacement fails. Desktop and MCP must agree on candidates, filters, source membership, and current publication. For media returned to agents, distinguish an actual delivered image/audio resource from a local path; verify client consumption before claiming the agent saw or heard it.

### Existing decisions remain binding

- **[0001](../decisions/0001-config-local-precedence.md):** New entry points use `load_project_config` or `project_config_path`: ignored `config.local.toml` takes precedence over tracked `config.example.toml`.
- **[0002](../decisions/0002-startup-scan-and-change-detection.md):** Scan enabled sources in the background at every launch without models or rendering. Unchanged content, including timestamp-only refreshes, must not rewrite scan/status files or bump views. Poll cheap stat tokens through `changes()` every 1.5 s; fetch data on changed tokens or while source operations run. Preserve visible cards through `refreshContext`. Do not add heavy periodic polls or manual Scan/Status controls; **Refresh published view** and **Importing failures report** remain.
- **[0003](../decisions/0003-per-publication-read-caches.md):** Reuse publication-identity read caches and per-file-stat digests/classification reads. Add required list/filter fields to `library_cache.slim` without mutating shared records; detail reads full records. Processing/indexing must read fresh full records through `membership.records`, never cached slim records.
- **[0004](../decisions/0004-stat-identity-hash-reuse.md):** Route runtime hashes through `verified_hash` and the shared `cache/file-hashes.sqlite`; scans seed it. Reuse requires unchanged file identity; missing/busy/corrupt cache data means hashing bytes again. Changed/replaced/missing required source or preview files still cause the appropriate exclusion/fault; unusable descriptions follow 0008 instead. Fresh byte audits and removal checks stay fresh. Preserve source/link boundaries, preview-identity thumbnail caching, and source verification in detail/`get_asset`; do not add another hash cache.
- **[0005](../decisions/0005-embedding-worker-and-prestart.md):** Keep the worker protocol to `contract`/`text`/`image`, with embedding requests returning vectors; catalog verification, validated vector matrices, keyword search, and ranking stay in the caller. Desktop pre-starts libraries at launch without a model/GPU lease; MCP starts its worker on the first semantic query. Load the model only for semantic requests under the GPU lease, unload after 10 idle minutes or immediately for a processing/peer GPU request, and retain 5 s busy heartbeats/90 s silence fault handling. Busy-queue/stopped-worker `TransientFault` errors are not retained per-query faults; keyword search never contacts the worker. Keep stdout protocol-only and settings/source actions/`changes()` outside the presentation lock. Audio/video operations require an owner-approved amendment.
- **[0006](../decisions/0006-retention.md):** After each combined publication, retain the active generation plus the two newest older `v_*` generations centrally and in each source; remove shortcuts to retired generations, leave work/scan folders alone, and do not fail publication on a retention fault. Keep the ten newest launch audits in `data/gui/runs`; do not touch other GUI evidence or MCP runs. Reuse `scratch/pytest`; old scratch needs the explicit cleanup plan/apply workflow. Removal uses `maintenance_files`, fresh hashes, link containment/refusal rules, changed-file faults, and receipts under `data/maintenance/`. This roadmap does not broaden those exact cleanup locations or authorize other evidence deletion.
- **[0007](../decisions/0007-batched-description-generation.md):** Preserve image-description batching, per-asset outcomes, completed fingerprints and generation provenance. GPU-memory exhaustion stops with assets pending and no smaller-batch retry. Changing the batch-size preference never re-queues descriptions. Validate new modality contracts separately.
- **[0008](../decisions/0008-optional-descriptions-and-notifications.md):** Importing never generates descriptions. Reuse separate per-source **Generate descriptions**, description vectors, and notifications. Missing/failed descriptions neither gate usable imports nor appear as import failures; unusable descriptions silently leave only their search channel. Retain failure evidence and never retry recorded failures without an explicit request.

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

Implement the minimum catalog/schema extension for asset types, file roles, relationships, preview capabilities, and applicable stages. Preserve 3D IDs, overlays, successful generated results, source boundaries, and retrieval behavior. Keep import/direct-media stages separate from optional description generation and description vectors, including outcome counts, search fallback, and notification readiness. Plan identity/schema migrations explicitly; do not use destructive in-place rewriting of active generations.

Use small synthetic records for existing models, one image, one audio item, and parent/child relationships to validate the design. Only enough image dispatch to prove the boundary belongs here; real image-pack processing and the complete image UI belong in step 2. Extend format eligibility, coverage, caches, and API validation only as needed for this foundation.

Done when: existing 3D fixtures and a captured representative baseline still work; synthetic non-model assets no longer require irrelevant model stages; optional missing/failed descriptions stay separate from import outcomes without losing faults; IDs/relationships and unknown metadata survive publication/reload; old catalog compatibility or migration is demonstrated; the next step has a concrete small implementation surface.

### Step 2 - Static sprites, icons, and images

Start with PNG, JPEG, and WebP, subject to verified decoding. Add first-class image records, measured dimensions/alpha, thumbnails, zoom, type filters, source details, and shared retrieval. Handle native-size/pixel-art viewing and transparent art on useful backgrounds. Preserve originals; record any derived display/model-input transformation.

Use EmbeddingGemma for direct image search during **Process assets**, without waiting for descriptions. Offer Qwen3-VL descriptions from actual images through separate **Generate descriptions**, with an image-appropriate versioned prompt and validated reuse of existing batching, provenance, controls, and notifications. Add description search when valid results exist; missing/stale/failed descriptions must not block import or exclude an otherwise usable image. Preserve existing 3D description contracts and fingerprints when adding the new prompt. Test tiny sprites, white/black transparent icons, wide art, duplicates, and damaged images. Decide the small-image preprocessing contract explicitly; nearest-neighbor enlargement is a candidate, not a preapproved default. Keep query/index preprocessing compatible and prevent derived backgrounds becoming invented source colors.

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

Search appearance using direct vectors from appropriate color maps and assembled previews plus separate metadata. Optional Qwen appearance descriptions use the separate per-source generation operation; their absence/failure does not gate usable materials or become an import failure. Reuse applicable batching/notification behavior while validating material-specific prompts and inputs. A rendered sample demonstrates that setup, not physical correctness or universal engine compatibility. Proposed pilot: about 20 varied material sets, including incomplete and packed-channel examples. Begin with conventional image-based materials; defer procedural authoring graphs such as Substance until a separate adapter is approved.

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

Retain segment timestamps, sample coverage, raw responses, generation settings, and review evidence. Compare keyword/direct-audio search with and without caption retrieval on held-out SFX and BGM queries. Integrate audio descriptions as optional extra data through the separate per-source operation, with validated audio readiness, generation settings, batch capability, description vectors, and notifications. Do not assume the image model's batch sizes or input settings suit the selected audio model. Keep optional ungenerated captions distinct from failed generation; retain faults in detail/counts rather than import-failure reporting, and silently omit unusable descriptions from search. Do not make audio imports, playback, or direct search depend on caption availability, or retry recorded failures without an explicit request.

Done when: a bounded study supports a justified model decision; the approved model produces reviewed descriptions from actual audio; caption retrieval adds demonstrated value or is honestly recorded as not yet justified; faults, warnings, and owner review remain distinct. A failed feasibility study is a documented partial outcome, not implementation completion or permission for unbounded model trials.

### Step 7 - Selectable 3D animation clips

Catalog clips as selectable children of their original source model/animation file. Distinguish authored clips/actions, rig bindings, and unused actions; enumeration alone does not prove playback. Start with a narrowly approved skeletal-animation path in supported glTF/GLB or FBX inputs. Verify duration and timing rather than treating Blender scene defaults as authoring facts.

Provide clip selection and play/pause/scrub/loop controls plus bounded offline previews. Record rig/skeleton references, known bone data, clip range, evaluated timing, root transform/motion measurements, and dependencies. Animation-only files may retain usable metadata when no compatible preview mesh/rig is available; record the preview limitation/fault instead of claiming animated success.

Evaluate motion-aware direct embeddings before exposing motion-search claims. Optional descriptions use ordered timestamped frames/video through separate **Generate descriptions**, after validating temporal inputs, batching, and provenance; missing/failed descriptions neither gate clip processing/playback nor exclude usable clips from search. Qwen video support is a candidate beyond the existing image adapter. EmbeddingGemma's default video sampling is one frame per second, so validate sampling for fast game motions. Single thumbnails or unordered frame averages are insufficient evidence for temporal distinctions such as movement direction.

Proposed pilot: 10-20 clips covering idle, locomotion, jumps, attacks, short actions, root motion, in-place motion, and animation-only cases. Do not automatically retarget, repair rigs, rewrite originals, or claim target-game compatibility. Morph/baked/vertex animation support is a later adapter unless explicitly selected.

Done when: a user can find a motion, play the identified clip, and retrieve the source with clip/rig references; temporal claims have reviewed evidence; unresolved compatibility is visible; existing static 3D behavior remains usable.

### Step 8 - Shader catalog, then one engine preview adapter

Deliver two slices inside this milestone. **8A** catalogs source code, supplied engine/version/renderer information, parameters, include/texture dependencies, supplied screenshots, and text search. **8B** adds a controlled preview adapter for one engine and shader category. Both slices require their own approved scope/plan if not approved together; do not treat 8A as completion of the preview slice.

Godot canvas shaders are the proposed first preview candidate because of the owner's game work; the engine/category choice remains pending. Distinguish Godot, Unity/HLSL/Shader Graph, Unreal materials, and other shader systems. Extensions alone do not establish compatibility, and a shader is not generally portable between them.

A preview needs a recorded engine build, scene/object, parameter values, textures, lighting where relevant, time sampling, and camera. Use a controlled temporary preview project, approved bounded inputs, and generated results outside originals. Do not execute arbitrary pack projects or their editor/tool scripts. Record compilation/runtime faults and partial static results; do not repair shader source automatically.

Use code/metadata retrieval first, with a distinct validated code-query contract if introduced. Use EmbeddingGemma for screenshots/temporal previews after validation. Offer Qwen descriptions of actual rendered appearance through separate optional generation with validated inputs/batching and the existing notification workflow; their absence/failure does not block cataloging, previews, or other search channels. Do not claim behavior based only on plausible code interpretation. Supplied screenshots remain supplied evidence unless linkage to the selected source/setup is established.

Proposed pilot: about 10 shader assets covering static and animated effects plus missing dependencies/compilation failures. Bound preview time, size, and retained video volume. Additional engines, graph exporters, universal conversion, and automatic source fixes are separate work.

Done when: source/dependency search works in both interfaces; at least one approved engine/category renders reproducibly; queries such as "animated water distortion" lead to inspectable effects with explicit requirements; unsupported engines and failed previews remain honest catalog states.

## Verification and completion for every milestone

Before coding, capture only the relevant current baseline. Use small synthetic fixtures for identity, decoding, metadata, migration, dependency boundaries, stage invalidation, and partial-result behavior; use approved original assets by path for representative integration. Do not copy asset packs into fixtures. Run focused checks plus required repository checks appropriate to the change; broaden when changes/failures justify it, not by repeatedly rerunning unrelated expensive inference.

Each handoff must report:

1. Approved scope, what changed, touched components, and remaining exclusions.
2. Actual technical checks and evidence paths, including relevant existing 3D preservation and GUI/MCP parity.
3. Real media/inference demonstrations separately from mocks, schema validity, and model loading.
4. A fixed evaluation sample and held-out queries, with useful top-five matches, negative/near-match behavior, and per-channel comparisons. Agree on relevance criteria before seeing results; do not invent a universal score threshold.
5. Coverage by asset type and stage: success, pending import work versus optional missing descriptions, unsupported content, actual faults, partial results, caption notes/warnings, and owner-review state. Verify description failures remain in detail/source counts without becoming import failures, unusable descriptions leave other search channels usable, notifications report actionable states without starting work, and completed descriptions survive cancellation/resource stops. For image-description batching changes, verify per-asset fault isolation, GPU-memory stops leaving assets pending, provenance, and no re-queue when batch size changes. Check relevant startup/change-token/cache/worker/retention preservation when those paths are touched.
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

Follow `AGENTS.md` and `docs/storage.md`: use existing wrappers and `cache/uv` hard links, independently pinned runtimes where necessary, and immutable dependency files. Explain any projected growth of at least 500 MiB, another runtime, or crossing the existing pilot target. Save new base-Python `scripts/storage-report.py` receipts under `data/storage/` before/after installations or bulk work, and include source-side generated allocation in combined accounting. Keep shared revisions in configured model storage. Apply documented cache cleanup only after verification and decision 0006 retention only in its exact locations; keep receipts, faults, protected evidence, and usable active results.

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
