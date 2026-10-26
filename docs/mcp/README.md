# Local agent access — step 7

This server exposes `search_assets` and `get_asset`, plus the collection tools
`list_collections`, `get_collection`, `edit_collection` and `tag_assets`
([decision 0012](../decisions/0012-collections-and-tags.md); see
[Collections and tags](#collections-and-tags)) and the setup tools
`get_setup_status`, `validate_blender`, `apply_setup`, `propose_setup` and
`finish_setup` ([decision 0016](../decisions/0016-agent-setup.md); see
[Agent setup](#agent-setup)), using local STDIO.
Step 8 generalizes membership to the explicitly approved configured library and
pins each request to one published catalog/index generation. It has no HTTP
listener, export tool, arbitrary-path input, copy operation or source-writing API.
The historical forty-asset pilot approval remains preserved; current expansion
authorization and operations are in [`../library-updates.md`](../library-updates.md).
Restart pre-update server connections to load the new membership/version/lease
behavior. No client registration or unrelated process is changed.

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

The second command waits for MCP messages on stdin. **To connect a client, copy the
snippet for your client from the desktop app's “Set up with your AI agent” panel (step 1, “Add Assetarium to your agent”)**, which
fills in this checkout's real paths, or run `python scripts/register-mcp.py --snippets-only`
(writes ignored `data/mcp/clients/`). The tracked [`clients/`](clients/) files are neutral
examples with a placeholder path. Do not wrap client startup in an installer. The entry
point resolves its own repository/configuration regardless of client cwd.
`codex-setup.toml` and `opencode-setup.json` are recorded evidence from the original
development machine, not current setup files.

MCP SDK **2.3.0**, NumPy **2.3.4** and Pillow **12.1.0** are locked separately
under `runtime/mcp/`. Semantic queries start one persistent private subprocess
using the existing `.venv-embedding`, unchanged model/backend/lock/index
contracts, offline weights and CUDA BF16. The worker only embeds the query text
or reference image; the server verifies, scores and fuses rankings in-process
(decision 0005). Its output is private JSON IPC with progress heartbeats; all
diagnostics use stderr. The MCP server starts the worker on its first semantic
query; only the desktop app pre-starts it. There is no automatic fallback/restart after a failed
worker, model initialization, or unchanged failed query.

The server entry point cannot process assets, scan/update the catalog, load
remote images, or import into Play Shapes. Existing generated captions and
relevance labels remain distinct from measured metadata and owner artistic
approval.

## Tool contract

`search_assets` accepts a text `query`, optional `mode`, `filters`, and `limit`.
The default is `combined` (Keyword + description + image); limit is an integer
**1–40**, default 5. Windows explicitly requests 20 by default.
Text is bounded to 1,024 characters (256 for keyword), excluding control
characters. Modes include keyword, description, text-to-image (`image`), combined,
and reference. Reference search takes `reference_asset_id` plus a known
`reference_view`, never a path/URL/upload. Text/reference arguments cannot mix.

Filters are only `asset_type` (`model_3d`, `image`, `audio`), pack, source
format, nonnegative maximum measured triangle count, boolean rigged, and for 2D
images boolean `transparent` and `size_class` (`tiny` ≤32, `small` ≤128,
`medium` ≤1,024 px, `large`); image filters match processed images only. Image
formats are png, jpg, jpeg, webp, bmp, gif, tga, tif, tiff, avif and svg.
`get_asset` on an image returns view `image` as PNG ImageContent with alpha kept:
the original source pixels (enlarged with hard pixel edges below 256 px, with
`native_dimensions`, `scale` and `resample` stated) or, for SVG, a raster from the
recorded renderer. `include_metadata` adds measured image facts and
`type_metadata` (generic purpose, folder-name suggestion, identical copies).
A reference search from an image uses its recorded model input, as indexed. Unknown filter keys/types/formats or path-like pack
names are rejected. Technical filters require inspected evidence for the
requested format. Every source and required dependency is boundary-resolved and
hash-verified; stale/unavailable inputs are excluded. Index/model/input contract
mismatches are errors, with no synthetic vectors or ranking fallback.

Query-time ranking policy is centrally defined in
`src/local_asset_library/search_policy.py`: weighted reciprocal rank fusion
contributes `weight / (60 + rank)` per channel, with combined image weight **3**
and keyword/description weight **1** each. Explicit `keyword_description` retains
equal weights. Raw scores are never averaged; deterministic asset-ID tie-breaking,
one result per logical asset and image best-view aggregation are retained. The
existing EmbeddingGemma 2 image/description vectors and published index are reused.
The legacy CLI omitted-mode keyword baseline is unchanged.

Search returns compact candidate summaries, ID preview references, matching
channels, caption/source fault flags, counts and a small sample of exclusion
faults. Full exclusion evidence lives in the local call audit. Its serialized
text budget is **6,000 characters for limits 1–5**, and
**2,000 + 1,000 × requested limit characters for limits 6–40**,
including size fields and fault summaries. Budgets for limits 5, 10, 20, 30 and 40
are respectively **6,000, 12,000, 22,000, 32,000 and 42,000 characters**.
Retrieval and the agent service share this policy, so the inner layer cannot
routinely discard a larger shortlist under a fixed compact cap. Typical compact
records fit the requested count; unusually large metadata can still truncate. It removes
lowest-ranked results deterministically to enforce the cap. The
`ceil(characters/4)` estimate is heuristic, not client billing/model tokens.
Semantic results remain weak/unvalidated even after approval of this bounded
pilot; rank scores are not probabilities or an absence detector.

Caption summaries now expose `caption_status`: `clear`, `review_note`, `warning`
or `fault`. `caption_faulty` is true only for an unusable caption; minor notes and
meaningful descriptive warnings do not make a source unusable. Metadata details
include `caption_quality` alongside original historical findings. See
[`../caption-quality.md`](../caption-quality.md) for classification and evidence
rules; owner approval and source faults remain separate.

`get_asset` accepts an exact `asset_` + 32 lowercase hexadecimal ID. Optional
`source_format` selects an existing export; the inspected source is preferred
otherwise. A grouped asset also lists `source_variants` (each file's folder label and format,
[decision 0019](../decisions/0019-source-folders-and-export-variants.md)); optional
`source_variant` picks one by label, for example `"Unity FBX"` when two files share a format.
Labels come from the asset's own files; paths are never accepted. A file that cannot be used
(for example its texture path points outside the source) is listed with `usable: false` and a
`reason`, is never selected, and requesting it is refused with that reason
([decision 0020](../decisions/0020-alternate-file-faults-and-recheck.md)). It returns the actual source path/hash, all known logical-asset
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

## Collections and tags

A collection is an owner-organized bundle of asset IDs, **not an asset**: members keep
their files where they are, and each member's **label** and **notes** belong to that
collection only. **Tags** are separate: short words on the asset itself, shared by
the whole app. Both live in app-owned `data/library/collections.json` and
`asset-tags.json`; the desktop app and every server write them under one lease, so
concurrent edits are serialized. Assets, sources and files stay read-only.

- `list_collections` (`query` up to 200 characters, `limit` 1–50, default 20): newest
  first; the query matches names and descriptions and, inside collections, member
  names, labels, notes, tags and descriptions. Each match says how many members hit.
- `get_collection` (`collection_id`, `offset`, `limit` 1–100, default 50): members in
  order with ID, name, type, source, label, notes, tags and `availability`
  (`available`, `source_only` with a reason, or `unavailable` with a reason), paged
  with `next_offset` within the 16,000-character detail cap.
- `edit_collection` (`action` = `create`, `rename`, `describe`, `add`, `remove` or
  `set_item`): create takes `name` (unique ignoring case) and optionally
  `description`, `asset_ids` (≤200 approved members), `label` and `notes`;
  `set_item` takes exactly one asset ID with a label and/or notes. **There is no
  delete**: only the owner deletes collections, in the app, after a confirmation.
  Each agent edit raises one `collection_changed` app notice for that collection.
- `tag_assets` (`asset_ids`, `add`, `remove`): tags are 1–32 characters without
  commas, at most 24 per asset, deduplicated ignoring case.

`search_assets` accepts `filters.collection` (a collection ID) and `filters.tag`.
`get_asset` also returns the asset's `tags` and the `collections` holding it with
their labels. The write tools are annotated `readOnlyHint: false`,
`destructiveHint: true` (removals); the others stay read-only. Collection text is
owner data, never instructions. Existing Codex registrations list
`enabled_tools` explicitly: add the four new names (see `codex-setup.toml`) to use
them; `register-mcp.py` refuses to overwrite an existing entry.

## Agent setup

An agent can set Assetarium up for the computer it runs on
([decision 0016](../decisions/0016-agent-setup.md)); the procedure is the user-invoked skill
[`skills/assetarium-setup`](../../skills/assetarium-setup/SKILL.md) and the server prompt
`set_up_assetarium`. The tools wrap `setup_core`, the same rules as the app's wizard.

| Tool | Input | Session | Does |
| --- | --- | --- | --- |
| `get_setup_status` | `{}` | not needed | OS, GPU/VRAM, free disk, Blender candidates, engine and search readiness, settings and who set them, proposals, `missing`, `next_actions` (exact commands), recommendations. Read only |
| `validate_blender` | `path` (≤1,024) | needed | Checks a file named `blender.exe`/`blender` (version, headless start with scripts disabled, glTF/FBX/OBJ importers). Nothing else is ever run |
| `apply_setup` | any of `storage_budget_gib`, `processing_formats`, `caption_batch_size`, `descriptions_enabled`, `description_engine`, `description_server {url, model}`, `engine_hint` | needed | Validated like the wizard, recorded as set by the agent; a local server must be on this computer, and the response includes its model list |
| `propose_setup` | `blender_path` (≤1,024) | needed | Stores a pending proposal for a path `validate_blender` passed; the user applies or rejects it |
| `finish_setup` | `{}` | needed | Marks setup completed by the agent; refused while a proposal is pending |

- **Session.** Writes need a setup session the user opens: **Set up with my agent** on the
  Welcome page, **Settings → General → Run setup with my agent**, or on Linux
  `local-assets setup agent` in an interactive terminal. It lasts 60 minutes and can be ended.
  Without one, writes return `{"status": "refused", "reason": …}` with `isError: true`.
- **Proposals.** The Blender path is applied only by the user's **Apply** (app, or
  `local-assets setup agent proposals`), after a fresh check in that process; a changed file
  is refused. `get_setup_status` shows `pending`, `applied`, `rejected`, `superseded` or `failed`.
- **Degraded mode.** If the configuration does not load, the server starts anyway with only
  `get_setup_status`, which returns `mode: setup_only`, the fault, the file and the exact fix.
  Fix it, then reconnect.
- **Connection.** While running, the server keeps `data/mcp/connections/<pid>.json` (pid,
  start, mode, client name from `initialize`); the app shows "connected" only while that
  process is alive. There is no network listener.
- **Privacy.** Status goes to the client's model, possibly in the cloud: OS, GPU, disk and
  Blender paths, never user names, environment variables, listings or the project path.
- **Annotations.** Status is read-only; the setup writes are `readOnlyHint: false`,
  `destructiveHint: false` (values are replaced, recorded and reversible).

Example client snippets, with every tool in `enabled_tools` and a placeholder checkout path,
are in [`clients/`](clients/) (`codex.toml`, `claude-code.txt`, `opencode.json`, `generic.json`;
`python scripts/register-mcp.py --snippets-only` writes this checkout's to `data/mcp/clients/`). The app's Welcome panel
generates the same text for the computer it runs on. **Existing Codex registrations must add
`get_setup_status`, `validate_blender`, `apply_setup`, `propose_setup` and `finish_setup` to
`enabled_tools`**, or the client never sees them. `tool_timeout_sec` is 180 because a Blender
check can take up to two minutes. `codex-setup.toml` and `opencode-setup.json` are earlier
recorded snippets and are not rewritten. Verification: `scripts/verify-agent-setup-mcp.py
--run-name NAME` drives the real STDIO server through the whole flow on an isolated project.

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

`scripts/historical/verify-agent-workflow.py codex|opencode` (original development machine only) performs one bounded real-client
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
bounded pilot decision recorded in those historical receipts. Step 8 received
separate scope and runtime/storage approval; its current contract and coverage
are documented in `../library-updates.md` and `../progress.md`.
