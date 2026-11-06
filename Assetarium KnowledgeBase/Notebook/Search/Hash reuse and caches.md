---
area: Search
tags: [system]
code: [hash_cache.location, hash_cache.require_fresh, hash_cache.lookup, publication.verified_hash, library_cache.library_records, library_cache.publication_key, library_cache.memo, scripts/gui_harness.isolate_hash_cache]
verified: 2026-10-28
branch: feature/library-view
---
# Hash reuse and caches

Hub: [Search](Search.md). Reads stay byte-verified without re-reading every file: a file's SHA-256 is
reused while its stat identity is unchanged, and parsed publication records are cached per immutable
generation. Decisions: [0003](../../Decisions/0003-per-publication-read-caches.md),
[0004](../../Decisions/0004-stat-identity-hash-reuse.md).

## How it works

- `publication.verified_hash(path)` asks `hash_cache` for a hash recorded under the file's current
  identity (file ID, size, mtime, change time) and re-reads bytes only when it changed. The record is
  the shared SQLite file `cache/file-hashes.sqlite`; scans seed it.
- `library_cache` keeps slim records per publication: a view is reused while the publication identity,
  the catalog and membership file stats and the source revision are unchanged; any change rebuilds it.

## Rules

- **Explicit audits and removal checks must read bytes**: `verified_hash(path, fresh=True)` or
  `hash_cache.require_fresh()` for the whole process (verification scripts do this).
- **Synthetic tests and verify scripts keep their hashes out of the shared cache**:
  `LAL_HASH_CACHE` points elsewhere (`gui_harness.isolate_hash_cache` uses `scratch/hash-cache/`) or
  `off` disables it.
- Published generations are immutable, which is what makes per-generation caching safe; never write
  into a published generation.

## Related

[Retrieval](Retrieval.md) · [Sources](../Sources%20and%20Catalog/Sources.md).
