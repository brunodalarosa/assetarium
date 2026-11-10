---
tags: [decision]
decided: 2026-11-06
area: Sources and Catalog
replaces: [0002]
code: [catalog.py, parse_cache.py, sources.write_changed, desktop.DesktopBridge.changes]
---
# 0027 — Startup scan: saved catalog first, fast change check, change tokens

**Decision.**

*At launch*
- The saved catalog is the truth. The library is usable at once; no scan stands between the owner and
  the view, and no blocking scan spinner is shown.
- Enabled library folders are scanned in the background at every launch. This is how new, changed or
  removed files are discovered; scans never run models or rendering.
- No launcher window. It is parked; revisit only if, after this, a core service still blocks the first
  usable view.

*The scan*
- It is a quick change check: one walk that only stats files (size, mtime) against `scan-cache.json`.
  Unchanged files are neither hashed nor parsed.
- Only new or changed files are hashed and parsed. What a parser reads from a file's bytes is saved by the
  file's SHA-256 and the parser's own code; matching those references to the files that exist still runs
  on every scan, so an added, renamed or removed texture is always seen.
- The second "Verifying files" walk stays: measured at 3–4% of a scan, it guards against files changing
  during the scan.
- A scan rewrites `source-status.json`, `import-status.json`, `asset-sources.json` and `scan-cache.json`
  only when their content changes (`scanned_utc` alone is not a change). An unchanged scan therefore
  leaves the source revision, and the open view, untouched.
- Every background scan logs one summary line when it finishes: files checked, files changed (new,
  changed, removed), models re-parsed and seconds per phase and in total. This is local analytics for
  tuning startup, not a progress feed.

*How the view learns of changes*
- The UI polls one cheap bridge call, `changes()`, every 1.5 s. It returns stat-only tokens for the
  library (publication, processing status, source revision) and for everything else the views show
  (library folders, status, operation, cancel and fault files, settings). Data is fetched only when a
  token changes, or while an operation is running (worker liveness is not a file change).
- Results arrive silently: only cards that actually changed update; a quiet status note ("3 new assets")
  replaces the spinner. A check that finds nothing changed redraws nothing.
- There are no manual **Scan** or **Status** buttons. **Refresh published view** and the recorded
  failures live on **Asset processing** ([decision 0011](0011-react-desktop-ui.md)).

**Why.** Startup used to load the library summary three or more times, every unchanged startup scan
invalidated and reloaded the whole view, and fixed 1.5 s and 20 s polls ran expensive summaries regardless
of change. Later, the 2026-11-04 launch scanned for 272 s (plus 222 s for one folder) on part of the
library, re-parsing every model and walking every file twice to cover the rare launch where something
changed. The full target library is ~124,000 files and ~28,900 models, so that design would cost tens of
minutes per launch. The window already opens fast; a launcher would hide the wait, not remove it. Startup
calls (`context`, `sources`, `tree`: ~22 s) are a separate cost handled on their own.

**Keep true.**
- Never block the view on a scan.
- Never re-hash a file whose stat identity is unchanged, and never re-parse bytes whose SHA-256 the
  current parsers have already read; never save a read failure.
- An unchanged scan writes nothing and redraws nothing. Writes that only refresh a timestamp must not
  bump views.
- Do not add periodic heavy polls; extend `changes()` with the file that changes instead.
- Scans and processing must not invalidate visible cards; library changes arrive through `refreshContext`.
- Measure before optimizing beyond this.

## Changes

- 2026-11-06: parsed results are saved per file and parser instead of reusing a model's whole dependency result (safer, measured).
- 2026-11-06: the second verifying walk stays (3–4% of a scan) instead of being replaced by a re-stat.
- 2026-11-10: decision 0002 (startup scan, change tokens, no manual Scan/Status buttons; October 17, 2026) is merged in, since both covered the startup scan. No rule changed. The "Importing failures report" it named is today's recorded failures list on Asset processing.
