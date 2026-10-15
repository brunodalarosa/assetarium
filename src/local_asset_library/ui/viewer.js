'use strict';
// The frame has an opaque origin, no desktop bridge, no network, and one model.
// Removing it also removes upstream document listeners and pending imports.
let session = null, viewer = null, loader = null, model = null, ready = false;
let modelFiles = [], sourceName = '', initialCamera = null;
const canvas = document.getElementById('model');
function send(type, data = {}) {
  parent.postMessage({kind: 'lal-3d', session, type, ...data}, '*');
}
function progress(message) { send('progress', {message}); }
function reportError(error) {
  send('fault', {reason: String(error?.message || error || 'Interactive preview failed.').slice(0, 1200)});
}
function resize() {
  if (viewer && innerWidth > 0 && innerHeight > 0) viewer.Resize(innerWidth, innerHeight);
}
function sphere() { return viewer.GetBoundingSphere(() => true); }
function fit() { viewer.FitSphereToWindow(sphere(), false); }
function direction(name) {
  const directions = {front:[0,0,1], back:[0,0,-1], right:[1,0,0], left:[-1,0,0],
                      top:[0,1,0], bottom:[0,-1,0], isometric:[1,0.75,1]};
  const d = directions[name];
  if (!d) throw Error('Unknown camera view');
  const current = viewer.GetCamera();
  const center = current.center.Clone();
  const distance = OV.CoordDistance3D(current.eye, current.center);
  const eye = OV.AddCoord3D(center, new OV.Coord3D(...d).Normalize().MultiplyScalar(distance));
  const up = name === 'top' ? new OV.Coord3D(0,0,-1) :
             name === 'bottom' ? new OV.Coord3D(0,0,1) : new OV.Coord3D(0,1,0);
  viewer.SetCamera(new OV.Camera(eye, center, up, current.fov));
  fit();
}
async function load() {
  try {
    progress('Preparing 3D preview…');
    viewer = new OV.Viewer();
    viewer.Init(canvas);
    viewer.SetBackgroundColor(new OV.RGBAColor(233,235,229,255));
    viewer.SetEnvironmentMapSettings(new OV.EnvironmentSettings(environmentMap, false));
    resize();
    loader = new OV.ThreeModelLoader();
    if (/\.(glb|gltf)$/i.test(sourceName)) {
      // The pinned upstream glTF importer accepts a prepared decoder. Supplying
      // its official local WASM here prevents its default CDN download path.
      progress('Preparing model reader…');
      const binary = Uint8Array.from(atob(dracoWasm), c => c.charCodeAt(0));
      const draco = await DracoDecoderModule({wasmBinary: binary});
      for (const importer of loader.GetImporter().importers) {
        if (importer.gltfExtensions) importer.gltfExtensions.draco = draco;
      }
    }
    await new Promise(resolve => setTimeout(resolve, 0));
    loader.LoadModel(OV.InputFilesFromFileObjects(modelFiles), new OV.ImportSettings(), {
      onLoadStart: () => progress('Reading model files…'),
      onFileListProgress: (current, total) => progress(`Reading model files ${current + 1} / ${total}…`),
      onFileLoadProgress: () => {},
      onImportStart: () => progress('Importing model…'),
      onSelectMainFile: (names, select) => {
        const index = names.findIndex(n => n.toLowerCase() === sourceName.toLowerCase());
        if (index < 0) throw Error('The selected source is missing from the preview package.');
        select(index);
      },
      onVisualizationStart: () => progress('Preparing materials and geometry…'),
      onTextureLoaded: () => { if (viewer) viewer.Render(); },
      onModelFinished: (result, object) => {
        try {
          model = result.model;
          viewer.SetMainObject(object);
          const bounds = sphere();
          if (!bounds || !Number.isFinite(bounds.radius) || bounds.radius <= 0) {
            throw Error('This source has no visible geometry to preview.');
          }
          viewer.AdjustClippingPlanesToSphere(bounds);
          viewer.SetUpVector(OV.Direction.Y, false);
          fit();
          initialCamera = viewer.GetCamera().Clone();
          ready = true;
          modelFiles = [];
          const summary = {meshes: model.MeshCount(), materials: model.MaterialCount(),
                           triangles: model.TriangleCount()};
          send('loaded', {summary, missing: [...new Set(result.missingFiles || [])]});
        } catch (error) { reportError(error); }
      },
      onLoadError: error => reportError(error.message || `Online 3D Viewer could not read this source (error ${error.code}).`)
    });
  } catch (error) { reportError(error); }
}
function command(action, value) {
  if (action === 'resize') { resize(); return; }
  if (action === 'focus') { canvas.focus(); return; }
  if (!ready) return;
  switch (action) {
    case 'fit': fit(); break;
    case 'reset': viewer.SetUpVector(OV.Direction.Y, false); viewer.SetCamera(initialCamera.Clone()); fit(); break;
    case 'zoom': viewer.navigation.Zoom(value); viewer.Render(); break;
    case 'view': direction(value); break;
    case 'projection': viewer.SetProjectionMode(value === 'orthographic' ? OV.ProjectionMode.Orthographic : OV.ProjectionMode.Perspective); fit(); break;
    case 'edges': viewer.SetEdgeSettings(new OV.EdgeSettings(value, new OV.RGBColor(60,71,66), 25)); break;
    case 'navigation': viewer.SetNavigationMode(value === 'free' ? OV.NavigationMode.FreeOrbit : OV.NavigationMode.FixedUpVector); break;
    case 'up': viewer.SetUpVector(OV.Direction[value], false); fit(); break;
    case 'background': {
      const color = value === 'dark' ? [51,57,55] : value === 'white' ? [255,255,255] : [233,235,229];
      viewer.SetBackgroundColor(new OV.RGBAColor(...color,255)); break;
    }
    default: throw Error('Unknown viewer action');
  }
}
window.addEventListener('message', async event => {
  if (event.source !== parent || event.data?.kind !== 'lal-3d') return;
  const message = event.data;
  if (message.type === 'init' && session === null) {
    session = message.session;
    sourceName = message.sourceName;
    let parentAccess = false;
    try { parentAccess = Boolean(parent.document); } catch (_) { /* Opaque origin is expected. */ }
    send('ready',{desktopBridge:Boolean(window.pywebview?.api),parentAccess});
    return;
  }
  if (message.session !== session || session === null) return;
  try {
    if (message.type === 'file') {
      for (const name of message.aliases) modelFiles.push(new File([message.buffer], name));
    } else if (message.type === 'load') {
      await load();
    } else if (message.type === 'command') {
      command(message.action, message.value);
      send('command-done', {request: message.request});
    }
  } catch (error) { reportError(error); }
});
// Upstream mouse navigation prevents mousedown's default action. Focus on the
// earlier pointer event so keyboard controls work immediately after dragging.
canvas.addEventListener('pointerdown', () => canvas.focus());
canvas.addEventListener('keydown', event => {
  if (event.ctrlKey && event.key.toLowerCase() === 'f') {
    send('search'); event.preventDefault(); return;
  }
  if (event.key === 'Escape') { send('escape'); event.preventDefault(); return; }
  if (!ready) return;
  let handled = true;
  const arrows = {ArrowLeft:[-12,0], ArrowRight:[12,0], ArrowUp:[0,-12], ArrowDown:[0,12]};
  if (arrows[event.key]) {
    const [x,y] = arrows[event.key];
    if (event.shiftKey) {
      const distance = OV.CoordDistance3D(viewer.GetCamera().eye, viewer.GetCamera().center);
      viewer.navigation.Pan(x * distance / 250, y * distance / 250);
    } else viewer.navigation.Orbit(x,y);
    viewer.Render();
  } else if (event.key === '+' || event.key === '=') command('zoom',0.15);
  else if (event.key === '-') command('zoom',-0.15);
  else if (event.key.toLowerCase() === 'f') command('fit');
  else if (event.key.toLowerCase() === 'r') command('reset');
  else handled = false;
  if (handled) event.preventDefault();
});
canvas.addEventListener('dblclick', () => { if (ready) fit(); });
canvas.addEventListener('webglcontextlost', event => {
  event.preventDefault(); reportError('The graphics context was lost. The existing image is still available.');
});
window.addEventListener('resize', resize);
window.addEventListener('error', event => reportError(event.error || event.message));
window.addEventListener('unhandledrejection', event => reportError(event.reason));
// Startup uses a source-window check, then a per-frame nonce for every message.
parent.postMessage({kind:'lal-3d',type:'boot'}, '*');
