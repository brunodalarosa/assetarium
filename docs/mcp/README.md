# Local agent access (MCP)

Assetarium's MCP server exposes `search_assets` and `get_asset`, plus the collection tools
`list_collections`, `get_collection`, `edit_collection` and `tag_assets`
([decision 0036](../../Assetarium%20KnowledgeBase/Decisions/0036-collections-and-tags.md); see
[Collections and tags](#collections-and-tags)) and the setup tools
`get_setup_status`, `validate_blender`, `apply_setup`, `propose_setup` and
`finish_setup` ([decision 0031](../../Assetarium%20KnowledgeBase/Decisions/0031-setup.md); see
[Agent setup](#agent-setup)), over local STDIO. Each request is pinned to one published
catalog/index generation. There is no HTTP listener, export tool, arbitrary-path input,
copy operation or source-writing API. Restart older server connections after an update to
load new membership, version and lease behavior.

How the server is built, how client registration is preserved and how it is verified are in
the knowledge base: [MCP server](../../Assetarium%20KnowledgeBase/Architecture/MCP/MCP%20server.md).

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
The registrations recorded on the original development machine are kept locally by
the owner, not published; they were never setup files.

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
Semantic results remain weak and unvalidated beyond the recorded benchmark
(`docs/evaluation/`); rank scores are not probabilities or an absence detector.

Caption summaries now expose `caption_status`: `clear`, `review_note`, `warning`
or `fault`. `caption_faulty` is true only for an unusable caption; minor notes and
meaningful descriptive warnings do not make a source unusable. Metadata details
include `caption_quality` alongside original historical findings. See
[Caption severity](../../Assetarium%20KnowledgeBase/Architecture/Processing/Caption%20severity.md) for classification and evidence
rules; owner approval and source faults remain separate.

`get_asset` accepts an exact `asset_` + 32 lowercase hexadecimal ID. Optional
`source_format` selects an existing export; the inspected source is preferred
otherwise. A grouped asset also lists `source_variants` (each file's folder label and format,
[decision 0019](../../Assetarium%20KnowledgeBase/Decisions/0019-source-folders-and-export-variants.md)); optional
`source_variant` picks one by label, for example `"Unity FBX"` when two files share a format.
Labels come from the asset's own files; paths are never accepted. A file that cannot be used
(for example its texture path points outside the source) is listed with `usable: false` and a
`reason`, is never selected, and requesting it is refused with that reason
([decision 0020](../../Assetarium%20KnowledgeBase/Decisions/0020-alternate-file-faults-and-recheck.md)). It returns the actual source path/hash, all known logical-asset
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
`enabled_tools` explicitly: add the four new names to use them, for example
`enabled_tools = ["search_assets", "get_asset", "list_collections", "get_collection",
"edit_collection", "tag_assets"]`; `register-mcp.py` refuses to overwrite an existing entry.

## Agent setup

An agent can set Assetarium up for the computer it runs on
([decisions 0031](../../Assetarium%20KnowledgeBase/Decisions/0031-setup.md) and
[0035](../../Assetarium%20KnowledgeBase/Decisions/0035-packs-and-variant-groups.md)); the procedure is the user-invoked skill
[`skills/assetarium-setup`](../../skills/assetarium-setup/SKILL.md) and the server prompt
`set_up_assetarium`. The tools wrap `setup_core`, the same rules as the app's wizard.

| Tool | Input | Tier | Does |
| --- | --- | --- | --- |
| `get_setup_status` | `{}` | read | Checks this computer itself (the configured Blender, or the first one found; runtimes; model weights by size) and returns `found` (plain statements), `ask_user` (the only questions for the user, each with a suggestion and why), `guide` (how to talk to the user), `next_actions` (each with `kind`: `tool` to run without asking, `install`/`download` to ask about with its size, `user`), settings and who set them, proposals and readiness. Changes nothing |
| `validate_blender` | optional `path` (≤1,024) | run | Checks a file named `blender.exe`/`blender` (version, headless start with scripts disabled, glTF/FBX/OBJ importers); without `path`, the configured one (or a refusal naming the Blenders found). Nothing else is ever run |
| `verify_weights` | optional `model` (`caption`, `embedding`, `all`) | run | Hashes weights already in `[storage].models` against the pinned file list (`docs/*-model-files.json`) and writes the same receipt a verified download writes. Local only, in the background; waits up to 20 s, then status shows progress |
| `apply_setup` | `answers {engines[], descriptions, model_server {url, model}, storage_gib}` and/or any of `storage_budget_gib`, `processing_formats`, `caption_batch_size`, `descriptions_enabled`, `description_engine`, `description_server {url, model}`, `search_device`, `engine_hint`; `finish` | apply and undo | Answers become settings (formats from the engines, the description engine and search device from the GPU, the batch size from its memory), each derived one returned in `implied` with why; explicit values override. Validated like the wizard, recorded as set by the agent with the replaced value kept for Undo. A local server must be on this computer, and the response includes its model list. `finish: true` also finishes |
| `propose_setup` | `blender_path` (≤1,024) | propose | Stores a pending proposal for a path `validate_blender` passed; the user applies or rejects it. `already_applied` when it is the configured Blender |
| `finish_setup` | `{}` | apply and undo | Ends the agent's part: setup waits in `review` until the user confirms the report in the app (**Looks good** → `completed`); refused while a proposal is pending |

- **Tiers, no session.** Since decision 0024 there is no setup session: what a tool may do depends
  on its tier. *Read* tools always answer; *apply and undo* values are recorded as set by the agent
  and raise one notice per day that the user can act on; *propose* waits for the user's Apply;
  *run* only ever starts a file named `blender.exe`/`blender`.
- **Proposals.** The Blender path is applied only by the user's **Apply** (app, or
  `local-assets setup agent proposals`), after a fresh check in that process; a changed file
  is refused. `get_setup_status` shows `pending`, `applied`, `rejected`, `superseded` or `failed`.
- **Guided conversation.** The agent checks everything verifiable itself and asks the user only the
  `ask_user` questions (engines, AI descriptions or, without an NVIDIA GPU with BF16, whether a local
  model server already runs, and the storage budget), in one message. The same guide is in the server
  instructions while setup is unfinished and in the `set_up_assetarium` prompt, so clients without the
  skill get it too.
- **Weights placed by hand** are reported as `present` (here, not verified yet) and get `verify_weights`,
  never a download; `local-assets setup verify-weights` does the same from a terminal.
- **Degraded mode.** If the configuration does not load, the server starts anyway with only
  `get_setup_status`, which returns `mode: setup_only`, the fault, the file and the exact fix.
  Fix it, then reconnect.
- **Connection.** While running, the server keeps `data/mcp/connections/<pid>.json` (pid,
  start, mode, client name from `initialize`); the app shows "connected" only while that
  process is alive. There is no network listener.
- **Privacy.** Status goes to the client's model, possibly in the cloud: OS, GPU, disk and
  Blender paths, never user names, environment variables, listings or the project path.
- **Agent entries.** A client whose entry starts a moved or deleted copy only reports
  "connection closed", so no tool can explain it. The app's agent panel (step 1) and
  `local-assets setup agent check` read only the `local_asset_library` entry in the Claude Code,
  Codex and OpenCode settings, say which copy each one starts and show the fix; nothing is
  written or sent to the agent. The Claude Code snippet removes an existing user entry before
  adding this checkout's, so running it again repairs a stale one.
- **Annotations.** Status is read-only; the setup writes are `readOnlyHint: false`,
  `destructiveHint: false` (values are replaced, recorded and reversible).

Example client snippets, with every tool in `enabled_tools` and a placeholder checkout path,
are in [`clients/`](clients/) (`codex.toml`, `claude-code.txt`, `opencode.json`, `generic.json`;
`python scripts/register-mcp.py --snippets-only` writes this checkout's to `data/mcp/clients/`). The app's Welcome panel
generates the same text for the computer it runs on. **Existing Codex registrations must add
`get_setup_status`, `validate_blender`, `apply_setup`, `propose_setup` and `finish_setup` to
`enabled_tools`**, or the client never sees them. `tool_timeout_sec` is 180 because a Blender
check can take up to two minutes. Verification: `scripts/verify-agent-setup-mcp.py
--run-name NAME` drives the real STDIO server through the whole flow on an isolated project.

## Pack structure

Agents fix how a scan reads a pack (decision 0024): which folders are packs, which names are variants
of one asset, which folders are engine copies, how images are meant. Every response is capped at about
8,000 characters (≈2,000 tokens) so small local models can work page by page.

| Tool | Input | Tier | Does |
| --- | --- | --- | --- |
| `list_packs` | `library_folder`?, `status`?, `cursor`?, `limit`? (≤50) | read | Packs, those that need a structure first, with their reasons |
| `get_pack_outline` | `library_folder`, `path`?, `cursor`?, `limit`? (≤60) | read | One folder level: subfolders with file and asset counts and pack evidence, and its files as patterns (`Car_11_{B,G,R}.obj (3)`, `Rock_{01..20}.fbx (20)`) |
| `get_profile` | `library_folder`, `pack` | read | The pack's rules, signals, version, any waiting proposal and the rule vocabulary |
| `propose_profile` | `library_folder`, `pack`, `rules` (≤500), `note`? | propose (instant rules: apply and undo) | The pack's whole rule list. Variant and pack rules apply at once (the user can undo); exclusions, engine copies, image kinds, export groups and the texture folder wait for the user's Apply and rescan. Returns the effect |
| `finish_structure` | `library_folder`, `pack` | apply and undo | Marks the pack's current signals reviewed; new signals show again |
| `say` | `message` (≤300) | apply and undo | One line in the user's Agent activity |

Rules are a closed vocabulary (`pack`, `pack_name`, `image_kind`, `variant_axis`, `separate_descriptions`,
`exclude`, `engine_copy`, `export_group`, `texture_folder`) with paths inside the pack; there are no patterns.
Search returns each variant group once (`variant`, `variants`), and `get_asset` lists an asset's variants and
`description_shared_from` when it shares its group's description. Every call appears in the app's Agent
activity, built from the server's call log.

**Try your agent** (Settings → General or optional setup) generates small practice packs and opens the same
discovery, handoff and proposal review used by the Library. Connect your agent, copy the practice prompt into it,
then accept or reject its proposed rules in Assetarium. The check observes engine copies, pack boundaries, image
classification and a correctly organized pack; marking signals reviewed alone does not pass it. Finish at any
time to see what worked and what remains unresolved. Practice does not render or generate descriptions.

Practice has a separate temporary library, hashes and activity. Generated files and test data are removed when
you finish or cancel; results exist only on the open results screen. If the app stops unexpectedly, it cleans up
on the next launch. A cleanup failure stays visible. The agent's own chat history is controlled by that agent.
The practice prompt scopes every call to its temporary `library_folder`; `say` also accepts that optional field.
No new MCP registration or tool names are needed. Existing Codex registrations must include the six pack tool
names in `enabled_tools`.

## Privacy

Rendering, captioning, indexing and search inference stay on this computer. Your agent's
model receives what the tools return: candidate text, descriptions, source/dependency paths,
requested metadata and PNG previews. If that model runs in the cloud, a local MCP transport
does not keep those results private. No full source model files or configuration backups are
returned through these tools, and no public server is exposed.
