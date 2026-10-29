# Linux (CLI + MCP)

Assetarium v1 on Linux x86_64 (glibc) is **command line plus the MCP server**, with
no desktop app ([decision 0013](../KnowledgeBase/Decisions/0013-platform-support.md)). Every owner
action except visual browsing runs from the [CLI](cli.md): sources, Process assets,
settings, failures and collection exports, plus scans, Blender previews, keyword
search, the STDIO MCP server and the test suite. Windows stays the fully verified
primary platform. GPU descriptions and semantic/image search are **not verified on
Linux yet**.

Verified on October 24, 2026 in WSL2 Ubuntu 24.04 (glibc 2.39, ext4) with Blender
5.2.2: full suite 575 passed, 1 skipped (a Windows-junction test), 4 real-Blender
tests ran, and the CLI-only smoke check passed. See [progress](history/progress-2026-10.md) for the
evidence paths.

## 1. Packages

Ubuntu/Debian (other x86_64 glibc ≥ 2.35 distributions need the same libraries):

```bash
sudo apt install -y git curl xz-utils libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libxkbcommon0 libsm6
```

Install [uv](https://docs.astral.sh/uv/) (tested with 0.12.11). uv installs Python
3.13 into the project's `cache/python`; no system Python is needed.

## 2. Clone and environments

Clone onto a Linux filesystem (in WSL: your home directory, not `/mnt/c`): hard
links, speed and case sensitivity differ there. The cache and environments must be
on one filesystem for `UV_LINK_MODE=hardlink`.

```bash
git clone https://github.com/brunodalarosa/assetarium.git && cd assetarium
./scripts/uv.sh sync --locked
./scripts/mcp-runtime.sh sync --locked --project runtime/mcp
./scripts/uv.sh run --locked --no-sync --offline local-assets check-config
./scripts/uv.sh run --locked --no-sync --offline local-assets doctor
```

The `.sh` wrappers are the POSIX twins of the `.ps1` wrappers (same project-local
caches plus `TMPDIR`). If a checkout lost their executable bit, run them with `sh`.
The `mcp` environment still installs pywebview, pythonnet and clr-loader; they are
pure-Python wheels and are not imported by the headless core.

## 3. Blender

Download the official Linux build from <https://www.blender.org/download/> (tested:
`blender-5.2.2-linux-x64.tar.xz`, verify it against the published `.sha256`) and
unpack it, for example into your home directory. Without a configured path,
discovery checks `blender` on `PATH`, `/usr/bin`, `/usr/local/bin`, `/snap/bin`,
`/opt/blender*/blender` and `~/blender*/blender`; `doctor` lists what it finds
without running Blender. To pin one, copy `config.example.toml` to the ignored
`config.local.toml` and set:

```toml
[tools]
blender = '/home/me/blender-5.2.2-linux-x64/blender'
```

Blender runs headless with scripts disabled and renders with CPU Cycles, isolated
from your profile (`HOME` and `XDG_*` point into `scratch/`). Off Windows the
launch adds one `--python-expr` that gives Blender's Python the Windows reserved-name
check (`ntpath.isreserved`), because the worker scripts are inspection fingerprints
and are not edited.

## 4. Tests and checks

```bash
LAL_REQUIRE_BLENDER=1 ./scripts/mcp-runtime.sh run --locked --no-sync --offline --project runtime/mcp python -m pytest --basetemp scratch/pytest
./scripts/mcp-runtime.sh run --locked --no-sync --offline --project runtime/mcp python scripts/smoke-headless.py --run-name <new-name>
.venv/bin/python scripts/storage-report.py --output <new-name>.json
```

The summary line `Real-Blender tests: …` counts the tests that really used Blender;
`LAL_REQUIRE_BLENDER=1` turns a missing Blender into a failure instead of a skip
(`LAL_TEST_BLENDER` pins the executable). `smoke-headless.py` (also on Windows)
copies the code into an isolated `scratch/smoke/<run>/project`, links the prepared
environments without installing anything and drives the CLI wrapper and the STDIO
server end to end with real Blender; your own library is never touched. The
embedding environment is not linked there, so the image-vector stage is recorded as
a fault and the inspected results are published with `refresh`.

`storage-report.py` excludes file symlinks off Windows (venv interpreters are
links); it reports them as `excluded_file_links`.

## 5. Using it

See [Command line](cli.md). In short:

```bash
./scripts/local-assets.sh sources add /path/to/assets
./scripts/local-assets.sh process --asset-source <key>     # Ctrl+C cancels safely
./scripts/local-assets.sh search lantern
```

## 6. MCP

Clients launch `.venv-mcp/bin/python scripts/asset-mcp.py` with the checkout as
`cwd`. `scripts/register-mcp.py` writes that entry for Codex (`CODEX_HOME`) and,
with `--opencode-config PATH`, for OpenCode.

## 7. Paths on a case-sensitive filesystem

Asset paths keep the Windows-compatible policy on every OS: Windows reserved names
(`con.png`, `aux.obj`), `:` and trailing dots/spaces are rejected and recorded as
faults. References are matched exactly. On Linux, a texture or MTL referenced with
a different letter case than the file on disk is therefore **missing** (a visible
fault), although Windows resolves it. The October 24 investigation
(`scripts/investigate-path-semantics.py`) also found that Blender's Linux OBJ importer
does not open `map_Kd` paths written with `\`, which the scanner accepts. Whether
to accept unique case-insensitive matches is an open owner decision; nothing
resolves them silently.

## 8. Known limits

- Descriptions and semantic/image search need the caption and embedding runtimes and
  an NVIDIA CUDA GPU with BF16; not yet validated on Linux (`caption-runtime.sh` and
  `embedding-runtime.sh` exist but were not installed).
- Overnight runs hold a `systemd-inhibit` sleep lock when allowed and print a note
  otherwise. Under WSL without a login session it is denied, and it never keeps
  Windows awake.
- No desktop app on Linux in v1 (owner decision); the WebView2 verification harness
  and PDF collection exports are Windows-only.
