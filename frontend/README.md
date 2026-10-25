# Assetarium desktop interface (`frontend/`)

The desktop app's UI: React 19, TypeScript, Vite, Tailwind v4, `motion`, Lucide
icons and the Geist font ([decision 0011](../docs/decisions/0011-react-desktop-ui.md)).
`npm run build` type-checks and writes one script and one stylesheet to
`src/local_asset_library/ui/build/`. That bundle is committed: the app
(`desktop.create_window`) inlines it into `ui/index.html` together with
`ui/interactive-preview.js`, so launching never needs Node.

## Building

Node 24 is a development tool only. Keep its cache inside the project:

```powershell
cd frontend
npm ci --cache ..\cache\npm --no-audit --no-fund
npm run build
```

`node_modules/` is ignored. After installing, `npm cache clean --force --cache ..\cache\npm`
removes the download cache (about 250 MiB) when offline reinstalls are not needed.
Commit `src/local_asset_library/ui/build/` with every source change; the encoding test
(`tests/test_ui_encoding.py`) covers both the sources here and the bundle.

## Layout of the source

- `src/app/store.ts`: application state and actions (search, browse, thumbnails,
  inspection, sources, notifications, history, appearance), ported from the
  former `ui/app.js`. The backend stays the authority; this only presents it.
- `src/app/api.ts`, `src/app/format.ts`: bridge types and presentation helpers.
- `src/ui/`: shell (rail, top bar), search and filters, asset grid, inspection
  sidebar, image viewer, notifications, toasts and run reports.
- `src/pages/`: Home, Collections and a collection, Asset processing, Settings,
  source browser, the Library placeholder. `src/ui/Menus.tsx` holds the shared
  right-click menu (beUI context menu) with its collection flyout, the red
  deletion confirmation, the new-collection dialog and the batch-selection bar.
- `src/components/beui/`, `src/lib/`: [beUI](https://beui.dev) components and
  helpers (MIT, `licenses/beui-MIT.txt`), adapted where marked "Assetarium".
- `src/styles.css`: light and dark tokens, Geist (`licenses/geist-OFL-1.1.txt`,
  latin subsets inlined as `data:` fonts) and the 3D preview's styles.

## Automation surface

`window.lal` exposes the store's actions and a live `state` getter. The real
WebView2 checks in `scripts/verify-*.py` use it through `scripts/gui_harness.py`
together with ordinary clicks and keys; keep it working when actions change.
