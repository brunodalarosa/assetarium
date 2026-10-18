# Assetarium

**Find, explore, and organize your game assets.**

Assetarium turns folders of 3D game assets into a searchable local catalog for
people and AI agents. Browse previews, explore models in 3D, search by filename
or visual description, and retrieve the actual source files and their known
dependencies without changing the originals.

The project is in early development and is being prepared for an open source
release. The current application targets Windows and runs from a source checkout;
there is no packaged installer yet. Earlier documentation and the application
still use the working name **Local Asset Library (LAL)**. Python packages, commands,
launchers, and MCP identifiers retain their existing names for compatibility.

## What it does

- **Browse your collection:** register asset folders, browse individual sources,
  and inspect saved previews and metadata in a Windows desktop app.
- **Find suitable assets:** search filenames, generated descriptions, preview
  images, or a combination of all three. Reference-image search uses an existing
  catalog asset.
- **Explore in 3D:** rotate, pan, and zoom supported source formats in the app,
  using a bundled offline viewer.
- **Inspect before choosing:** review geometry facts, alternate formats, known
  dependencies, license evidence, and processing results.
- **Connect AI agents:** expose the same search and asset-detail backend through
  the local MCP tools `search_assets` and `get_asset`.
- **Update incrementally:** detect source changes, resume unfinished processing,
  and publish complete catalog/index generations while retaining usable results
  and recorded failures.

Original asset files remain read only. Generated source information lives in a
`metadata-lal` directory alongside each registered collection. Settings, combined
indexes, caches, and application reports stay in local project storage.

Assetarium catalogs assets you supply; this repository does not include asset
packs, model weights, or a prebuilt personal catalog. Generated descriptions and
search scores help discovery but do not establish visual accuracy, artistic
suitability, or licensing permissions.

## Requirements

| Component | Used for |
| --- | --- |
| Windows, Git, PowerShell, and Python **3.13** | Current development and desktop workflow |
| `uv`, available on your PATH | Installing the pinned Python environments through the project wrappers |
| Microsoft Edge WebView2 Runtime and .NET Framework | The Windows desktop app |
| Blender with the required importers | Technical inspection and preview rendering |
| Compatible NVIDIA CUDA hardware with BF16 support | The current caption and embedding pipelines |
| Locally prepared model weights | Visual descriptions and semantic/image search |

Saved previews, catalog browsing, and keyword search do not require model
inference. New preview generation needs Blender; semantic search and caption
generation need their separately prepared runtimes and models. Other operating
systems and CPU-only inference are not validated by the current workflow.

## Getting started

### 1. Clone and configure

```powershell
git clone https://github.com/brunodalarosa/assetarium.git
cd assetarium
Copy-Item config.example.toml config.local.toml
```

Edit `config.local.toml` before running the application. The example contains
machine-specific paths: set `[tools].blender` to your Blender executable and
`[storage].models` to your shared model directory, or use `"models"` for a
project-local model directory. Runtime entry points prefer `config.local.toml`
when present. The local file is ignored by Git.

### 2. Prepare the base and desktop environments

Run these commands from the repository root:

```powershell
.\scripts\uv.ps1 sync --locked
.\scripts\mcp-runtime.ps1 sync --locked --project runtime/mcp
.\scripts\uv.ps1 run --locked --no-sync --offline local-assets check-config
.\scripts\uv.ps1 run --locked --no-sync --offline local-assets doctor
```

`check-config` validates configuration. `doctor` checks the base dependencies and
whether the configured Blender executable exists; it does not verify rendering,
model inference, or asset compatibility.

The wrappers keep environments and caches in project-controlled locations and
share the uv cache using hard links. Captioning and embeddings have separate
locks because their dependencies differ. See [storage guidance](docs/storage.md)
before installing the larger runtimes or downloading models; account for several
GiB beyond the source checkout.

### 3. Open the app and add your assets

Double-click **Local Asset Library.vbs** in the checkout. The launcher uses the
prepared desktop environment; it does not install dependencies or download models.

In **Settings → Asset sources**, register your asset directories. Enabled sources
are scanned at startup to detect changes; scanning does not render assets or run
models. **Process assets** starts the processing/publication workflow explicitly,
using the Blender, runtime, and model setup required by its pending stages.

For the current setup and processing details, read:

- [Desktop app and controls](docs/gui/README.md)
- [Asset sources and processing](docs/asset-sources.md)
- [Incremental library updates](docs/library-updates.md)
- [Model locations and shared storage](docs/model-storage.md)
- [Caption model contract](docs/caption-contract.md)
- [Embedding and search contract](docs/embedding-contract.md)

Model preparation is still a developer workflow. Some historical preparation and
verification scripts read `config.example.toml` directly rather than the local
override; review their configuration assumptions before using them on a new
machine. Installing the base and desktop environments alone does not prepare
captioning or semantic search.

## Use with AI agents

Assetarium provides a local STDIO MCP server with two tools:

| Tool | Purpose |
| --- | --- |
| `search_assets` | Return a bounded shortlist using the shared search modes and filters |
| `get_asset` | Retrieve source paths, known dependencies, metadata, and an optional actual preview image |

After preparing the desktop/MCP runtime, clients can launch:

```powershell
& '.\.venv-mcp\Scripts\python.exe' scripts\asset-mcp.py
```

This command waits for MCP messages on standard input. Configure your client with
absolute executable and script paths from your own checkout. Existing setup
snippets in the detailed documentation describe the original development machine
and need their paths adapted. The server searches published results; it does not
process assets or import them into a game engine.

See [MCP setup and tool contracts](docs/mcp/README.md) and the
[asset-selection skill](skills/local-asset-library/SKILL.md).

## Development and contributions

Bug reports, reproducible examples, documentation improvements, and focused pull
requests are welcome through the [GitHub repository](https://github.com/brunodalarosa/assetarium).
Describe the expected behavior, what happened, and the relevant runtime or format.
Use small synthetic examples instead of uploading proprietary asset packs,
private configuration, or model weights.

Read [AGENTS.md](AGENTS.md) and the [recorded decisions](docs/decisions/README.md)
before implementation. These document the project's approval checkpoints,
original-file protection, fault handling, and storage requirements. Desktop and
MCP changes should continue to use the same retrieval and validation backend.

With the desktop/MCP environment already prepared, run the test suite using:

```powershell
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest --basetemp scratch/pytest
```

Some integration checks require Blender or the native Windows desktop stack.
The reusable test directory contains temporary fixtures; application evidence
and processing reports are retained separately.

## Documentation and project status

- [Progress and verification history](docs/progress.md)
- [Owner-approved technical decisions](docs/decisions/README.md)
- [Interactive 3D previews](docs/gui/3d-preview.md)
- [Caption quality and review](docs/caption-quality.md)
- [Storage and retention](docs/storage.md)
- [Original staged project plan](docs/plan/PROJECT.md)
- [Vendored viewer dependencies and attribution](src/local_asset_library/ui/vendor/README.md)

Detailed reports include historical pilot results and development-machine paths.
They record the checks performed at those milestones, rather than promising
compatibility with every machine, asset format, or collection.

## License

A project-wide open source license has not been selected yet. The project is
being prepared for that release. Bundled third-party components retain their own
licenses and attribution notices; asset packs and model weights are separate.
