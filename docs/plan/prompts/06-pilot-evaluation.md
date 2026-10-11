# Step 6 prompt — Evaluate before scaling

```text
Work in C:\BrunoOS\Local-Asset-Library and implement only step 6. Read applicable AGENTS.md, docs\progress.md, and step 6 plus the retrieval/acceptance requirements in docs\plan\PROJECT.md. Do not spawn subagents or process the full asset library.

Create a reproducible evaluation set of at least 24 text queries spanning exact names, natural descriptions, shape/color/style, verified format filters, confusing variants, and at least four absent/negative requests. Add a small reference-image query set using views or crops distinct from the exact indexed image when possible. Mark a held-out subset and keep it out of ranking/prompt tuning. Prevent trivial self-image lookup from masquerading as general similarity quality.

Prepare a relevance-labeling artifact before viewing competing rankings. Use existing explicit owner judgments if present; otherwise produce provisional labels clearly marked as model-generated and ask Bruno to review the manageable shortlist. Do not use the captions being evaluated as the only ground truth. Technical benchmarking can proceed while human labels are pending, but final quality claims cannot.

Compare filename/keyword, description-only, image-only, keyword-plus-description, and full combined retrieval on the same pilot. Report Hit@5, ranked relevance where labels permit, exact-name successes, negative false positives, verified-filter correctness, unique-asset diversity, cold/warm latency, indexing/caption costs, and context size. Use actual token counts when available; otherwise name the estimator and report exact characters too. Publish raw counts and limits of the small sample.

Apply the proposed expansion criteria without changing them after seeing results. Investigate clear implementation defects and rerun only affected checks. If results miss the targets or the baseline has little room to improve, explain the evidence and a bounded alternative. Do not infer human approval from successful tests.

Save the benchmark artifacts and report, update docs\progress.md with a pass/fail/provisional status, and make a checked local commit without pushing. Finish with a concise recommendation and the specific pilot decision or relevance review Bruno must provide before step 7. Do not advance to integration or full processing.
```
