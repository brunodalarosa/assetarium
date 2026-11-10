---
tags: [architecture]
parent: "[Architecture](../Architecture.md)"
status: draft
verified: 2026-11-10
branch: feature/audit-simplify
level: system
code: [caption_quality.py, scripts/record_caption_review.py]
---
# Caption severity in the desktop app and agent results

> How a finding about a description is graded, and what each grade does. `AGENTS.md` and the
> `local-asset-library` skill point here. Rewritten on 2026-11-10; the pilot's review counts it used to
> carry are in git (commit `af02e91`).

Up: [Architecture](../Architecture.md) · Where in code: [Descriptions](../../Notebook/Processing/Descriptions.md) ·
The description itself: [caption contract](../../../docs/caption-contract.md).

A successful search or a usable asset does not need every detail of its description to be right.
**A finding never excludes an otherwise usable asset and never changes search ranking.**

| Status | Meaning | In the app |
| --- | --- | --- |
| `clear` | No recorded finding. This is not owner approval | No badge |
| `review_note` | A minor precision or an uncertain detail; the broad identity is still useful | A note in asset detail; no badge |
| `warning` | A descriptive error or interpretation that could mislead a choice | A warning badge and an explanation in detail |
| `fault` | Generation failed or was incomplete, or there is no usable description | A fault in detail with the recorded reason |
| `pending` | Generation has not started; there is no provenance and no fault | No badge; counted as pending |

Examples: an apple whose exact polygon count is uncertain is a note; a road bridge described as furniture is
a warning; a description that never finished is a fault.

## Rules

- Do not mark a usable description or asset faulty only because a visual detail is uncertain, an exact
  count is unsupported, a material is inferred, or owner review is pending.
- Minor precision or appearance uncertainty is a `review_note`. A meaningful identity, color or structure
  error is a `warning`. **When the severity is unclear, keep a warning** with its evidence and reason.
- `fault` is only for failed or incomplete generation, or a missing or unusable description. A review
  finding cannot use it, and cannot approve owner review.
- A description that was never generated is `pending`, with null description and provenance. That state
  never downgrades a failed or unusable one.
- Changing these grades reruns no model, rewrites no description, retries nothing and touches no original.
- Real source, dependency, decoding, generation, publication or runtime failures are processing faults and
  follow the fault policy in `AGENTS.md`, not this table.

## Recording a review

A review input has a `scope` and an `assets` object keyed by asset ID. Each asset uses `findings`:

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

```powershell
.\scripts\mcp-runtime.ps1 run --locked --no-sync --offline --project runtime/mcp python scripts/record_caption_review.py library --notes data/review-input.json
```

`scripts/record_caption_review.py` checks the saved results and image hashes, keeps the original provenance
before it changes working data, stores each severity and reason in the description's provenance, keeps the
owner's review states and never reruns a model. Publish afterwards. Older `faults` strings without a severity
are accepted as warnings, never as `fault`.

## Where grades come from

- **A recorded review** (above): the severity stored with the description wins.
- **The validator.** Use wording in a description ("designed for use in games") is saved as a `review_note`
  in `caption_provenance.validation_notes` when the description is written. These sit beside review findings
  and a later review never replaces them.
- **`docs/caption-review-classification.json`**: severities recorded for the first reviewed assets, each bound
  to the asset ID and a digest of the description, its generation fingerprint and the original findings. A
  changed description, a missing or malformed entry leaves the findings visible as warnings. This file cannot
  downgrade a failed description.

## What the interfaces show

One implementation, `caption_quality`, serves the desktop app, search and the MCP server.

- Search results and basic detail carry `caption_status` and the boolean `caption_faulty`, which means an
  unusable description, not the presence of a note.
- With `include_metadata=true`, agent detail adds `metadata.caption_quality`: the graded issues with their
  original evidence and reasons. `caption_fault_evidence` still returns the original, ungraded findings.
- The app shows notes and warnings apart from source, preview and runtime faults; the original findings open
  under "Original caption review evidence".
- The owner's review of a description and of its artistic fit is a separate state that no grade sets.
