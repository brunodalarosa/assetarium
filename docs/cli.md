# Command line (Windows and Linux)

Everything except visual browsing works from a terminal, the same way on Windows
PowerShell and a Linux shell. On Linux the CLI plus the MCP server *is* Assetarium
v1 ([decision 0013](decisions/0013-platform-support.md)). The commands call the
same backend as the desktop app, so the rules (fault handling, budgets, what is
processed) are identical.

Run them through the launcher, which uses the prepared `mcp` environment (it has
Pillow for PNG and Markdown exports) and installs nothing:

```powershell
.\scripts\local-assets.ps1 sources list
```

```bash
./scripts/local-assets.sh sources list
```

`.\scripts\uv.ps1 run --locked --no-sync --offline local-assets …` (or `uv.sh`)
works too; only PNG and Markdown exports need the launcher. Add `--json` before
the command for machine-readable output. Exit codes: `0` done, `1` finished with
recorded faults or still running, `2` refused or invalid.

## Sources

| Command | Same as in the app |
| --- | --- |
| `sources list` | Settings → Asset sources (status, pending, failed, reason) |
| `sources add PATH` | Add a folder; scans it (no rendering or models) |
| `sources enable KEY` / `sources disable KEY` | Enabled switch (enabling rescans) |
| `sources images KEY on\|off` | Include 2D images (rescans; nothing is deleted) |
| `sources exclude KEY PATTERN` / `sources include KEY PATTERN` | Excluded folders: a folder name with `*` or a path inside the source (rescans; nothing is deleted) |
| `sources textures KEY` | Models missing textures: folder suggestions with counts; choose with `--use FOLDER` and/or `--single-copies`, undo with `--undo` (rescans; originals never change) |
| `sources exports KEY` | Duplicate export folder suggestions and saved answers; answer with `--group ID`, `--separate ID`, `--exclude ID`, undo with `--undo ID` (rescans) |
| `sources remove KEY` | Remove: stops listing the source; files and results stay on disk |

## Processing

| Command | Same as in the app |
| --- | --- |
| `process --asset-source KEY` | Asset processing → Process assets: previews and search data, then publish |
| `describe --asset-source KEY` | Generate descriptions (built-in engine: the caption runtime and an NVIDIA CUDA GPU; local model server: only the running server) |
| `cancel --asset-source KEY` | Cancel |
| `process --asset-source KEY --follow` | Watch an operation that is already running |
| `refresh --asset-source KEY` | Refresh published view (publishes usable partial results) |
| `failures` | Importing failures report: original paths of assets whose import failed |
| `recheck --asset-source KEY` | Recheck failures: lists failures from the file/dependency check that pass it now and, after a typed `yes`, retries them on the next Process assets (decision 0020) |

`process` and `describe` wait and print progress. **Ctrl+C cancels safely**: the
current asset finishes (descriptions finish their batch) and saved work is kept;
a second Ctrl+C only stops watching while the cancel completes. The work runs as
its own process, so closing the terminal does not stop it; `--follow` reattaches.
Recorded failures are never retried by these commands.

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
```

Changing settings never deletes results or retries faults. Server addresses must be on
this computer ([description engines](description-engines.md)).

## Setup

The desktop app's setup wizard, in a terminal ([decision 0014](decisions/0014-setup-wizard.md));
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
([decision 0016](decisions/0016-agent-setup.md)): it opens the setup session agents need for
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

`sources remove` and `collections delete` ask you to type `yes`, like the app's red
confirmations. They refuse to run without an interactive terminal and have no
bypass flag: agents can run commands, and only the owner deletes (decision 0012).
Replacing an existing export file asks the same way.

## Agents (MCP)

Agents use the STDIO MCP server for search, asset detail, collections and tags
([MCP setup](mcp/README.md)). The owner commands above are not MCP tools: sources and
processing stay owner actions. Setup is available to agents only inside a session you open
(`setup agent`), and the Blender path only as a proposal you approve.
