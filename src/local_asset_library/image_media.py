"""Static 2D images: verified local decoding, measured facts and bounded derived files.

This module's bytes are part of the image inspection fingerprint: editing it
re-inspects images and re-queues their vectors and descriptions. Scanner rules
live in image_catalog.py. Originals are only read. Thumbnails, SVG rasters and model inputs are derived
files whose recipe is recorded with them. A model-input backdrop is a display
choice for transparent pixels and never a source color. Animated/multi-frame
images and external SVG resources are explicit unsupported states.
"""
from io import BytesIO
import json
import math
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ElementTree

from .config import ConfigError

RASTER = {'png': 'PNG', 'jpg': 'JPEG', 'jpeg': 'JPEG', 'webp': 'WEBP', 'bmp': 'BMP', 'gif': 'GIF',
          'tga': 'TGA', 'tif': 'TIFF', 'tiff': 'TIFF', 'avif': 'AVIF'}
VECTOR = ('svg',)
FORMATS = tuple(RASTER) + VECTOR
# Raster files carry the authored pixels; an SVG export is preferred only when alone.
PREFERENCE = ('png', 'webp', 'avif', 'tif', 'tiff', 'bmp', 'tga', 'gif', 'jpg', 'jpeg', 'svg')
MAX_RASTER_BYTES = 64 * 1024 * 1024
MAX_SVG_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 16_000_000
THUMBNAIL_EDGE = 320
DISPLAY_EDGE = 1024
MAX_RENDER_EDGE = 2048
MAX_MODEL_EDGE = 4096
SVG_TIMEOUT = 30
PROBE = 16384  # Content-bounds probe for SVGs without width/height/viewBox, in user units.
GRAY = (82, 82, 82)
# Candidate model-input contracts; ACTIVE is chosen from the step 2 evaluation.
POLICIES = {
    'a': {'name': 'image-model-input-a-v1', 'min_edge': 32, 'background': 'gray82'},
    'b': {'name': 'image-model-input-b-v1', 'min_edge': 256, 'background': 'gray82'},
    'c': {'name': 'image-model-input-c-v1', 'min_edge': 256, 'background': 'contrast-v1'},
}
ACTIVE = 'b'


def image_format(path):
    suffix = PurePosixPath(path).suffix.lower()[1:]
    return suffix if suffix in FORMATS else None


def _alpha(rgba):
    alpha = rgba.getchannel('A')
    low, high = alpha.getextrema()
    histogram = alpha.histogram()
    visible = sum(histogram[1:])
    total = rgba.width * rgba.height
    kind = 'none' if low == 255 else 'binary' if visible == histogram[255] else 'partial'
    return {'alpha': kind, 'alpha_coverage': round(visible / total, 6) if total else 0,
            'visible_bounds': list(alpha.getbbox() or ()) or None}


def facts(rgba, source_mode=None):
    width, height = rgba.size
    colors = rgba.getcolors(maxcolors=4096) if width * height <= 1_048_576 else None
    value = {'width': width, 'height': height, **_alpha(rgba),
             'color_count': len(colors) if colors else None,
             'size_class': size_class(width, height),
             'aspect': 'square' if max(width, height) <= 1.25 * min(width, height) else 'wide' if width > height else 'tall'}
    # A display hint for nearest-neighbour viewing; not an artistic classification.
    value['pixel_art_candidate'] = bool(max(width, height) <= 256 and value['color_count'] is not None
                                        and value['color_count'] <= 256 and value['alpha'] != 'partial')
    if source_mode:
        value['mode'] = source_mode
    return value


def size_class(width, height):
    edge = max(width, height)
    return 'tiny' if edge <= 32 else 'small' if edge <= 128 else 'medium' if edge <= 1024 else 'large'


def decode_raster(path, fmt):
    """Return (RGBA image, measured facts) or raise ConfigError / UnsupportedMedia."""
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise ConfigError('Image decoding requires the MCP runtime (Pillow)') from exc
    if path.stat().st_size > MAX_RASTER_BYTES:
        raise ConfigError('Image exceeds the 64 MiB decode cap')
    try:
        with Image.open(path, formats=[RASTER[fmt]]) as image:
            if image.width * image.height > MAX_PIXELS:
                raise ConfigError('Image exceeds the 16 megapixel decode cap')
            frames = getattr(image, 'n_frames', 1)
            if frames > 1:
                raise UnsupportedMedia(f'{frames}-frame {RASTER[fmt]} image; animation and multi-page images are deferred')
            mode = image.mode
            image.load()
            rgba = ImageOps.exif_transpose(image).convert('RGBA')
    except Image.DecompressionBombError as exc:
        raise ConfigError('Image exceeds the pixel decode cap') from exc
    except (Image.UnidentifiedImageError, SyntaxError) as exc:
        raise ConfigError(f'Content is not a decodable {RASTER[fmt]} image: {exc}') from exc
    except OSError as exc:
        raise ConfigError(f'Image is damaged or truncated: {exc}') from exc
    return rgba, {**facts(rgba, mode), 'format': fmt, 'frames': 1}


