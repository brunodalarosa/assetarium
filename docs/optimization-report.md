# LAL optimization report: 2026-10-17

This report is read-only analysis. Nothing has been implemented. Each item
still needs the two AGENTS.md checkpoints (scope, then plan) before any code
changes.

## How this was measured

- Read-only probe scripts ran against the live library through `.venv-mcp`
  and `.venv-embedding`, using `DesktopService` / `SearchEngine` directly.
  No Gateway was used, so no audit folders were written. Nothing ran on the
  GPU, no models were loaded and no files were written.
- Library size: **2,080 member assets** (3,393 catalog records) across 10
  registered sources, with 14,795 vectors.
- Semantic search overhead was measured with a stub query vector, so the
  numbers below cover everything *except* the model's own forward pass.
- "Cold" means the first run in that process, with the OS file cache partly
  warm. After a reboot the cold numbers will be worse. Each figure is a single
  run, so treat it as an order of magnitude, not a benchmark.

| Operation (as the app runs it today) | Measured |
| --- | --- |
| `import local_asset_library.desktop` | 0.66 s (0.47 s of it is the `mcp` SDK) |
| `pilot_records()` (called many times per request) | 1.3–1.6 s each |
| `context()`: startup, then every 20 s | **5.4 s cold / 4.7 s warm** |
| `browse()`, one page of 40 | 2.3 s cold / 1.7 s warm |
| Thumbnails, 12 cards | 1.3 s (≈4.5 s for a 40-card page; they run one at a time) |
| `sources()` poll, every 1.5 s | 3.6 s first call, then 0.11 s |
| **Keyword search** | **33.8 s first / 8.1 s afterwards** |
| **Combined search, excluding the model** | **23.3 s first / 17.8 s afterwards** |
| Embedding worker imports (`torch` + `sentence_transformers`) | **20.5 s cold / 4.6 s warm** |
| Re-hashing the 1.5 GB embedding model on every load | 0.9 s warm (several seconds cold) |

Rough estimate for the **first combined search** today: worker imports (5–20 s)
+ model load to GPU (not measured, typically several seconds) + model re-hash
(1–5 s) + verification (18–23 s, more when the disk is cold) ≈ **30–60 s**.
Every later search still costs about 18 s, even with the model loaded.

---

## 1. Root cause: every request re-verifies the whole library from scratch

Almost all of the slowness comes from one design choice, repeated in many
places: **each request re-reads and SHA-256-hashes every source file, every
preview PNG and the catalog databases**, and re-parses the whole catalog. It
does this for all 2,080 assets, even when the answer needs only 20 of them.

`publication.verified_hash` caches hashes only *within one request*. Its
docstring says "later requests verify bytes afresh". Meanwhile the scanner
(`catalog.walk_source`) already trusts a `(size, mtime_ns, ctime_ns, inode)`
identity cache (`scan-cache.json`) to skip re-hashing. The runtime path is
therefore far stricter than the path that produced the catalog in the first
place.

### 1.1 `source_check` hashes about 8,000 files on every search ⭐ biggest win

- `SearchEngine.search` runs `source_check` on **every member**, before ranking.
  That is 7,985 files and 163 MB hashed per search (`retrieval.py:342-349`).
- Semantic modes then hash the caption input views for every description
  vector (`description_input`) and the preview PNG for every image vector
  (`preview_file`). That is about 11,500 more PNG files (`retrieval.py:379-407`).
- `AssetService.search` hashes each result's previews *again*
  (`mcp_assets.py:201-208`).
- Profile of one combined search: 26k `read()` calls (6.3 s), 112k
  `Path.resolve` calls (3.8 s), 147k `stat` calls (1.7 s).

**Options, which are your policy decision:**

- **A. Stat-identity hash cache, process-wide or persisted.** Re-hash a file
  only when its `(size, mtime_ns, ctime_ns, inode)` changes. This gives the
  same guarantee the scanner already relies on. Expected: keyword search
  8–34 s → **~0.1–0.3 s**, and combined search overhead 18–23 s → **~0.3 s**.
- **B. Verify only what is returned.** Rank using stat checks only, then
  byte-verify the ≤40 shortlisted results and the opened detail. Every asset
  the user actually receives is still byte-verified.
- **A + B together** is what I recommend. B keeps the "verified hash" promise
  for anything handed to a user or agent, and A makes even that nearly free.

### 1.2 The whole catalog is parsed again on every request

- `membership.records()` loads and `json.loads` **all 3,393 records (125 MB
  of JSON; average 37 KB, largest 108 KB)**, then keeps 2,080 of them. That
  costs 1.2–1.6 s each time.
