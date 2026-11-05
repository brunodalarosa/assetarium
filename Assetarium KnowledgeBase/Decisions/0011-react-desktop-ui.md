---
tags: [decision]
decided: 2026-10-21
---
# 0011 — React desktop interface, view navigation and themes

**Decision (owner, October 21, 2026).** The desktop app's interface is a React
application built from `frontend/` (Vite, React 19, TypeScript, Tailwind v4,
`motion`, Lucide icons, Geist). It follows the Assetarium Figma handoff and
prefers [beUI](https://beui.dev) components (MIT, copied with notices into
`frontend/src/components/beui/`). The build writes one script and one stylesheet
into `src/local_asset_library/ui/build/`; that bundle is committed, and
`desktop.create_window` inlines it, so launching the app never needs Node.

- **Shell.** Left rail: back/forward history of views, then Home, Library,
  Collections, Asset processing, with Settings at the bottom. Library and
  Collections are reserved pages without actions. A top bar holds the
  notifications bell and the inspection toggle.
- **Home** is a centred search pill (no suggestion chips). The sliders button
  opens the existing nine filters with Reset and Apply. Search modes, defaults
  and the 5/10/20/30/40 limits are unchanged; an empty search browses.
- **The right sidebar is only asset inspection.** It is continuously resizable
  (width remembered), hides and shows without losing the selection or tab, and
  has Overview / Sources / Evidence tabs that keep measured facts, generated
  observations, caption notes, faults and owner review separate. On narrow
  windows it floats over the results.
- **Asset processing** gathers per-source import work (Process assets, progress,
  Cancel), optional descriptions (Generate descriptions, progress, Cancel, run
  reports), published-library status and the importing failures report.
  Processing notifications lead there, focused on their source.
- **Themes.** Light and dark token sets; Settings → General → Appearance offers
  Match Windows (default), Light and Dark. Appearance and inspector width live in
  app-owned `data/library/interface.json`, separate from `settings.json`, and
  the theme is applied before the first paint.

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

> **Later changes.** Collections became a working page under [decision 0012](0012-collections-and-tags.md),
> superseding "Library and Collections are reserved pages" for Collections. On October 25, 2026 the owner
> hid the reserved **Library** destination from the rail until a library browser is built (beta cleanup);
> the placeholder page stays in the source for that future work.
