---
tags: [architecture]
parent: "[Architecture](../Architecture.md)"
status: draft
verified:
branch:
level: system
code: [caption_quality.py, caption_review.py, scripts/record_caption_review.py]
---
# Caption severity in the desktop app and agent results

Up: [Architecture](../Architecture.md) · Where in code: [Descriptions](../../Notebook/Processing/Descriptions.md). Moved from `docs/caption-quality.md` on 2026-10-28. `AGENTS.md` and the `local-asset-library` skill point here.

The current pilot uses a practical severity classification separate from its
original AI caption review. A successful search or usable source does not require
every caption detail to be accurate. Caption findings never exclude an otherwise
usable source or alter search ranking.

| Status | Meaning | Desktop presentation |
| --- | --- | --- |
| `clear` | No recorded caption findings; this does not mean owner approval | No caption badge |
| `review_note` | Minor precision or uncertain detail; broad identity remains useful | Note in asset detail; no caption badge |
| `warning` | Meaningful descriptive error or interpretation that could mislead selection | Caption warning badge and detail explanation |
| `fault` | Caption processing failed/incomplete, or there is no usable description | Caption fault badge and recorded fault |
| `pending` | Description generation has not started; no generation provenance or caption fault exists | No fault badge; coverage reports captions pending |

The approved reclassification contains **16 assets with review notes, 14 with
warnings, 1 failed caption, and 9 with no recorded findings**. All original 32
visual findings remain available. Examples: the apple's exact polygon count is a
note; a road bridge described as furniture is a warning; road-crossroad's failed
caption remains a fault. These are classifications of existing evidence, not new
visual inspections, caption corrections, or owner approval.

`docs/caption-review-classification.json` holds individually recorded severities
and reasons, bound to the asset ID and a digest of the stored description,
generation fingerprint and original visual findings. Changed captions/evidence,
missing classifications, malformed records or incomplete coverage leave the
findings visible as warnings. This file cannot downgrade failed/unusable captions.

The validator adds its own notes: use wording in a description ("designed for use in
games") is recorded as a `review_note` in `caption_provenance.validation_notes` when the
description is saved. These are already classified, sit beside review findings and are
never replaced by a later review.

The shared `caption_quality` implementation serves desktop browse/detail and
retrieval/MCP responses. Search summaries and basic asset details expose
`caption_status` and the compatible boolean `caption_faulty`. The boolean now
means an actual unusable caption, not any review note. With `include_metadata=true`,
agent details also include `metadata.caption_quality` with classified issues,
their original evidence, and reasons. The legacy `caption_fault_evidence` field
retains the original unmodified findings; interpret their historical `faulty`
labels through the current classification. Owner caption/artistic review states
remain separate and are not approved by this change.

## Rules for future imports and reviews

The current processing rules in `AGENTS.md` apply this distinction to new assets.
Step 8 applies the same classification to configured library membership. The
forty-asset classifications above remain historical evidence; newly generated
captions await review and do not inherit an approval or a clear visual review.
Expanded coverage and pending reviews are reported separately in
`docs/step8-verification.json`.
Intentionally ungenerated descriptions have `processing.caption=pending` and
null description/provenance. They remain eligible for a later generation run;
this state does not downgrade failed, partially generated, or unusable captions.
Record a caption review using `findings`, for example:

```json
{
  "observations": "Apple identity and main colors agree.",
  "findings": [
    {
      "severity": "review_note",
      "evidence": "The exact polygon count is uncertain.",
      "reason": "Apple identity remains useful; exact facet count is a minor detail."
    }
  ]
}
```

`scripts/record_caption_review.py` preserves that explicit severity and rationale
in caption provenance. Future usable captions do not need entries in the pilot's
historical reclassification file. Newly recorded severity takes precedence over
that older file; it belongs to the reviewed caption's provenance. Legacy `faults`
strings are accepted as unclassified warnings, rather than automatically becoming
`faulty`. Ambiguous severity stays a warning. Review-only findings cannot use a
`fault` severity or approve owner review. Generated review pages use the same
classification when showing notes, warnings and real caption failures.

The review-page checker validates current severity banners and can still verify
preserved historical pages under an explicit historical format. It saves a new
receipt instead of overwriting the Step 4 receipt. Future measurement summaries
use `caption_quality_counts` and `visual_review_findings_assets`; the presence of
a review finding is no longer reported as a faulty asset.

Source/import, dependency, image decoding, generation, schema/publication or
runtime failures remain actual processing faults. Preserve partial results and
recorded evidence; no inference retries, caption rewrites or full-library import
are triggered by changing these rules. Existing caption generation schema and
model settings remain unchanged. The original numbered implementation plan is
historical; current caption handling follows `AGENTS.md` and this document.

The desktop detail displays caption warnings/notes separately from source,
preview, runtime and actual caption faults. Original findings are expandable
under “Original caption review evidence.” Earlier static review pages and receipts
retain their historical wording. No catalog, caption result, correction overlay,
embedding/index, original asset, dependency pin, or model file is rewritten.

Verification: `data/caption-classification/{before,after}.json` retains protected
input hashes and all 40 keyword-query rankings, plus classification parity across
the real pilot. Focused synthetic tests cover stale/invalid classifications,
failed/missing descriptions, source-fault preservation and shared search behavior.
The actual Windows rendering/STDIO checks are retained separately under
`data/gui/caption-classification/`.
