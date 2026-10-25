# Step 4: local vision evidence

Only the existing 40-asset pilot is processed. The other 843 catalog assets,
embedding stage and full-library expansion remain pending. Generated captions
are provisional: schema success and AI technical review do not establish
accuracy, artistic suitability or Bruno's final caption approval.

Open the [static caption review](../data/captions/review/pilot-v2.html) to compare
each generated description with all its actual front/side/three-quarter views
and optional top view. Full-size image links, structured attributes, separate
suggested uses, provenance, measured inspector facts, faults and editable owner
correction files are included. No caption comes from a filename fallback.

## Model choice and runtime

Selected one candidate: Qwen/Qwen3-VL-2B-Instruct, exact revision
`89644892e4d85e24eaac8bacfd4f463576704203`. Its official model card identifies
Apache-2.0 and image input. Official Transformers documentation supports
multi-image input. We checked the exact-revision API's file sizes before transfer.
Downloaded ten inference files totaling **4,266,640,306 bytes (3.97 GiB)**,
including one 4,255,140,312-byte BF16 safetensors file. Its SHA-256 is
`7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`.
All local file sizes/hashes are recorded and rechecked before loading.

Primary sources checked October 11, 2026:

- [Official Qwen model card](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)
- [Exact-revision metadata](https://huggingface.co/api/models/Qwen/Qwen3-VL-2B-Instruct/revision/89644892e4d85e24eaac8bacfd4f463576704203?blobs=true)
- [Official Transformers Qwen3-VL runtime documentation](https://huggingface.co/docs/transformers/model_doc/qwen3_vl)
- [Pinned Transformers implementation](https://github.com/huggingface/transformers/tree/v4.57.6/src/transformers/models/qwen3_vl)
- [Official PyTorch Windows/CUDA installation instructions](https://pytorch.org/get-started/previous-versions/)

Environment: Windows CPython 3.13.15, PyTorch 2.10.0+cu128,
torchvision 0.25.0+cu128, Transformers 4.57.6, Pillow 12.1.0,
Hugging Face Hub 0.36.2. Exact transitive dependencies are in the separate
`runtime/caption/uv.lock`. The RTX 5070 reports capability 12.0; the installed
PyTorch wheel includes sm_120. A real finite BF16 CUDA matrix multiplication
passed before downloading the weights. The driver snapshot was 616.64.
No installed coding model was assumed to accept images.

Dependencies, CUDA/HF/Torch/uv caches and temporary files stay in this project.
The base catalog environment/lock and existing local agent installation were
not upgraded. Inference uses verified local files, offline mode, no remote code
and no cloud caption API. Original sources and Play Shapes are unchanged.

Before download: no project model weights, 49,432,673 bytes of generated data,
94.02 GiB free on C:. The initial 8 GiB model/20 GiB generated project budgets
were checked. Model download allowance remaining: **4,323,294,286 bytes
(4.03 GiB)**. Runtime/cache copies are conservatively counted against generated
project storage. Detailed final measurements are linked below.

## Real inference and calibration

The initial smoke test consumed three actual views each of the car and apple,
588 image tokens per asset and finite image tensors with three distinct image
grids. It identified a red car with gray underside, bumper and side mirror,
then a red apple with green leaf and brown stem. Those responses took 2.127 s
and 0.873 s after a 2.808 s model load. Peak CUDA allocation was
4,464,284,672 bytes; reserved memory 4,498,391,040 bytes. Sampled process RSS
peaked at 4,810,797,056 bytes. This is actual comprehension evidence, not
accuracy calibration over the library.

Ten varied assets cover vehicles/components, thin road pieces, food, a chair,
ambiguous rocks, mushroom and a snowy tree. AI reviewed all **32 actual input
views** and their generated text in three labeled mosaics. Prompt v1 took
95.155 s. Evidence justified v2: remove presentation boilerplate, locate colors,
describe geometric forms and record specific uncertainty. Greedy v2 took
107.658 s but retained repeated wording and contradictory certainty. Those
outputs are retained under `data/captions/calibration-v2-greedy/`.

Final v2 keeps the revised prompt and uses fixed seed 0 with sampling
temperature 0.7, top-p 0.8, top-k 20 and repetition penalty 1.1. The model card
motivates sampling; the extra modest repetition penalty is a local calibration
choice. It took **140.767 s** for ten schema-valid captions, including two
corrective responses to descriptions below the minimum word count. There is
still inaccurate geometry/part interpretation. Review faults are explicit and
the model is not accepted as an authoritative asset identifier.

See [v1 review notes](caption-calibration-v1-review.json),
[final v2 review notes](caption-calibration-v2-review.json) and
[caption schema/failure/correction contract](caption-contract.md). The full pilot
is gated on a receipt tied to current model, code, settings, prompt and input
hashes. Ten calibration captions are reused without another inference.

## Evidence paths

- `data/captions/smoke.json`: real image inputs, responses, tensors, tokens, timing.
- `data/captions/model-preflight.json`, `model-download.json`: metadata, kernel
  probe and verified local files. The initial download completed (progress about
  25 seconds), then the path/stream hashing helper failed. A verification-only
  run fixed that code issue and verified the already downloaded files in 2.294 s.
  No second model download occurred. Exact initial transfer timing was not saved.
  The verification run overwrote the preflight snapshot; that file reflects the
  later verification state. The pre-download selection/budget record is
  `docs/caption-model.json`, saved before transfer.
- `data/captions/calibration-v1-report.json`, `calibration-v2-greedy-report.json`,
  `calibration-v2-report.json`: retained actual calibration responses/settings.
- `data/captions/pilot-v2-report.json`, `pilot-v2-resources.json`,
  `measurements.json`: outcomes, actual inference costs and byte accounting.
- `data/captions/pilot-v2-review.json`: AI review bound to results and real views.
- `data/captions/corrections/`: editable owner overlays; new files are pending.
- `data/evidence/step4-catalog-before.json`, `step4-catalog-check.json`: measured
  facts, source faults, noncaption fields and nonpilot preservation.
- `data/evidence/step4-full-source-verification.json`: full 4,938-file byte/hash/
  size/mtime comparison, zero changed paths. Access times/ownership are not covered.

No generated catalog, captions, images, correction files, weights or environment
is committed. Review notes and source/runtime/prompt contracts are versioned;
generated local evidence remains available in ignored project storage.

## Final measured pilot result

The pilot batch took **416.469 seconds**, reused ten final calibration captions,
and generated the other thirty. **39 captions passed the schema; one failed**:
road-crossroad produced contradictory identity certainty, then insufficient
prose on the one corrective attempt. Both raw outputs, real images and errors
are retained; its catalog description is null. All **124 actual input views**
were consumed and hash-verified, including four for that failed caption.

Across all forty final pilot assets including calibration, **53 real generation
attempts** took 552.784 seconds in total. Thirteen assets required the bounded
corrective response. Per-attempt median was **10.416 s** and nearest-rank p95
**12.905 s**. Those timings cover tokenization, generation and CUDA synchronization;
image decode/compositing occurs before the timer. Description lengths were
60–103 words. Input token counts were 1,016–1,254, including 588–784 image tokens.

Peak pilot-process CUDA allocation: **4,749,480,448 bytes (4.42 GiB)**;
reserved memory: **5,194,645,504 bytes (4.84 GiB)**. Sampled peak process RSS:
**4,877,275,136 bytes (4.54 GiB)** at 0.25-second intervals. Model load was
2.830 s. CUDA figures are process allocator measurements, not total system GPU
usage; RSS is working memory, not a complete system RAM budget.

AI reviewed all 124 views in ten labeled mosaics alongside structured text.
**Thirty of the 39 schema-valid captions have flagged visual claims.** Some are
minor count/material interpretations; others are substantial wrong identity,
especially road-bridge as a bench and the forest bridge as a torii-like arch.
See [asset-specific pilot review](caption-pilot-review.json). Faults are shown
prominently in the review sheet and persisted in caption provenance. No flagged
asset was silently repaired or automatically recaptioned. Only nine successful
captions have no flagged claims in this limited AI review; that is not calibrated
accuracy or owner approval. This candidate is technically usable but unreliable
as an authoritative captioner for these stylized assets.

Managed file bytes at measurement: models 4,266,641,371; data 54,066,841;
cache 4,863,051,800; scratch 8,044,888; base environment 50,570,014; isolated
caption environment 4,718,328,020. Total **13,960,702,934 bytes (13.00 GiB)**,
about 12.83 GiB above the pre-step snapshot. Conservative remaining generated
budget (including runtime/cache copies): **11,780,774,917 bytes (10.97 GiB)**.
Model download allowance remaining is separately 4.03 GiB. Later small reports
change byte totals slightly; regenerate `measurements.json` for a fresh count.

Final checks confirm all 883 records retain their noncaption fields, all measured
inspector facts and seven original source fault flags. The 843 nonpilot captions
are pending; FTS retains 883 rows, SQLite integrity is `ok`, foreign keys have
zero errors, and no embedding exists. Forty editable owner overlays remain pending.
An explicit UTF-8 read fix restored cached text from its canonical raw response;
the checker confirms generated text is preserved exactly. No additional model
inference or weight download was needed for that helper correction.
