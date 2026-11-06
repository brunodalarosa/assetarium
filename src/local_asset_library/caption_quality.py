"""Current caption severity, separate from immutable generation/review evidence."""
from .catalog import digest


CLASSIFICATION_PATH = "docs/caption-review-classification.json"
LEVELS = {"review_note", "warning"}


def review_findings(note):
    """Normalize future review input; legacy unclassified findings are warnings.

    Reviewers explicitly provide severity and rationale. No heuristic guesses or
    successful retrieval claims can turn failed generation into success.
    """
    if not isinstance(note, dict):
        return []
    if "findings" in note:
        if note.get("faults"):
            raise ValueError("Use findings or legacy faults, not both")
        findings = note["findings"]
        if not isinstance(findings, list):
            raise ValueError("Caption findings must be a list")
        for finding in findings:
            if (not isinstance(finding, dict) or set(finding) != {"severity", "evidence", "reason"}
                    or not isinstance(finding["severity"], str) or finding["severity"] not in LEVELS
                    or any(not isinstance(finding[k], str) or not finding[k].strip() for k in ("evidence", "reason"))):
                raise ValueError("Caption findings require review_note/warning, evidence and reason")
    else:
        faults = note.get("faults", [])
        if not isinstance(faults, list) or any(not isinstance(f, str) or not f.strip() for f in faults):
            raise ValueError("Legacy caption findings must be nonempty strings")
        findings = [{"severity": "warning", "evidence": f,
                     "reason": "Unclassified visual review finding; inspect the retained evidence."} for f in faults]
    return [{**f, "status": f["severity"], "kind": "caption_visual_claim",
             "repair": "not_performed", "owner_review": "pending"} for f in findings]


def review_digest(record):
    provenance = record.get("caption_provenance") or {}
    return digest({"description": record.get("description"),
                   "fingerprint": provenance.get("fingerprint"),
                   "visual_faults": provenance.get("visual_faults", [])})


def caption_quality(config, record):
    """Unclassified/stale findings remain warnings; failed captions remain faults.

    Classification never controls source usability, ranking, or owner approval.
    No generated evidence or catalog record is modified.
    """
    findings = (record.get("caption_provenance") or {}).get("visual_faults", [])
    issues = []
    for finding in findings:
        classified = (isinstance(finding, dict) and isinstance(finding.get("severity"), str) and finding.get("severity") in LEVELS
                      and isinstance(finding.get("reason"), str) and bool(finding["reason"].strip()))
        issues.append({"severity": finding["severity"] if classified else "warning",
                       "evidence": finding.get("evidence", str(finding)) if isinstance(finding, dict) else str(finding),
                       "reason": finding["reason"] if classified else "Finding has not been classified for this caption."})
    classification = ("recorded" if findings and all(isinstance(f, dict) and isinstance(f.get("severity"), str) and f.get("severity") in LEVELS
                      and isinstance(f.get("reason"), str) and f["reason"].strip() for f in findings)
                      else "unclassified" if findings else "no_findings")
    if findings and classification != "recorded":
        try:
            path = (config.project_root / CLASSIFICATION_PATH).resolve()
            if not path.is_relative_to(config.project_root):
                raise ValueError("Classification path escapes project")
            if config.sources_registry:
                from .sources import get_source, bound
                local = bound(config, get_source(config, record['pack_id'])).output_path('data','reviews/caption-classification.json')
                if local.exists():
                    path = local
            if path.is_file():
                from .library_cache import cached_json
                saved = cached_json(path)
                if saved.get("schema_version") != 1 or not isinstance(saved.get("assets"), dict):
                    raise ValueError("Unsupported classification record")
                entry = saved["assets"].get(record["asset_id"])
                if entry is not None:
                    if entry.get("review_digest") != review_digest(record):
                        raise ValueError("Caption or review evidence changed; classification is stale")
                    classified = entry.get("issues")
                    if (not isinstance(classified, list) or len(classified) != len(issues)
                            or any(not isinstance(c, dict) or c.get("severity") not in LEVELS
                                   or c.get("evidence") != original["evidence"]
                                   or not isinstance(c.get("reason"), str) or not c["reason"].strip()
                                   for c, original in zip(classified, issues))):
                        raise ValueError("Classification does not cover the original findings")
                    issues = [{k: c[k] for k in ("severity", "evidence", "reason")} for c in classified]
                    classification = "classified"
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            classification = "unavailable_or_stale"
            for issue in issues:
                issue["severity"] = "warning"
                issue["reason"] = str(exc)
    # The validator's own notes (use wording) are classified when written; reviews never replace them.
    issues += [{k: note[k] for k in ("severity", "evidence", "reason")}
               for note in (record.get("caption_provenance") or {}).get("validation_notes", [])]
    processing = (record.get("processing") or {}).get("caption", "missing")
    description = record.get("description")
    if (processing == 'pending' and description is None
            and not record.get('caption_provenance') and not issues
            and not (record.get('stage_faults') or {}).get('caption')):
        return {'status': 'pending', 'caption_faulty': False,
                'classification': 'not_processed', 'issues': []}
    usable = (processing == "complete" and isinstance(description, dict)
              and isinstance(description.get("description"), str) and bool(description["description"].strip()))
    if not usable:
        issues.append({"severity": "fault", "evidence": "No usable caption; processing state: " + str(processing),
                       "reason": "Caption generation is incomplete, failed, or its description is missing."})
    status = ("fault" if not usable else "warning" if any(i["severity"] == "warning" for i in issues)
              else "review_note" if issues else "clear")
    return {"status": status, "caption_faulty": status == "fault",
            "classification": classification, "issues": issues}


def caption_summary(config, record):
    quality = caption_quality(config, record)
    return {"caption_status": quality["status"], "caption_faulty": quality["caption_faulty"]}
