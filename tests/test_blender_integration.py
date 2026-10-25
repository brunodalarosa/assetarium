"""Small real Blender fixtures; all source/output files remain under scratch."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from local_asset_library.config import Config
from local_asset_library.inspection import blender_candidates, blender_command, environment, run_process

# LAL_TEST_BLENDER pins the executable; otherwise the app's own discovery (no Blender run).
_found = blender_candidates(Config(Path.cwd(), Path.cwd(), None))
BLENDER = Path(os.environ.get("LAL_TEST_BLENDER") or (_found[0] if _found else "blender-not-found"))
WORKER = Path(__file__).resolve().parents[1] / "src/local_asset_library/blender_worker.py"


@pytest.fixture
def small_fixture(tmp_path, request):
    request.node.user_properties.append(("real_blender", str(BLENDER)))
    if not BLENDER.is_file():
        reason = f"Real Blender unavailable ({BLENDER}); set LAL_TEST_BLENDER or install Blender"
        if os.environ.get("LAL_REQUIRE_BLENDER") == "1":
            pytest.fail(reason + " (LAL_REQUIRE_BLENDER=1)")
        pytest.skip(reason)
    project, source = tmp_path / "project", tmp_path / "source"
    project.mkdir()
    source.mkdir()
    return Config(project, source, BLENDER)


def invoke(config, source_relative, source_format, timeout=90, outside_output=None):
    path = config.source_root / source_relative
    output = outside_output or config.output_path("data", "fixture")
    job = {"asset_id":"fixture", "project_root":str(config.project_root), "source_root":str(config.source_root),
           "source_path":source_relative, "source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
           "format":source_format,"output":str(output),"resolution":320}
    task = config.output_path("data", "job.json")
    task.parent.mkdir(parents=True, exist_ok=True)
    task.write_text(json.dumps(job), encoding="utf-8")
    process = run_process(blender_command(BLENDER,"--python-exit-code","5","--python",str(WORKER),"--",str(task)),
                          config.project_root, environment(config), timeout)
    result_path = output / "result.json"
    result = json.loads(result_path.read_text()) if result_path.is_file() else None
    return process, result


def test_blend_metadata_render_and_embedded_script_disabled(small_fixture):
    config = small_fixture
    marker = config.project_root / "embedded-script-marker.txt"
    path = config.source_root / "animated-cube.blend"
    creator = config.output_path("scratch", "create_fixture.py")
    creator.parent.mkdir(parents=True, exist_ok=True)
    creator.write_text("\n".join([
        "import bpy",
        "bpy.ops.wm.read_factory_settings(use_empty=True)",
        "bpy.ops.mesh.primitive_cube_add()",
        "cube = bpy.context.object",
        "cube.scale = (1,2,3)",
        "cube.keyframe_insert(data_path='location', frame=1)",
        "cube.location.x = 1",
        "cube.keyframe_insert(data_path='location', frame=10)",
        "bpy.context.scene.frame_start = 1",
        "bpy.context.scene.frame_end = 10",
        "bpy.context.scene.frame_set(1)",
        "bpy.context.scene.unit_settings.system = 'METRIC'",
        "bpy.context.scene.unit_settings.scale_length = 0.01",
        "bpy.ops.object.armature_add()",
        "text = bpy.data.texts.new('embedded_test.py')",
        "text.use_module = True",
        "text.write(" + repr("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n") + ")",
        "bpy.ops.wm.save_as_mainfile(filepath=" + repr(str(path)) + ")",
    ]), encoding="utf-8")
    creation = run_process(blender_command(BLENDER,"--python",str(creator)),
                           config.project_root, environment(config), 30)
    assert creation["returncode"] == 0, creation["output"]
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    process, result = invoke(config, "animated-cube.blend", "blend")
    assert process["returncode"] == 0, process["output"]
    assert result["status"] == "complete", result
    technical = result["technical"]
    assert technical["evaluated_instance_totals"]["triangles"] == 12
    assert technical["evaluated_instance_totals"]["vertices"] == 8
    assert technical["mesh_object_count"] == 1
    assert technical["meshes"][0]["local_bounds"] == {"min":[-1,-1,-1],"max":[1,1,1]}
    assert technical["world_bounds"] == {"min":[-1,-2,-3],"max":[1,2,3]}
    assert technical["units"]["system"] == "METRIC"
    assert technical["units"]["scale_length"] == pytest.approx(0.01)
    assert len(technical["animation_clips"]) == 1 and technical["armatures"][0]["bones"] == 1
    assert len(result["previews"]) == 3 and all(not p["quality"]["off_frame"] and not p["quality"]["empty"] for p in result["previews"])
    assert not technical["autoexec_enabled"] and not marker.exists()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_empty_missing_texture_and_unsupported_are_distinct(small_fixture):
    config = small_fixture
    (config.source_root / "empty.obj").write_text("# empty fixture\n")
    process, result = invoke(config, "empty.obj", "obj")
    assert process["returncode"] == 0 and result["status"] == "failed"
    assert "Empty model" in result["errors"][0]
    (config.source_root / "model.obj").write_text("mtllib model.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nusemtl missing\nf 1/1 2/2 3/3\n")
    (config.source_root / "model.mtl").write_text("newmtl missing\nKd 1 1 1\nmap_Kd missing.png\n")
    process, result = invoke(config, "model.obj", "obj")
    assert process["returncode"] == 0 and result["status"] == "failed"
    assert any(t["status"] == "missing" and t["required_for_render"] for t in result["technical"]["textures"])
    assert "texture" in result["errors"][0]
    (config.source_root / "model.dae").write_text("fixture")
    process, result = invoke(config, "model.dae", "dae")
    assert process["returncode"] == 0 and result["status"] == "unsupported"


def test_worker_output_boundary_rejection(small_fixture):
    config = small_fixture
    (config.source_root / "model.obj").write_text("# fixture")
    outside = config.project_root.parent / "outside-output"
    process, result = invoke(config, "model.obj", "obj", outside_output=outside)
    assert process["returncode"] != 0 and result is None
    assert not outside.exists()
