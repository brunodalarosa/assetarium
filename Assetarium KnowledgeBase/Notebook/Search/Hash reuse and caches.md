---
area: Search
tags: [system]
code: [hash_cache.location, hash_cache.require_fresh, hash_cache.lookup, publication.verified_hash, library_cache.library_records, library_cache.slim, library_cache.publication_key, library_cache.memo, scripts/gui_harness.isolate_hash_cache]
verified: 2026-11-10
branch: feature/audit-simplify
---
# Hash reuse and caches

Hub: [Search](Search.md). Reads stay byte-verified without re-reading every file: a file's SHA-256 is
reused while its stat identity is unchanged, and parsed publication records are cached per immutable
generation. Decision: [0028](../../Decisions/0028-result-identity.md). The read caches were decision 0003
until November 2026; they are a design, so they live here.

## How it works

- `publication.verified_hash(path)` asks `hash_cache` for a hash recorded under the file's current
  identity (file ID, size, mtime, change time) and re-reads bytes only when it changed. The record is
  the shared SQLite file `cache/file-hashes.sqlite`; scans seed it.
- `library_cache` keeps read-only views per publication: a view is reused while the publication identity
  (project and store roots, folder key, generation), the catalog and membership file stats and the source
  revision are unchanged; any change rebuilds it.
- `library_cache.library_records` returns shared **slim** records (`library_cache.slim`): no `variants`,
  `grouping`, `dependency_inspection`, `provenance`, `texture_repair_history`, `license_evidence` or
  `effective_caption`, and `technical` cut down to the inspected facts filters and source checks use.
  Detail views read the full record.
- Publication file digests shown in the UI and caption classification JSON are computed once per file stat.
- Why: every request used to re-parse all catalog records (125 MB of JSON, about 1.4 s), and the library
  summary re-hashed 208 MB of SQLite on every call.

## Rules

- **Cached records are shared: never mutate them.**
- **A new field that list or search views need must be kept by `library_cache.slim`**, or it silently
  reads as missing there.
- Processing and indexing (`incremental`, batch scripts) read fresh full records through
  `membership.records`, never the cache.
- **Explicit audits and removal checks must read bytes**: `verified_hash(path, fresh=True)` or
  `hash_cache.require_fresh()` for the whole process (verification scripts do this).
- **Synthetic tests and verify scripts keep their hashes out of the shared cache**:
  `LAL_HASH_CACHE` points elsewhere (`gui_harness.isolate_hash_cache` uses `scratch/hash-cache/`) or
  `off` disables it.
- Published generations are immutable, which is what makes per-generation caching safe; never write
  into a published generation.

## Related

[Retrieval](Retrieval.md) · [Sources](../Sources%20and%20Catalog/Sources.md).
