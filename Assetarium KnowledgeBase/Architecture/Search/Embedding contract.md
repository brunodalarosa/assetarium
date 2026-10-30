---
tags: [architecture]
parent: "[Architecture](../Architecture.md)"
status: draft
verified:
branch:
level: system
code: [embedding_backend.py, embedding_cpu.py, library_index.py, retrieval.recorded_contract]
---
# Step 5 embedding and retrieval contract

Up: [Architecture](../Architecture.md) · Where in code: [Search](../../Notebook/Search/Search.md). Moved from `docs/embedding-contract.md` on 2026-10-28 (written as pilot step 5).

Verified October 11, 2026 against Google's [model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2),
[text inference guide](https://ai.google.dev/gemma/docs/embeddinggemma/inference-embeddinggemma-with-sentence-transformers),
[multimodal inference guide](https://ai.google.dev/gemma/docs/embeddinggemma/multimodal-embeddinggemma-with-sentence-transformers)
and the [publisher repository](https://huggingface.co/google/embeddinggemma-2).
The Google pages were updated October 6. The repository metadata reports
Apache-2.0 and no access gate. No alternative model/runtime or fine-tuning used.

## Inference

Weights resolve through `[storage].models` (the shared model directory in `config.local.toml`, or the project `models/` folder).
Runtime caches remain under project `cache/`. Relocation changes storage only;
the adapter, model revision, runtime lock and inference fingerprint are unchanged.

`docs/embedding-model.json` pins `google/embeddinggemma-2` revision
`914f7f89142e33e77833254d9c9b90c3cef7303b`. Download the original checkpoint;
disable audio at load via `config_kwargs={"audio_config": None}`. Actual loaded
text/vision parameter count: 438,760,448. Vision is present; audio is absent.

Use the isolated `runtime/embedding/uv.lock` and `.venv-embedding`. The runtime
wrapper reuses only project-local dependency downloads from `cache/uv-caption`;
it does not update `.venv-caption`, the base environment or other installations.
Model weights/configuration/tokenizers are hash-checked against the exact-revision
receipt before every load. Native library implementations only, offline/local
files only, no remote model code, no cloud inference. Inference runs at CUDA BF16
on the verified RTX 5070 with SDPA and TF32 disabled. FP16 and silent CPU/precision
fallback are forbidden. A different hardware/precision contract requires explicit
validation and reindexing; CPU inference is not verified in this step.

Text search queries use `task: search result | query: {query}`. Description documents
have no title and use `title: none | text: {observations}`. Prefixes are applied
explicitly and the runtime's default prompt is suppressed. Documents contain only
the structured visual observations: identity with uncertainty, prose, shape,
colors, parts, style, distinguishing features and uncertainties. Suggested uses,
pack/filename text and measured geometry are excluded from description vectors.
Descriptions remain provisional observations, not verified technical facts.
Live owner correction files are validated; their observation changes invalidate
description vectors. Suggestions remain separately available in detail records.

Images use the documented `{"image": PIL_image}` API, with **no text prefix**.
EXIF transpose, decode, RGBA composite over gray RGB (82,82,82), conversion to RGB,
native image size and the publisher processor's 280 soft-token budget are fixed.
No contact sheets/textures are indexed as individual asset views. Image queries
use the same preprocessing as indexed images. Source/project relative reference
paths only; URLs, traversal and external absolute paths are rejected.

**2D image assets (expansion step 2)** are embedded from exactly one recorded
`model_input` preview: the derived `image-model-input-b-v1` PNG described in the
[catalog contract](../Sources%20and%20Catalog/Catalog%20contract.md) (nearest-neighbour enlargement to at least
256 px, flat rgb(82,82,82) behind transparent pixels, Lanczos reduction above
1,024 px). This file then passes through the unchanged preprocessing above, so
the embedding contract, adapter hash, capability receipt and every existing
vector are unchanged; tiny sprites no longer reach the 16 px rejection. Originals,
SVG display rasters and thumbnails are presentation, never extra vectors. A
reference query on an image asset uses that same `model_input` file, so query and
index preparation are identical. Images also get a description vector once a
valid description exists; a missing or failed one leaves only that channel
(decision 0008).

All vectors retain 768 dimensions and are checked for finite, nonzero output,
converted to FP32 and L2 normalized. Stored vectors must already be unit length;
search refuses corrupt/checksum-mismatched, nonfinite, zero or nonunit vectors.
An 8,192-token input limit is checked before text truncation, and actual processed
pixel tensors/context are checked. Inference faults propagate or become explicit
item failures; there is no synthetic/random/zero-vector fallback and no ranking
fallback after a query inference error.

## Persistence and failure handling

`data/embeddings/index.sqlite` is separate from the existing catalog/FTS baseline.
The current contract includes model ID/revision/file hashes, dependency versions,
runtime lock hash, backend source hash, precision, device/attention, dimensions,
both text prompts, image preprocessing and normalization. Each vector stores the
contract fingerprint, modality/role, input/source fingerprint, dimension, FP32
bytes/checksum and its individual view reference. Query and index contracts must
match exactly before similarity is computed. Input fingerprints are checked
against current descriptions/view bytes; unavailable or changed input rows are
excluded with evidence. Changing a contract requires an explicit capability check
and reindex, not automatic migration. A backend source or runtime lock that differs
from `data/embeddings/capability.json`, or else from the published index's
`data/library/embedding-contract.json`, only by LF/CRLF line endings (a git checkout)
keeps its recorded hash (`retrieval.recorded_contract`); any other byte change is
still a contract change. The published index counts because a source's `metadata-lal`
can bring vectors built on another checkout to an install with no search check yet;
the search check then records that reconciled form.

Only the existing 40 IDs in the pilot manifest are accepted for step 5 indexing.
Jobs publish atomically to SQLite and preserve usable successful items. Unchanged
successful vectors are reused after verification; unchanged inference failures
are retained without another inference attempt. Changed inputs/contracts are new
jobs. Old vectors cannot survive failed replacement. Jobs/report evidence exposes
absent captions, inference errors and individual image faults. Process/load faults
leave the existing index intact and make the command fail.

The road-crossroad caption remains failed; its actual views can still be indexed.
BirchTree_1's missing image datablock is verified `required_for_render: false`;
retain this source fault and its unresolved dependency in detail without discarding
usable geometry/views. Missing/stale source files or required dependencies exclude
the logical asset. Conservatively, any missing/stale recorded alternate source
also excludes the asset. Unknown binary/alternate dependency completeness is
reported, never inferred from a successful render.

## Retrieval and evidence

Omitting `--mode` preserves the step 2 full-catalog keyword CLI exactly. Explicit
`keyword`, `description`, `image`, `combined` and `reference` modes operate on the
same pilot. Filename/keyword ranking uses the existing FTS5 literal AND terms and
BM25 ordering. Semantic ranking is normalized exact NumPy dot product; each image
channel ranks an asset by its best individual view. All views/formats resolve to
one logical ID. Combine unique-asset ranked lists by reciprocal rank fusion with
`k=60`, retaining channel rankings and deterministic ID tie-breaking.

Before every search/detail, boundary-resolve and SHA-256 verify recorded source
files and required dependency bytes. Verified filters: pack, available format,
maximum inspected evaluated-instance triangle count, and inspected armature
presence (`rigged`, an enumeration rather than behavior/animation validation).
Technical filters exclude unknown/uninspected facts; combined format and technical
filters must refer to the actual inspected format. Caption colors/styles/uses
are not verified metadata filters. Unknown filter keys are errors.

Default shortlist: at most five logical assets, short provisional observation
excerpt, formats, preview reference, availability, matching channels, fault/review
flags and ranking score. No full source/dependency paths until `detail`. Output is
capped at 6,000 serialized characters with an explicitly heuristic characters/4
token estimate. Requested images and transport/schema overhead are excluded.
Scores mean BM25, cosine similarity or RRF rank score; none is a probability.

Semantic results are explicitly `weak_unvalidated` without human judgments.
Keyword/filtered empty sets return `no_match`. Optional `--min-similarity` is an
evaluation cosine floor applied before fusion; it is not a calibrated confidence
threshold. Unthresholded and eligible channel rankings are both retained, so
negative-query behavior can be examined later without losing scores. Rank names
are channel contributions, not proofs of relevance.

Default full ranking evidence: `data/embeddings/last-search.json`; use distinct
`--rankings-output embeddings/<name>.json` paths to preserve comparisons. It is
intentionally separate from the compact response. Reference querying requires a
matching capability receipt proving real image inference. The step 5 reference
demonstration uses an already indexed apple view: capability/self-retrieval proof,
not held-out relevance evidence.

`detail ID --format FORMAT` resolves and hashes the selected source and all known
logical-asset dependency references, retaining each referring source and missing
optional faults. It does not export or copy anything. The legacy `get` command
retains its raw catalog behavior.