class UnsupportedMedia(ConfigError):
    """Recognized content without an implemented adapter (recorded, not failed)."""


def _number(value):
    match = re.fullmatch(r'\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*(px)?\s*', value or '')
    return float(match.group(1)) if match else None


def svg_info(text):
    """Structure checks before rendering; external resources are refused, scripts never run."""
    if re.search(r'<!ENTITY', text, re.I):
        raise UnsupportedMedia('SVG declares XML entities; entity expansion is not supported')
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ConfigError(f'SVG is not well-formed XML: {exc}') from exc
    if root.tag.rsplit('}', 1)[-1] != 'svg':
        raise ConfigError('Root element is not <svg>')
    external, texts, scripts = [], 0, 0
    for element in root.iter():
        tag = element.tag.rsplit('}', 1)[-1] if isinstance(element.tag, str) else ''
        texts += tag == 'text'
        scripts += tag == 'script'
        for key, value in element.attrib.items():
            if key.rsplit('}', 1)[-1] in {'href', 'src'} and not value.strip().startswith(('#', 'data:')):
                external.append(value[:200])
        styles = [element.attrib.get('style', '')] + ([element.text or ''] if tag == 'style' else [])
        for style in styles:
            if '@import' in style:
                external.append('@import')
            external.extend(u[:200] for _, u in re.findall(r'url\(\s*([\'"]?)(.*?)\1\s*\)', style)
                            if not u.startswith(('#', 'data:')))
    if external:
        raise UnsupportedMedia('SVG references external resources (' + ', '.join(sorted(set(external))[:4])
                               + '); only self-contained SVG is supported')
    box = [float(v) for v in re.split(r'[\s,]+', root.get('viewBox', '').strip()) if v] if root.get('viewBox') else None
    if box is not None and (len(box) != 4 or box[2] <= 0 or box[3] <= 0 or not all(map(math.isfinite, box))):
        raise ConfigError('SVG viewBox is invalid')
    width, height = _number(root.get('width')), _number(root.get('height'))
    return {'width': width, 'height': height, 'view_box': box, 'text_elements': texts, 'script_elements': scripts}


