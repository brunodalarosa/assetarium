---
tags: [hub]
---
# Improvements

Cross-cutting friction, with the dates it was seen. Remove an item once it's fixed; add a `Seen:`
date instead of a duplicate. System-specific friction lives in that note's
`## Friction and improvements`. Up: [Notebook](Notebook.md).

Format: `- **<what gets in the way>**: why it hurts, what would improve it. Seen: YYYY-MM-DD`

## Tooling and build

- **Tests patch module-level `time.sleep` globally**: `test_owner_commands` sets `owner_commands.time.sleep`, which is
  the shared `time` module, so any code that sleeps during those tests gets their fake. Patch a local alias instead.
  Seen: 2026-11-01
- **Fingerprints hash raw file bytes, so line endings matter**: `core.autocrlf` can turn LF into
  CRLF on checkout and change `blender_worker.py`, caption or embedding code hashes.
  `incremental.recorded_fingerprint` and `retrieval.recorded_contract` tolerate LF/CRLF-only
  differences, and `EQUIVALENT_WORKERS` lists both forms, but any new fingerprinted file needs the
  same care. A `.gitattributes` `eol` rule for fingerprinted files would remove the trap (the owner
  chose not to add one in October 2026). Seen: 2026-10-18, 2026-10-28, 2026-10-30
- **The release fixture records the path of the checkout that built it**: `scripts/build-release-fixture.py`
  scans `samples/Sample assets` in place, so the frozen SQLite files in `tests/fixtures/releases/0.2.0/`
  contain this checkout's absolute path (drive and folder, no user name), against "tracked files describe no
  computer". Building from a neutral path (for example a copy of the samples under the throwaway project in
  `scratch/`) would remove it; frozen fixtures are never replaced, so it can only change from 0.3.0.
  Seen: 2026-11-05
- **The full test suite takes minutes and needs real Blender**: a skipped Blender fixture counts as
  unverified. Targeted runs (`tests/test_<area>.py`) are the everyday path. Seen: 2026-10-28
- **`scripts/verify-loading-states.py` is stale**: it waits for `#source-warnings-loading`, which the
  rebuilt Asset processing tab no longer has, so it fails before its later checks. Seen: 2026-10-31
- **No process memory probe in the runtimes**: `.venv-mcp` has no `psutil`, so measuring peak memory
  needed a `kernel32.K32GetProcessMemoryInfo` ctypes snippet (`PeakWorkingSetSize`). A small helper
  in `scripts/gui_harness.py` would make memory checks repeatable. Seen: 2026-10-31
- **Verify scripts move to wizard steps by number**: `verify-agent-setup.py` used `goToSetupStep(6)`,
  which stopped being Review when the model step was added. Look steps up by name, as
  `verify-setup-wizard.py` does (`STEPS.index(name)`). Seen: 2026-11-01

## Agent setup

- **Codex has no path-scoped rules**: Claude gets per-area pointers from `.claude/rules/`; Codex
  relies on the `AGENTS.md` Knowledge base section. Seen: 2026-10-28

## Process

- **Evidence lives in the owner's ignored `data/`**: verification reports, receipts and
  screenshots cited in docs and pull requests can't be opened by other contributors. Summarize
  the outcome in the PR; cite `data/` paths only as the owner's local record. Seen: 2026-10-28
- **Search capability receipt on a fresh install**: `scripts/historical/embedding_capability.py`
  uses the original pilot asset IDs, so a fresh install can't record it the historical way (see
  [Inference ports](../Architecture/Setup%20and%20Engines/Inference%20ports.md#known-debt-and-direction)). Seen: 2026-10-26

## Codebase-wide

- **Error and warning text can't be copied easily**: users need to paste fault reasons into bug
  reports or searches. Every error or warning label and message in the app should have a copy
  button next to it. Seen: 2026-10-29
- **"Step N" names**: "step N" in docstrings and doc titles still reads like history
  ([Codebase](Codebase.md#misleading-or-historical-names)); the "pilot" names were cleaned up in
  November 2026. Check fingerprinted files before renaming: editing them re-queues work. Seen: 2026-10-28
- **3D preview files travel as base64 JSON over the pywebview bridge** (up to 64 MiB per file):
  fine for kits, worth revisiting for large assets. Seen: 2026-10-17
- **Windows Defender real-time scanning** of the `.venv*` folders accounts for much of the ~20 s
  cold `torch` import. Excluding them is a security setting, so it stays the user's choice and is
  never automated. Seen: 2026-10-17
- **Multi-file edits through inline Python in shell heredocs** repeatedly broke escaped `\n` and quotes. Use the Edit tool or a script file instead. Seen: 2026-10-31; 2026-11-01 (a heredoc whose text held a typographic `’` failed with "unexpected EOF" in the Bash tool; a script file in the scratchpad worked; a second sighting the same day: `\n` in a heredoc-written string became real line breaks in `verify-agent-activity.py`; 2026-11-06: a doubled backslash-x00 in a heredoc became a real NUL byte inside `catalog.py`)
