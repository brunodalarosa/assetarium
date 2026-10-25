# Step 6 pilot benchmark — provisional

The fixed expansion criteria pass **conditionally on model-generated relevance
labels**, but the overall quality verdict remains **provisional**. Bruno has not
reviewed the labels or approved expansion. Recommend keeping the pilot bounded:
keyword-plus-description is the measured lighter text-search candidate; image
retrieval remains useful for explicit references. This sample provides no text
Hit@5 justification for scaling full image fusion, and semantic search does not
abstain reliably on absent requests.

## Inputs and evidence boundaries

Existing pilot only: **40 logical assets, 208 vectors (39 descriptions, 169
individual views), one failed description job**. Thirty descriptions retain
recorded visual faults; no captions, vectors or sources were repaired. Source
identity and actual preview geometry/color were used for relevance labeling;
evaluated captions were excluded from the labeling inputs. No existing explicit
owner relevance judgments were found. All labels remain model-generated.

Queries, grades and criteria were frozen at **2026-10-11 16:17:33 UTC**, before
the competing benchmark rankings. There are **32 text queries**: 8 exact-name,
8 description, 6 shape/color/style/variant, 4 verified-format and 6 absent requests.
The natural-language gate has the predefined **17** description/style/format-
description requests. Eight text requests are held out; four references have
two held out. Held-out requests ran last with no tuning. Earlier step 5 apple,
car/chair and dragon demonstrations were already seen; this is a query holdout,
not unseen assets or a claim about model training data.

Two repeats of each text query/mode and reference gave **328 successful searches,
zero inference failures**. Quality counts use the first repeat only (26 positive
text queries, 6 negatives); repeats are not independent relevance samples. All
five modes use the same pilot/filters, L2-normalized exact cosine similarity,
maximum-per-asset view aggregation, and equal-weight RRF k=60 where combined.
Keyword uses the preserved FTS5 filename/path/pack baseline, conjunctive terms
and BM25. Similarity and fused scores are not probabilities.

Grading: 0 irrelevant, 1 weak/partial, 2 useful but qualified, 3 direct. Hit@5
and MRR@5 require grade >=2; nDCG@5 uses gains `2**grade-1` and complete 40-asset
grades. Ambiguous requests **S03** (brown rock versus gray mossy rock), **S04**
(white canopy versus green foliage with white caps), **N06** (stacked doors) and
broad **S06** particularly require Bruno's judgment. Negative absence concerns
this pilot, not the full collection.

## Text retrieval, provisional relevance

| Mode | Positive Hit@5 | Natural Hit@5 | Exact-name hits | Positive nDCG@5 | Positive MRR@5 | Held-out positive hits |
| --- | --- | --- | --- | --- | --- | --- |
| Filename/keyword | 9/26 (34.6%) | 0/17 | 8/8 | 0.3320 | 0.3269 | 2/6 |
| Description | 25/26 (96.2%) | 17/17 | 7/8 | 0.9320 | 0.9423 | 6/6 |
| Text-to-image | 26/26 (100%) | 17/17 | 8/8 | 0.9461 | 0.9615 | 6/6 |
| Keyword + description | 26/26 (100%) | 17/17 | 8/8 | 0.9704 | 0.9808 | 6/6 |
| Full combined | 26/26 (100%) | 17/17 | 8/8 | 0.9687 | 0.9808 | 6/6 |

Development natural hits are 0/13 for keyword and 13/13 for each semantic mode;
held-out natural hits are 0/4 and 4/4 respectively. Keyword already reaches the
exact-name ceiling, but has ample measured room on these sentence queries. The
baseline's AND-term behavior explains empty sentence-query results; it was
preserved, not retuned against this set. A synonym/token-selection baseline is
an untested bounded alternative, not a proven inferior option.

Description-only misses **E04 road-crossroad** because its caption failed and
there is no invented description vector. Keyword+description recovers it through
the keyword channel; full combined also recovers it. This is a known partial
input failure, not a new inference defect. No ranking weights, prompts, thresholds
or labels were changed after looking at results; no benchmark inference was rerun.

Full fusion adds **0/17 natural hits** and **0/26 positive hits** over keyword+
description; mean positive nDCG is slightly lower (0.9687 versus 0.9704). The
sample has a ceiling for Hit@5 in both modes, so it cannot establish the value
of full vision indexing on harder text requests or a larger asset pool.

## Negatives, filters and diversity

Any returned candidate on a labeled absent request is counted as an operational
false positive, even if explicitly weak. Threshold stayed `null`; no universal
cosine cutoff was invented from this evaluation.