def render_svg(text, width, height, view_box, system_fonts=False):
    job = {'width': width, 'height': height, 'view_box': view_box, 'system_fonts': system_fonts}
    try:
        done = subprocess.run([sys.executable, '-I', str(Path(__file__).with_name('svg_worker.py')), json.dumps(job)],
                              input=text.encode('utf-8'), capture_output=True, timeout=SVG_TIMEOUT,
                              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    except subprocess.TimeoutExpired as exc:
        raise ConfigError(f'SVG rendering exceeded {SVG_TIMEOUT} s') from exc
    if done.returncode:
        raise ConfigError('SVG rendering failed: ' + done.stderr.decode('utf-8', 'replace').strip()[-300:])
    from PIL import Image
    with Image.open(BytesIO(done.stdout), formats=['PNG']) as image:
        image.load()
        if image.size != (width, height):
            raise ConfigError('SVG renderer returned an unexpected size')
        return image.convert('RGBA')


def svg_canvas(text, info):
    """The SVG's own canvas, or measured content bounds when it declares none (recorded)."""
    if info['view_box']:
        return info['view_box'], 'viewBox'
    if info['width'] and info['height']:
        return [0.0, 0.0, info['width'], info['height']], 'width-height'
    box, scale = [-PROBE, -PROBE, 2 * PROBE, 2 * PROBE], 2 * PROBE / MAX_RENDER_EDGE
    for _ in range(2):
        edge = MAX_RENDER_EDGE
        size = (edge, max(1, round(edge * box[3] / box[2]))) if box[2] >= box[3] else (max(1, round(edge * box[2] / box[3])), edge)
        image = render_svg(text, *size, box, info['text_elements'] > 0)
        bounds = image.getchannel('A').getbbox()
        if not bounds:
            raise ConfigError('SVG renders no visible content')
        if box[0] == -PROBE and (bounds[0] == 0 or bounds[1] == 0 or bounds[2] == size[0] or bounds[3] == size[1]):
            raise UnsupportedMedia('SVG declares no canvas and its content exceeds the measurable bounds')
        sx, sy = box[2] / size[0], box[3] / size[1]
        box = [box[0] + (bounds[0] - 1) * sx, box[1] + (bounds[1] - 1) * sy,
               (bounds[2] - bounds[0] + 2) * sx, (bounds[3] - bounds[1] + 2) * sy]
    x0, y0 = math.floor(box[0]), math.floor(box[1])
    return [x0, y0, math.ceil(box[0] + box[2]) - x0, math.ceil(box[1] + box[3]) - y0], 'content-bounds-v1'


def decode_svg(path, edge=DISPLAY_EDGE):
    """Return (RGBA raster, facts) for a self-contained SVG rendered to fit ``edge``."""
    if path.stat().st_size > MAX_SVG_BYTES:
        raise ConfigError('SVG exceeds the 8 MiB cap')
    raw = path.read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ConfigError('SVG is not UTF-8 text') from exc
    info = svg_info(text)
    box, basis = svg_canvas(text, info)
    edge = max(1, min(int(edge), MAX_RENDER_EDGE))
    scale = edge / max(box[2], box[3])
    size = (max(1, round(box[2] * scale)), max(1, round(box[3] * scale)))
    rgba = render_svg(text, *size, box, info['text_elements'] > 0)
    import importlib.metadata
    measured = facts(rgba)
    vector = {'canvas': box, 'canvas_basis': basis, 'declared_width': info['width'], 'declared_height': info['height'],
              'text_elements': info['text_elements'], 'script_elements': info['script_elements'],
              'text_fonts': 'system fonts' if info['text_elements'] else 'none loaded',
              'renderer': 'resvg-py ' + importlib.metadata.version('resvg-py'), 'raster_size': list(size)}
    # Vector facts describe the canvas; pixel-derived measurements describe this raster only.
    measured.update(width=round(box[2], 3), height=round(box[3], 3), size_class=size_class(box[2], box[3]),
                    pixel_art_candidate=False, format='svg', frames=1, vector=vector)
    return rgba, measured


def decode(path, fmt, edge=DISPLAY_EDGE):
    return decode_svg(path, edge) if fmt == 'svg' else decode_raster(path, fmt)


def thumbnail(rgba):
    from PIL import Image
    edge = max(rgba.size)
    if edge <= THUMBNAIL_EDGE // 2:
        k = THUMBNAIL_EDGE // edge
        return rgba.resize((rgba.width * k, rgba.height * k), Image.Resampling.NEAREST), {'resample': 'nearest', 'scale': k}
    image = rgba.copy()
    image.thumbnail((THUMBNAIL_EDGE, THUMBNAIL_EDGE), Image.Resampling.LANCZOS)
    return image, {'resample': 'lanczos', 'scale': round(image.width / rgba.width, 6)}


def backdrop(rgba, rule):
    if rule == 'gray82':
        return GRAY
    # Contrast with the alpha-weighted luminance of visible pixels.
    import numpy as np
    pixels = np.asarray(rgba, dtype=np.float64)
    weight = pixels[..., 3].sum()
    luminance = float((pixels[..., :3] @ [0.2126, 0.7152, 0.0722] * pixels[..., 3]).sum() / weight / 255) if weight else 0.0
    return (40, 40, 40) if luminance >= 0.5 else (215, 215, 215)


def model_input(rgba, policy=None):
    """Derived RGB pixels for EmbeddingGemma and Qwen; returns (image, derivation)."""
    from PIL import Image
    policy = POLICIES[policy or ACTIVE]
    width, height = rgba.size
    image, resample = rgba, []
    if max(width, height) > DISPLAY_EDGE:
        image = rgba.copy()
        image.thumbnail((DISPLAY_EDGE, DISPLAY_EDGE), Image.Resampling.LANCZOS)
        resample.append('lanczos-downscale')
    scale = max(1, math.ceil(policy['min_edge'] / max(image.size)), math.ceil(32 / min(image.size)))
    if max(image.size) * scale > MAX_MODEL_EDGE or image.width * image.height * scale * scale > MAX_PIXELS:
        raise ConfigError('Image aspect ratio is too extreme for a bounded model input')
    if scale > 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
        resample.append('nearest-integer-upscale')
    alpha = image.getchannel('A').getextrema()[0] < 255
    color = backdrop(image, policy['background']) if alpha else None
    output = (Image.alpha_composite(Image.new('RGBA', image.size, color + (255,)), image) if alpha else image).convert('RGB')
    return output, {'policy': policy['name'], 'min_edge': policy['min_edge'], 'background_rule': policy['background'],
                    'background': list(color) if color else None, 'scale': scale, 'resample': resample,
                    'source_size': [width, height], 'size': list(output.size),
                    'note': 'Backdrop fills transparent pixels for model input only; it is not a source color.'}


def png_bytes(image, optimize=False):
    stream = BytesIO()
    image.save(stream, format='PNG', optimize=optimize)
    return stream.getvalue()
