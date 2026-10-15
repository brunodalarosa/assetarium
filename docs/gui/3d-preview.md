# Interactive 3D preview within LAL

The inspection card's image opens an interactive preview using the selected
source format. **Open fullscreen** opens it across the LAL app window, rather
than launching another application or entering operating-system fullscreen.
The original image, view choices and inspection evidence remain available.

## Interaction

- Drag to rotate; right-drag or Shift-drag to pan; scroll or pinch to zoom.
- Use Fit, Reset view and zoom buttons without relying on gestures.
- Choose isometric, front, back, left, right, top or bottom view presets.
- Display options provides perspective/orthographic projection, studio/white/dark
  backgrounds, edge display, X/Y/Z up-axis and upright/free-orbit navigation.
- When the canvas has focus, arrows rotate, Shift + arrows pan, +/− zoom,
  F fits and R resets the view. Tab moves between controls.
- Fullscreen retains the same frame, camera and loaded model. Escape exits
  fullscreen first; Back to image releases the frame and its file ticket.

Loading indicators cover file verification/delivery, import, material/geometry
preparation, display changes and fullscreen transitions. Closing an inspection,
switching asset/source/view, or visiting Settings/report pages releases the
frame. Late results cannot replace the newer selection. Loading can be left
without waiting for completion. No automatic rotation or animation starts.

## Formats and evidence

The exposed formats are GLB, glTF, FBX, OBJ with MTL/textures, DAE and STL.
Blender files require selecting an existing supported alternative. LAL does not
convert source files, silently select another export, or repair missing content.
The selected source's name and format stay explicit. Preview geometry counts
describe this viewer import and remain distinct from the inspection's measured
facts, physical scale and owner approval.

The backend follows the selected export's recorded dependency graph and passes
verified files to the viewer as memory-backed File objects. Existing approved
texture bindings contribute their original reference aliases; no source bytes
are rewritten and no new bindings are guessed. Binary/alternate dependencies
may be incomplete in the catalog. The viewer reports missing references and
retains any usable geometry as a partial preview.

Failures are retained separately in
`data/gui/interactive-preview-faults.jsonl`, bound to the asset, selected format,
source/dependency hashes and texture-binding evidence. Reopening unchanged faulty
inputs returns the saved failure rather than retrying import. Other source
formats, existing images and inspection evidence remain available. Unreadable
fault history disables 3D delivery while leaving normal browsing available.
Fault history is never automatically cleared. Application/test-harness defects
can be corrected under the normal repository policy.

## Runtime and resource boundaries

Online 3D Viewer **0.18.0** and the official Draco **1.5.7** JS/WASM decoder are
bundled locally, together with a lighting cube and upstream license notices.
The existing WebView2 and Python environments are reused. Runtime needs no npm,
CDN, HTTP server, inference, model downloads or duplicate converted asset cache.
See [vendored dependencies and attribution](../../src/local_asset_library/ui/vendor/README.md).

The desktop bridge accepts asset IDs, source formats and opaque file tickets;
it never accepts a caller-supplied path. Membership, enabled-source visibility,
publication generation and resolved source boundaries are checked before
delivery. Each file's actual bytes are verified against its catalog hash.
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

Synthetic native delivery evidence: `preview-native-final-delivery/verification.json`.
Search regression evidence: `preview-search-regression-fixed/report.json`.
The search harness now resolves the replayed search started by a publication
refresh, fixing an existing harness deadlock without changing search behavior.
Native source-navigation regression evidence: `source-settings-986e0ebf4b/report.json`.
Owner usability/material acceptance and a full screen-reader audit remain pending.

Storage receipts `data/storage/3d-preview-before-20261015.json` and
`3d-preview-after-20261015.json` both passed. Unique allocated project storage
increased by 120,007,440 bytes (114.45 MiB), including 108.49 MiB of isolated
verification fixtures, about 3.97 MiB of reports/captures and 1.91 MiB of source
files. The actual upstream viewer/lighting/decoder/license payload is 1,873,510
bytes (1.79 MiB). The project was already above the historical 6 GiB pilot target
before this change (8.42 GiB); no existing results or evidence were deleted.
The redundant 3,551,087-byte downloaded archive was removed after verifying the
vendored payload hashes. Cleanup, savings and accounting are recorded separately
in `data/storage/3d-preview-comparison-20261015.json`. No runtime was installed.
