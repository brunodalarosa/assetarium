# Local agent access — step 7

This server exposes exactly `search_assets` and `get_asset`, using local STDIO.
It serves only the approved forty-asset pilot. It has no HTTP listener, export
tool, arbitrary-path input, copy operation, or source-writing API. Stop before
step 8; pilot approval is not full-library approval.

Bruno's current client decision is **Codex for now**. OpenCode completion is not
required for current use, and further OpenCode work is on hold pending his
explicit request. Existing failure evidence remains valid. See
`client-decision.json` and the later decision entry in `../progress.md`.

## Install and start

From the project root, install the isolated transport environment:

```powershell
.\scripts\mcp-runtime.ps1 sync --locked --project runtime\mcp
& '.\.venv-mcp\Scripts\python.exe' scripts\asset-mcp.py
```

The second command waits for MCP messages on stdin. Clients should use the
absolute executable/script paths in `codex-setup.toml` and
`opencode-setup.json`. Do not wrap client startup in an installer. The entry
point resolves its own repository/configuration regardless of client cwd.

MCP SDK **2.3.0**, NumPy **2.3.4** and Pillow **12.1.0** are locked separately
under `runtime/mcp/`. Semantic queries start one persistent private subprocess
using the existing `.venv-embedding`, unchanged model/backend/lock/index
contracts, offline weights and CUDA BF16. Its output is private JSON IPC; all
diagnostics use stderr. There is no automatic fallback/restart after a failed
worker, model initialization, or unchanged failed query.

The server entry point cannot process more assets, scan/update the catalog, load
remote images, or import into Play Shapes. Existing generated captions and
relevance labels remain distinct from measured metadata and owner artistic
approval.

## Tool contract

`search_assets` accepts a text `query`, optional `mode`, `filters`, and `limit`.
The default is `keyword_description`; limit is an integer **1–5**, default 5.
Text is bounded to 1,024 characters (256 for keyword), excluding control
characters. Modes include keyword, description, text-to-image (`image`), combined,
and reference. Reference search takes `reference_asset_id` plus a known
`reference_view`, never a path/URL/upload. Text/reference arguments cannot mix.

Filters are only pack, source format, nonnegative maximum measured triangle
count, and boolean rigged. Unknown filter keys/types/formats or path-like pack
names are rejected. Technical filters require inspected evidence for the
requested format. Every source and required dependency is boundary-resolved and
hash-verified; stale/unavailable inputs are excluded. Index/model/input contract
mismatches are errors, with no synthetic vectors or ranking fallback.

Search returns compact candidate summaries, ID preview references, matching
channels, caption/source fault flags, counts and a small sample of exclusion
faults. Full exclusion evidence lives in the local call audit. Its serialized
text is at most **6,000 characters**, including the size fields. It removes
lowest-ranked results deterministically to enforce the cap. The
`ceil(characters/4)` estimate is heuristic, not client billing/model tokens.
Semantic results remain weak/unvalidated even after approval of this bounded
pilot; rank scores are not probabilities or an absence detector.

`get_asset` accepts an exact `asset_` + 32 lowercase hexadecimal ID. Optional
`source_format` selects an existing export; the inspected source is preferred
otherwise. It returns the actual source path/hash, all known logical-asset
dependencies with referring-source evidence, completeness limitations and faults.
`include_metadata=true` requests observations, measured summary, license evidence,
processing states and caption fault evidence. No incomplete dependency package is
declared usable when the 64-dependency or **16,000-character** detail cap is exceeded.
Unknown binary/alternate dependency completeness remains explicit.

`include_preview=true` requests one named view (`three_quarter` by default,
alternatively front/side). The tool returns actual base64 PNG **ImageContent**,
at most 512 × 512 pixels and **512 KiB**, with the original hash, derived hash,
dimensions and byte count in text. Source decode is capped at 16 MiB/16 million
pixels. Missing/stale/faulty views remain faulty; the server never substitutes
another view. Usable source detail can survive a preview fault. A reference path,
successful render, image transport test or receipt is not proof of model vision.
Actual client events and image-specific reasoning establish that separately.

