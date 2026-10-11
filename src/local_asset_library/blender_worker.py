"""Trusted background worker. Source assets are loaded with script execution off."""

import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import sys
import time
import traceback

import bpy
from mathutils import Vector
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_math import duplicate_faces, framing  # noqa: E402 -- same trusted source directory


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inside(root, path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ValueError(f"Path outside permitted root: {path}")
    relative = resolved.relative_to(root)
    if any(os.path.isreserved(part) or part.endswith((".", " ")) or ":" in part for part in relative.parts):
        raise ValueError("Reserved or ambiguous path")
    return resolved


def source_path(root, relative):
    if PureWindowsPath(relative).anchor or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Source path must be relative without parent traversal")
    path = inside(root, root / relative)
    if not path.is_file():
        raise ValueError(f"Source is missing: {relative}")
    return path


def import_source(path, source_format):
    bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    if source_format == "blend":
        bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
        bpy.context.preferences.filepaths.use_scripts_auto_execute = False
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if source_format in {"glb", "gltf"}:
            bpy.ops.import_scene.gltf(filepath=str(path))
        elif source_format == "obj":
            bpy.ops.wm.obj_import(filepath=str(path), forward_axis="NEGATIVE_Z", up_axis="Y")
        elif source_format == "fbx":
            bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True)
        elif source_format == "stl":
            bpy.ops.wm.stl_import(filepath=str(path))
        else:
            raise NotImplementedError(f"No verified importer for {source_format}")
    if bpy.context.preferences.filepaths.use_scripts_auto_execute:
        raise ValueError("Embedded script execution is unexpectedly enabled")


def bounds(points):
    return {"min": [min(p[i] for p in points) for i in range(3)],
            "max": [max(p[i] for p in points) for i in range(3)]}


