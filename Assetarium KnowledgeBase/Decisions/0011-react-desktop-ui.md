---
tags: [decision]
decided: 2026-10-21
area: Desktop App
---
# 0011 — React desktop interface, view navigation and themes

**Decision (owner, October 21, 2026).** The desktop app's interface is a React
application built from `frontend/` (Vite, React 19, TypeScript, Tailwind v4,
`motion`, Lucide icons, Geist). It follows the Assetarium Figma handoff and
prefers [beUI](https://beui.dev) components (MIT, copied with notices into
`frontend/src/components/beui/`). The build writes one script and one stylesheet
into `src/local_asset_library/ui/build/`; that bundle is committed, and
`desktop.create_window` inlines it, so launching the app never needs Node.

- **Shell.** Left rail: back/forward history of views, then Home,
  Collections ([decision 0036](0036-collections-and-tags.md)), Asset processing,
  with Library ([decision 0032](0032-library-store-and-queue.md)) and Settings at
  the bottom. A top bar holds the notifications bell and the inspection toggle.
- **Home** is a centred search pill (no suggestion chips). The sliders button
  opens the existing nine filters with Reset and Apply. Search modes, defaults
  and the 5/10/20/30/40 limits are unchanged; an empty search browses.
- **The right sidebar is only asset inspection.** It is continuously resizable
  (width remembered), hides and shows without losing the selection, and is one
  scroll: a fault line when something is faulty, the preview (a model's live 3D
  view loads by itself once the selection rests, over its still), fact chips, the
  description, tags, and collapsible File & license, Geometry (Image for images)
  and Processing record sections. Each section stays open or closed as the owner
  left it. On narrow windows it floats over the results.
- **Asset processing** gathers per-source import work (Process assets, progress,
  Cancel), optional descriptions (Generate descriptions, progress, Cancel, run
  reports), published-library status and the importing failures report.
  Processing notifications lead there, focused on their source.
- **Themes.** Light and dark token sets; Settings → General → Appearance offers
  Match Windows (default), Light and Dark. Appearance, inspector width and the
  inspector's open sections live in app-owned `data/library/interface.json`,
  separate from `settings.json`, and the theme is applied before the first paint.

**Why.** The owner asked for a complete visual and layout revamp using beUI's
React components, with dark mode. Committing the bundle keeps the launcher and
offline guarantees: Node is a development tool only.

**Keep true.** The backend stays the authority for retrieval, availability,
faults, notifications and processing; the frontend presents its answers and
never re-implements those rules. The CSP stays closed: inline code only, and
`data:` images and fonts. Rebuild and commit `ui/build/` with every frontend
change (`npm run build` in `frontend/`). Verification scripts drive the app
through `window.lal` (`frontend/src/main.tsx`) and real controls; keep that
surface working. Notices only offer actions that can change their state.

## Changes

- 2026-10-25: the reserved Library destination was hidden from the rail until a library browser was built (beta cleanup).
- 2026-11-01: Library became the library browser (formerly Asset sources, decision 0032) and returned to the rail above Settings.
- 2026-11-07: Collections became a working page (decision 0036); it was a reserved page without actions.
- 2026-11-08: inspector tabs (Overview / Sources / Evidence) replaced by one scroll with remembered sections (owner co-design, 2026-11-07).
- 2026-11-08: the 3D preview became a live viewer that loads on a resting selection, with its controls on the canvas (owner co-design, 2026-11-07).
