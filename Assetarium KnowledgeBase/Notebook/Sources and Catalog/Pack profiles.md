---
area: Sources and Catalog
tags: [system]
code: [pack_profiles.py, pack_profiles.validate, pack_profiles.current, pack_profiles.apply, pack_profiles.effect, pack_profiles.signals, pack_profiles.record_change, variant_groups.py, variant_groups.assign, variant_groups.shared_map, variant_groups.membership, folder_view.group, folder_view.view_answers, library_store.replace_answers, library_index.shared_input]
verified: 2026-10-31
branch: feature/library-view
---
# Pack profiles

Hub: [Sources and Catalog](Sources%20and%20Catalog.md). A pack's structure as one versioned rule set, and the
variant groups those rules steer. Start at `pack_profiles.apply` and `variant_groups.assign`. Binding:
[decision 0024](../../Decisions/0024-pack-profiles-and-variant-groups.md).

## How it works

- **A profile has no table of its own for its current state.** `pack_profiles.current` gathers it from where each
  answer already lives: `library.sqlite` `answers` (`pack`, `pack_name`, `image_kind`, `variant_axis`,
  `separate_descriptions`, `engine_copy`) and the folder's `source.json` (excluded folders, export decisions, the
  texture folder). `apply` writes them back (`library_store.replace_answers` in one transaction, then
  `sources._change_source_settings`) and appends the result to `profiles` (one row per version, with its origin).
  The first change of a pack first records version 1, "earlier", so it can be restored.
- **Two ways a rule takes effect.** `variant_axis` and `separate_descriptions` are in `folder_view.VIEW_ANSWERS`:
  they are part of the view stamp, so the next read rebuilds the view. `pack`/`pack_name` are read by
  `packs.structure`. Everything else (`RESCAN`, plus `pack` for image kinds) needs a scan; `apply` returns
  `rescan: true` and the caller (bridge, CLI) starts it. Nothing processes.
- **Variant groups are assigned in `folder_view.group`**, folder by folder, after the asset rows are written:
  `group_key`, `variant`, `representative`, `card` columns, and description `shared` for non-representatives
  (unless `separate_descriptions`). `library_view.folder_items` pages by `card` with a window function and
  attaches every member (≤ `variant_groups.CAP`) to the card.
- **Shared descriptions reach search and detail at read time**: `library_index` embeds a shared variant with
  `shared_input` (the representative's description plus " Variant: G"); `desktop_service` shows the
  representative's observations with `description_shared_from`. Records never carry group data.

## Rules

- **The rule vocabulary is closed** (`KINDS`, `FIELDS`); paths are pack-relative and never patterns. Agents choose
  rules, the code validates them.
- **Never call `current`/`effect`/`signals` with whole records**: they read folder views and answers only.
- Export and texture rules need a current suggestion; `apply` refuses before saving anything when one is gone.

## Gotchas

- Image kinds are classified **during the scan** (`image_catalog.image_assets`), not when read, so `image_kind`
  rules rescan; pack boundaries are read-time but also feed that classification.
- An asset whose folder becomes excluded is `excluded` in `library.sqlite` (not Missing): `library_store.recognize`
  gets the scan's excluded folders.
- "Folder variants" in `get_asset` (`source_variants`, decision 0019) are files of one asset; variant groups are
  separate assets.

## Related

[Sources](Sources.md) · [Processing queue](../Processing/Processing%20queue.md) ·
Decisions: [0019](../../Decisions/0019-source-folders-and-export-variants.md), [0023](../../Decisions/0023-central-asset-library.md),
[0024](../../Decisions/0024-pack-profiles-and-variant-groups.md).
