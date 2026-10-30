---
area: Desktop App
tags: [system]
code: [scripts/gui_harness.py, scripts/gui_harness.isolate_hash_cache, tests/ui_text.py, scripts/verify-source-browser.py, scripts/verify-setup-wizard.py, scripts/verify-loading-states.py]
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

- `verify-setup-wizard.py`'s opening-focus check (`opens_by_itself_on_a_fresh_install` → `focus`)
  failed on unchanged `develop` when launched from an agent session on 2026-10-28; treat a failure there
  as possibly environmental before blaming a change *(unverified: cause)*.

## Related

[Frontend build](Frontend%20build.md) · [Desktop app design → Verification](../../Architecture/Desktop%20App/Desktop%20app%20design.md#verification-and-remaining-scope).
