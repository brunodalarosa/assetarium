# Local visual captions — step 4

Weights now resolve through `[storage].models` at `C:\BrunoOS\Local-models`.
Runtime caches remain under project `cache/`; original inference receipts and
model revisions are unchanged. See `model-storage.md` for exact shared paths.

The schema is enforced by `validate_caption` before publication. An inference
response contains exactly `identity`, `description`, `shape`, `colors`, `parts`,
`style`, `distinguishing_features`, `uncertainties` and `suggested_uses`.
Identity has a short label and `probable`, `uncertain` or `unknown` certainty.
Unknown labels cannot be probable. Uncertain/unknown identity needs a stated
uncertainty. Confidence labels are uncalibrated model heuristics.

Description is bounded to 60–170 words, with 80–150 preferred; short simple
assets need not be padded. Attributes are bounded lists of short strings.
Duplicate JSON keys, wrong types, extra fields, truncated JSON and specified
technical/use claims in observation fields are rejected. This validation cannot
prove the semantic truth of a visually plausible statement. Review can flag
incorrect components, overconfident materials and wrong identities even when
the schema passes.

The catalog stores `description` containing only visual observations, and
`suggested_uses` as a separate list of interpretations. Technical fields are
retained verbatim from the inspector. No filename, source path, pack identity,
inspector count or license evidence enters the model prompt. All generated
front, side and three-quarter images are required; the existing top view is
also included where present. Source-author front and physical size remain
unknown. The seven existing source fault flags remain attached to the assets.

Images must resolve inside project data, have current matching SHA-256 hashes
and not be marked empty/off-frame. PIL decodes actual pixels, composites alpha
over the renderer's gray background, converts to RGB and downsizes to a maximum
448-pixel edge. The processor must produce one image grid per input, finite
pixel tensors and nonzero image tokens. Token counts, grids, original/processed
sizes and elapsed time are saved with each attempt.

Only a malformed response can receive one corrective generation, with an
explicit validation error and a larger token cap. The failed response is kept.
Runtime errors, OOM, corrupt/missing images, unsupported input and timeout are
failed outcomes without unchanged automatic retry or filename fallback. An
unchanged persisted fault is retained; `--retry-faults` is for a subsequent
explicit retry request. Model/code/prompt/settings/image changes invalidate
the stage fingerprint. This pilot cache does not implement full-library refresh.

Qwen uses local files only, pinned revision and runtime lock, verified model file
hashes, BF16 CUDA/SDPA, fixed seed per call, one beam and bounded output/time.
Final sampling: temperature 0.7, top-p 0.8, top-k 20, repetition penalty 1.1;
1,100 output tokens (1,500 corrective), 120-second generation limit. The model
card motivates sampling; the modest repetition penalty was selected after
greedy calibration repeated viewpoint wording. These inputs/settings are
reproducible; byte-identical output across different hardware/library versions
is not promised. PyTorch's time limit is checked between generation iterations,
so it is not an OS-level hard deadline for a hung CUDA kernel.

Owner overlays live in `data/captions/corrections/<asset_id>.json`. They contain
schema version, a partial `description` object, optional replacement
`suggested_uses`, `caption_review`, `artistic_suitability` and `notes`. New files
start with both reviews `pending`. Existing files are never rewritten during
generation. Only visual fields are editable; measured technical facts cannot
be replaced by captions or overlays. Invalid corrections retain their file and
produce a visible publication/review error. `effective_caption` merges valid
corrections while preserving the raw generated description. A failed caption
cannot be turned into successful model inspection by applying an overlay.

Edit a correction JSON file locally, then run the review refresh command in
the README. Back up this ignored directory with generated project data; Git
deliberately excludes all generated captions, views, owner edits and weights.
Regeneration preserves correction bytes and re-applies them to new output.
An explicit Bruno review may set a review field to approved/rejected. AI review
receipts cannot approve either caption quality or artistic suitability for him.

The static review sheet links every caption to full-size real inputs, structured
observations, separate suggestions, correction file, full provenance, measured
facts and retained faults. The full pilot requires a ten-asset AI calibration
receipt bound to the current model, code, settings, prompt and image hashes.
No descriptions are added to FTS and no embedding model is loaded in step 4.
