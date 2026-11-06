---
tags: [decision]
decided: 2026-11-06
---
# 0027 — Saved catalog first, fast change check, no launcher window

**Decision.**
- At launch the saved catalog is the truth. The library is usable at once; no scan
  stands between the owner and the view, and no blocking scan spinner is shown.
- The startup scan of [decision 0002](0002-startup-scan-and-change-detection.md) stays,
  but becomes a quick change check: one walk that only stats files (size, mtime) against
  `scan-cache.json`. Unchanged files are neither hashed nor parsed.
- Only new or changed files are hashed and parsed, plus the models that reference them.
  An unchanged model keeps its saved dependency result. A reused result is valid only when
  the model file **and every file it references** are unchanged; a changed texture sends
  its model back to parsing.
- The second full "Verifying files" walk is replaced by a re-stat of the changed files only.
- Results arrive silently: only cards that actually changed update; a quiet status note
  ("3 new assets") replaces the spinner. A check that finds nothing changed redraws nothing.
- Every background scan logs one summary line when it finishes: files checked, files
  changed (new, changed, removed), models re-parsed and seconds per phase and in total.
  This is local analytics for tuning startup, not a progress feed.
- No launcher window. It is parked; revisit only if, after this, a core service still
  blocks the first usable view.

**Why.** The 2026-11-04 launch scanned for 272 s (plus 222 s for one folder) on part of
the library, re-parsing every model and walking every file twice to cover the rare launch
where something changed. The full `D:\Game Assets` target is ~124,000 files and ~28,900
models, so the old design would cost tens of minutes per launch. The window already opens
fast; a launcher would hide the wait, not remove it. Startup calls (`context`, `sources`,
`tree`: ~22 s) are a separate cost handled on their own.

**Keep true.** Never re-parse or re-hash a file whose stat identity is unchanged unless a
file it references changed. Never block the view on a scan. An unchanged scan writes
nothing and redraws nothing (decision 0002). Measure before optimizing beyond this.