def inspect(source_root):
    scene = bpy.context.scene
    scene.frame_set(scene.frame_start)
    graph = bpy.context.evaluated_depsgraph_get()
    objects = list(scene.objects)
    meshes, world_points = [], []
    totals = {"vertices": 0, "edges": 0, "polygons": 0, "triangles": 0}
    unique_meshes = {}
    for obj in objects:
        if obj.type != "MESH":
            continue
        original = obj.data
        original.calc_loop_triangles()
        original_counts = {"vertices": len(original.vertices), "edges": len(original.edges),
                           "polygons": len(original.polygons), "triangles": len(original.loop_triangles)}
        unique_meshes[original.name] = original_counts
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            if not mesh.vertices:
                continue
            mesh.calc_loop_triangles()
            points = [tuple(v.co) for v in mesh.vertices]
            transformed = [tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices]
            world_points.extend(transformed)
            counts = {"vertices": len(mesh.vertices), "edges": len(mesh.edges),
                      "polygons": len(mesh.polygons), "triangles": len(mesh.loop_triangles)}
            for key in totals:
                totals[key] += counts[key]
            meshes.append({"object": obj.name, "mesh": original.name,
                           "duplicate_position_faces": duplicate_faces(points, (p.vertices for p in mesh.polygons)),
                           "original_counts": original_counts, "evaluated_counts": counts,
                           "local_bounds": bounds(points), "matrix_world": [list(row) for row in evaluated.matrix_world],
                           "world_bounds": bounds(transformed), "hide_render_original": obj.hide_render,
                           "material_slots": [s.material.name if s.material else None for s in obj.material_slots],
                           "modifiers": [{"name": m.name, "type": m.type} for m in obj.modifiers]})
        finally:
            evaluated.to_mesh_clear()
    if not meshes or not world_points or totals["triangles"] == 0:
        raise ValueError("Empty model: no renderable mesh triangles")
    material_rows = []
    used_materials = {slot.material for obj in objects if obj.type == "MESH" for slot in obj.material_slots if slot.material}
    for material in sorted(used_materials, key=lambda m: m.name):
        material_rows.append({"name": material.name, "diffuse_color": list(material.diffuse_color),
                              "use_nodes": material.use_nodes,
                              "image_nodes": sorted({node.image.name for node in material.node_tree.nodes
                                                     if node.type == "TEX_IMAGE" and node.image}) if material.node_tree else []})
    images = []
    image_users = {}
    def linked_images(tree, visited=None):
        visited = set() if visited is None else visited
        if not tree or tree.name in visited:
            return set()
        visited.add(tree.name)
        found = set()
        pending = [node for node in tree.nodes if node.type in {"OUTPUT_MATERIAL", "GROUP_OUTPUT"} and getattr(node, "is_active_output", True)]
        seen_nodes = set()
        while pending:
            node = pending.pop()
            if node.name in seen_nodes:
                continue
            seen_nodes.add(node.name)
            if node.type == "TEX_IMAGE" and node.image:
                found.add(node.image.name)
            elif node.type == "GROUP":
                found.update(linked_images(node.node_tree, visited))
            pending.extend(link.from_node for socket in node.inputs for link in socket.links)
        return found
    for material in used_materials:
        for name in linked_images(material.node_tree):
            image_users.setdefault(name, []).append("material:" + material.name)
    for obj in objects:
        for modifier in obj.modifiers:
            texture = getattr(modifier, "texture", None)
            if texture and getattr(texture, "image", None):
                image_users.setdefault(texture.image.name, []).append("modifier:" + obj.name + "/" + modifier.name)
    for image in list(bpy.data.images):
        if image.type in {"RENDER_RESULT", "COMPOSITING"} or image.name == "Render Result":
            continue
        row = {"name": image.name, "original_path": image.filepath, "source": image.source,
               "size": list(image.size), "path": None, "sha256": None,
               "colorspace": image.colorspace_settings.name,
               "render_users": sorted(image_users.get(image.name, [])),
               "required_for_render": bool(image_users.get(image.name))}
        if image.packed_file or len(image.packed_files):
            row.update(status="embedded", packed_sha256=[hashlib.sha256(bytes(packed.packed_file.data)).hexdigest() for packed in image.packed_files])
        elif image.source == "GENERATED":
            row["status"] = "generated_in_source"
        elif image.filepath:
            try:
                actual = inside(source_root, bpy.path.abspath(image.filepath, library=image.library))
                row["path"] = actual.relative_to(source_root).as_posix()
                row["status"] = "available" if actual.is_file() else "missing"
                if actual.is_file():
                    row["sha256"] = sha(actual)
            except ValueError as exc:
                row.update(status="rejected", error=str(exc))
        else:
            row["status"] = "unknown"
        images.append(row)
    armatures = [{"object": obj.name, "bones": len(obj.data.bones)} for obj in objects if obj.type == "ARMATURE"]
    actions = [{"name": action.name, "frame_range": list(action.frame_range)} for action in bpy.data.actions]
    animation_objects = [{"object": obj.name, "action": obj.animation_data.action.name if obj.animation_data.action else None,
                          "nla_tracks": [track.name for track in obj.animation_data.nla_tracks],
                          "drivers": len(obj.animation_data.drivers)} for obj in objects if obj.animation_data]
    return {"object_count": len(objects), "object_types": {kind: sum(o.type == kind for o in objects) for kind in sorted({o.type for o in objects})},
            "mesh_object_count": sum(o.type == "MESH" for o in objects), "measured_mesh_count": len(meshes),
            "unique_mesh_count": len(unique_meshes), "unique_original_meshes": unique_meshes,
            "evaluated_instance_totals": totals, "meshes": meshes, "world_bounds": bounds(world_points),
            "units": {"system": scene.unit_settings.system, "scale_length": scene.unit_settings.scale_length,
                      "length_unit": scene.unit_settings.length_unit, "physical_scale": "unknown; imported settings are not proof of real size"},
            "materials": material_rows, "textures": images, "armatures": armatures,
            "animation_clips": actions, "animation_objects": animation_objects,
            "sample_frame": scene.frame_start, "fps": scene.render.fps, "fps_base": scene.render.fps_base,
            "autoexec_enabled": bpy.context.preferences.filepaths.use_scripts_auto_execute,
            "autoexec_fail": bpy.app.autoexec_fail,
            "limitations": ["Measured only this imported file at the recorded frame; alternate formats are uninspected.",
                            "Mesh local bounds precede object transforms; world bounds include evaluated instance transforms.",
                            "Importer may convert coordinates/materials; source author front and physical scale are unknown.",
                            "Action data and armatures are enumerated, not played or behaviorally validated."]}