- One request calls it several times. `context()` calls it twice (directly and
  through `coverage()`). A search calls it 3–4 times: `Gateway.call`
  (`has_sources`), `AssetService.search` (`has_sources`), `SearchEngine.search`,
  plus one `record()` per result, which re-reads membership, the detail row and
  `visible()`.
- The heaviest fields are rarely needed in lists: `variants` (up to 72 KB),
  `technical` (17 KB), `caption_provenance` (7 KB), `previews` (6 KB) and
  `texture_repair` (4.6 KB).

**Fix:** generations are immutable and named by UUID, so the parsed records
for `(generation, sources revision)` can be cached in memory with no staleness
risk. Add a slim projection for list and search views (id, name, pack,
formats, processing, preview refs, filter facts) and load the full record only
for detail. Expected: about 1.4 s per call → microseconds after the first load.

### 1.3 `context()` hashes 208 MB of SQLite every 20 seconds

- `DesktopService.context` SHA-256s `catalog.sqlite` (139 MB),
  `index.sqlite` (69 MB) and `membership.json` **on every call**
  (`desktop_service.py:72-74`).
- It runs at startup, again right after the first browse, **every 20 s from
  `setInterval`** and on every sources revision change. While it runs it holds
  the global presentation lock, so thumbnails and detail clicks wait behind it.

**Fix:** the generation id already identifies an immutable publication.
Compute the digests once per generation (or show the generation id instead of
a content hash). Expected: 5 s → under 50 ms.

### 1.4 Repeated path resolution

- `Config.output_path` → `sources.generated_path` → `validate_directory`
  re-resolves the source root and `metadata-lal` on **every** data-path access.
- `source_file` → `source_for_path` → `registry()` → `_inside(...).resolve()`
  runs for every file.
- This costs about 3.8 s of `nt._getfinalpathname` per combined search.

**Fix:** resolve and validate each source root once per snapshot (keyed by
registry revision). Then do containment as a string-prefix check on the
already-resolved root, plus one `resolve()` for the leaf file only. This keeps
the link and escape guarantees.

### 1.5 Vectors are reloaded and re-checksummed on every search

- `SELECT * FROM vectors` loads 69 MB every search. `checked_vector` then
  computes a SHA-256 and a norm for each of the 14,795 vectors before a single
  matmul.

**Fix:** build a validated `float32` matrix once per generation and keep it
in memory (about 45 MB). After that, each search is a single matmul.

---

## 2. Startup: what happens when you open the app

The sequence in `ui/app.js:119` and `desktop.py:38-60` is:

1. `DesktopBridge` initializes. The window does not appear until this
   finishes. If no combined catalog exists, it also runs `aggregate()` here.
2. `context()`: 5 s.
3. `browse()`: 2 s, then thumbnails one at a time behind the lock.
4. `refreshContext()`: **`context()` again**, another 5 s, right after step 2.
5. `loadSources()`: 3.6 s on the first call.
6. `sourceAction('scan')`: **starts a full scan process of every enabled
   source on every launch.**
7. The scan rewrites `source-status.json` for every source. That changes
   their mtimes, so `revision()` changes. The 1.5 s `loadSources` poll sees
   the change and calls `refreshContext()`, which runs `context()` (5 s
   more), re-renders and browses again. All of this competes with the scan
   process for disk.

So a launch does **at least 3 × `context()` (about 15 s), 2 browses, a full
library scan and a thumbnail queue**, all serialized through one lock.

**Fixes:**

- **2.1** Remove the redundant `refreshContext()` right after the first
  browse (`app.js:119`).
- **2.2** Make the startup scan a decision rather than a default: skip it,
  delay it until idle, or limit it to a cheap stat check. Only rewrite
  `source-status.json` when its *content* changes, and/or base `revision()`
  on content instead of mtime. Today an unchanged scan still invalidates every
  view.
- **2.3** Replace the two polls (1.5 s sources and 20 s context) with one
  cheap **change token**: the stat of `active.json`, the registry revision and
  the status-file stats. Fetch the heavy data only when the token changes.
  Poll slowly (or not at all) when no operation is running.
- **2.4** Narrow `_presentation_lock` (`desktop.py:28,89`). Today it serializes
  every UI call: thumbnails, browse, detail, polls. Once 1.1–1.3 land, it only
  needs to protect the small fault dictionaries.
- **2.5** Show the window immediately with a "Loading library…" state, and
  initialize the bridge in the background.
- **2.6** Import the `mcp` SDK lazily. The desktop app never uses the MCP
  transport, but importing `mcp_server.Gateway` pulls in the SDK (0.47 s of
  the 0.66 s module import). Split the gateway core from the STDIO transport.

