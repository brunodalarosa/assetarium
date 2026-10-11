# Step 9 prompt — Optional classification and clustering

```text
Work in C:\BrunoOS\Local-Asset-Library. This prompt opts into the optional step 9 only; do not alter the core retrieval contract or reorganize any source files. Read applicable AGENTS.md, docs\progress.md, and step 9 plus the observation/technical-fact/suggestion boundaries in docs\plan\PROJECT.md. Do not spawn subagents or modify Play Shapes.

Propose a small readable taxonomy covering this collection, allowing multiple labels and unknown identity. Separate object identity, visible attributes, inferred uses, and measured technical filters. Use existing reviewed labels where available. Generated labels remain suggestions until reviewed; never overwrite owner corrections or factual metadata.

Implement inspectable category suggestions from the factual descriptions and, where validated, image evidence. If using embedding classification or clustering, consult the model's task-specific contracts and compare a reviewed sample rather than assuming retrieval embeddings are optimal. Record contract/model revisions. Similarity scores and model confidence are not calibrated probabilities.

Produce exploratory groups with member previews, representative examples, descriptions of likely shared features, and clearly identified outliers. Distinguish possible duplicates from verified equivalent geometry. Keep parameter choices deterministic/versioned for comparison; stable asset IDs remain independent of changing cluster membership.

Evaluate on a modest owner-reviewable sample: label correctness, unknown handling, preservation of accepted labels, cluster coherence, and whether groups help find assets or review duplicate candidates. Do not claim completion from an attractive grouping alone. Keep a clean option to disable or skip the extension without losing search functionality.

Save the suggestion/cluster reports and focused test evidence; update docs\progress.md with human review status and measured limitations. Make a checked local commit without pushing. Stop before final handoff work.
```
