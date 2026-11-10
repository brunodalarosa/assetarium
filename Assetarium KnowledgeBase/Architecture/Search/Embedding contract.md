---
tags: [architecture]
parent: "[Architecture](../Architecture.md)"
status: draft
verified: 2026-11-10
branch: feature/audit-simplify
level: system
code: [embedding_backend.py, embedding_cpu.py, library_index.py, retrieval.recorded_contract, retrieval.SearchEngine, search_policy.py]
---
# Embedding and retrieval contract

> What a search vector is made from, what makes two vectors comparable, and what search verifies before it
> answers. Rewritten on 2026-11-10 as the current contract; the pilot notes it used to carry are in git
> (commit `af02e91`).

Up: [Architecture](../Architecture.md) · Where in code: [Search](../../Notebook/Search/Search.md) ·
Binding rules: [0018](../../Decisions/0018-cpu-search-embedder.md) (CPU or CUDA),
[0028](../../Decisions/0028-result-identity.md) (what a contract change re-queues).

## The model

`docs/embedding-model.json` pins `google/embeddinggemma-2` at one revision with the hash of every file
(Apache-2.0, no access gate). Sources checked when it was chosen (October 2026): Google's
[model card](https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2), the
[text](https://ai.google.dev/gemma/docs/embeddinggemma/inference-embeddinggemma-with-sentence-transformers) and
[multimodal](https://ai.google.dev/gemma/docs/embeddinggemma/multimodal-embeddinggemma-with-sentence-transformers)
inference guides, and the [publisher repository](https://huggingface.co/google/embeddinggemma-2).

- Weights resolve through `[storage].models`; moving them changes storage only, not the contract.
- Weights, configuration and tokenizer are hash-checked against the pinned receipt before every load.
- Offline, local files only, no remote model code, no cloud inference. Audio is disabled at load
  (`audio_config: None`); the contract covers text and images.
- BF16 on CUDA (`embedding_backend.py`, `runtime/embedding/uv.lock`) or on the CPU (`embedding_cpu.py`,
  `runtime/embedding-cpu/uv.lock`), chosen by the saved `search_device`. **Nothing falls back** from one device
  or precision to another. The two have different contract identities, so their vectors never share an
  index; switching device rebuilds search data.

## What goes in

| Input | Prepared as |
| --- | --- |
| Search text | `task: search result \| query: {query}` |
| A description | `title: none \| text: {observations}` |
| An image | The documented image API, **no text prefix** |

- Prefixes are applied explicitly; the runtime's default prompt is suppressed.
- A description document holds only what the model observed: identity with its uncertainty, prose, shape,
  colors, parts, style, distinguishing features. Suggested uses, pack and file names and measured geometry
  are left out. The owner's corrections count: a changed effective description invalidates its vector.
- Images: EXIF transpose, decode, RGBA over flat rgb(82,82,82), RGB, native size, the publisher processor's
  280 soft-token budget. A query image is prepared exactly like an indexed one.
- A 3D asset contributes one image vector per rendered view. A 2D image contributes one, from its recorded
  `model_input` preview ([Catalog contract](../Sources%20and%20Catalog/Catalog%20contract.md#images)); originals,
  display rasters and thumbnails are presentation, never extra vectors. Contact sheets and textures of a model
  are not indexed as views.
- A description vector exists only once a valid description does; a missing or failed description leaves just
  that channel empty ([decision 0033](../../Decisions/0033-descriptions-and-engines.md)).

## What comes out

Every vector has 768 dimensions, is checked finite and nonzero, converted to FP32 and L2-normalized. Stored
vectors must already be unit length. The 8,192-token limit is checked before any truncation. An inference
fault is an error or an explicit item failure: there is no synthetic, random or zero vector, and no ranking
fallback after a query fails.

## The contract fingerprint

`data/embeddings/index.sqlite` is separate from the catalog. Its contract covers the model ID, revision and
file hashes, dependency versions, the runtime lock hash, the adapter's source hash, precision, device and
attention, dimensions, both text prompts, image preprocessing and normalization. Each vector row stores the
contract fingerprint, its modality and role, its input fingerprint, FP32 bytes with a checksum, and the view
it came from.

- **Query and index contracts must match exactly** before any similarity is computed.
- A changed contract needs a search check and a reindex, never an automatic migration.
- A source file or lock that differs from the recorded one only by LF/CRLF line endings (a git checkout on
  another platform) keeps its recorded hash (`retrieval.recorded_contract`); any other byte change is a
  contract change. The published index's own contract counts too, because a library store can bring vectors
  built on another checkout to an install that has no search check yet.
- The **search check** (`data/embeddings/capability.json`) proves real text and image inference on this
  computer's search device before search data is built ([decision 0031](../../Decisions/0031-setup.md)).

## Building the index

Only members of the configured library are indexed; the index records their IDs, and search refuses an index
whose members differ. Jobs publish atomically. An unchanged successful vector is reused after verification;
an unchanged inference failure is kept without another attempt; changed inputs or contracts are new jobs. An
old vector cannot survive a failed replacement. A process or load fault leaves the existing index intact.

## Retrieval

- Modes: `keyword`, `description`, `image` (text to image), `reference` (an asset's own view, never a path or
  upload), `keyword_description` and `combined` (the default).
- Keyword ranking is FTS5 literal AND terms ordered by BM25. Semantic ranking is an exact NumPy dot product of
  unit vectors; an asset ranks by its best view. Every view and format resolves to one logical asset.
- Channels are fused by weighted reciprocal rank with `k = 60` (`search_policy`), ties broken by asset ID.
  Scores are BM25, cosine similarity or a fused rank score; **none is a probability**, and semantic candidates
  are labeled weak until a person has judged them.
- **Before every search and detail**, recorded source files and required dependencies are resolved inside
  their boundary and their SHA-256 verified. A stale or missing required file excludes the asset, counted
  with its reason. Stale description or view inputs exclude only their rows.
- Filters are verified facts only: asset type, pack, available format, maximum inspected triangle count,
  `rigged` (an armature was found, not that it animates), and for images `transparent` and `size_class`.
  Unknown filter keys are errors; a technical filter excludes assets whose fact is unknown.
- A shortlist is bounded: at most 40 results (5 when omitted over MCP, 20 in the app), a short observation
  excerpt, formats, a preview reference, matching channels, review flags and a score. Full paths appear only
  in detail. `--min-similarity` on the CLI is an evaluation floor applied before fusion, not a confidence
  threshold; `--rankings-output` saves every channel's ranking under `data/` for comparison.

How ranking is implemented and tuned is in [Retrieval](../../Notebook/Search/Retrieval.md); the frozen
evaluation that chose these weights is in [`docs/evaluation/`](../../../docs/evaluation/README.md).