**Expected result once Section 1 and Section 2 land:** first cards on screen
drop from roughly 10–20 s to **about 1–3 s**.

### 2.7 Thumbnails

Each card's thumbnail is a full `get_asset`:

- membership check, detail, `visible()`
- `resolved_detail` → `source_check`, which hashes the asset's source files and
  dependencies just to show a PNG
- PIL decode, LANCZOS resize, **`PNG optimize=True`** encode, then base64 over
  the pywebview bridge

This takes about 110 ms per card, and cards run one at a time behind the lock.

**Fixes:**

- Skip the source check for thumbnails. The thumbnail shows the preview, not
  the source, and the detail view still verifies the source.
- Cache derived thumbnails keyed by the preview's sha256, in memory and/or as
  files under the source's `metadata-lal`.
- Use a cheaper encode: JPEG or WebP, or `optimize=False`, sized to the card.
- Optionally batch thumbnails into one bridge call per page.

---

## 3. The first semantic search

### 3.1 Move ranking out of the worker, leaving it to compute embeddings only ⭐ architecture

Today `scripts/asset-worker.py` runs the *entire* `AssetService.search` inside
the embedding process. That process has its own cold catalog parse,
verification and vector load, separate from the GUI or MCP process.

**Proposal:** the worker only returns a query vector for a text (or reference
image). Catalog loading, verification, FTS, the cached vector matrix and RRF
all stay in the main process, where the caches from Section 1 are already
warm.

- The worker no longer needs the catalog at all.
- Keyword and semantic search share one snapshot.
- The worker protocol becomes tiny and easier to test.

### 3.2 Worker cold start

- **Imports:** `torch` + `sentence_transformers` take 20.5 s cold and 4.6 s
  warm. `sentence_transformers.util` pulls in **scikit-learn**, and
  `transformers.configuration_utils` alone takes about 2.5 s. The script
  imports `SentenceTransformer` up front on purpose (the comment mentions a
  Windows DLL deadlock).
- **Model verification:** every `EmbeddingBackend()` re-hashes all 13 model
  files (1.5 GB) (`embedding_backend.py:94-97`). The same stat-identity cache
  from 1.1A would make this nearly free after the first verification.
- **Idle unload after 60 s** (`asset-worker.py:65`): the next search after a
  one-minute pause pays model load and re-hash again. Options:
  - a longer or configurable idle time (for example 10 min); the queue
    already yields to batches through `batch_requested` / `peer_requested`
  - keep the weights in CPU RAM after unload and move them back to the GPU,
    instead of reloading from disk
- **Pre-warm (your call; CLAUDE.md says "never start models at startup"):**
  start the worker and do the imports only, with no model and no GPU, when the
  user focuses the search box or starts typing. That hides 5–20 s of import
  time without loading a model at startup.
- **Bigger option:** drop `sentence_transformers` and call `transformers`
  directly. This removes the sklearn/scipy imports, but it changes the
  embedding contract fingerprint (it records library versions), so the vectors
  would need explicit revalidation. That risk is higher than the gain is worth
  unless import time is still a problem after the other fixes.

### 3.3 The first-search timeout can permanently disable semantic search ⚠ UX/correctness

`Gateway.semantic` waits 90 s for the worker's first line
(`mcp_server.py:93`). On a timeout it stores `worker_fault`, and **every
later semantic search fails with "explicit retry required" until the app
restarts**.

A cold first search costs today: verification of 34 s or more on a cold disk,
plus imports of up to 20 s, plus model load and hash. That can approach 90 s
on a slower machine. This matters for open-source users with HDDs or no
Defender exclusions. Section 1 removes most of the risk. Separately, the app
should tell "still loading the model" apart from "hung", for example with a
worker heartbeat or progress line.

**Expected result:** a warm combined search drops from about 18 s to **under
0.5 s**. The first combined search drops from about 30–60 s to about 8–15 s
(import plus model load), or to about 1 s once pre-warmed.

---

## 4. Footprint

| Item | Size | Notes |
| --- | --- | --- |
| `data/library/generations` (combined) | **2.3 GB, 17 generations** | Each is about 208 MB (139 MB catalog + 69 MB index). Old ones are never retired. |
| Per-source `metadata-lal/library/generations` | 4–7 per source, up to 103 MB each | Same: no retention. |
| `scratch/` | **2.8 GB, 207 folders** | Mostly old pytest `--basetemp` and verify runs (100–160 MB each). |
| `data/gui` | 110 MB, 47 run folders | One audit folder per launch, plus a `desktop.jsonl` line for every call, including each thumbnail. |
| `cache/` | 209 MB | |
| `.venv-caption` / `.venv-embedding` | 4.5 GB / 0.56 GB unique | Pinned for compatibility; no change suggested. |

