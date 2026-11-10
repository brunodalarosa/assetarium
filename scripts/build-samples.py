"""Build Assetarium's built-in sample assets and the search check images (decision 0031). Run inside Blender:

    blender --background --factory-startup --python scripts/build-samples.py

Writes samples/Sample assets/ (a blue cube, a green pyramid and a red sphere as GLB, low poly, plus a CC0 license)
and src/local_asset_library/data/search-check/ (256 px renders of the cube and the sphere that the search check
reads). Re-running replaces those files; nothing else is written.
"""
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / 'samples' / 'Sample assets'
CHECK = ROOT / 'src' / 'local_asset_library' / 'data' / 'search-check'
SHAPES = {  # name: (color, mesh builder)
    'Blue cube': ((0.08, 0.30, 0.90, 1), lambda: bpy.ops.mesh.primitive_cube_add(size=1.6)),
    'Green pyramid': ((0.10, 0.65, 0.22, 1), lambda: bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=1.1, depth=1.6)),
    'Red sphere': ((0.85, 0.08, 0.08, 1), lambda: bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.9)),
}
RENDERS = {'Blue cube': 'blue-cube.png', 'Red sphere': 'red-sphere.png'}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def shape(name, color, build):
    build()
    obj = bpy.context.active_object
    obj.name = obj.data.name = name
    material = bpy.data.materials.new(name)
    material.diffuse_color = color  # Workbench renders this; glTF exports the shader's base color below.
    material.use_nodes = True
    material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = color
    material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.6
    obj.data.materials.append(material)
    if name != 'Red sphere':
        return obj
    bpy.ops.object.shade_smooth()
    return obj


def render(obj, path):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'MATERIAL'
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new('Background')
    scene.world.color = (0.82, 0.84, 0.88)
    scene.display.shading.background_type = 'WORLD'
    camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scene.collection.objects.link(camera)
    camera.location = (3.2, -3.2, 2.4)
    direction = obj.location - camera.location
    camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = camera
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


SAMPLES.mkdir(parents=True, exist_ok=True)
CHECK.mkdir(parents=True, exist_ok=True)
for name, (color, build) in SHAPES.items():
    reset()
    obj = shape(name, color, build)
    bpy.ops.export_scene.gltf(filepath=str(SAMPLES / f'{name}.glb'), export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True)
    if name in RENDERS:
        render(obj, CHECK / RENDERS[name])
(SAMPLES / 'License.txt').write_text('Assetarium sample assets: a blue cube, a green pyramid and a red sphere.\n'
                                     'Made for Assetarium and dedicated to the public domain (CC0 1.0).\n', encoding='utf-8')
print('Samples written to', SAMPLES, 'and', CHECK)