| Mode | Negative requests with candidates | Negative candidate slots | Strong match claims on negatives | Verified-format returned slots checked | Violations | Unique assets / returned text slots |
| --- | --- | --- | --- | --- | --- | --- |
| Filename/keyword | 0/6 | 0 | 0 | 1 | 0 | 10/10 |
| Description | 6/6 | 30 | 0 | 19 | 0 | 38/159 |
| Text-to-image | 6/6 | 30 | 0 | 20 | 0 | 40/160 |
| Keyword + description | 6/6 | 30 | 0 | 19 | 0 | 39/159 |
| Full combined | 6/6 | 30 | 0 | 20 | 0 | 40/160 |

All four filter queries were evaluated in every mode. Zero violations were also
confirmed independently in the complete channel rankings, against recorded
source formats/availability/hashes and pack IDs. Empty keyword results do not
prove filter recall. Unique counts above include negative-request candidates;
coverage is not proof of useful diversity. **Zero duplicate logical assets**
within any shortlist, despite 169 view/format vectors. All 40 shortlisted asset
sources and recorded required dependencies resolve; the existing inactive
BirchTree texture fault remains visible and is not silently repaired.

## Reference images, provisional relevance

Four deterministic central crops use unchanged rendered pixels/background. Crop
SHA-256 values differ from every indexed image; **all parent-image hash matches
were removed before view aggregation**. Thus the original view cannot score
itself. Other indexed views/formats of the same logical asset remain available.

| Reference | Split | Same-asset cross-view Hit@5 | Useful different assets returned / labeled pool | Different-asset Hit within five original slots | Different-asset nDCG |
| --- | --- | --- | --- | --- | --- |
| R01 tractor crop | Development | 1/1 | 0/0 | Undefined: no useful different target | 0.9675, weak grade-1 matches only |
| R02 double-cheese burger crop | Development | 1/1 | 2/2 | 1/1 | 1.0000 |
| R03 snow birch crop | Held out | 1/1 | 1/2 | 1/1 | 0.6329 |
| R04 cushioned wooden chair crop | Held out | 1/1 | 1/1 | 1/1 | 1.0000 |

Same-asset recovery is **4/4**, all first-ranked. Winning indexed views are side
for R01/R02/R03 and three-quarter for R04, each different from its parent view.
Useful different-asset retrieval
hits **3/3 evaluable references**, returning **4/5** labeled useful different
assets across those requests. The snow-tree crop misses one relevant birch in
the five returned slots. Same-asset success is not presented as independent
similarity quality. Four correlated synthetic-render crops cannot establish
general photographic, background, lighting or unseen-object robustness.

## Timing and returned context

Warm timing includes query inference, current source/preview hash checks,
ranking, view aggregation, fusion and compact serialization. Output-tokenizer
measurement and evidence writes are excluded. P95 uses nearest-rank, **64 warm
samples per text mode**, with fixed mode order and a resident model. These are
single-machine sequential measurements, not concurrent/server guarantees.

| Mode | Warm median s | Warm p95 s | Fresh process + first query s | Max exact characters | Max characters/4 estimate | Max EmbeddingGemma tokenizer tokens |
| --- | --- | --- | --- | --- | --- | --- |
| Filename/keyword | 0.587 | 0.699 | 0.926 | 1,695 | 424 | 518 |
| Description | 1.102 | 1.279 | 13.420 | 3,790 | 948 | 1,230 |
| Text-to-image | 1.153 | 1.280 | 13.733 | 3,754 | 939 | 1,237 |
| Keyword + description | 1.129 | 1.327 | 13.589 | 3,773 | 944 | 1,235 |
| Full combined | 1.521 | 1.692 | 14.132 | 3,798 | 950 | 1,252 |

Cold values have **one fresh process per mode**, same development E01 query;
reference startup uses development R01 (**13.441 s**). OS disk cache was not
purged. Parent launch to child first-completion timestamps include imports,
verified model load, first search and first tokenizer measurement, excluding
second query/shutdown. Cold-process model-load measurements span
**11.417–11.903 s**; the separate warm benchmark initialized in **12.635 s**.
Warm reference queries have eight samples, median **1.281 s**, p95 **1.352 s**,
with exact per-run times in `results.json`.

Character counts include compact output metadata, exclude trailing newline,
images and transport/tool-schema overhead. `ceil(characters/4)` is the declared
estimator. Additional **actual tokenizer counts** use the pinned EmbeddingGemma
tokenizer with special tokens disabled; they are a **surrogate**, not Codex or
OpenCode billing/context tokens. All shortlists stay below 6,000 characters and
the about-1,500-token target by both measurements. No agent integration/tool
schema was run, so no claim of actual agent-context or billing savings is made.
Repeat shortlist IDs/ranks were identical in every text mode.

