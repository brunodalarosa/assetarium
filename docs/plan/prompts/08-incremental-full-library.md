# Step 8 prompt — Make updates reliable and process the library

```text
Work in C:\BrunoOS\Local-Asset-Library and implement only step 8. Read applicable AGENTS.md, docs\progress.md, prior pilot/agent evidence, and step 8 plus storage/update contracts in docs\plan\PROJECT.md. Confirm pilot expansion was approved and the required prior stages passed. Do not spawn subagents, edit original packs, or modify Play Shapes.

Implement stage-specific fingerprints for source/dependency content, inspection/render settings, caption model/prompt, owner correction overlays, and embedding contracts. Preserve successful stages when unrelated settings change. Add resumable job state, bounded retries/timeouts, failure isolation, deletion handling, explicit rename behavior, and transactional index publication so interrupted work does not corrupt active search. A no-change refresh should not rerender or re-caption assets.

Test modifications, dependency changes, deletions, renames, corrupt files, process interruption, and contract changes using copied or synthetic fixtures. Do not exercise destructive cases on the real library. Demonstrate that manual corrections survive refresh and stale/deleted assets do not appear as valid candidates. Provide scan/process/refresh/status commands with dry-run summaries.

Estimate total storage, download budget, render/caption time, and GPU use from measured pilot data before full processing. Remain within the plan's budget. If the estimate exceeds it, report the concrete overage and stop the dependent full batch pending a revised budget. Stage GPU-heavy jobs and unload competing models; do not assume all models plus Blender can stay resident.

Process the complete source catalog when estimates fit and approval exists. Save coverage by pack with successful, ambiguous, unsupported, and failed counts plus actionable details. Resume after recoverable failures instead of silently omitting records. Rerun targeted search checks against the enlarged collection.

Update docs\progress.md with actual runtime/storage/coverage, interruption evidence, and remaining limitations. Make a checked local commit without pushing. Do not implement optional classification automatically; indicate that step 9 is optional and step 10 can proceed without it.
```
