# Command line (Windows and Linux)

Everything except visual browsing works from a terminal, the same way on Windows
PowerShell and a Linux shell. On Linux the CLI plus the MCP server *is* Assetarium
v1 ([decision 0013](../Assetarium%20KnowledgeBase/Decisions/0013-platform-support.md)). The commands call the
same backend as the desktop app, so the rules (fault handling, budgets, what is
processed) are identical.

Run them through the launcher, which uses the prepared `mcp` environment (it has
Pillow for PNG and Markdown exports) and installs nothing:

```powershell
.\scripts\local-assets.ps1 library list
```

```bash
./scripts/local-assets.sh library list
```

`.\scripts\uv.ps1 run --locked --no-sync --offline local-assets …` (or `uv.sh`)
works too; only PNG and Markdown exports need the launcher. Add `--json` before
the command for machine-readable output. Exit codes: `0` done, `1` finished with
recorded faults or still running, `2` refused or invalid.

## Library folders

A library folder is a watched folder of assets; nothing is ever written into it. `sources …` still works
as the old name of `library …`.

| Command | Same as in the app |
| --- | --- |
| `library list` | Asset sources tab: each library folder with pending, failed and its reason |
| `library add PATH` | Add library folder; scans it (no rendering or models). A folder inside a library folder is refused as already covered; one around library folders replaces them and keeps their assets, IDs and results |
| `library enable KEY` / `library disable KEY` | Included in search switch (enabling rescans) |
| `library exclude KEY PATTERN` / `library include KEY PATTERN` | Exclude folder / Include again: a folder name with `*` or a path inside the folder (rescans; nothing is deleted) |
| `library images KEY FOLDER textures\|2d\|auto` | Treat images here as textures / as 2D assets, or let detection decide (rescans) |
| `library textures KEY` | Models missing textures: folder suggestions with counts; choose with `--use FOLDER` and/or `--single-copies`, undo with `--undo` (rescans; originals never change) |
| `library exports KEY` | Duplicate export folder suggestions and saved answers; answer with `--group ID`, `--separate ID`, `--exclude ID`, undo with `--undo ID` (rescans) |
| `library remove KEY` | Remove: stops watching the folder; its results stay in the library store and adding it again restores them |
| `forget-missing KEY [--pack FOLDER]` | Forget missing: assets whose files vanished are forgotten (interactive `yes`; their history stays) |

## Packs

| Command | Same as in the app |
| --- | --- |
| `packs list KEY` | The packs and bundles detected in a library folder, with the evidence (license, readme, preview, versioned name) |
| `packs rename KEY FOLDER NAME` | Rename a pack (an empty name restores the folder name) |
| `packs merge KEY FOLDER` | Merge into parent pack (rescans) |
| `packs split KEY FOLDER` | Make this a pack (rescans) |
| `packs reset KEY FOLDER` | Forget a merge or split; detection decides again (rescans) |

## Processing

| Command | Same as in the app |
| --- | --- |
| `previews KEY[/FOLDER]` | Make previews for a library folder, folder or pack: inspection, previews and search data. It starts at once or waits in the queue |
| `previews KEY --asset ID …` | Make previews for picked assets |
| `describe KEY[/FOLDER]` | Generate descriptions (built-in engine: the caption runtime and an NVIDIA CUDA GPU; local model server: only the running server) |
| `previews … --dry-run` | What it would do: counts, an estimated time range and disk, and what is blocked with its fix |
| `queue list` | Asset processing: Running, Up next, Blocked |
| `queue move ID POSITION` / `queue remove ID` | Reorder or remove an item; removing the running one cancels it cleanly |
| `queue pause` / `queue resume` | A queue left over after a restart is paused and never resumes by itself |
| `queue overnight on\|off [--window 22:00-07:00]` | Hold descriptions until the overnight window |
| `process --asset-source KEY` | Process a whole library folder now, watching its progress |
| `cancel --asset-source KEY` | Cancel |
| `refresh --asset-source KEY` | Refresh published view (publishes usable partial results) |
| `failures` | Original paths of assets whose import failed |
| `recheck --asset-source KEY` | Recheck failures: lists failures from the file/dependency check that pass it now and, after a typed `yes`, retries them on the next Make previews (decision 0020) |

