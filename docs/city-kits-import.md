# City Kit import — October 12, 2026

Status: **completed and published**. Active generation:
`v_aeb7c30b435442b988274ee826cc1fbe`.

Added **81 assets** from the two explicitly approved folders, expanding published
membership from 883 to **964 assets across ten packs**.

| Pack | Assets | Inspection | Rendered previews | Descriptions |
| --- | ---: | --- | ---: | --- |
| City_Kit_Suburban | 40 | Complete | 129 | 40 pending |
| City_Kit_Commercial | 41 | Complete | 123 | 41 pending |

The importer produced **252 renders**: front, side and three-quarter views for
every asset, plus nine top views for thin assets. It indexed these renders and
81 supplied thumbnails as **333 successful image vectors**. No caption model
was started and no text description or description vector was generated for
these packs. Description-only search has no results for them until later text
processing; browsing, keyword and image search are usable now.

`library-batch.py process --skip-captions` skips generation while inspecting,
indexing available images and publishing. Ungenerated captions remain pending,
without a caption fault badge. Deferred description vectors create no failed
jobs and become eligible automatically when descriptions are later generated.
Unchanged existing failures remain retained without automatic retries. The run
used the existing environments/models and a 500 MiB peak additional allowance.

## Verification and retained faults

- All 81 inspections and preview stages completed; all 333 new image jobs passed.
- Fifty focused tests passed, including later description-vector processing,
  publication with image-only results, and retention of actual failures.
- Both packs browse with their correct counts. All 81 details/previews were
  verified through the desktop backend; six sample view images were delivered
  through actual STDIO MCP. Six keyword/image/description query cases returned
  identical desktop and MCP payloads. Verification workers exited cleanly.
- Visually inspected both complete three-quarter overview sheets, 24 rendered
  views of eight representatives beside supplied thumbnails, and all nine extra
  top views. Framing and palettes looked usable; owner artistic approval remains
  pending. Alternate-format geometry equivalence and physical scale are unverified.
- Source geometry flags affect **12 assets**: overlapping duplicate faces in
  one suburban and eleven commercial models. Evidence and usable previews remain;
  originals were not repaired or retried. No new inspection/preview/vector
  processing failure occurred.
- All 5,373 original source entries, 4,344 existing vectors and 5,443 protected
  output files retained their hashes. Inspection, caption, owner and vector
  results for the previous 883 assets remain intact. One older Mini Forest fence
  received a cross-pack same-name inventory note and refreshed decoded license
  excerpts; original license paths/hashes/identifiers are unchanged.

The strict first preservation receipt is retained separately: it initially treated
that expected inventory refresh as a result change. The corrected checker records
inventory updates separately and verifies downstream preservation. An isolated
review-helper attempt failed because PowerShell did not forward piped input to
the runtime wrapper; using a saved script resolved the harness issue. Neither
case reran model inference or repaired an asset.

## Evidence

- `data/library/city-kits-20261012/verification.json`
- `data/library/city-kits-20261012/access-verification.json`
- `data/library/city-kits-20261012/visual-review.json`
- `data/library/city-kits-20261012/City_Kit_Suburban-overview.png`
- `data/library/city-kits-20261012/City_Kit_Commercial-overview.png`
- `data/library/city-kits-20261012/representative-views.png`
- `data/library/city-kits-20261012/top-views.png`
- `data/library/operations/3b0e9098fde343abb6bc29b7a2626043/`
- `data/storage/city-kits-before-20261012.json`
- `data/storage/city-kits-after-20261012.json`

Unique allocated project storage increased from 6,957,196,032 to 7,097,082,480
bytes: **133.4 MiB additional**, for **6.610 GiB total**. This includes import
outputs, publication snapshots and verification evidence, stays below the
approved 500 MiB peak increase and 8 GiB total ceiling, and excludes external
originals/shared models. Per-batch receipts were also retained. No dependency
installation or cleanup was needed.

Reopen an already running desktop app to load the updated pending-caption
presentation. Existing published snapshots and historical evidence are retained.
