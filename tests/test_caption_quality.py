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


def test_validator_use_notes_are_review_notes_beside_classified_findings(tmp_path):
    config, item = Config(tmp_path, tmp_path / "source", None), record()
    note = {"severity": "review_note", "evidence": 'description: "designed for use in games."',
            "reason": "Use wording in visual observations."}
    item["caption_provenance"]["validation_notes"] = [note]
    write_classification(config, [item], "warning")
    quality = caption_quality(config, item)
    assert quality["classification"] == "classified" and quality["issues"][1] == note
    assert quality["status"] == "warning" and not quality["caption_faulty"]
    item["caption_provenance"]["visual_faults"] = []
    quality = caption_quality(config, item)
    assert quality["status"] == "review_note" and quality["issues"] == [note] and not quality["caption_faulty"]


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


def test_ungenerated_description_is_pending_and_recorded_failure_stays_fault(tmp_path):
    config, item = Config(tmp_path, tmp_path / 'source', None), record()
    item.update(description=None, caption_provenance=None)
    item['processing']['caption'] = 'pending'
    quality = caption_quality(config, item)
    assert quality['status'] == 'pending' and not quality['caption_faulty']
    item['stage_faults'] = {'caption': {'error': 'Recorded generation failure'}}
    assert caption_quality(config, item)['caption_faulty']


def test_no_findings_is_not_owner_approval(tmp_path):
    item = record()
    item["caption_provenance"]["visual_faults"] = []
    item["owner_overlay"] = {"caption_review": "pending"}
    assert caption_quality(Config(tmp_path, tmp_path / "source", None), item)["status"] == "clear"
    assert item["owner_overlay"]["caption_review"] == "pending"


@pytest.mark.parametrize("severity", ["review_note", "warning"])
def test_future_review_preserves_severity_without_recorded_classification(tmp_path, severity):
    config, item = Config(tmp_path, tmp_path / "source", None), record()
    supplied = {"findings": [{"severity": severity, "evidence": "Uncertain <script> detail", "reason": "Explicit reviewer rationale."}]}
    before = deepcopy(supplied)
    # A future review for an existing asset must supersede its old classified overlay.
    write_classification(config, [item])
    item["caption_provenance"]["visual_faults"] = review_findings(supplied)
    quality = caption_quality(config, item)
    assert quality["status"] == severity and quality["classification"] == "recorded"
    assert not quality["caption_faulty"] and supplied == before
    assert item["caption_provenance"]["visual_faults"][0]["owner_review"] == "pending"


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
