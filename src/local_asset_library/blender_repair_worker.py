"""Opt-in scene-only texture repairs around the unchanged inspection renderer."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import blender_worker as worker

job = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
recipe = job['texture_repair']
original_import = worker.import_source
original_inspect = worker.inspect


def import_repaired(source, format):
    original_import(source, format)
    if worker.sha(source) != recipe['source_sha256'] or recipe['source_path'] != job['source_path']:
        raise ValueError('Repair source hash/identity mismatch')
    root = Path(job['source_root']).resolve()
    for binding in recipe['bindings']:
        image = bpy.data.images.get(binding['image'])
        if image is None or image.filepath != binding['original_path']:
            raise ValueError('Repair image identity/path differs from inspected evidence')
        texture = worker.source_path(root, binding['path'])
        if worker.sha(texture) != binding['sha256']:
            raise ValueError('Repair texture changed')
        image.filepath = str(texture)
        image.reload()
        if min(image.size) <= 0:
            raise ValueError('Repair texture cannot be decoded')
        if binding.get('preserve_supplied_alpha') and binding['role'] == 'Albedo' and image.channels == 4:
            pixels = worker.np.empty(len(image.pixels), dtype=worker.np.float32)
            image.pixels.foreach_get(pixels)
            alpha = pixels[3::4]
            if alpha.min() < 0.99 and alpha.max() > 0.01:
                for material in bpy.data.materials:
                    if not material.node_tree:
                        continue
                    tree = material.node_tree
                    for node in tree.nodes:
                        if node.type != 'TEX_IMAGE' or node.image != image:
                            continue
                        for link in list(node.outputs['Color'].links):
                            if link.to_node.type == 'BSDF_PRINCIPLED' and link.to_socket.name == 'Base Color':
                                socket = link.to_node.inputs['Alpha']
                                if not socket.is_linked:
                                    tree.links.new(node.outputs['Alpha'], socket)
            del pixels


def inspect_repaired(root):
    technical = original_inspect(root)
    technical['texture_repair'] = recipe
    return technical


worker.import_source = import_repaired
worker.inspect = inspect_repaired
worker.main()
