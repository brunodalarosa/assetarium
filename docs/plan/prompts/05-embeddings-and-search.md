# Step 5 prompt — Embed and search

```text
Work in C:\BrunoOS\Local-Asset-Library and implement only step 5. Read applicable AGENTS.md, docs\progress.md, and the embedding model contract, retrieval behavior, and step 5 in docs\plan\PROJECT.md. Preserve the working pilot and keyword baseline. Do not spawn subagents, fine-tune a model, change source assets, or modify other installations.

Verify current official EmbeddingGemma 2 text-and-image inference documentation, then install the required pinned dependencies/model inside the project budget and isolated environment. Use the proposed Python/SentenceTransformers backend unless a capability test establishes a better supported local alternative. Validate actual text and image inference; an endpoint name or successful model load is insufficient. Follow the central precision, prompting, dimensions, normalization, and revision contract. Unload competing heavy models when necessary.

Index the pilot descriptions and individual preview views. Keep factual descriptions distinct from speculative suggested uses. Implement separate filename/keyword, description-semantic, text-to-image, and combined modes. Add reference-image search after proving image-query support. Use normalized exact similarity search and rank fusion; aggregate multiple views/formats into one logical-asset result. Persist vectors with contract fingerprints and enforce compatible query/index contracts. Never return random, zero, stale, or fabricated vectors after inference failure.

Apply verified metadata filters and source availability checks. Add compact default results, explicit weak/no-match behavior for evaluation, and a detail command resolving the selected source and dependencies. Similarity scores are not probabilities. Preserve channel rankings for benchmark analysis rather than only exposing the fused list.

Test normalization/finite output, mismatched contracts, filter enforcement, duplicate-view aggregation, unavailable files, and error propagation. Demonstrate real queries in each channel, including a reference image, and measure result text size plus cold/warm timing. Update docs\progress.md with exact runtime/model versions, actual evidence, and limitations; make a checked local commit without pushing. Stop before the benchmark verdict or full indexing.
```