## Client setup, preservation and restoration

Current official references, read October 11, 2026:

- [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [OpenCode MCP servers](https://opencode.ai/docs/mcp-servers/)
- [OpenCode configuration precedence](https://opencode.ai/docs/config/)
- [MCP server development](https://modelcontextprotocol.io/docs/develop/build-server)

The active Codex user configuration was discovered at
`C:\Users\backup pc\.codex\config.toml`; there was no project override or
CODEX_HOME override. Existing node_repl, gimp and blender entries and model
`gpt-6.1-sol` were retained. OpenCode's actual launcher sets OPENCODE_CONFIG to
`C:\BrunoOS\OpenCode-local-agent\outputs\opencode-local.json` and relocates XDG
directories; no additional global JSON configuration was found there. Its
`ollama/qwen3.8:local-agent`, small model, provider, options, model setup and
permissions were retained.

`scripts/register-mcp.py` performs first registration only: copy original bytes
to ignored `data/mcp/config-backups/<UTC>/`, verify them, add just this server,
compare parsed unrelated settings, check for concurrent edits, then verify the
write. Never rerun it blindly over an existing server entry. Exact setup snippets
are versioned here; `data/mcp/registration.json` records paths, hashes and backups.
Backups can contain private settings and must not be committed or sent to models.

To restore, close the client. Check for later changes before restoring the whole
file. If none exist, copy the exact backup bytes back to the corresponding
receipt path. If later changes exist, remove only this server entry after review
and preserve those later settings. Restart/reconnect the client to load changes.
The existing desktop chat was not treated as having hot-reloaded new tools:
verification used fresh installed CLI sessions with the same active configuration.

## Verification and disclosure

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
& '.\.venv-mcp\Scripts\python.exe' -m pytest tests\test_mcp_assets.py tests\test_retrieval.py tests\test_evaluation.py --basetemp scratch\pytest-mcp-new-run
& '.\.venv-mcp\Scripts\python.exe' scripts\verify-mcp.py --run-name unique-run-name
```

Read previous faults before requesting any repeat. The protocol harness creates
a distinct directory and captures real initialization, tool discovery, both
tools, image decoding/hash, malformed ID/path/filter/cap errors, semantic default
and clean EOF shutdown. This is explicitly **not agent-use evidence**. The
initial harness incorrectly matched a Windows environment-launcher PID to its
child Python PID; original faulty evidence is preserved. The corrected harness
identifies the new audit directory instead.

`scripts/verify-agent-workflow.py codex|opencode` performs one bounded real-client
selection workflow and saves events/stderr plus final manifest in
`data/exports/<client>-selection.json`. It runs installed clients as verification
targets, without delegation/subagents. It never changes the persistent model or
permission setup. Codex disables other MCPs for that one invocation; OpenCode's
one-run inline permission overlay authorizes exactly the two read-only project
tools. Neither changes unrelated saved configuration. A failed unchanged client
workflow is not automatically retried.

Each server process records returned text size/UTF-8 bytes, estimated tokens,
image bytes/base64 length, errors, full fault evidence and timing under
`data/mcp/runs/<id>/`. Preview PNGs are preserved separately. These are local
evidence writes, not source edits. Tool-schema and full-client token usage are
measured separately; reported client usage includes instructions, prior context,
tool schemas, repeated context and images as accounted by that client. It cannot
be used to claim retrieval-only token savings.

Rendering/captioning/indexing/search inference remain local. Codex's configured
cloud model receives returned candidate text, descriptions, source/dependency
paths, requested metadata and PNG previews. OpenCode's existing provider is local
Ollama on localhost. A local MCP transport does not keep cloud-requested results
private. No full source model files or configuration backups are returned through
these tools, and no public server was exposed.

See `client-results.json`, `owner-review.json`, `preservation.json` and
`../progress.md` for real outcomes and current limitations. Owner labels were
validated and quality recomputed only from saved first-repeat rankings; frozen
step 6 artifacts were preserved. The current session supplies the explicit
bounded pilot decision. Next step is separate authorization for step 8, not an
automatic continuation.
