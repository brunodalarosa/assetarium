---
area: Desktop App
tags: [system]
code: [frontend/package.json, frontend/src/app/store.ts, frontend/src/main.tsx, frontend/src/components/beui, src/local_asset_library/ui/build, tests/test_ui_encoding.py]
verified: 2026-10-28
branch: feature/library-view
---
# Frontend build

Hub: [Desktop App](Desktop%20App.md). The UI is React 19 + TypeScript + Vite + Tailwind v4 in
`frontend/`; `npm run build` type-checks and writes one script and one stylesheet to
`src/local_asset_library/ui/build/`. Layout and build commands: [frontend/README.md](../../../frontend/README.md).

## Rules

- **Commit the regenerated `ui/build/` with every frontend source change**; the app runs from it and
  never needs Node. **Never edit `ui/build/` by hand.**
- Node 24 is a development tool only; keep npm's cache in `cache/npm` and clean it afterwards.
- **App-owned UI text must be valid UTF-8 with real characters (`…`, `·`, `→`), no mojibake.**
  `tests/test_ui_encoding.py` checks `frontend/src`, the bundle and the packaged HTML. Read and write
  UI files explicitly as UTF-8: Windows' default encoding corrupts punctuation and icons.
- State and actions live in `src/app/store.ts`; the backend stays the authority, the store only presents it.
- `window.lal` is the automation surface the [Verify harness](Verify%20harness.md) uses: keep it working
  when actions change.

## Gotchas

- Comments in `frontend/src` don't reach the bundle, so comment-only edits need no rebuild.
- beUI components are vendored source (MIT) adapted where marked "Assetarium", not an npm dependency.

## Related

[Desktop bridge](Desktop%20bridge.md) · [Desktop app design → Loading states](../../Architecture/Desktop%20App/Desktop%20app%20design.md#loading-states).
