"""Application-owned settings shared by the desktop and processing workers."""
import json

from .config import ConfigError
from .publication import atomic_json, read_json

GIB = 1024**3
MAX_BUDGET_GIB = 1048576
PROCESSING_FORMATS = ('fbx', 'gltf', 'obj')
CAPTION_BATCH_SIZES = (1, 2, 4, 8)
DEFAULT_CAPTION_BATCH_SIZE = 8


def validate_formats(value):
    if (not isinstance(value, list) or any(type(item) is not str or item not in PROCESSING_FORMATS for item in value)
            or len(value) != len(set(value))):
        raise ConfigError('Choose processing formats using the FBX, glTF and OBJ checkboxes in Settings → General')
    return [item for item in PROCESSING_FORMATS if item in value]


def processing_formats(config):
    path = settings_path(config)
    value = read_json(path) if path.exists() else {}
    return validate_formats(value.get('processing_formats', list(PROCESSING_FORMATS)))


def validate_caption_batch_size(value):
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if type(value) is not int or value not in CAPTION_BATCH_SIZES:
        raise ConfigError('Choose a description batch size of 1, 2, 4 or 8 in Settings → General')
    return value


def caption_batch_size(config):
    path = settings_path(config)
    value = read_json(path) if path.exists() else {}
    return validate_caption_batch_size(value.get('caption_batch_size', DEFAULT_CAPTION_BATCH_SIZE))


def format_group(extension):
    return 'gltf' if extension == 'glb' else extension


def inspected_path(record):
    return record.get('primary_inspection_path') or (record.get('technical') or {}).get('inspected_path')


def processing_eligible(record, formats):
    from .asset_structure import asset_type
    if asset_type(record) == 'audio' or record.get('identity_version') == 'subasset-v1':
        return False  # Recognized content, without an implemented processing adapter.
    if asset_type(record) == 'image':
        # Sources opt in to images; model-format checkboxes do not filter them,
        # but the empty selection still pauses all work.
        from .image_media import FORMATS
        return bool(formats) and any(f['format'] in FORMATS for f in record['files'])
    # Downstream work belongs to the source actually inspected, even when the
    # inventory also contains an enabled alternate. Settings never replace it.
    path = inspected_path(record) if record['processing'].get('inspection') != 'pending' else None
    files = [f for f in record['files'] if not path or f['path'] == path]
    return any(format_group(f['format']) in formats for f in files)


def settings_path(config):
    # Settings belong to the application, even when config is bound to a source.
    return config.storage_root('data') / 'library/settings.json'


def storage_budget(config, fallback=None):
    path = settings_path(config)
    if path.exists():
        value = read_json(path)
        limit = value.get('storage_budget_bytes')
        if (value.get('schema_version') != 1 or type(limit) is not int
                or not GIB <= limit <= MAX_BUDGET_GIB * GIB or limit % GIB):
            raise ConfigError('Invalid saved storage budget; save a valid value in Settings → General')
        # A user-selected total replaces the historical per-run growth cap too.
        # Explicit reserves on older command-line jobs still bound those jobs.
        return {'total_allocated_bytes': limit, 'peak_additional_allocated_bytes': limit}
    if fallback is None:
        value = json.loads((config.project_root / 'docs/library-membership.json').read_text(encoding='utf-8'))
        fallback = value['budget']
    return dict(fallback)


def general_settings(config):
    return {'status': 'ready', 'storage_budget_gib': storage_budget(config)['total_allocated_bytes'] / GIB,
            'processing_formats': processing_formats(config), 'caption_batch_size': caption_batch_size(config)}


def save_general_settings(config, storage_budget_gib, processing_formats=None, caption_batch_size=None):
    try:
        if isinstance(storage_budget_gib, bool):
            raise ValueError
        limit = float(storage_budget_gib)
        if not 1 <= limit <= MAX_BUDGET_GIB or not limit.is_integer():
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ConfigError(f'Enter a whole number from 1 to {MAX_BUDGET_GIB:,} GiB') from None
    path = settings_path(config)
    value = read_json(path) if path.exists() else {'schema_version': 1}
    formats = validate_formats(processing_formats if processing_formats is not None else
                               value.get('processing_formats', list(PROCESSING_FORMATS)))
    batch = validate_caption_batch_size(caption_batch_size if caption_batch_size is not None else
                                        value.get('caption_batch_size', DEFAULT_CAPTION_BATCH_SIZE))
    value.update(schema_version=1, storage_budget_bytes=int(limit) * GIB, processing_formats=formats,
                 caption_batch_size=batch)
    atomic_json(path, value)
    return dict(general_settings(config), status='saved')


# Presentation preferences live apart from settings.json so they never touch budget validation.
APPEARANCES = ('system', 'light', 'dark')
INSPECTOR_WIDTH = (320, 960, 440)  # minimum, maximum, default in CSS pixels


def interface_path(config):
    return config.storage_root('data') / 'library/interface.json'


def interface_settings(config):
    path = interface_path(config)
    try:
        value = read_json(path) if path.exists() else {}
    except Exception:
        value = {}  # A damaged preference file only resets presentation, never library data.
    appearance = value.get('appearance')
    width = value.get('inspector_width')
    low, high, default = INSPECTOR_WIDTH
    return {'status': 'ready', 'appearance': appearance if appearance in APPEARANCES else 'system',
            'inspector_width': width if type(width) is int and low <= width <= high else default}


def save_interface_settings(config, appearance=None, inspector_width=None):
    current = interface_settings(config)
    if appearance is not None:
        if appearance not in APPEARANCES:
            raise ConfigError('Choose Match Windows, Light or Dark in Settings → General')
        current['appearance'] = appearance
    if inspector_width is not None:
        low, high, _ = INSPECTOR_WIDTH
        if isinstance(inspector_width, bool) or not isinstance(inspector_width, (int, float)):
            raise ConfigError('Inspector width must be a number of pixels')
        current['inspector_width'] = int(min(high, max(low, round(inspector_width))))
    atomic_json(interface_path(config), {'schema_version': 1, 'appearance': current['appearance'],
                                         'inspector_width': current['inspector_width']})
    return dict(current, status='saved')
