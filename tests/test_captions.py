from copy import deepcopy
import json
from pathlib import Path

import pytest

from local_asset_library.captions import file_hash
from local_asset_library.config import Config, ConfigError
from local_asset_library.captions import (validate_caption, parse_caption, infer_caption,
    image_inputs, merge_record, effective_caption, overlay_for, reuse_caption,
    verify_calibration, caption_fingerprint)


def caption():
    return {"identity": {"label": "unknown upright object", "certainty": "uncertain"},
            "description": "An upright object has a broad faceted upper section above a narrower supporting column. Its outline is uneven and angular, with large flat regions and a few small protrusions. The visible surfaces are predominantly brown, with lighter faces on the upper region and darker areas underneath. The different views show the same compact form from several angles. No distinct markings are visible. The precise identity cannot be established confidently from these views alone.",
            "shape": ["broad top over narrow column"], "colors": ["brown"],
            "parts": ["upper section", "supporting column"], "style": ["faceted stylized object"],
            "distinguishing_features": ["uneven angular outline"],
            "uncertainties": ["could be a mushroom or another stylized prop"],
            "suggested_uses": ["hypothetical scenery prop"]}


class Backend:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []
    def generate(self, inputs, prompt, max_new_tokens):
        self.calls.append((inputs, prompt, max_new_tokens))
        value = next(self.outputs)
        if isinstance(value, Exception):
            raise value
        return value, {"elapsed_seconds": 0.01}


def test_uncertainty_and_uses_remain_separate():
    result = infer_caption(Backend([json.dumps(caption())]), [{"pixels": "real"}], "inspect images")
    assert result["status"] == "complete"
    assert result["description"]["identity"]["certainty"] == "uncertain"
    assert result["description"]["uncertainties"]
    assert "suggested_uses" not in result["description"]
    assert result["suggested_uses"] == ["hypothetical scenery prop"]


@pytest.mark.parametrize('words,accepted',[(9,False),(10,True),(59,True),(60,True),(170,True),(171,False)])
def test_description_word_boundaries(words,accepted):
    value=caption()
    value['description']=' '.join(['brown']*words)
    if accepted:
        assert parse_caption(json.dumps(value))['description']==value['description']
    else:
        with pytest.raises(ValueError,match='10-170 words'):
            parse_caption(json.dumps(value))


def test_short_caption_still_requires_consistent_identity_and_visual_fields():
    value=caption()
    value['description']='A brown faceted object has a broad top and narrow stem.'
    assert validate_caption(value)
    value['identity']={'label':'unknown object','certainty':'probable'}
    with pytest.raises(ValueError,match='Unknown identity'):
        validate_caption(value)
    value=caption()
    value['description']='A brown faceted object has a broad top and narrow stem.'
    value['colors']=[]
    with pytest.raises(ValueError,match='Core visual attributes'):
        validate_caption(value)


@pytest.mark.parametrize("raw", ["{}", "not json", '{"identity":',
    json.dumps({**caption(), "technical": {"triangles": 12}}),
    json.dumps({**caption(), "uncertainties": []}),
    json.dumps({**caption(), "colors": "brown"}),
    json.dumps({**caption(), "identity": {"label": "unknown object", "certainty": "probable"}}),
    json.dumps({**caption(), "parts": ["ideal for racing gameplay"]}),
    json.dumps({**caption(), "description": "An unrigged mesh has 120 triangles."}),
    '{"identity":{},"identity":{}}'])
def test_malformed_or_unsupported_claims_rejected(raw):
    with pytest.raises(ValueError):
        parse_caption(raw)


def test_corrective_retry_changes_prompt_and_preserves_input():
    inputs = [{"path": "actual.png", "sha256": "real"}]
    backend = Backend(["{}", json.dumps(caption())])
    result = infer_caption(backend, inputs, "Original image instruction")
    assert result["status"] == "complete" and len(result["attempts"]) == 2
    assert backend.calls[0][0] is inputs and backend.calls[1][0] is inputs
    assert backend.calls[0][1] != backend.calls[1][1]
    assert backend.calls[1][2] > backend.calls[0][2]


def test_retry_exhaustion_never_uses_filename_fallback():
    backend = Backend(["{}", "{}"])  # no third attempt
    result = infer_caption(backend, [], "filename hint must never become a caption")
    assert result["status"] == "failed" and result["description"] is None
    assert len(result["attempts"]) == 2 and result["suggested_uses"] == []


@pytest.mark.parametrize("error", [RuntimeError("CUDA OOM"), TimeoutError("timeout"), OSError("invalid image")])
def test_runtime_fault_not_retried(error):
    backend = Backend([error])
    result = infer_caption(backend, [], "inspect")
    assert result["description"] is None and len(backend.calls) == 1
    assert type(error).__name__ in result["attempts"][0]["error"]


@pytest.mark.parametrize("status", ["failed", "unsupported"])
def test_persisted_unchanged_fault_requires_explicit_retry(status):
    record = {"caption_provenance": {"fingerprint": "same"}, "processing": {"caption": status}}
    assert reuse_caption(record, "same")
    assert not reuse_caption(record, "changed")
    assert not reuse_caption(record, "same", retry_faults=True)


def config_fixture(tmp_path):
    root, source = tmp_path / "project", tmp_path / "source"
    root.mkdir(); source.mkdir()
    return Config(root, source, None)


