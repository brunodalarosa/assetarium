---
tags: [hub]
---
# Improvements

Cross-cutting friction, with the dates it was seen. Remove an item once it's fixed; add a `Seen:`
date instead of a duplicate. System-specific friction lives in that note's
`## Friction and improvements`. Up: [Notebook](Notebook.md).

Format: `- **<what gets in the way>**: why it hurts, what would improve it. Seen: YYYY-MM-DD`

## Tooling and build

- **Fingerprints hash raw file bytes, so line endings matter**: `core.autocrlf` can turn LF into
  CRLF on checkout and change `blender_worker.py`, caption or embedding code hashes.
  `incremental.recorded_fingerprint` and `retrieval.recorded_contract` tolerate LF/CRLF-only
  differences, and `EQUIVALENT_WORKERS` lists both forms, but any new fingerprinted file needs the
  same care. A `.gitattributes` `eol` rule for fingerprinted files would remove the trap (the owner
  chose not to add one in October 2026). Seen: 2026-10-18, 2026-10-28
- **The full test suite takes minutes and needs real Blender**: a skipped Blender fixture counts as
  unverified. Targeted runs (`tests/test_<area>.py`) are the everyday path. Seen: 2026-10-28

## Agent setup

- **Codex has no path-scoped rules**: Claude gets per-area pointers from `.claude/rules/`; Codex
  relies on the `AGENTS.md` Knowledge base section. Seen: 2026-10-28

## Process

- **Evidence lives in the owner's ignored `data/`**: verification reports, receipts and
  screenshots cited in docs and pull requests can't be opened by other contributors. Summarize
  the outcome in the PR; cite `data/` paths only as the owner's local record. Seen: 2026-10-28
- **Roadmap notes have no list of allowed `status:` values**: agents guess (ASSETRM-0001 used
  `done`). A short status vocabulary in `Home.md` or a roadmap template would settle it. Seen: 2026-10-29
- **Search capability receipt on a fresh install**: `scripts/historical/embedding_capability.py`
  uses the original pilot asset IDs, so a fresh install can't record it the historical way (see
  [Inference ports](../Architecture/Setup%20and%20Engines/Inference%20ports.md#known-debt-and-direction)). Seen: 2026-10-26

## Codebase-wide

- **Error and warning text can't be copied easily**: users need to paste fault reasons into bug
  reports or searches. Every error or warning label and message in the app should have a copy
  button next to it. Seen: 2026-10-29
- **Pilot-era names**: "step N" and "pilot" in docstrings and doc titles mislead new readers into
  thinking code is pilot-only ([Codebase](Codebase.md#misleading-or-historical-names)). Renaming
  docstrings is cheap, but check fingerprinted files first: editing them re-queues work. Seen: 2026-10-28
- **3D preview files travel as base64 JSON over the pywebview bridge** (up to 64 MiB per file):
  fine for kits, worth revisiting for large assets. Seen: 2026-10-17
- **Windows Defender real-time scanning** of the `.venv*` folders accounts for much of the ~20 s
  cold `torch` import. Excluding them is a security setting, so it stays the user's choice and is
  never automated. Seen: 2026-10-17
