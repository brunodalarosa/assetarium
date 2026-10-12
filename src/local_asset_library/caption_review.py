"""Presentation-only review flags; does not change generation fingerprints."""
import html
import re

from .catalog import detail
from .caption_quality import caption_quality

BANNER_LABELS = {"fault": "Caption fault", "warning": "Caption warning", "review_note": "Caption review note"}


def check_severity_banners(config, page, records):
    """Check current pages or preserved historical pages without rewriting either."""
    if 'Caption visual claims: faulty' in page:
        expected = sum(bool((r.get('caption_provenance') or {}).get('visual_faults')) for r in records)
        assert page.count('Caption visual claims: faulty') == expected
        return {"format": "historical", "visible_historical_fault_banners": expected}
    counts = {status: sum(caption_quality(config, r)["status"] == status for r in records) for status in BANNER_LABELS}
    for status, label in BANNER_LABELS.items():
        assert page.count('<strong>' + label + ' — owner review pending.</strong>') == counts[status]
    return {"format": "current", "caption_banner_counts": counts}


def highlight_faults(config, path, assets):
    page = path.read_text(encoding="utf-8")
    for asset in assets:
        record = detail(config, asset["asset_id"])
        quality = caption_quality(config, record)
        if not quality["issues"]:
            continue
        expression = r"(<p>" + re.escape(html.escape(asset["asset_id"])) + r" —[^<]*</p>)"
        label = BANNER_LABELS[quality["status"]]
        banner = '<p><strong>' + label + ' — owner review pending.</strong></p><ul>'
        banner += "".join('<li>' + html.escape(issue["severity"] + ': ' + issue["evidence"]) + '</li>' for issue in quality["issues"]) + '</ul>'
        page, count = re.subn(expression, lambda m: m[0] + banner, page, count=1)
        if count != 1:
            raise ValueError("Missing asset status in review artifact")
    path.write_text(page, encoding="utf-8")
    return path