## Costs and fixed decision criteria

No new model/dependency installation, caption inference or index inference in
step 6. Prior measured preprocessing remains part of the cost of this approach:

- Caption batch: **416.469 s**, ten reused calibration jobs, thirty new jobs;
  **53 total attempts / 552.784 s** including calibration, 39 schema-valid
  captions and one failure. Per-attempt median/p95 **10.416/12.905 s**; 30 visual
  faults show that schema validity is not authoritative caption quality.
- Initial embedding publication: **22.813 s**, 204 successes/five precondition
  failures; a verified inactive-dependency handling correction then added four
  vectors in **2.225 s** while reusing others. Unchanged 208-vector reuse took
  **1.296 s**. These are preserved step 5 receipts, excluding download/startup,
  not a newly measured all-208 fresh indexing cost.
- Embedding model download: **1,525,787,092 bytes**; current project model
  directories approximately **5.39 GiB** across caption/embedding models. No
  full-library cost is extrapolated from this small pilot.

The frozen expansion gate is applied unchanged:

| Criterion | Actual arithmetic | Conditional result |
| --- | --- | --- |
| Natural-language Hit@5 improvement >=10 percentage points | 17/17 versus 0/17; +100 points | Pass on provisional labels |
| Lose at most one exact-name success | 8/8 retained, zero lost IDs | Pass on provisional labels |
| Do not bypass verified filters | Zero violations in combined and every comparison | Technical pass |
| Warm combined p95 strictly below two seconds | 1.691895 s | Technical pass |

The overall status is **provisional**, not human quality approval or permission
to scale. Each natural-language hit is **5.88 percentage points** (held-out
natural subset: 25 points); each exact request is 12.5 points. Queries/assets
were deliberately selected rather than randomly sampled. Labels, easy-pilot
ceiling, six negatives, four correlated crops, small held-out set, fixed mode
order and two timing repeats limit statistical/generalization claims.

## Bruno's review and pilot decision before step 7

Open `data/evaluation/relevance-review.html`: rank-blind shortlist, original
pilot order, actual views, grade controls and an option to inspect all 40 assets.
Review all **36** query sections, especially the qualified color/shape requests,
six absent requests and different-asset reference labels; export
`data/evaluation/owner-labels.json`. Recompute metrics from saved rankings only.
Passing tests or a saved export does not approve integration.

Then explicitly choose whether to **approve this bounded pilot with keyword+
description as the candidate default and image search on request**, accepting
the documented weak-candidate/abstention limitation, or **request another bounded
pilot experiment** before integration (harder independently sourced references
and a separately frozen negative/abstention set are the most useful next test).
Keep the existing criteria and original held-out results intact. No step 7,
client registration, full indexing, game import or push was performed.

Evidence: `protocol.json`, `queries.json`, `labels-provisional.json`, `freeze.json`,
`results.json` (raw counts/per-query arithmetic), `rankings.jsonl` (all first-
repeat separate channel rankings and responses), `verification.json` (technical
preservation), plus hash-bound local `data/evaluation/run/` for both repeats and
fresh-process receipts. Reproduction/review commands are in `README.md`.

Technical verification: **32 focused tests passed** (27 retrieval, 5 evaluation),
**328 successful searches / 520 separate channel rankings checked**, all **208**
stored vectors valid/finite/normalized, **1,444** review-image links resolve,
catalog/index/pilot byte hashes unchanged and all **4,938** source SHA-256/size/
mtime entries unchanged. The first new parent-exclusion test used a mistaken
`preview` field name; corrected to the existing `input` field before benchmarking,
then the affected test and final focused suite passed. No inference or relevance
result was silently repaired/retried. The existing managed-Python location
warning remains nonfatal. No full unrelated test suite was repeated.

Managed project storage snapshot: **20,821,007,204 bytes**, model directories
**5,792,432,361 bytes**; remaining conservative generated/runtime/cache budget
**6,446,261,637 bytes**, model budget **2,797,502,231 bytes**. Managed growth versus
the step 5 snapshot is **47,921,235 bytes (45.70 MiB)**, including new test scratch
outputs; versioned benchmark docs/rankings add approximately 2.90 MiB. Logical
file sizes count cache/runtime copies, not filesystem blocks. No new models or
dependencies were installed and both project limits remain satisfied.
