# 0002 — Startup scan, change detection, no manual Scan/Status buttons

**Decision.**
- Enabled sources are scanned in the background at every launch. This is how new,
  changed or removed files are discovered; scans never run models or rendering.
- A scan rewrites `source-status.json`, `import-status.json`,
  `asset-sources.json` and `scan-cache.json` only when their content changes
  (`scanned_utc` alone is not a change). An unchanged scan therefore leaves the
  source revision, and the open view, untouched.
- The UI polls one cheap bridge call, `changes()`, every 1.5 s. It returns
  stat-only tokens for the library (publication, processing status, source
  revision) and the sources (registry, status/operation/cancel/fault files,
  settings). Library and source data are fetched only when a token changes, or
  while a source operation is running (worker liveness is not a file change).
- The manual **Scan** and **Status** buttons are removed from the main view.
  **Refresh published view** and **Importing failures report** remain.

**Why.** Startup used to load the library summary three or more times, and every
unchanged startup scan invalidated and reloaded the whole view. Fixed 1.5 s and
20 s polls ran expensive summaries regardless of change.

**Keep true.** Do not add periodic heavy polls; extend `changes()` with the file
that changes instead. Writes that only refresh a timestamp must not bump views.
Scans and processing must not invalidate visible cards; library changes arrive
through `refreshContext`.
