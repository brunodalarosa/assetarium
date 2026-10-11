"""Presentation-only review flags; does not change generation fingerprints."""
import html
import re

from .catalog import detail


def highlight_faults(config, path, assets):
    page = path.read_text(encoding="utf-8")
    for asset in assets:
        record = detail(config, asset["asset_id"])
        faults = (record.get("caption_provenance") or {}).get("visual_faults", [])
        if not faults:
            continue
        expression = r"(<p>" + re.escape(html.escape(asset["asset_id"])) + r" —[^<]*</p>)"
        banner = '<p><strong>Caption visual claims: faulty — owner review pending.</strong></p><ul>'
        banner += "".join('<li>' + html.escape(fault["evidence"]) + '</li>' for fault in faults) + '</ul>'
        page, count = re.subn(expression, lambda m: m[0] + banner, page, count=1)
        if count != 1:
            raise ValueError("Missing asset status in review artifact")
    path.write_text(page, encoding="utf-8")
    return path
