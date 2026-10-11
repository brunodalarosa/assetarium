from pathlib import Path
import os
import sys

import pytest

from local_asset_library.config import Config, ConfigError
from local_asset_library.inspection import choose_source, inspect_pilot, reuse_result, run_process, validate_result
from local_asset_library.render_math import duplicate_faces, framing


def test_duplicate_faces_use_positions_without_merging_nearby_geometry():
    vertices = [(0,0,0), (1,0,0), (0,1,0), (0,0,0), (1,0,0), (0,1,0), (0,1,0.000001)]
    assert duplicate_faces(vertices, [(0,1,2), (5,4,3), (0,1,6)]) == 1


@pytest.mark.parametrize("run", [
    {"status": "failed", "errors": ["timeout"]},
    {"status": "unsupported"},
    {"status": "failed", "errors": ["off-frame render"]},
    {"status": "complete", "source_faults": [{"kind": "geometry"}]},
    {"status": "complete", "source_faults": [{"kind": "other definition of faulty"}]},
])
def test_faults_are_retained_without_automatic_retries(run):
    record = {"inspection_run": {**run, "fingerprint": "same"}}
    assert reuse_result(record, "same")
    assert not reuse_result(record, "same", retry_faults=True)
    assert not reuse_result(record, "changed")


@pytest.mark.parametrize("minimum,maximum", [((-1,-2,-3),(1,2,3)), ((100,200,300),(100.01,240,300.01)), ((0,0,0),(1000,0.001,0.001))])
def test_framing_fits_all_views_at_same_scale(minimum, maximum):
    result = framing(minimum, maximum)
    assert result["ortho_scale"] > 0 and result["radius"] > 0
    assert result["center"] == tuple((a+b)/2 for a,b in zip(minimum,maximum))
    for view in result["views"].values():
        assert view["width"] / result["ortho_scale"] <= 1 - 2 * result["margin"] + 1e-10
        assert view["height"] / result["ortho_scale"] <= 1 - 2 * result["margin"] + 1e-10


def test_flat_models_add_top_view():
    assert "top" in framing((-1,-1,0),(1,1,0.01))["views"]
    assert "top" not in framing((-1,-1,0),(1,1,3))["views"]


@pytest.mark.parametrize("low,high", [((0,0,0),(0,0,0)), ((1,0,0),(0,1,1)), ((float('nan'),0,0),(1,1,1))])
def test_invalid_bounds_rejected(low, high):
    with pytest.raises(ValueError):
        framing(low, high)


def test_timeout_and_failure_do_not_poison_next_job(tmp_path):
    timed = run_process([sys.executable,"-c","import time; time.sleep(5)"], tmp_path, os.environ.copy(), 0.1)
    assert timed["timed_out"] and timed["returncode"] != 0
    failed = run_process([sys.executable,"-c","raise SystemExit(3)"], tmp_path, os.environ.copy(), 10)
    assert failed["returncode"] == 3 and not failed["timed_out"]
    good = run_process([sys.executable,"-c","print('next asset succeeded')"], tmp_path, os.environ.copy(), 10)
    assert good["returncode"] == 0 and "succeeded" in good["output"]


def test_source_choice_is_explicit_and_conservative():
    asset = {"pack":"other","name":"chair","files":[{"format":"obj","availability":"available","path":"chair.obj"}]}
    source, reason = choose_source(asset)
    assert source["format"] == "obj" and "alternate" in reason
    asset.update(pack="kenney_food-kit",name="apple")
    with pytest.raises(ConfigError, match="missing"):
        choose_source(asset)


def test_worker_result_identity_missing_metadata_and_boundaries(tmp_path):
    root, source = tmp_path / "project", tmp_path / "source"
    root.mkdir()
    source.mkdir()
    config = Config(root, source, None)
    job = {"asset_id":"fixture","source_path":"chair.obj","format":"obj","output":str(root / "data/job")}
    wrong = {"asset_id":"other","source_path":"chair.obj","format":"obj","status":"failed"}
    with pytest.raises(ConfigError, match="identity"):
        validate_result(config, job, wrong)
    result = {"asset_id":"fixture","source_path":"chair.obj","format":"obj","status":"complete","previews":[],"technical":None}
    with pytest.raises(ConfigError, match="metadata"):
        validate_result(config, job, result)
    result["technical"] = {"autoexec_enabled":False, "object_count":1, "mesh_object_count":1, "evaluated_instance_totals":{}, "world_bounds":{}, "units":{}, "materials":[], "armatures":[], "animation_clips":[]}
    with pytest.raises(ConfigError, match="views"):
        validate_result(config, job, result)
    result["previews"] = [{"view_label":v,"filename":"../../../outside.png","sha256":"none","quality":{"empty":False,"off_frame":False}} for v in ("front","side","three_quarter")]
    with pytest.raises((ConfigError, ValueError)):
        validate_result(config, job, result)


def test_worker_false_success_is_rejected(tmp_path):
    root, source = tmp_path / "project", tmp_path / "source"
    root.mkdir()
    source.mkdir()
    config = Config(root, source, None)
    job = {"asset_id":"fixture","source_path":"chair.obj","format":"obj","output":str(root / "data/job")}
    result = {"asset_id":"fixture","source_path":"chair.obj","format":"obj","status":"complete","technical":{"autoexec_enabled":False,"object_count":1,"mesh_object_count":1,"evaluated_instance_totals":{},"world_bounds":{},"units":{},"materials":[],"armatures":[],"animation_clips":[]},
              "previews":[{"view_label":v,"filename":v+".png","sha256":"none","quality":{"empty":True,"off_frame":False}} for v in ("front","side","three_quarter")]}
    with pytest.raises(ConfigError, match="invalid preview"):
        validate_result(config, job, result)


def test_full_pilot_requires_prior_representative_review(tmp_path, monkeypatch):
    root, source = tmp_path / "project", tmp_path / "source"
    root.mkdir()
    source.mkdir()
    config = Config(root, source, None)
    monkeypatch.setattr("local_asset_library.inspection.load_pilot", lambda config: {"assets":[]})
    with pytest.raises(ConfigError, match="Review the four"):
        inspect_pilot(config, "pilot")


def test_changed_loaded_dependency_rejected_on_cached_result(tmp_path):
    root, source = tmp_path / "project", tmp_path / "source"
    root.mkdir()
    source.mkdir()
    (source / "texture.png").write_bytes(b"changed fixture")
    config = Config(root, source, None)
    job = {"asset_id":"fixture","source_path":"chair.obj","format":"obj"}
    result = {**job,"status":"failed","sources":[{"path":"texture.png","before":"old hash","after":"old hash","unchanged":True}]}
    with pytest.raises(ConfigError, match="hash no longer"):
        validate_result(config, job, result)
