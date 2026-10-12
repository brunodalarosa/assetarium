"""Severity is nonblocking presentation metadata; immutable evidence stays intact."""
from copy import deepcopy
import json

import pytest

from test_retrieval import indexed
from test_mcp_assets import update
from local_asset_library.caption_quality import caption_quality, caption_summary, review_digest, review_findings
from local_asset_library.config import Config
from local_asset_library.desktop_service import DesktopService
from local_asset_library.mcp_assets import AssetService


def record():
    return {"asset_id": "asset_" + "a" * 32, "processing": {"caption": "complete"},
            "description": {"description": "A useful synthetic caption."},
            "caption_provenance": {"fingerprint": "synthetic", "visual_faults": [{"evidence": "Uncertain small detail"}]}}


def write_classification(config, records, severity="review_note"):
    path = config.project_root / "docs/caption-review-classification.json"
    path.parent.mkdir(exist_ok=True)
    assets = {r["asset_id"]: {"review_digest": review_digest(r),
              "issues": [{"severity": severity, "evidence": f["evidence"], "reason": "Synthetic classification."}
                         for f in r["caption_provenance"]["visual_faults"]]} for r in records}
    path.write_text(json.dumps({"schema_version": 1, "assets": assets}), encoding="utf-8")
    return path


@pytest.mark.parametrize("severity", ["review_note", "warning"])
def test_classification_preserves_raw_evidence_and_caption(tmp_path, severity):
    config, item = Config(tmp_path, tmp_path / "source", None), record()
    path = write_classification(config, [item], severity)
    before, saved = deepcopy(item), path.read_bytes()
    quality = caption_quality(config, item)
    assert quality["status"] == severity and not quality["caption_faulty"]
    assert quality["issues"][0]["evidence"] == item["caption_provenance"]["visual_faults"][0]["evidence"]
    assert quality["classification"] == "classified"
    assert item == before and path.read_bytes() == saved


@pytest.mark.parametrize("change", ["missing", "stale_caption", "stale_evidence", "invalid_json", "unknown_level", "partial", "reordered", "bad_schema", "bad_assets"])
def test_unclassified_or_stale_notes_stay_visible_as_warnings(tmp_path, change):
    config, item = Config(tmp_path, tmp_path / "source", None), record()
    item["caption_provenance"]["visual_faults"].append({"evidence": "Another detail"})
    if change != "missing":
        path = write_classification(config, [item])
        content = json.loads(path.read_text())
        entry = content["assets"][item["asset_id"]]
        if change == "stale_caption": item["description"]["description"] = "Changed caption."
        elif change == "stale_evidence": item["caption_provenance"]["visual_faults"][0]["evidence"] = "Changed finding"
        elif change == "unknown_level": entry["issues"][0]["severity"] = "clear"
        elif change == "partial": entry["issues"].pop()
        elif change == "reordered": entry["issues"].reverse()
        elif change == "bad_schema": content["schema_version"] = 99
        elif change == "bad_assets": content["assets"] = []
        path.write_text("{" if change == "invalid_json" else json.dumps(content), encoding="utf-8")
    quality = caption_quality(config, item)
    assert quality["status"] == "warning" and not quality["caption_faulty"]
    assert len(quality["issues"]) == 2
    assert all(i["severity"] == "warning" for i in quality["issues"])
    assert all(i["reason"] for i in quality["issues"])


@pytest.mark.parametrize("processing,description", [("failed", {"description": "Partial"}), ("pending", {"description": "Partial"}),
                                                    ("complete", None), ("complete", {"description": " "}), ("complete", {"description": []})])
def test_classification_cannot_downgrade_unusable_captions(tmp_path, processing, description):
    config, item = Config(tmp_path, tmp_path / "source", None), record()
    item["processing"]["caption"], item["description"] = processing, description
    write_classification(config, [item])
    quality = caption_quality(config, item)
    assert quality["status"] == "fault" and quality["caption_faulty"]
    assert any(i["severity"] == "fault" for i in quality["issues"])


def test_no_findings_is_not_owner_approval(tmp_path):
    item = record()
    item["caption_provenance"]["visual_faults"] = []
    item["owner_overlay"] = {"caption_review": "pending"}
    assert caption_quality(Config(tmp_path, tmp_path / "source", None), item)["status"] == "clear"
    assert item["owner_overlay"]["caption_review"] == "pending"


@pytest.mark.parametrize("severity", ["review_note", "warning"])
def test_future_review_preserves_severity_without_pilot_classification(tmp_path, severity):
    config, item = Config(tmp_path, tmp_path / "source", None), record()
    supplied = {"findings": [{"severity": severity, "evidence": "Uncertain <script> detail", "reason": "Explicit reviewer rationale."}]}
    before = deepcopy(supplied)
    # A future review for an existing asset must supersede its old pilot overlay.
    write_classification(config, [item])
    item["caption_provenance"]["visual_faults"] = review_findings(supplied)
    quality = caption_quality(config, item)
    assert quality["status"] == severity and quality["classification"] == "recorded"
    assert not quality["caption_faulty"] and supplied == before
    assert item["caption_provenance"]["visual_faults"][0]["owner_review"] == "pending"
    from local_asset_library import caption_review
    from unittest.mock import patch
    page = tmp_path / "review.html"
    page.write_text('<p>' + item['asset_id'] + ' — complete </p>', encoding="utf-8")
    with patch.object(caption_review, "detail", return_value=item):
        caption_review.highlight_faults(config, page, [item])
    rendered = page.read_text(encoding="utf-8")
    assert ("Caption warning" if severity == "warning" else "Caption review note") in rendered
    assert "faulty" not in rendered and "&lt;script&gt;" in rendered and "<script>" not in rendered
    counts = caption_review.check_severity_banners(config, rendered, [item])
    assert counts["format"] == "current" and counts["caption_banner_counts"][severity] == 1


