# Live 3D preview

Selecting a model shows its still render at once. When the selection rests for
about 250 ms, the live view of the selected source format loads behind the
still and crossfades in; no click is needed. Browsing quickly (arrow keys or
clicks) never loads a viewer for an asset it passes. **Fullscreen** opens the
same view across the app window, rather than launching another application or
entering operating-system fullscreen.

Library, Search and Collections use the same resolved asset, selected source format and inspection revision.
If the library changes during loading, **Refresh inspection** loads current details. A changed view is not
an asset failure; genuine file/import failures remain recorded with their evidence.

## Interaction

- Drag to rotate; right-drag or Shift-drag to pan; scroll or pinch to zoom;
  double-click fits the model.
- **3/4 · Front · Side · Top** on the canvas move the camera to the same angles
  as the still renders. Before the live view is up they switch the stills
  (there is no top still, so Top waits for the live view).
- The corner icons: **?** shows the controls (also shown once, the first time a
  live view appears), **Fullscreen**, and **⋯** with Fit, Reset view,
  perspective/orthographic projection, studio/white/dark background,
  upright/free-orbit navigation, X/Y/Z up axis and edges. The background starts
  dark in the dark theme.
- When the canvas has focus, arrows rotate, Shift + arrows pan, +/− zoom,
  F fits and R resets the view. Tab moves between controls.
- Fullscreen keeps the same frame, camera and loaded model. Escape closes the ⋯
  menu, then leaves fullscreen.

A small **Loading 3D…** chip shows while files are verified and imported; the
still stays visible underneath. Switching asset or source, closing the
inspection or visiting another page releases the frame; a released view says
**Live 3D paused · Load**. Late results cannot replace the newer selection. No
automatic rotation or animation starts.

## When there is no live view

The canvas always says why, over the still:

- **Live 3D isn’t available for .blend · showing renders**: the viewer can't open
  that format; choose another source format if the asset has one.
- **Large model · 17.0 MiB · Click to load**: packages over 16 MiB wait for a
  click, so browsing never reads them. The viewer refuses packages over
  128 MiB even on a click.
- **Live 3D unavailable: <reason>**: a load fault, recorded once with its
  evidence and never retried automatically.

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

How the preview is isolated and verified is in the knowledge base:
[3D preview](../../Assetarium%20KnowledgeBase/Notebook/Desktop%20App/3D%20preview.md).
