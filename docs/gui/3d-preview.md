# Interactive 3D preview

The inspection card's image opens an interactive preview using the selected
source format. **Open fullscreen** opens it across the app window, rather
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

How the preview is isolated and verified is in the knowledge base:
[3D preview](../../KnowledgeBase/Notebook/Desktop%20App/3D%20preview.md).
