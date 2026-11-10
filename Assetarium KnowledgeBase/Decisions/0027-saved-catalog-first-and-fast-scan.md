---
tags: [decision]
decided: 2026-11-06
area: Sources and Catalog
---
# 0027 — Saved catalog first, fast change check, no launcher window

**Decision.**
- At launch the saved catalog is the truth. The library is usable at once; no scan
  stands between the owner and the view, and no blocking scan spinner is shown.
- The startup scan of [decision 0002](0002-startup-scan-and-change-detection.md) stays,
  but becomes a quick change check: one walk that only stats files (size, mtime) against
  `scan-cache.json`. Unchanged files are neither hashed nor parsed.
- Only new or changed files are hashed and parsed. What a parser reads from a file's bytes is
  saved by the file's SHA-256 and the parser's own code; matching those references to the files
  that exist still runs on every scan, so an added, renamed or removed texture is always seen.
- The second "Verifying files" walk stays: measured at 3–4% of a scan, it guards against files
  changing during the scan.
- Results arrive silently: only cards that actually changed update; a quiet status note
  ("3 new assets") replaces the spinner. A check that finds nothing changed redraws nothing.
- Every background scan logs one summary line when it finishes: files checked, files
  changed (new, changed, removed), models re-parsed and seconds per phase and in total.
  This is local analytics for tuning startup, not a progress feed.
- No launcher window. It is parked; revisit only if, after this, a core service still
  blocks the first usable view.

**Why.** The 2026-11-04 launch scanned for 272 s (plus 222 s for one folder) on part of
the library, re-parsing every model and walking every file twice to cover the rare launch
where something changed. The full target library is ~124,000 files and ~28,900
models, so the old design would cost tens of minutes per launch. The window already opens
fast; a launcher would hide the wait, not remove it. Startup calls (`context`, `sources`,
`tree`: ~22 s) are a separate cost handled on their own.

**Keep true.** Never re-hash a file whose stat identity is unchanged, and never re-parse
bytes whose SHA-256 the current parsers have already read; never save a read failure. Never block the view on a scan. An unchanged scan writes
nothing and redraws nothing (decision 0002). Measure before optimizing beyond this.

## Changes

- 2026-11-06: parsed results are saved per file and parser instead of reusing a model's whole dependency result (safer, measured).
- 2026-11-06: the second verifying walk stays (3–4% of a scan) instead of being replaced by a re-stat.
