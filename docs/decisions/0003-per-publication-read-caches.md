# 0003 — Read paths reuse per-publication caches

**Decision.** `library_cache.py` holds read-only views keyed by publication
identity: project/metadata root, source key, generation, catalog and membership
file stats, and the source revision. Any change rebuilds the view.
- `retrieval.pilot_records` returns shared **slim** records (no `variants`,
  `grouping`, `dependency_inspection`, `provenance`, `texture_repair_history`,
  `license_evidence`, `effective_caption`; `technical` limited to the inspected
  facts used by filters and source checks). Detail views read the full record.
- Publication file digests shown in the UI are computed once per file stat.
- Caption classification JSON is parsed once per file stat.

**Why.** Every request re-parsed all catalog records (125 MB of JSON, ~1.4 s), and
the library summary re-hashed 208 MB of SQLite every call.

**Keep true.** Cached records are shared: never mutate them. Processing and
indexing (`index_pilot`, `incremental`, batch scripts) read fresh full records
through `membership.records`. A new field needed by list/search views must be
kept by `library_cache.slim`.
