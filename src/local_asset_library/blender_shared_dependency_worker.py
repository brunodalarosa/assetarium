"""Scene-only shared texture bindings around the unchanged inspection renderer."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
import blender_worker as worker

job = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
recipe = job['texture_repair']
grants = {item['path']: item for item in job['dependency_files']}
original_source_path, original_import, original_inspect = worker.source_path, worker.import_source, worker.inspect


def source_path(root, relative):
    grant = grants.get(relative)
    if grant is None:
        return original_source_path(root, relative)
    provider = Path(grant['provider_root'])
    if provider.resolve() != provider or provider.is_relative_to(root) or root.is_relative_to(provider):
        raise ValueError('Invalid shared dependency provider root')
    # Reuse the ordinary worker guard under that provider, for this exact file.
    prefix = worker.SOURCE_PREFIX
    try:
        worker.SOURCE_PREFIX = relative.split('/', 1)[0]
        path = original_source_path(provider, relative)
    finally:
        worker.SOURCE_PREFIX = prefix
    if str(path) != grant['resolved_path'] or worker.sha(path) != grant['sha256']:
        raise ValueError('Shared dependency file changed')
    return path


def import_shared(source, format):
    original_import(source, format)
    if worker.sha(source) != recipe['source_sha256'] or recipe['source_path'] != job['source_path']:
        raise ValueError('Shared dependency model identity changed')
    for binding in recipe['bindings']:
        image = bpy.data.images.get(binding['image'])
        if image is None or image.filepath != binding['original_path']:
            raise ValueError('Shared texture image identity differs from the source reference')
        image.filepath = str(source_path(Path(job['source_root']).resolve(), binding['path']))
        image.reload()
        if min(image.size) <= 0:
            raise ValueError('Shared texture cannot be decoded')


def inspect_shared(root):
    technical = original_inspect(root)
    for binding in recipe['bindings']:
        texture = next(t for t in technical['textures'] if t['name'] == binding['image'])
        path = source_path(root, binding['path'])
        if Path(bpy.path.abspath(texture['original_path'])).resolve() != path:
            raise ValueError('Inspected shared texture differs from its binding')
        texture.update(path=binding['path'], sha256=binding['sha256'], status='available')
        if binding.get('dependency_resolution'):
            texture['dependency_resolution'] = binding['dependency_resolution']
        texture.pop('error', None)
    technical['texture_repair'] = recipe
    return technical


worker.source_path, worker.import_source, worker.inspect = source_path, import_shared, inspect_shared
worker.main()