def test_future_legacy_review_is_a_warning_and_processing_failure_stays_fault(tmp_path):
    item = record()
    item["caption_provenance"]["visual_faults"] = review_findings({"faults": ["Original unclassified concern"]})
    config = Config(tmp_path, tmp_path / "source", None)
    assert caption_quality(config, item)["status"] == "warning"
    assert item["caption_provenance"]["visual_faults"][0]["status"] == "warning"
    item["processing"]["caption"] = "failed"
    assert caption_quality(config, item)["caption_faulty"]


@pytest.mark.parametrize("note", [{"findings": [{"severity": "fault", "evidence": "Minor", "reason": "Wrong severity"}]},
                                 {"findings": [{"severity": "review_note", "evidence": "Minor", "reason": ""}]},
                                 {"findings": [] , "faults": ["Cannot drop this"]},
                                 {"findings": [{"severity": [], "evidence": "Minor", "reason": "Invalid"}]},
                                 {"findings": "invalid"}, {"faults": [None]}])
def test_future_review_rejects_invalid_severity_or_silent_evidence_loss(note):
    with pytest.raises(ValueError): review_findings(note)


def test_review_writer_publishes_nonfault_severity_and_retains_source_facts(indexed, monkeypatch, tmp_path):
    import runpy
    from pathlib import Path
    from local_asset_library import config as config_module
    from local_asset_library.catalog import detail
    config, _, records = indexed
    item = records[0]
    identifier = item["asset_id"]
    result = {"status": "complete", "description": item["description"], "suggested_uses": item["suggested_uses"],
              "provenance": {"fingerprint": "synthetic-caption", "input_views": []}}
    folder = config.output_path("data", "captions/pilot-v2")
    folder.mkdir(parents=True)
    (folder / (identifier + ".json")).write_text(json.dumps(result), encoding="utf-8")
    config.output_path("data", "captions/pilot-v2-report.json").write_text(
        json.dumps({"outcomes": [{"asset_id": identifier}]}), encoding="utf-8")
    notes = tmp_path / "notes.json"
    notes.write_text(json.dumps({"scope": "Synthetic review only", "assets": {identifier: {
        "observations": "Synthetic object identity agrees", "findings": [{"severity": "review_note",
        "evidence": "Exact count uncertain", "reason": "Minor detail"}]}}}), encoding="utf-8")
    monkeypatch.setattr(config_module, "load_config", lambda *_: config)
    monkeypatch.setattr("sys.argv", ["record_caption_review.py", "pilot-v2", "--notes", str(notes)])
    script = Path(__file__).resolve().parents[1] / "scripts/record_caption_review.py"
    runpy.run_path(str(script), run_name="__main__")
    published = detail(config, identifier)
    assert published["processing"]["caption"] == "complete"
    assert published["description"] == item["description"] and published["technical"] == item["technical"]
    assert published["files"] == item["files"]
    assert published["caption_provenance"]["visual_faults"][0]["status"] == "review_note"
    assert published["caption_provenance"]["visual_faults"][0]["owner_review"] == "pending"
    assert caption_quality(config, published)["status"] == "review_note"


def test_shared_browse_search_detail_flags_do_not_change_ranking_or_usability(indexed):
    config, backend, records = indexed
    service = AssetService(config, backend=backend)
    arguments = {"query": "red object", "mode": "keyword_description"}
    before = service.execute("search_assets", arguments)[0]
    modified = deepcopy(records)
    for index, item in enumerate(modified):
        item["caption_provenance"]["visual_faults"] = [{"evidence": "Small detail"}]
        if index == 0: item["inspection_run"] = {"source_faults": [{"kind": "Retained source fault"}]}
        update(config, item)
    write_classification(config, modified)
    path = config.project_root / "docs/caption-review-classification.json"
    manifest = json.loads(path.read_text())
    manifest["assets"][modified[1]["asset_id"]]["issues"][0]["severity"] = "warning"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    after = service.execute("search_assets", arguments)[0]
    assert [(r["asset_id"], r["score"], r["matching_channels"]) for r in before["results"]] == [
           (r["asset_id"], r["score"], r["matching_channels"]) for r in after["results"]]
    assert after["serialized_characters"] <= 6000 and len(after["results"]) == 5
    desktop = DesktopService(config)
    browse = {r["asset_id"]: r for r in desktop.browse()["items"]}
    for item in modified[:2]:
        expected = caption_summary(config, item)
        payload, _, _ = service.execute("get_asset", {"asset_id": item["asset_id"], "include_metadata": True})
        ui = desktop.asset(item["asset_id"])["payload"]["presentation"]
        assert payload["usable"]
        assert all(all(response[k] == value for k, value in expected.items()) for response in (payload, ui, browse[item["asset_id"]]))
        assert payload["metadata"]["caption_quality"] == ui["caption_quality"]
        assert payload["metadata"]["caption_fault_evidence"] == item["caption_provenance"]["visual_faults"]
    assert browse[modified[0]["asset_id"]]["source_faulty"]
    assert after["results"][0]["caption_owner_review"] == "pending"
