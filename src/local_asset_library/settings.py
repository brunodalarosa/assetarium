"""Application-owned settings shared by the desktop and processing workers."""
import json

from .config import ConfigError
from .publication import atomic_json, read_json

GIB = 1024**3
MAX_BUDGET_GIB = 1048576
PROCESSING_FORMATS = ('fbx', 'gltf', 'obj')
CAPTION_BATCH_SIZES = (1, 2, 4, 8)
DEFAULT_CAPTION_BATCH_SIZE = 8
DEFAULT_SERVER = {'url': 'http://127.0.0.1:8080/v1', 'model': ''}


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


def _saved(config):
    path = settings_path(config)
    return read_json(path) if path.exists() else {}


def validate_descriptions_enabled(value):
    if type(value) is not bool:
        raise ConfigError('Turn descriptions on or off with the switch in Settings → General')
    return value


def descriptions_enabled(config):
    """Optional descriptions (decision 0014); off never deletes, hides or re-queues existing ones."""
    return validate_descriptions_enabled(_saved(config).get('descriptions_enabled', True))


def validate_engine(engine, server):
    from .engines import DESCRIPTION_ENGINES, SERVER
    from .engine_server import checked_model, checked_url
    if engine not in DESCRIPTION_ENGINES:
        raise ConfigError('Choose how descriptions are generated in Settings → General')
    server = server if isinstance(server, dict) else {}
    url, model = server.get('url') or DEFAULT_SERVER['url'], server.get('model') or ''
    if engine == SERVER or url != DEFAULT_SERVER['url'] or model:
        url, model = checked_url(url), checked_model(model)
    return engine, {'url': url, 'model': model}


def description_engine_settings(config):
    value = _saved(config)
    engine, server = validate_engine(value.get('description_engine', 'builtin'), value.get('description_server'))
    return {'engine': engine, 'server': server}


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
        from .library_policy import default_budget
        fallback = default_budget(config)

    return dict(fallback)


SETTING_KEYS = ('storage_budget_gib', 'processing_formats', 'caption_batch_size', 'descriptions_enabled',
                'description_engine', 'description_server')


def general_settings(config):
    engine = description_engine_settings(config)
    return {'status': 'ready', 'storage_budget_gib': storage_budget(config)['total_allocated_bytes'] / GIB,
            'processing_formats': processing_formats(config), 'caption_batch_size': caption_batch_size(config),
            'descriptions_enabled': descriptions_enabled(config), 'description_engine': engine['engine'],
            'description_server': engine['server']}


def validate_budget_gib(value):
    try:
        if isinstance(value, bool):
            raise ValueError
        limit = float(value)
        if not 1 <= limit <= MAX_BUDGET_GIB or not limit.is_integer():
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ConfigError(f'Enter a whole number from 1 to {MAX_BUDGET_GIB:,} GiB') from None
    return int(limit)


def checked_general(config, storage_budget_gib, processing_formats=None, caption_batch_size=None,
                    descriptions_enabled=None, description_engine=None, description_server=None):
    """Validated settings.json content; omitted values keep what is saved. Writes nothing."""
    limit = validate_budget_gib(storage_budget_gib)
    path = settings_path(config)
    value = read_json(path) if path.exists() else {'schema_version': 1}
    formats = validate_formats(processing_formats if processing_formats is not None else
                               value.get('processing_formats', list(PROCESSING_FORMATS)))
    batch = validate_caption_batch_size(caption_batch_size if caption_batch_size is not None else
                                        value.get('caption_batch_size', DEFAULT_CAPTION_BATCH_SIZE))
    enabled = validate_descriptions_enabled(descriptions_enabled if descriptions_enabled is not None else
                                            value.get('descriptions_enabled', True))
    engine, server = validate_engine(description_engine if description_engine is not None else
                                     value.get('description_engine', 'builtin'),
                                     description_server if description_server is not None else value.get('description_server'))
    value.update(schema_version=1, storage_budget_bytes=limit * GIB, processing_formats=formats,
                 caption_batch_size=batch, descriptions_enabled=enabled, description_engine=engine,
                 description_server=server)
    return value


def save_general_settings(config, storage_budget_gib, processing_formats=None, caption_batch_size=None,
                          descriptions_enabled=None, description_engine=None, description_server=None, actor='user'):
    value = checked_general(config, storage_budget_gib, processing_formats, caption_batch_size,
                            descriptions_enabled, description_engine, description_server)
    path = settings_path(config)
    try:
        before = general_settings(config)
    except (ConfigError, OSError, ValueError, KeyError):
        before = {}  # Saving a valid value is how a damaged or missing saved setting gets fixed.
    atomic_json(path, value)
    after = general_settings(config)
    from .setup_core import note_set_by
    note_set_by(config, [key for key in SETTING_KEYS if before.get(key) != after[key]], actor)
    return dict(after, status='saved')


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
