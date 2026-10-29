---
tags: [decision]
decided: 2026-10-26
---
# 0019 — Excluded folders, owner-confirmed duplicate export folders, folder variants

**Decision (user of this checkout, October 26, 2026; for the owner's review before any merge
upstream).** Packs often ship the same models several times: per format (`FBX/`, `gLTF/`,
`OBJ/`) and per engine (`Unity FBX/`, `FBX(Unity)/`…), with names that differ by publisher.
Assetarium recognizes a fixed list of format folders ([decision 0009](0009-general-capabilities.md)
keeps that structural); anything else became separate, often failing assets. Three general
capabilities, all saved per source in `metadata-lal/source.json`:

- **Excluded folders** (`excluded_folders`). A pattern is a folder name with `*` (any level) or a
  path from the source root; case is ignored. A scan neither walks nor hashes an excluded folder;
  it is listed as a `boundary_exclusion` row (`excluded_folder`) with its file count. Changing the
  list rescans; removing a pattern restores the files and reuses finished work. Files in excluded
  folders cannot serve as dependencies.
- **Duplicate export folder suggestions** (`export_decisions`). A scan compares sibling folders by
  the stems of their model files (no extension, case or subfolders; each unique in its folder, at
  least 3). Equal sets become a suggestion unless every folder is already grouped by the
  recognized layouts. **Near misses** are suggested too (October 27, 2026): sibling folders whose
  names found once in every folder cover at least 90% of each folder's model files, for example an
  engine copy missing a few models, or a folder repeating one name in two subfolders. A name
  repeated inside a folder is set aside instead of disqualifying the folder. Group then groups only
  the names found once in every folder; names in only some folders, or repeated inside one, stay as
  they are. The card and CLI say how many names are shared and which stay as they are, and Exclude
  says how many ungrouped names it would also skip. Near-miss answers are bound to the shared names
  and to each folder's remaining and repeated names. Exact matches keep their suggestion identities,
  so earlier answers stay valid. Nothing groups on a guess: the owner answers **Group**, **Keep separate** or
  **Exclude** (adds the extra folders to the exclusions). An answer is bound to the anchor, the
  folders and a hash of the name list; when a folder's names change it stops applying (its files
  are separate again and the suggestion returns) and applies again if the names match again.
  Grouping keeps the identity of the reference folder's file (recognized group or standalone), so
  asset IDs, inspections, previews and descriptions are kept; search vectors are rebuilt because
  their source fingerprint covers every file. Grouping evidence is
  `confirmed-sibling-export-v1`; geometry equivalence is not inspected.
- **Folder variants.** Each file of a grouped asset is labeled with its folder (`FBX`,
  `Unity FBX`…), derived on read from the grouping evidence. `get_asset` returns
  `source_variants` and accepts `source_variant` (a label, never a path) to pick between files of
  the same format; without it, the rendered file, then the reference folder, then recognized
  folders win. The inspector shows the labels.

Bridge `source_exclusions`, `source_export`, `source_export_undo`; CLI `sources exclude|include
KEY PATTERN` and `sources exports KEY [--group|--separate|--exclude|--undo ID]`.

**Why.** On the user's packs, `Unity FBX` copies (bytes differ from `FBX/`, so hashes cannot tell)
and an `OBJ/` folder whose subfolder is spelled `Landscape` instead of `Landscapes` tripled
`Low Poly Nature - Extended` to 9,900 assets, and the Unity copies failed on missing textures.

**Keep true.** Structure and owner answers, never publisher names. Never regroup without a current
answer; an answer that no longer matches is inert. Exclusions never delete anything. A
variant is chosen from an asset's own files only.
