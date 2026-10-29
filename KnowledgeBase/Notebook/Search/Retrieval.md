---
area: Search
tags: [system]
code: [retrieval.SearchEngine, retrieval.MODES, retrieval.source_check, retrieval.recorded_contract, search_policy.RRF_WEIGHTS, search_policy.RRF_K, search_policy.MAX_LIMIT, search_policy.search_character_cap, mcp_assets.AssetService, mcp_assets.bounded]
verified: 2026-10-28
branch: feature/library-view
---
# Retrieval

Hub: [Search](Search.md). `retrieval.SearchEngine` is the one search implementation; the desktop
(`DesktopService`), the CLI and MCP (`mcp_assets.AssetService`) all call it. Ranking policy constants
live in `search_policy.py`.

## How it works

- Modes (`retrieval.MODES`): `keyword`, `description`, `image` (text to image), `reference` (an
  asset's view, never a path or upload), `keyword_description` and `combined` (default).
- Fusion is weighted reciprocal rank: each channel contributes `weight / (RRF_K + rank)` with
  `RRF_K = 60`; `combined` weights image 3, keyword 1, description 1. Raw scores are never averaged;
  ties break by asset ID; one result per logical asset; image views aggregate to the best view.
- Limits are 1 to `MAX_LIMIT` (40). MCP's omitted limit is 5; the desktop asks for 20. The serialized
  response cap scales with the limit (`search_character_cap`: 6,000 characters up to 5 results, then
  2,000 + 1,000 per result) and is shared by the inner layers, so they never cut a larger shortlist
  under a fixed cap.
- Each request reads one pinned publication generation; results are boundary-resolved and their
  files verified, with stale or unavailable inputs excluded and counted.

## Rules

- **No fallbacks**: a semantic runtime or query fault is an error, never a silent keyword result or a
  worker restart. Index, model or input contract mismatches are errors.
- Policy changes go in `search_policy.py`, not in a caller. The desktop must not add its own ranking,
  filtering or availability rules.
- Scores are ranks, not confidence; there is no absence detector.

## Gotchas

- The module docstring and `VERSION = "pilot-retrieval-v1"` say "pilot"; this is the live engine for
  the whole library.
- `pilot_records` returns the shared slim records from `library_cache`, not pilot-only data.
- Search used to re-hash every member's files on every request (about 8,000 files per search on the
  original library). [Hash reuse and caches](Hash%20reuse%20and%20caches.md) explains what replaced it;
  don't reintroduce per-request full verification.

## Related

[MCP server](../../Architecture/MCP/MCP%20server.md) (tool contract and caps) ·
[Embedding contract](../../Architecture/Search/Embedding%20contract.md) · [GPU lease](../Processing/GPU%20lease.md).