def test_multiview_requires_real_hashes_and_project_boundary(tmp_path):
    config = config_fixture(tmp_path)
    previews = []
    for label in ("front", "side", "three_quarter"):
        path = config.output_path("data", label + ".png")
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(label.encode())
        previews.append({"origin": "rendered", "path": "data/" + path.name,
                         "sha256": file_hash(path), "view_label": label,
                         "coordinate_convention": "test convention"})
    record = {"technical": {"inspected": True}, "processing": {"inspection": "complete"}, "previews": previews}
    assert len(image_inputs(config, record)) == 3
    one = deepcopy(record); one["previews"] = previews[:1]
    with pytest.raises(ConfigError, match="distinct actual"):
        image_inputs(config, one)
    previews[0]["path"] = "data/../escape.png"
    with pytest.raises(ConfigError):
        image_inputs(config, record)
    previews[0]["path"] = "data/front.png"
    config.output_path("data", "front.png").write_bytes(b"changed")
    with pytest.raises(ConfigError, match="hash mismatch"):
        image_inputs(config, record)
    config.output_path("data", "front.png").unlink()
    with pytest.raises(ConfigError, match="missing"):
        image_inputs(config, record)


def test_measured_facts_faults_and_owner_edits_survive_regeneration(tmp_path):
    config = config_fixture(tmp_path)
    record = {"asset_id": "fixture", "technical": {"triangles": 231, "units": "unknown"},
              "inspection_run": {"source_faults": [{"kind": "overlap"}]},
              "embeddings": [], "license_evidence": ["supplied"], "owner_overlay": {},
              "processing": {"caption": "pending", "inspection": "complete"}}
    overlay, path = overlay_for(config, record)
    overlay["description"] = {"identity": {"label": "owner corrected mushroom", "certainty": "probable"}}
    overlay["notes"] = "Owner correction example"
    path.write_text(json.dumps(overlay), encoding="utf-8")
    before_bytes = path.read_bytes()
    outcome = infer_caption(Backend([json.dumps(caption())]), [], "inspect")
    first = merge_record(record, outcome, {"revision": "one"}, overlay)
    second = merge_record(first, outcome, {"revision": "two"}, overlay_for(config, first)[0])
    assert path.read_bytes() == before_bytes
    assert second["technical"] == record["technical"]
    assert second["inspection_run"] == record["inspection_run"]
    assert second["license_evidence"] == record["license_evidence"]
    assert second["owner_overlay"] == overlay
    assert second["description"]["identity"]["label"] == "unknown upright object"
    assert second["effective_caption"]["description"]["identity"]["label"] == "owner corrected mushroom"
    assert second["owner_overlay"]["caption_review"] == "pending"
    overlay["description"]["technical"] = {"triangles": 0}
    with pytest.raises(ValueError):
        effective_caption(second, overlay)


def test_pilot_gate_rejects_absent_and_stale_review(tmp_path, monkeypatch):
    import local_asset_library.captions as module
    config = config_fixture(tmp_path)
    prompt_path = config.project_root / "prompt.txt"
    prompt_path.write_text("inspect actual views")
    backend = Backend([])
    backend.contract = {"model": "fixture"}
    backend.settings = {"seed": 0}
    manifest = {"assets": [{"asset_id": str(i)} for i in range(40)]}
    with pytest.raises(ConfigError, match="current calibration"):
        verify_calibration(config, backend, "inspect actual views", prompt_path, manifest)
    receipt_path = config.output_path("data", "captions/calibration-review.json")
    receipt_path.parent.mkdir(parents=True)
    receipt = {"status": "technically_reviewed", "approved_prompt_sha256": file_hash(prompt_path),
               "receipts": [{"asset_id": str(i), "caption_fingerprint": "same", "input_views": ["pixels"]}
                            for i in module.CALIBRATION_INDICES]}
    receipt_path.write_text(json.dumps(receipt))
    monkeypatch.setattr(module, "detail", lambda *_: {})
    monkeypatch.setattr(module, "caption_fingerprint", lambda *_: "changed")
    with pytest.raises(ConfigError, match="changed"):
        verify_calibration(config, backend, "inspect actual views", prompt_path, manifest)
    monkeypatch.setattr(module, "caption_fingerprint", lambda *_: "same")
    monkeypatch.setattr(module, "image_inputs", lambda *_: ["pixels"])
    verify_calibration(config, backend, "inspect actual views", prompt_path, manifest)
    monkeypatch.setattr(module, "image_inputs", lambda *_: ["different pixels"])
    with pytest.raises(ConfigError, match="images changed"):
        verify_calibration(config, backend, "inspect actual views", prompt_path, manifest)


def test_unicode_caption_survives_parse_and_record_merge(tmp_path):
    value = caption()
    value["description"] += " The surface is brown—gray, with an irregular outline."
    parsed = parse_caption(json.dumps(value, ensure_ascii=False))
    assert "brown—gray" in parsed["description"]


def test_visual_faults_visible_and_escaped_in_review(tmp_path, monkeypatch):
    from local_asset_library import caption_review
    path = tmp_path / "review.html"
    path.write_text('<p>asset_fixture — complete </p><details>provenance</details>', encoding="utf-8")
    monkeypatch.setattr(caption_review, "detail", lambda *_: {"asset_id": "asset_fixture",
        "processing": {"caption": "complete"}, "description": {"description": "Useful description"},
        "caption_provenance": {"visual_faults": [{"evidence": "Unsupported <script> count"}]}})
    from local_asset_library.config import Config
    caption_review.highlight_faults(Config(tmp_path, tmp_path / "source", None), path, [{"asset_id": "asset_fixture"}])
    result = path.read_text(encoding="utf-8")
    assert "Caption warning — owner review pending" in result
    assert "&lt;script&gt;" in result and "<script>" not in result
