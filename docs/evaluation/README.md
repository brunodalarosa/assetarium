# Frozen pilot evaluation

Status: provisional relevance labels; owner review and pilot expansion decision pending.

The evaluation uses the existing 40-asset pilot, 39 description vectors and 169
individual image-view vectors. Nothing is recaptioned, reindexed or processed
outside that pilot. The existing filename/path/pack FTS5 keyword baseline uses
AND terms and BM25. Each comparison uses identical queries, filters and pilot
membership; image rows aggregate by maximum similarity per logical asset before
equal-weight reciprocal rank fusion (k=60). Similarity is not probability.

`queries.json`, `protocol.json` and `labels-provisional.json` are frozen before
comparisons in `freeze.json`. The 32 text requests include eight exact names,
eight descriptions, six shape/color/style/variant requests, four verified-format
requests and six negatives. Seventeen requests form the predefined natural
language gate subset. Eight text requests and two of four references are held
out, run last, and never used for ranking/prompt tuning. This is a query split,
not unseen assets or a guarantee about model training data.

Labels were made from actual preview inspection, source identities and verified
formats, without reading the captions as labeling inputs or competing benchmark
rankings. Grades cover all 40 pilot assets for every query: 0 irrelevant, 1 weak,
2 useful/qualified, 3 direct. Hit@5 and MRR@5 require grade >=2. nDCG@5 uses
`2**grade-1` gains and the complete graded pool. Negative requests have no positive
pool, so positive-quality metrics are undefined and false positives are counted
separately. These are model judgments until Bruno reviews them.

Reference crops retain original pixels/background and are never byte-identical
to an indexed input. Every image row matching the parent image SHA-256 is excluded
before view aggregation. Report same-asset cross-view recovery separately from
other-asset relevance **within the original five returned slots**. A related
asset failure cannot be hidden by retrieving the query's original asset. Crops
are correlated with the indexed asset/render domain; independent photo quality
is untested.

Generated local evidence under `data/evaluation/` includes preview sheets, crop
inputs/manifest, rank-blind `relevance-review.html`, both repeats' full results
and separate channel lists, raw checksums, and fresh-process timing receipts.
The first repeat's full channel rankings are also versioned in `rankings.jsonl`;
`results.json` contains all first-repeat metric counts and limits. Two repeated
queries improve timing coverage but do not double the number of quality queries.

## Commands in this isolated project

For the initial, already completed preparation (do not rerun labeling after
seeing results):

```powershell
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python scripts/prepare_evaluation.py
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python scripts/label_evaluation.py
```

For a separately authorized reproduction, preserve all existing evidence and
use a new run name, with the same frozen local inputs and compatible index:

```powershell
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python scripts/benchmark_evaluation.py --run-name reproduction-1
.\scripts\embedding-runtime.ps1 run --locked --project runtime/embedding python scripts/benchmark_evaluation.py --cold --run-name reproduction-1
.\scripts\uv.ps1 run --locked python scripts/report_evaluation.py --run-name reproduction-1
```

Reproduction reports stay inside their new local run directory. The original
run/report/checks use the default `data/evaluation/run/`:

```powershell
.\scripts\uv.ps1 run --locked python scripts/report_evaluation.py
.\scripts\uv.ps1 run --locked python scripts/verify_evaluation.py
.\scripts\uv.ps1 run --locked python -m pytest tests/test_retrieval.py tests/test_evaluation.py
```

To review relevance, open `data/evaluation/relevance-review.html`. Its shortlist
is in original pilot order, with deliberate distractors and an option to reveal
all 40 items; no rankings or scores. Check every query, correct/add grades, and
export `owner-labels.json` into `data/evaluation/`. This does not approve step 7.
After an explicit Bruno review, recompute arithmetic from saved rankings only:

```powershell
.\scripts\uv.ps1 run --locked python scripts/report_evaluation.py --owner-labels data/evaluation/owner-labels.json
```

Do not relabel the frozen model artifact, retry unchanged faulty inference,
change thresholds/weights/prompts against held-out results, or treat a technical
pass as human relevance or expansion approval. Any future experiment needs its
own declared split/criteria; these pilot criteria remain unchanged.
