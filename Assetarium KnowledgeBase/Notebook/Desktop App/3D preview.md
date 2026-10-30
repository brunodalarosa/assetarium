---
area: Desktop App
tags: [system]
code: [interactive_preview.py, src/local_asset_library/ui/viewer.html, src/local_asset_library/ui/viewer.js, src/local_asset_library/ui/interactive-preview.js, src/local_asset_library/ui/vendor, scripts/verify-interactive-preview.py, tests/test_interactive_preview.py]
verified:
branch:
---
# 3D preview

Hub: [Desktop App](Desktop%20App.md). The interactive preview is the vendored Online 3D Viewer in a
sandboxed iframe; start reading at `interactive_preview.py` (delivery, tickets, fault history) and
`ui/viewer.html` / `viewer.js`. User guide: [docs/gui/3d-preview.md](../../../docs/gui/3d-preview.md).
Moved from that guide on 2026-10-28; not yet re-verified line by line.

## How it works

Online 3D Viewer **0.18.0** and the official Draco **1.5.7** JS/WASM decoder are
bundled locally, together with a lighting cube and upstream license notices.
The existing WebView2 and Python environments are reused. Runtime needs no npm,
CDN, HTTP server, inference, model downloads or duplicate converted asset cache.
See [vendored dependencies and attribution](../../../src/local_asset_library/ui/vendor/README.md).

The desktop bridge accepts asset IDs, source formats and opaque file tickets;
it never accepts a caller-supplied path. Membership, publication generation,
resolved source boundaries and the caller's browsing scope are checked before
delivery. Each file's actual bytes are verified against its catalog hash.
Library inspection respects enabled-source visibility. The explicit source
contents view can inspect a registered disabled source's saved published assets
without enabling it; it uses that source's membership and generation. Removed
sources cannot issue or read tickets. Both views share retained viewer failures.
Delivery is bounded to 64 files, 64 MiB per file, 128 MiB total and 128 filename
aliases. Conflicting basenames with different contents are an explicit fault
because the upstream importer resolves dependency filenames by basename.

The scripts-only iframe has an opaque origin, no desktop bridge or parent DOM
access, and no network resources. LAL validates the source window and session
nonce on messages. The frame is created only on demand; removing it releases
its WebGL context, object URLs, decoder, upstream document listeners and pending
imports. The 90-second loading deadline records a timeout without a retry. Local
file tickets expire after ten minutes for delivery and are released on exit.
Already-loaded previews do not need their source files to be reread.

## Verification

Use the existing runtime wrapper, with a new evidence name for every native run:

```powershell
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python -m pytest tests/test_interactive_preview.py tests/test_desktop.py tests/test_mcp_assets.py tests/test_sources.py
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/verify-interactive-preview.py --run-name unique-preview-run
```

The native harness uses tiny synthetic models and actual WebView2. It checks
visible textured rendering, real mouse rotation/wheel zoom/keyboard orbit,
fullscreen focus containment and return, resize without reimport, reduced-motion
loading, display controls, selected-format changes, cancellation/stale completion,
graphics/frame disposal and retained failures. Captures and reports are under
`data/gui/<run-name>/`. It runs no inference and changes no real sources.

The optional `--real-assets` mode reads six representative enabled/published
sources once, disables automatic source scans in the harness, and records each
result without retrying an asset fault. The initial run `preview-real-01` passed
GLB (`building-d`), OBJ (`apple`), two FBX sources with existing texture bindings,
DAE and STL. Twenty-three original model/dependency files remained hash-identical.
These are representative format checks, not full-library compatibility approval.

## Rules

- **`src/local_asset_library/ui/vendor/**` is upstream, byte-for-byte (`-text`); never reformat it.**
- **The bridge never accepts a path from the window**: only asset IDs, source formats and opaque tickets.
- Fault history in `data/gui/interactive-preview-faults.jsonl` is never cleared automatically, and an
  unchanged faulty input returns the saved failure instead of re-importing.

## Gotchas

- The upstream importer resolves dependencies by basename, so two dependencies with the same basename
  and different bytes are an explicit fault, not a guess.
- Preview geometry counts come from the viewer import and are not the inspection's measured facts.

## Related

[Desktop app design](../../Architecture/Desktop%20App/Desktop%20app%20design.md) · [Desktop App](Desktop%20App.md).
Storage history: adding the viewer (October 15, 2026) cost about 1.8 MiB of vendored payload; the rest
of that change's 114 MiB was verification fixtures and reports under ignored `data/`.
