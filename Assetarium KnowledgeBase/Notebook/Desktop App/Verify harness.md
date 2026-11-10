---
area: Desktop App
tags: [system]
code: [scripts/gui_harness.py, scripts/gui_harness.isolate_hash_cache, tests/ui_text.py, scripts/verify-asset-sources.py, scripts/verify-setup-wizard.py]
verified: 2026-10-28
branch: feature/library-view
---
# Verify harness

Hub: [Desktop App](Desktop%20App.md). UI changes are checked in the real WebView2 window by
`scripts/verify-<feature>.py --run-name <unique-name>`, built on `scripts/gui_harness.py`.

## How it works

- Scripts read state and call store actions through `window.lal`, and drive controls the way a user
  does (clicks, keys). Page helpers in `gui_harness.PRELUDE`: `until()`, `frame()`, `pick()`, `type()`.
- Each run writes its report and screenshots to `data/gui/<run-name>/` and uses synthetic assets in an
  isolated project, so real sources are never touched.

## Rules

- **Use a new `--run-name` every time**: scripts refuse to overwrite earlier runs, which are evidence.
- Keep existing verify scripts passing when UI behavior changes; add a script for new UI behavior.
- Synthetic runs isolate the hash cache (`isolate_hash_cache`) so their hashes never enter the shared
  `cache/file-hashes.sqlite`.

## Gotchas

- **Every `store.ts` export is reachable as `window.lal.<name>`** (`frontend/src/main.tsx`), from verify
  scripts and from `desktop.py` (`askClose`). "No importer in `frontend/src`" does not mean unused: search
  `scripts/` and `src/` for the name too.

- **Routes are not in `location.hash`.** Wait on `lal.state.history[lal.state.historyIndex].page` (for example `'sources'`) to see where `navigate` went.

- **A restart can be simulated.** Set a flag (`window.__beforeRestart=true`), call
  `window.load_html(page_html(config)[0])`, then `ui.wait_ready(extra='!window.__beforeRestart')`. A bridge
  poll still in flight then logs a harmless `_returnValuesCallbacks … is not a function` traceback.
  See `scripts/verify-inspector-layout.py`.

- **Timers are throttled in the verify window.** It runs in the background, so `setInterval` /
  `setTimeout` can fire far less often than asked. To count UI changes during fast input, use a
  `MutationObserver` (for example on `aria-pressed`), not a sampling timer. See the browsing check in
  `scripts/verify-interactive-preview.py`.

- **A fixture with no registered sources opens setup**, which covers the window and swallows global keys.
  Close it after `ui.wait_ready()` with `lal.closeSetup()`.

- `verify-setup-wizard.py`'s opening-focus check (`opens_by_itself_on_a_fresh_install` → `focus`)
  failed on unchanged `develop` when launched from an agent session on 2026-10-28; treat a failure there
  as possibly environmental before blaming a change *(unverified: cause)*.

## Related

[Frontend build](Frontend%20build.md) · [Desktop app design → Verification](../../Architecture/Desktop%20App/Desktop%20app%20design.md#verification-and-remaining-scope).
