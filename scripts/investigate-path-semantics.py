"""Investigation only (milestone 1A, L6): how synthetic case/separator/name edge cases behave here.

Builds tiny synthetic packs in an isolated scratch project, then records what the
scanner (dependency statuses) and the real Blender worker (texture statuses,
result status) report for each. It changes no policy and repairs nothing: every
outcome, including faults, is recorded as observed. Report:
data/platform/<run-name>/report.json
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from local_asset_library.catalog import build_inventory
from local_asset_library.config import Config, load_project_config
from local_asset_library.inspection import blender_command, discover_blender, environment, run_process

parser = argparse.ArgumentParser()
parser.add_argument('--run-name', required=True)
args = parser.parse_args()
if not re.fullmatch('[a-z0-9-]{1,40}', args.run_name):
    raise SystemExit('Invalid run name')
out = ROOT / 'data/platform' / args.run_name
out.mkdir(parents=True, exist_ok=False)
base = ROOT / 'data/evidence/path-semantics' / args.run_name
project, source = base / 'project', base / 'source'
project.mkdir(parents=True)
source.mkdir()
blender, probe = discover_blender(load_project_config(ROOT))
config = Config(project, source, blender)
WORKER = ROOT / 'src/local_asset_library/blender_worker.py'
# A tetrahedron (a flat triangle renders edge-on in the front view and reads as empty).
SOLID = 'v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\nvt 0 0\nvt 1 0\nvt 0 1\n'
FACES = 'f 1 2 3\nf 1 2 4\nf 1 3 4\nf 2 3 4\n'
UV_FACES = 'f 1/1 2/2 3/3\nf 1/1 2/2 4/3\nf 1/1 3/2 4/3\nf 2/1 3/2 4/3\n'


def png(color):
    from PIL import Image
    import io
    buffer = io.BytesIO()
    Image.new('RGB', (4, 4), color).save(buffer, 'PNG')
    return buffer.getvalue()


def gltf(uri):
    points = struct.pack('<12f', 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1)
    uvs = struct.pack('<8f', 0, 0, 1, 0, 0, 1, 1, 1)
    blob = points + uvs + struct.pack('<12H', 0, 1, 2, 0, 1, 3, 0, 2, 3, 1, 2, 3)
    return json.dumps({'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'TEXCOORD_0': 1}, 'indices': 2, 'material': 0}]}],
        'materials': [{'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}}}],
        'textures': [{'source': 0}], 'images': [{'uri': uri}],
        'buffers': [{'byteLength': len(blob), 'uri': 'data:application/octet-stream;base64,' + base64.b64encode(blob).decode()}],
        'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': 48}, {'buffer': 0, 'byteOffset': 48, 'byteLength': 32},
                        {'buffer': 0, 'byteOffset': 80, 'byteLength': 24}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 4, 'type': 'VEC3', 'min': [0, 0, 0], 'max': [1, 1, 1]},
                      {'bufferView': 1, 'componentType': 5126, 'count': 4, 'type': 'VEC2'},
                      {'bufferView': 2, 'componentType': 5123, 'count': 12, 'type': 'SCALAR'}]})


def obj(name, mtl, texture_reference):
    return {f'{name}.obj': f'mtllib {mtl}\n' + SOLID + 'usemtl skin\n' + UV_FACES,
            'skin.mtl': f'newmtl skin\nKd 1 1 1\nmap_Kd {texture_reference}\n'}


# name: (files {relative: text|bytes}, model to inspect, what the case probes)
CASES = {
    'exact-control': ({**obj('crate', 'skin.mtl', 'textures/palette.png'), 'textures/palette.png': png('red')},
                      'crate.obj', 'Every reference matches exactly'),
    'obj-mtllib-case': ({**obj('crate', 'Skin.MTL', 'textures/palette.png'), 'textures/palette.png': png('red')},
                        'crate.obj', 'mtllib names Skin.MTL; the file is skin.mtl'),
    'mtl-texture-case': ({**obj('crate', 'skin.mtl', 'Textures/Palette.PNG'), 'textures/palette.png': png('red')},
                         'crate.obj', 'map_Kd names Textures/Palette.PNG; the file is textures/palette.png'),
    'mtl-backslash': ({**obj('crate', 'skin.mtl', 'textures\\palette.png'), 'textures/palette.png': png('red')},
                      'crate.obj', 'map_Kd uses a Windows separator with the exact case'),
    'gltf-texture-case': ({'bark.gltf': gltf('Textures/Bark.PNG'), 'textures/bark.png': png('green')},
                          'bark.gltf', 'glTF image uri Textures/Bark.PNG; the file is textures/bark.png'),
    'gltf-backslash': ({'bark.gltf': gltf('textures\\bark.png'), 'textures/bark.png': png('green')},
                       'bark.gltf', 'glTF image uri uses a Windows separator (invalid URI syntax)'),
    'reserved-texture-name': ({**obj('crate', 'skin.mtl', 'con.png'), 'con.png': png('blue')},
                              'crate.obj', 'Texture named con.png (reserved on Windows)'),
    'reserved-model-name': ({'aux.obj': SOLID + FACES}, 'aux.obj', 'Model named aux.obj (reserved on Windows)'),
    'colon-in-name': ({'lamp:post.obj': SOLID + FACES}, 'lamp:post.obj', 'Colon in a file name (legal on Linux)'),
    'case-twin-textures': ({**obj('crate', 'skin.mtl', 'rock.png'), 'Rock.png': png('red'), 'ROCK.png': png('blue')},
                           'crate.obj', 'Reference rock.png; only Rock.png and ROCK.png exist (ambiguous ignoring case)'),
    'case-twin-models': ({'Stone.obj': SOLID + FACES, 'stone.obj': SOLID.replace('v 0 0 1', 'v 0 0 2') + FACES},
                         'stone.obj', 'Two models whose names differ only by case'),
}
FBX_MAKER = '''import bpy, sys
folder, texture = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_plane_add()
image = bpy.data.images.load(folder + "/" + texture)
material = bpy.data.materials.new("wood")
material.use_nodes = True
node = material.node_tree.nodes.new("ShaderNodeTexImage"); node.image = image
material.node_tree.links.new(node.outputs["Color"], material.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
bpy.context.object.data.materials.append(material)
bpy.ops.export_scene.fbx(filepath=folder + "/plank.fbx", path_mode="RELATIVE", embed_textures=False)
'''

report = {'platform': sys.platform, 'blender': probe['version_output'].splitlines()[0], 'cases': {}}
for name, (files, model, probe_text) in CASES.items():
    entry = report['cases'][name] = {'probe': probe_text, 'model': f'{name}/{model}'}
    try:
        for relative, content in files.items():
            target = source / name / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content if isinstance(content, bytes) else content.encode())
        entry['files_on_disk'] = sorted(p.relative_to(source / name).as_posix() for p in (source / name).rglob('*') if p.is_file())
    except OSError as exc:
        entry['not_creatable'] = f'{type(exc).__name__}: {exc}'
# FBX: Blender writes the reference with the exact case, then the texture is renamed.
fbx = source / 'fbx-texture-case'
fbx.mkdir()
(fbx / 'Wood.png').write_bytes(png('brown'))
made = run_process(blender_command(blender, '--python-expr', FBX_MAKER, '--', str(fbx), 'Wood.png'), project, environment(config), 120)
(fbx / 'Wood.png').rename(fbx / 'wood.png')
report['cases']['fbx-texture-case'] = {'probe': 'FBX exported referencing Wood.png; the file is renamed to wood.png',
    'model': 'fbx-texture-case/plank.fbx', 'creation_returncode': made['returncode'],
    'files_on_disk': sorted(p.name for p in fbx.iterdir())}

rows, assets, *_ = build_inventory(config)
by_path = {row['path']: row for row in rows}
for name, entry in report['cases'].items():
    if 'not_creatable' in entry:
        continue
    entry['scan_rows'] = {path.split('/', 1)[1]: row.get('status') for path, row in by_path.items() if path.startswith(name + '/')}
    asset = next((a for a in assets if any(f['path'] == entry['model'] for f in a.get('files', []))), None)
    entry['scan_dependencies'] = [{k: d.get(k) for k in ('reference', 'path', 'status')} for d in (asset or {}).get('dependencies', [])]
    path = source / entry['model']
    output = config.output_path('data', 'inspection/' + name)
    job = {'asset_id': 'fixture', 'project_root': str(project), 'source_root': str(source), 'source_path': entry['model'],
           'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'format': path.suffix[1:], 'output': str(output),
           'resolution': 128}
    task = config.output_path('data', 'jobs/' + name + '.json')
    task.parent.mkdir(parents=True, exist_ok=True)
    task.write_text(json.dumps(job), encoding='utf-8')
    process = run_process(blender_command(blender, '--python-exit-code', '5', '--python', str(WORKER), '--', str(task)),
                          project, environment(config), 120)
    result_path = output / 'result.json'
    if not result_path.is_file():
        entry['blender'] = {'returncode': process['returncode'], 'result': None, 'log_tail': process['output'][-600:]}
        continue
    result = json.loads(result_path.read_text(encoding='utf-8'))
    entry['blender'] = {'returncode': process['returncode'], 'status': result.get('status'), 'errors': result.get('errors', []),
        'textures': [{k: t.get(k) for k in ('original_path', 'status', 'required_for_render')}
                     for t in (result.get('technical') or {}).get('textures', [])]}
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
