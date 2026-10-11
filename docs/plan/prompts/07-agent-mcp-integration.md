# Step 7 prompt — Connect agents through local MCP

```text
Work in C:\BrunoOS\Local-Asset-Library and implement only step 7. Read applicable AGENTS.md, docs\progress.md, the evaluation report, and the agent access/retrieval contracts plus step 7 in docs\plan\PROJECT.md. Confirm Bruno's pilot decision is recorded in current trusted session evidence or progress. If it is missing, request that decision before dependent integration; do not fabricate it. Do not spawn subagents, expose a public server, or import anything into Play Shapes.

Implement a local STDIO MCP server exposing only search_assets and get_asset initially. Keep search compact and details opt-in. Resolve IDs rather than arbitrary filesystem input. Enforce source-root boundaries, dependency availability, query/filter validation, deterministic output caps, and stale/unavailable state. Return preview images/resources using a transport the actual intended client can consume; do not assume a path is a displayed image.

Use current official client documentation. This prompt authorizes additive registration of this project server in the local Codex and OpenCode clients. Discover the actual active configuration, save a restorable copy, and preserve unrelated servers, providers, permissions, and existing model setup. If a client is absent or its active configuration cannot be safely identified, save exact setup snippets and mark only that client connection pending. Do not place MCP diagnostics on STDOUT.

Test protocol initialization, both tools, malformed IDs/paths, root escapes, result caps, and process startup/shutdown. Then perform an actual agent workflow through the intended connected client: search for a prop, inspect a preview, choose a candidate, resolve a usable format and dependencies, and produce a selection manifest inside project output. No automatic copying into game/source directories. A transport test alone does not establish agent use.

Measure returned context and tool calls, disclose cloud-bound results/previews, and verify a local-model workflow separately if available. Mark unavailable clients/models unverified. Update docs\progress.md with configuration/evidence and real client results; make a checked local commit without pushing. Stop before full-library processing.
```