Previews always run ahead of descriptions, one item at a time; each finished item starts the next, so
the queue runs without the app or the terminal. The scope is resolved when an item starts ("whatever in
this pack still lacks previews"). An item estimated over 30 minutes, or one that would reach the storage
budget, prints its estimate and starts only with `--yes`. Blocked work (Blender not set up, the search
runtime missing) is never queued: the command names the fix instead.

`process` waits and prints progress. **Ctrl+C cancels safely**: the current asset finishes and saved work
is kept; a second Ctrl+C only stops watching while the cancel completes. The work runs as its own process,
so closing the terminal does not stop it; `--follow` reattaches. Recorded failures are never retried by
these commands.

## The one-time library migration

Results from before the library store live in a `metadata` folder inside each old source. Move them into
the store once, with the app and MCP servers closed (base runtime; nothing renders or is described again):

```powershell
.\scripts\uv.ps1 run --locked python scripts/migrate-library.py --library-folder "D:\Game Assets"
.\scripts\uv.ps1 run --locked python scripts/migrate-library.py --library-folder "D:\Game Assets" --apply
.\scripts\uv.ps1 run --locked python scripts/migrate-library.py --remove-old
```

The first run is a dry run that writes a plan to `data/library/migration/`; `--apply` asks for a typed `yes`,
imports, verifies and writes a receipt; `--remove-old` deletes only verified old folders, asking for each.
See [Asset sources](asset-sources.md#moving-results-into-the-library-store).

`process --stage inspection|caption|embeddings` is the existing stage-level
maintenance command (used by `library-batch.py`) and is unchanged.

## Settings

```text
settings show
settings set --formats gltf,fbx        # "none" pauses processing; glb counts as gltf
settings set --budget-gib 24           # whole GiB
settings set --batch-size 4            # 1, 2, 4 or 8 (built-in engine only)
settings set --descriptions off        # on/off; off keeps existing descriptions
settings set --engine local-server --server-url http://127.0.0.1:8080/v1 --server-model qwen3-vl-2b
settings set --engine builtin
settings set --search-device cpu       # cuda or cpu: where search by description and image runs
settings set --search-threads 24       # auto (the speed test's choice) or CPU threads for search data
```

Changing settings never deletes results or retries faults. Server addresses must be on
this computer ([description engines](description-engines.md)).

## Rendering

```text
rendering show                          # what renders now and why, the last speed test, device keys
rendering set --device cpu              # auto (fastest tested), cpu, or a GPU key from "rendering show"
rendering set --processes 2             # auto or 1-8: at most this many renders at a time
rendering set --memory-gib 20           # auto (70% of free memory) or whole GiB, e.g. more overnight
rendering test                          # run the speed test now (about 2 minutes); Ctrl+C cancels
rendering cancel                        # cancel a running speed test; the previous result is kept
```

Limits only lower the number of renders at a time or change their memory allowance; rendering
never goes past the fastest tested number or the memory free now
([decision 0022](../Assetarium%20KnowledgeBase/Decisions/0022-parallel-rendering.md)).

## Setup

The desktop app's setup wizard, in a terminal ([decision 0014](../Assetarium%20KnowledgeBase/Decisions/0014-setup-wizard.md));
the same backend rules decide everything.

```text
setup                                  # guided setup (needs an interactive terminal)
setup status                           # this computer, Blender, engines and missing commands; runs nothing
setup blender check PATH               # executable name, version, headless start, importers
setup blender set PATH [--confirm-rerender]   # check, then save to config.local.toml
setup skip                             # record that setup was skipped
setup agent                            # let your AI agent set up Assetarium for 60 minutes (interactive)
setup agent proposals                  # apply or reject the agent's Blender proposal (interactive)
setup agent end                        # end the agent's setup access
```

`setup agent` is the terminal version of the app's **Set up with my agent**
([decision 0016](../Assetarium%20KnowledgeBase/Decisions/0016-agent-setup.md)): it opens the setup session agents need for
any setup change and prints the client configuration and the prompt to give them. Opening a
session and deciding proposals need an interactive terminal and have no flag, so an agent
running commands cannot grant itself access.

`setup blender set` writes nothing when the path is already what Assetarium uses. A
changed Blender marks finished 3D inspections as pending again (the path is part of
their fingerprint), so it needs `--confirm-rerender` when processed assets exist.

## Collections

| Command | Notes |
| --- | --- |
| `collections list [TEXT]` | Same search as the Collections tab |
| `collections export ID --format json\|png\|md [--output FILE]` | Default `data/exports/collections/<name>`; `--output` must stay under `data/exports` (decision 0012). PDF needs the desktop app |
| `collections delete ID` | Deletes the collection with its labels and notes; the assets are not affected |

Creating and editing collections and tags is available to agents through the MCP
tools (`edit_collection`, `tag_assets`) and in the desktop app.

## Confirmations

`library remove` and `collections delete` ask you to type `yes`, like the app's red
confirmations. They refuse to run without an interactive terminal and have no
bypass flag: agents can run commands, and only the owner deletes (decision 0012).
Replacing an existing export file asks the same way.

## Agents (MCP)

Agents use the STDIO MCP server for search, asset detail, collections and tags
([MCP setup](mcp/README.md)). The owner commands above are not MCP tools: sources and
processing stay owner actions. Setup is available to agents only inside a session you open
(`setup agent`), and the Blender path only as a proposal you approve.