- **4.1 Generation retention.** Keep the active generation and the last N.
  Retire older ones through the existing manifest-driven
  `maintenance_files.py`, with an owner-approved receipt. This could free about
  2 GB now, and it stops the growth.
- **4.2 Stop copying the whole combined catalog on every publish.**
  `sources.aggregate` copies every source's records and vectors into a new
  139 + 69 MB generation, even when only one source changed. Alternatives:
  - SQLite `ATTACH` of the per-source generations with UNION views, or
  - an in-memory combined snapshot built from the per-source generations at
    load time (it fits naturally with the snapshot in Section 5).

  Either one removes most of the 208 MB written per publish, and the time it
  takes.
- **4.3 Slim the catalog record.** Move `variants`, the full `technical` block
  and `caption_provenance` into separate columns or tables. This shrinks the
  catalog and speeds up every parse that remains.
- **4.4 Scratch hygiene.** The rule "use a new `--basetemp` each time"
  accumulates about 130 MB per test run. AGENTS.md already allows reusing a
  bounded temporary folder for repeatable checks. Adopt one reusable pytest
  folder and do a one-time reviewed cleanup of the old ones (about 2.5 GB).
- **4.5 Audit rotation.** Cap or rotate `data/gui/runs`, and skip per-thumbnail
  audit lines, or aggregate them.

---

## 5. Recommended shape of the refactor

One concept covers most of Sections 1–3: an immutable **`LibrarySnapshot`**
per `(combined generation, sources revision, processing formats)`.

- It is built once: parsed slim records, membership, the visibility filter,
  resolved source roots, an open read-only FTS connection, a validated vector
  matrix, and the context and coverage summaries.
- Requests only check a cheap change token and reuse the snapshot. A change
  builds a new snapshot and drops the old one atomically. This matches the
  existing pinned-generation model in `publication.py`.
- File verification goes through one **stat-identity hash cache**, shared by
  scanner, runtime and model checks, so the same guarantee applies everywhere.
- The embedding worker becomes a pure "text or image → vector" service (3.1).

Suggested phases, so you can stop after any of them:

| Phase | Contents | Expected gain | Risk | Rough effort |
| --- | --- | --- | --- | --- |
| 1. Quick wins | 1.3 context digests per generation · 2.1 drop duplicate refresh · 2.3 change-token polling · 2.6 lazy `mcp` · 1.2 per-generation record cache | Startup about −10 s; the UI stops stalling every 20 s | Low | ~1 day |
| 2. Verification policy | 1.1 A+B · 1.4 root memo · 2.7 thumbnail path · model-hash cache | Search 8–34 s → under 0.5 s (keyword) | Medium; **needs your approval of the hashing policy** | 1–2 days |
| 3. Architecture | 3.1 embedding-only worker · 1.5 vector matrix · `LibrarySnapshot` · 2.4 lock narrowing · 3.3 heartbeat · longer idle / pre-warm | Combined search about 18 s → under 0.5 s warm; the first one about 8–15 s | Medium; touches MCP and GUI paths, so it needs full suite + verify scripts | 3–5 days |
| 4. Footprint | 4.1 retention · 4.4 scratch · 4.5 audits · later 4.2 / 4.3 | About 4–5 GB now, and growth stops | Low (4.1, 4.4, 4.5) / High (4.2, 4.3: catalog contract) | 0.5 day + optional 2–4 days |

Each phase stays testable with the existing `tests/` and the
`scripts/verify-*.py --run-name` checks. Phase 2 and Phase 3 should add a timing
receipt (the probe scripts used here can be turned into a
`scripts/benchmark-*.py`) so improvements are recorded in `docs/progress.md`
like other evidence.

---

## 6. Other findings (not performance)

- **Config override ignored:** `desktop.main`, `mcp_server.main` and
  `scripts/asset-worker.py` always load `config.example.toml`. CLAUDE.md
  documents `config.local.toml` as the local override, but nothing reads it.
- **Windows Defender:** a large part of the 20 s cold `torch` /
  `sentence_transformers` import is typically real-time scanning of thousands
  of DLLs and `.pyc` files. Excluding the project's `.venv*` folders would help
  a lot, but it is a security setting, so it is your decision and is not
  something to automate.
- **`bounded()` / search response capping** re-encodes the payload 8–12 times
  per response. It is negligible today (milliseconds), so this is only a
  cleanup.
- **3D preview files** travel as base64 JSON over the pywebview bridge (up to
  64 MB per file). That is acceptable for small kits, but worth watching if
  bigger assets are added.
