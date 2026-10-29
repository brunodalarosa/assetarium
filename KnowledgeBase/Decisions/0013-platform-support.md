---
tags: [decision]
decided: 2026-10-24
---
# 0013 — Platform support: Windows primary, Linux v1 is CLI + MCP

**Decision (owner, October 24, 2026).** Windows stays the fully verified primary
platform. Linux x86_64 with glibc (≥ 2.35; verified on Ubuntu 24.04 under WSL2) is a
supported tier for the **headless core**: CLI, scans, Blender inspection and
previews, Process assets, keyword search, the STDIO MCP server and the test suite.
**Linux v1 has no desktop app**: the owner chose a CLI-only Linux version. A Linux
GUI may come later as its own checkpoint (the Qt plan from milestone 1B is
deferred, not scheduled). Descriptions and semantic/image search on Linux are not
supported until verified on a CUDA machine.

- **Owner CLI on both platforms** (`owner_commands.py`, [docs/cli.md](../../docs/cli.md)):
  sources, Process assets / Generate descriptions / Cancel with progress, settings,
  importing failures and collection export/delete, as thin wrappers over the same
  backend calls as the desktop. `scripts/local-assets.ps1` / `.sh` run it from the
  `mcp` environment. Ctrl+C cancels safely; operations run in their own session off
  Windows so a closed terminal never kills them.
- **Deletions stay with the owner.** `sources remove` and `collections delete` need an
  interactive terminal and a typed `yes`, with no bypass flag, so an agent with shell
  access cannot delete ([decision 0012](0012-collections-and-tags.md)). Scripted
  export targets stay under `data/exports`. The owner commands are not MCP tools.
- **One helper per OS difference.** `config.venv_python` (`Scripts/python.exe` /
  `bin/python`) and `config.runtime_command` (`.ps1` through PowerShell / `.sh`
  through `sh`) give the same Windows paths and commands as before. Blender discovery
  is `inspection.blender_candidates` (never runs Blender), shared with setup checks.
- **Windows-compatible path policy everywhere.** Reserved names, `:` and trailing
  dots/spaces are rejected on every OS (`ntpath.isreserved`), so a catalog accepted on
  Linux stays valid on Windows. References are matched exactly; on a case-sensitive
  filesystem a wrong-case reference is a recorded fault. Accepting case-insensitive
  matches needs a separate owner decision.
- **Fingerprints stay byte-stable.** Blender worker scripts are not edited for
  portability (their hashes are inspection fingerprints); off Windows the launch adds
  `--python-expr` mapping `os.path.isreserved` to `ntpath.isreserved`.
- **Configuration.** The tracked `config.example.toml` is neutral (`models = "models"`,
  Blender discovered); machine paths live in the ignored `config.local.toml`
  ([decision 0001](0001-config-local-precedence.md)). Scripts load the project config.
- **Dependencies.** No platform markers were needed: all four lockfiles install with
  `--locked` on Linux unchanged. pywebview/pythonnet/clr-loader stay in the `mcp`
  environment until milestone 1B changes that lock.
- **Faults stay visible.** Missing runtimes, denied sleep inhibitors and unreadable
  references are reported, never treated as success. Process liveness reads the
  Linux process state and never reaps another owner's child.

**Why.** The owner wants other people, including Linux users, to run Assetarium as a
developer tool. The headless core had no OS-specific dependency beyond paths,
launchers and a few Windows-only calls, so it could be supported without changing
Windows behavior.

**Keep true.** Every owner action the desktop offers, except visual browsing and the
PDF print, stays reachable from the CLI on both platforms through the shared backend
call (no rule re-implemented in the CLI). New OS-specific code goes behind the
helpers above, with the Windows result unchanged and covered by a test. Run the
suite on both platforms with `LAL_REQUIRE_BLENDER=1` on Linux and report real-Blender
counts; a skipped Blender fixture is unverified. Do not call Linux support "full"
until the GPU path is verified there, and do not describe a Linux GUI as supported
until one is built and verified.
