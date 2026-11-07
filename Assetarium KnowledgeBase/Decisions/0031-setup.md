---
tags: [decision]
decided: 2026-11-07
supersedes: [0014, 0016, 0026]
code: [setup_core.py, setup_core.first_run, setup_core.save_setup, setup_core.check_blender, setup_agent.py, search_check.record, source_operations.search_check, source_operations.ensure_search_check, sources.include_samples, engines.search_readiness, settings.uses, frontend/src/ui/SetupWizard.tsx]
---
# 0031 — Setup: short checks that leave every core feature working

> **Approved by the owner on November 7, 2026** (decision review: "short checks, no processing"). Merges [0014](0014-setup-wizard.md), [0016](0016-agent-setup.md) and
> [0026](0026-setup-leaves-core-features-working.md), which become history. Parts already replaced live in
> [0028](0028-result-identity.md) (Blender in the key), [0029](0029-agent-trust.md) (what agents may do) and
> [0030](0030-counted-exclusions.md) (formats that are off).

**Decision.** When setup finishes, every **core feature** works without the user running anything. To get
there, setup records choices and runs **short checks that prove a feature works**. It never processes the
owner's assets, installs, downloads, or starts work that keeps running after it.

## What setup may run

| Check | What it does | Cost |
| --- | --- | --- |
| Blender check | Runs a file named `blender.exe` / `blender`: version, headless start with scripts disabled, glTF/FBX/OBJ importers | Seconds |
| Runtimes and weights | Reads what is installed; weights by size, or by hash with **Verify** (`verify_weights`), never downloads | Seconds |
| Search check | Loads the search model once on **built-in sample images** (`src/local_asset_library/data/search-check/`), never library assets; writes only `data/embeddings/capability.json` | The longest: one model load |
| Model server Test connection | Lists the models a local server offers; never generates text | Seconds |

**Never during setup:** previews, descriptions or search data for library assets; installs, downloads, starting a
model server; scans of a folder other than the samples. Installs and downloads are shown as commands with Copy
(Design language P3), or run by the user's own agent in its shell with the user's approval.

The search check also runs by itself at the start of Make previews when it is missing (after an install that
finished later), and from **Run check** in Settings. **Run check** is offered only when the runtime and model are
installed: an action must be able to resolve what is shown.

## Core features and how setup provides them

The list lives in [Core features](../Notebook/Platform%20and%20Storage/Core%20features.md) (and
[Optional features](../Notebook/Platform%20and%20Storage/Optional%20features.md)). Rule: **no hidden steps.** A
core feature that needs something setup cannot provide yet gets it automatically later, never as a step the
user must discover. A new core feature comes with its setup path in all three surfaces.

- **Library:** **Include sample assets** (checked by default; agents ask it as `answers.samples`) adds
  `samples/Sample assets` (a blue cube, a green pyramid, a red sphere; low poly GLB, CC0). It is the only folder
  inside Assetarium that may be a library folder.
- **Previews:** Blender, discovered, checked and saved.
- **Search by description and image:** runtime, weights and the search check above.
- **Agents (MCP):** the server is ready in every install. **Connect your agent** shows the configuration with
  Copy, a live connection line and what a connected agent may do on its own ([decision 0029](0029-agent-trust.md)).

## Three surfaces, one set of rules

The app wizard (a full-window overlay), the terminal (`local-assets setup`) and an agent (MCP setup tools) all call
`setup_core`; no rule lives in a surface. The Welcome page offers **Set up with my agent** and **Set it up
yourself** as equal paths; Settings → General offers **Run setup** and **Run setup with my agent**.

- **First run.** The wizard opens by itself only on a fresh install: no `data/library/setup.json`, no
  `settings.json`, no registered library folder (an unreadable registry counts as existing). Existing installs
  are never interrupted. **Skip setup** saves only a `skipped` record.
- **Setup record** (`data/library/setup.json`): state (`not_run`, `skipped`, `review`, `completed`), times,
  version, skipped steps, engine hints, and who last set each value (`user` or `agent`). A damaged record is
  reported and kept, never reset.
- **Saving.** Nothing is saved before the review's **Save**; each part reports its own result, so a failed
  Blender write keeps the other settings.
- **Blender** is saved as `[tools].blender` in `config.local.toml` by a minimal edit (keeps every other line and
  the line endings, re-parsed, replaced atomically; unusual TOML is refused with the line to add by hand), only
  after a passing check in the same process. A Blender that was only discovered is saved too. Changing it asks
  first while the Blender path is part of the inspection key ([decision 0028](0028-result-identity.md)).
- **`descriptions_enabled`** (default on). Off is enforced by the backend: Generate descriptions is refused, the
  caption stage does no work, no *ready to generate* notice. Existing descriptions stay stored and searchable;
  nothing is deleted or re-queued.
- **Recommendations are data:** engine hints (Godot → glTF; Unity, Unreal → FBX; Blender/web → glTF), the batch
  size from measured GPU memory, the storage budget (current use + 20 GiB within 80% of free space).
- **Zero-edit first launch:** an empty project with the shipped example config starts every view without a fault
  (`tests/test_first_launch.py`).

### Setup through an agent

- **Conversation, led by Assetarium.** `get_setup_status` runs the safe checks itself and returns what it found,
  what to ask the user (engines, descriptions, an already running model server, the storage budget, samples) and
  a tone guide. `apply_setup` takes the user's answers and derives the rest (formats, engine, search device,
  batch size). `finish_setup` sets `review`; the user's **Looks good** sets `completed`, and each agent-set
  value can be undone there.
- **The Blender executable is proposed** (`propose_setup`), never saved by an agent; the user's **Apply** checks
  it again and refuses a file that changed ([decision 0029](0029-agent-trust.md) owner-only list).
- **What status reveals:** OS, GPU names and memory, disk space, Blender paths, engine and search readiness with
  the commands for what is missing, settings and who set them, setup state, proposals. Never user names,
  environment variables, directory listings, the project path or asset records. A cloud model receives it, and
  the tool descriptions say so.
- **Connection signal:** the server writes `data/mcp/connections/<pid>.json` and removes it on exit; the app
  counts a connection only while that process is alive. There is no network listener.
- **Degraded mode:** when the configuration does not load, only `get_setup_status` answers, with the fault, the
  file and the fix.

## Formats Assetarium uses

Setup picks the formats from the engine hints (several allowed); Settings changes them later.

- Toggles: the 3D formats Assetarium processes (glTF/GLB, FBX, OBJ) and every standalone image format (PNG,
  JPEG, SVG, WebP, TGA, TIFF, BMP, GIF, AVIF). `.glb` counts as glTF, `.jpg` as JPEG, `.tif` as TIFF. File types
  without a toggle (`.blend`, audio…) stay listed as not processed.
- Image toggles cover standalone images only; textures used by 3D models are always read.
- What happens to assets in a format that is off: [decision 0030](0030-counted-exclusions.md).

## Why

Other people, on other machines and Linux, should get a working Assetarium from a guided, honest setup that
never surprises an existing install. The search section once asked the owner to run a command before search
worked, so setup left a core feature broken; a short check on built-in samples fixes that without touching the
library. Agents with a shell can resolve what the wizard can only describe.

## Keep true

- Setup runs only the checks in the table above; a new check is short, uses built-in data and is added there.
- Setup never processes library assets, installs, downloads or starts lasting work; nothing in it runs at app
  startup except reading the setup state.
- Rules live in `setup_core` and the backend, identical for app, CLI and agent.
- An unchecked Blender path is never written; an agent only proposes one.
- Turning descriptions off never deletes, hides or re-queues results.
