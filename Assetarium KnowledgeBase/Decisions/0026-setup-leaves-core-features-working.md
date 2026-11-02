---
tags: [decision]
decided: 2026-11-01
---
# 0026 — Setup leaves every core feature working; built-in samples; formats Assetarium uses

**Decision (owner, November 1, 2026; co-designed, approved for implementation).** After setup finishes (the app
wizard, the CLI wizard or the agent-assisted setup), every **core feature** works without an extra step from the
user. The core and optional features are listed in [Core features](../Notebook/Platform%20and%20Storage/Core%20features.md)
and [Optional features](../Notebook/Platform%20and%20Storage/Optional%20features.md).

- **No hidden steps.** A core feature that needs something setup cannot provide yet gets it **automatically
  later**, never as a command handed to the user. Example: the search check runs in setup after Save, from
  **Run check** in Settings, and by itself in the search stage of Make previews when it is missing.
- **The search check runs on built-in sample images** (`src/local_asset_library/data/search-check/`, rendered by
  `scripts/build-samples.py`), never on library assets, so it needs no library. It writes only
  `data/embeddings/capability.json`. **Run check** is offered only when the search runtime and model are installed
  (an action must be able to resolve the shown state).
- **Agents (MCP) are core**: the MCP server must be ready. Connecting an agent is the user's choice; setup has a
  **Connect your agent** step (configuration with Copy, a live connection line), and the agent-assisted setup is
  already connected.
- **Built-in sample assets**: a blue cube, a green pyramid and a red sphere (low poly GLB, a few KB, CC0) in
  `samples/Sample assets`. Setup offers **Include sample assets**, checked by default; the agent-assisted setup asks
  the same question (`answers.samples`). It is the **only** folder inside Assetarium that may be a library folder.

## Formats Assetarium uses

One setting with one meaning: **a format that is off does not exist for Assetarium.**

- Toggles: the 3D formats Assetarium processes (glTF/GLB, FBX, OBJ) and every standalone image format (PNG, JPEG,
  SVG, WebP, TGA, TIFF, BMP, GIF, AVIF). `.glb` counts as glTF, `.jpg` as JPEG, `.tif` as TIFF. File types without a
  toggle (`.blend`, audio…) stay listed as not processed.
- An asset whose files are all in formats that are off is **hidden**: from the Library, its counts, search, browse,
  agent results and processing. A collection keeps it, marked "Format off".
- **Image toggles cover standalone images only.** Textures used by 3D models are always read.
- Changing formats is instant (folder views rebuild), never deletes results, scans again or retries faults; turning a
  format back on brings its assets back with their results. Every format off is the paused state.

## Why

The search section asked the owner to run a command before search worked, so setup left a core feature broken.
Make previews offered work the queue then refused, because the Library counted FBX copies that the format setting
excluded from processing. One meaning for formats removes both the mismatch and the dead end.

## What future work must keep true

- A new core feature comes with the setup step (or automatic later step) that makes it work.
- Nothing the user must run is shown as inline text (design principle P3, [decision 0025](0025-design-principles.md)).
- Folder views, search, agent results and the queue apply the same format rule (`settings.uses`).