def render(technical, output, resolution):
    scene = bpy.context.scene
    # Keep imported model objects/materials; hide source cameras/lights, isolate from their staging.
    models = [o for o in scene.objects if o.type in {"MESH", "ARMATURE"}]
    render_scene = bpy.data.scenes.new("LocalAssetLibraryInspection")
    shadow_overrides = []
    duplicate_objects = {mesh["object"]: mesh["duplicate_position_faces"] for mesh in technical["meshes"] if mesh["duplicate_position_faces"]}
    for obj in models:
        render_scene.collection.objects.link(obj)
        obj.hide_render = False
        if obj.name in duplicate_objects:
            obj.visible_shadow = False
            shadow_overrides.append({"object": obj.name, "duplicate_position_faces": duplicate_objects[obj.name],
                                     "visible_shadow": False, "reason": "Exact overlapping faces cause self-shadow artifacts; geometry and materials retained"})
    scene = render_scene
    bpy.context.window.scene = scene
    scene.frame_set(technical["sample_frame"])
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 128
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_use_gpu = False
    scene.cycles.seed = 0
    scene.cycles.use_animated_seed = False
    scene.render.resolution_x = scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    scene.render.use_file_extension = True
    scene.use_nodes = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    world = bpy.data.worlds.new("InspectionWorld")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.2, 0.2, 0.2, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
    scene.world = world
    settings = framing(technical["world_bounds"]["min"], technical["world_bounds"]["max"])
    center = Vector(settings["center"])
    radius = settings["radius"]
    # Scale light area/energy together so differently sized imports get consistent illumination.
    for name, direction, energy in (("key", (-3, -4, 6), 200), ("fill", (4, -1, 3), 100), ("rim", (1, 4, 5), 150)):
        light = bpy.data.lights.new("Inspection_" + name, "AREA")
        light.energy = energy * radius * radius
        light.shape = "DISK"
        light.size = radius * 4
        obj = bpy.data.objects.new(light.name, light)
        scene.collection.objects.link(obj)
        obj.location = center + Vector(direction).normalized() * radius * 5
        obj.rotation_euler = (center - obj.location).to_track_quat("-Z", "Y").to_euler()
    camera_data = bpy.data.cameras.new("InspectionCamera")
    camera = bpy.data.objects.new("InspectionCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = settings["ortho_scale"]
    camera_data.clip_start = max(1e-5, radius * 0.01)
    camera_data.clip_end = radius * 20
    records = []
    for name, view in settings["views"].items():
        camera.location = center + Vector(view["outward"]) * radius * 5
        if name == "top":
            camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        else:
            camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        path = inside(output, output / (name + ".png"))
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True, scene=scene.name)
        image = bpy.data.images.load(str(path), check_existing=False)
        try:
            pixels = np.empty(resolution * resolution * 4, dtype=np.float32)
            image.pixels.foreach_get(pixels)
            pixels = pixels.reshape((resolution, resolution, 4))
            mask = pixels[:, :, 3] > 0.05
            ys, xs = np.where(mask)
            count = int(mask.sum())
            bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if count else None
            clipped = bool(count and (min(bbox[:2]) <= 3 or max(bbox[2:]) >= resolution - 4))
            empty = count < 32
            quality = {"foreground_pixels": count, "foreground_fraction": count / (resolution * resolution),
                       "pixel_bounds_bottom_origin": bbox, "empty": empty, "off_frame": clipped,
                       "method": "transparent render alpha mask > 0.05; border margin 4 px; minimum 32 foreground px"}
            # Loaded byte PNG pixels are sRGB; composite explicitly in linear light.
            alpha = pixels[:, :, 3:4]
            rgb = pixels[:, :, :3]
            linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
            background = ((0.32 + 0.055) / 1.055) ** 2.4
            composed = linear * alpha + background * (1 - alpha)
            pixels[:, :, :3] = np.where(composed <= 0.0031308, composed * 12.92, 1.055 * composed ** (1 / 2.4) - 0.055)
            pixels[:, :, 3] = 1
            image.pixels.foreach_set(pixels.ravel())
            image.save_render(str(path), scene=scene)
        finally:
            bpy.data.images.remove(image)
        records.append({"view_label": name, "filename": path.name, "sha256": sha(path),
                        "camera_location": list(camera.location), "camera_rotation_euler": list(camera.rotation_euler),
                        "quality": quality})
    return records, {"engine": scene.render.engine, "resolution": [resolution, resolution],
                     "device": "CPU", "samples": 128, "seed": 0, "denoising": "OpenImageDenoise CPU",
                     "coordinate_convention": "Blender imported Z-up; canonical front -Y and side +X, both elevated 14 degrees; source-author front unknown",
                     "projection": "orthographic; shared scale across all views", "framing": settings,
                     "color_management": {"view_transform": "Standard", "look": "None", "exposure": 0, "gamma": 1},
                     "background_srgb": [0.32, 0.32, 0.32], "lighting": "three area lights; energies and sizes scaled to bounding sphere",
                     "materials": "imported materials preserved; new render scene omits source cameras/lights",
                     "shadow_overrides": shadow_overrides,
                     "top_view_reason": "vertical extent <18% of horizontal extent" if "top" in settings["views"] else None}


