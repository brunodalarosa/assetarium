"""What an image is: a model texture, a material texture or a 2D image (decision 0023).

Layered evidence, each recorded as ``{value, basis, evidence}`` like ``image_catalog.suggested_purpose``, never
a bare fact: model references (glTF, OBJ/MTL, FBX names) and Blender's texture list make a model texture (a
dependency, not a selectable asset); a pack without models makes its images 2D images; material names, nearby
models and folder words lean one way or the other; decoded pixels add evidence once an image is inspected; an
owner answer on a folder wins over everything but a model reference. The vision model is never used for this.
"""
from pathlib import PurePosixPath
import re

KINDS = ('model_texture', 'material_texture', 'image')
MATERIAL = re.compile(r'(?:^|[_\-. ])(albedo|basecolou?r|base_colou?r|diffuse|diff|normal|nrm|nor|norm|rough|roughness|metal|metallic|'
                      r'metalness|ao|ambientocclusion|occlusion|height|disp|displacement|bump|orm|arm|emission|emissive|spec|'
                      r'specular|gloss|glossiness|opacity|alpha|mask|col|d|n|r|m)$', re.I)
TEXTURE_WORDS = {'texture', 'textures', 'tex', 'material', 'materials', 'maps', 'pbr'}
IMAGE_WORDS = {'icon', 'icons', 'sprite', 'sprites', 'ui', 'gui', 'hud', 'logo', 'logos', 'tile', 'tiles', 'tileset', 'tilesets',
               'background', 'backgrounds', 'character', 'characters', 'vector', 'png', 'svg', 'cursor', 'cursors', 'button', 'buttons'}
FBX_NAMES = re.compile(rb'([\w\- .]{1,200}\.(?:png|jpe?g|tga|bmp|tiff?|webp|dds|exr))', re.I)
FBX_LIMIT = 64 * 1024 * 1024


def fbx_references(config, path, size):
    """Image file names an FBX file mentions (ASCII ``RelativeFilename`` and strings in binary FBX); never parsed further."""
    if (size or 0) > FBX_LIMIT:
        return set()
    try:
        with config.open_source(path) as stream:
            data = stream.read(FBX_LIMIT)
    except (OSError, ValueError):
        return set()
    return {PurePosixPath(m.decode('utf-8', 'replace').replace('\\', '/').strip()).name.casefold() for m in FBX_NAMES.findall(data)}


def words(folders):
    found = set()
    for name in folders:
        found |= set(re.findall(r'[a-z]+', re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name).lower()))
    return found


def classify(path, referenced, model_stems, model_folders, pack_has_models, answer=None, pixels=None):
    """``{'value', 'basis', 'evidence'}`` for one image path (source-prefixed POSIX)."""
    p = PurePosixPath(path)
    if path in referenced:
        return {'value': 'model_texture', 'basis': 'model-reference', 'evidence': referenced[path]}
    if answer in {'texture', 'image'}:
        return {'value': 'material_texture' if answer == 'texture' else 'image', 'basis': 'owner',
                'evidence': 'Owner answer: treat images in this folder as ' + ('textures' if answer == 'texture' else '2D assets')}
    material = MATERIAL.search(p.stem)
    if not pack_has_models:
        if material:
            return {'value': 'material_texture', 'basis': 'material-name', 'evidence': f'Name ends with {material.group(1)!r}; the pack has no models'}
        return {'value': 'image', 'basis': 'pack-without-models', 'evidence': 'The pack holds no 3D models'}
    folder_words = words(p.parts[1:-1])
    if p.stem.casefold() in model_stems:
        return {'value': 'model_texture', 'basis': 'model-stem', 'evidence': f'Shares its name with a model ({p.stem})'}
    if material:
        return {'value': 'material_texture', 'basis': 'material-name', 'evidence': f'Name ends with {material.group(1)!r}'}
    if folder_words & TEXTURE_WORDS:
        return {'value': 'material_texture', 'basis': 'folder-name', 'evidence': 'Folder name ' + ', '.join(sorted(folder_words & TEXTURE_WORDS))}
    if folder_words & IMAGE_WORDS:
        return {'value': 'image', 'basis': 'folder-name', 'evidence': 'Folder name ' + ', '.join(sorted(folder_words & IMAGE_WORDS))}
    if p.parent.as_posix() in model_folders:
        return {'value': 'model_texture', 'basis': 'beside-models', 'evidence': 'In the same folder as 3D models'}
    return refine({'value': 'image', 'basis': 'default', 'evidence': 'No texture evidence'}, pixels)


def refine(kind, pixels):
    """Decoded pixels decide only an image no other layer has evidence for."""
    if kind['basis'] == 'default' and pixels and pixels.get('value') == 'material_texture':
        return {'value': 'material_texture', 'basis': 'pixels', 'evidence': pixels['evidence']}
    return kind


def pixel_evidence(rgba):
    """Decoded-pixel hints (normal map, single-channel map, seamless edges, cutout alpha); evidence, never a verdict."""
    import numpy as np
    pixels = np.asarray(rgba, dtype=np.float32)
    if pixels.ndim != 3 or pixels.shape[0] < 8 or pixels.shape[1] < 8:
        return None
    rgb, alpha = pixels[..., :3], pixels[..., 3] if pixels.shape[2] == 4 else None
    mean = rgb.reshape(-1, 3).mean(axis=0)
    hints = []
    if abs(mean[0] - 128) < 20 and abs(mean[1] - 128) < 20 and mean[2] > 200:
        hints.append('normal-map colors (mean about 128/128/255)')
    if float(np.abs(rgb[..., 0] - rgb[..., 1]).mean() + np.abs(rgb[..., 1] - rgb[..., 2]).mean()) < 1.0:
        hints.append('single-channel grayscale')
    edges = float(np.abs(rgb[0] - rgb[-1]).mean() + np.abs(rgb[:, 0] - rgb[:, -1]).mean()) / 2
    detailed = float(rgb.std()) > 8  # A flat color is trivially seamless; that says nothing.
    square = pixels.shape[0] == pixels.shape[1]
    if detailed and square and edges < 6 and (alpha is None or alpha.min() > 250):
        hints.append('seamless edges')
    cutout = alpha is not None and float((alpha < 5).mean()) > 0.05
    texture = bool(hints) and not cutout
    return {'value': 'material_texture' if texture else 'image', 'basis': 'pixels',
            'evidence': '; '.join(hints + (['cutout alpha'] if cutout else [])) or 'No texture pattern in the pixels'}
