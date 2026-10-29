---
tags: [decision]
decided: 2026-10-26
---
# 0020 — A broken alternate file fails alone; owner-confirmed recheck of check failures

**Decision (user of this checkout, October 26, 2026; for the owner's review before any merge
upstream).** `retrieval.source_check` used to reject a logical asset when any of its files or
dependencies had a problem. With grouped exports ([decision 0019](0019-source-folders-and-export-variants.md))
that let one unusable alternate (an OBJ whose material points at the author's desktop) fail
3,300 assets that render fine from glTF.

- **Per-file problems.** A dependency belongs to the file that refers to it, also through a
  material (OBJ → MTL → texture; `dependency_owners`). `file_problems` lists files that are
  unavailable, changed, or have a broken or stale dependency.
- **Rule.** A problem in the file the asset is rendered from (`used_file`: the inspected file, or
  the one inspection picks under the current format settings), in a dependency no file owns, or at
  asset level still excludes the asset; nothing switches to another file. A problem only in
  alternate files excludes just those files: they and their dependencies leave the check, and the
  check records them (`unusable_files`). When nothing is broken the result is byte-identical, so
  fingerprints and finished work are unchanged; the per-file breakdown runs only after the normal
  check fails.
- **Visibility.** `get_asset` never selects an unusable file: `source_variants` marks it
  `usable: false` with its reason, a `source_format` / `source_variant` request for it is refused
  with that reason, and only usable files' dependencies are returned. The inspector shows it.
- **Recheck** (`recheck.py`). Recorded failures still never retry on their own. **Recheck
  failures** on a source's Asset processing card (or `local-assets recheck --asset-source KEY`)
  lists failed inspection/description jobs whose recorded reason was this check and runs the check
  again, read only. Releasing needs the owner's click in a confirmation dialog (or a typed `yes`)
  and the preview it saw; a changed source refuses it. Each released job becomes `released` in the
  ledger with its previous evidence, the record keeps `released_faults`, and the next Process
  assets tries it once. Failures from Blender, rendering or models are never released here. It is
  not an MCP tool.

**Why.** Packs commonly ship a broken copy in one format; excluding good assets because of it
hides usable work. The 3,300 `Low Poly Nature - Extended` failures pass the new check; every
asset that passed before keeps its exact fingerprint on all six real sources.

**Keep true.** Keep `source_check` byte-identical for healthy assets. Never select or render an
unusable file, never switch to an alternate after the used file fails, and never release a fault
without an explicit owner action tied to a preview.