def main():
    job_path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    job = json.loads(job_path.read_text(encoding="utf-8"))
    project = Path(job["project_root"]).resolve()
    source_root = Path(job["source_root"]).resolve()
    if project.is_relative_to(source_root) or source_root.is_relative_to(project):
        raise ValueError("Source and project overlap")
    inside(project, job_path)
    output = inside(project / "data", job["output"])
    output.mkdir(parents=True, exist_ok=True)
    result_path = inside(output, output / "result.json")
    result = {"schema_version": 1, "asset_id": job["asset_id"], "source_path": job["source_path"],
              "format": job["format"], "status": "failed", "technical": None, "previews": [],
              "blender_version": bpy.app.version_string, "blender_build_hash": bpy.app.build_hash.decode(),
              "errors": [], "sources": []}
    result["runtime_resources"] = {kind: bpy.utils.user_resource(kind) for kind in ("CONFIG", "SCRIPTS", "DATAFILES", "EXTENSIONS")}
    for path in result["runtime_resources"].values():
        inside(project, path)
    started = time.perf_counter()
    try:
        source = source_path(source_root, job["source_path"])
        before = sha(source)
        if before != job["source_sha256"]:
            raise ValueError("Source hash differs from catalog")
        result["sources"].append({"path": job["source_path"], "before": before})
        import_source(source, job["format"])
        technical = inspect(source_root)
        result["technical"] = technical
        for texture in technical["textures"]:
            if texture["status"] == "available":
                result["sources"].append({"path": texture["path"], "before": texture["sha256"]})
        bad = [texture for texture in technical["textures"] if texture["required_for_render"] and texture["status"] in {"missing", "rejected", "unknown"}]
        result["warnings"] = ["Unused image reference " + texture["name"] + ": " + texture["status"]
                              for texture in technical["textures"] if not texture["required_for_render"] and texture["status"] in {"missing", "rejected", "unknown"}]
        if bad:
            raise ValueError("Missing, rejected or unresolved texture dependencies: " + ", ".join(t["name"] for t in bad))
        previews, settings = render(technical, output, job["resolution"])
        result.update(previews=previews, render_settings=settings)
        if any(v["quality"]["empty"] or v["quality"]["off_frame"] for v in previews):
            raise ValueError("Empty or off-frame preview detected")
        result["status"] = "complete"
    except NotImplementedError as exc:
        result.update(status="unsupported", errors=[str(exc)])
    except Exception as exc:
        result["errors"].append(str(exc))
        result["traceback"] = traceback.format_exc()
    for row in result["sources"]:
        try:
            row["after"] = sha(source_path(source_root, row["path"]))
            row["unchanged"] = row["before"] == row["after"]
        except Exception as exc:
            row.update(unchanged=False, error=str(exc))
        if not row["unchanged"]:
            result["status"] = "failed"
            result["errors"].append("Source mutation detected: " + row["path"])
    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("INSPECTION_RESULT=" + str(result_path), flush=True)


if __name__ == "__main__":
    main()
