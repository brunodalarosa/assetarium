"""Application-owned settings shared by the desktop and processing workers."""
import json
import logging

from .config import ConfigError
from .publication import atomic_json, read_json

GIB = 1024**3
MAX_BUDGET_GIB = 1048576
PROCESSING_FORMATS = ('fbx', 'gltf', 'obj')
# Standalone image formats Assetarium can use; each is its own toggle (decision 0026). Textures follow their models.
IMAGE_FORMATS = ('png', 'jpeg', 'svg', 'webp', 'tga', 'tiff', 'bmp', 'gif', 'avif')
ALIASES = {'glb': 'gltf', 'jpg': 'jpeg', 'tif': 'tiff'}
CAPTION_BATCH_SIZES = (1, 2, 4, 8)
DEFAULT_CAPTION_BATCH_SIZE = 8
DEFAULT_SERVER = {'url': 'http://127.0.0.1:8080/v1', 'model': ''}


def validate_formats(value):
    if (not isinstance(value, list) or any(type(item) is not str or item not in PROCESSING_FORMATS for item in value)
            or len(value) != len(set(value))):
        raise ConfigError('Choose processing formats using the FBX, glTF and OBJ checkboxes in Settings → General')
    return [item for item in PROCESSING_FORMATS if item in value]


def format_key(extension):
    """The toggle a file extension belongs to: .glb is glTF, .jpg JPEG, .tif TIFF."""
    return ALIASES.get(extension, extension)


def validate_image_formats(value):
    if (not isinstance(value, list) or any(type(item) is not str or item not in IMAGE_FORMATS for item in value)
            or len(value) != len(set(value))):
        raise ConfigError('Choose image formats using the checkboxes in Settings → General')
    return [item for item in IMAGE_FORMATS if item in value]


def image_formats(config):
    path = settings_path(config)
    value = read_json(path) if path.exists() else {}
    return validate_image_formats(value.get('image_formats', list(IMAGE_FORMATS)))


def used_formats(config):
    """Every format Assetarium uses: the 3D formats and the standalone image formats that are on (decision 0026)."""
    return processing_formats(config) + image_formats(config)


def uses(kind, extensions, formats):
    """Whether Assetarium uses an asset of ``kind`` with these file extensions, given the formats that are on.

    A model or standalone image is hidden when every file is in a format with a toggle that is off. Textures follow
    their models, and file types without a toggle (.blend, audio…) stay listed as not processed.
    """
    if kind not in {'model_3d', 'image'}:
        return True
    toggles = set(PROCESSING_FORMATS if kind == 'model_3d' else IMAGE_FORMATS)
    keys = {format_key(e) for e in extensions}
    return bool(keys & set(formats)) or bool(keys - toggles)


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


SEARCH_DEVICES = ('cuda', 'cpu')


def validate_search_device(value):
    if value not in SEARCH_DEVICES:
        raise ConfigError('Choose where search runs (NVIDIA GPU or CPU) in Settings → General')
    return value


def search_device(config):
    """Device of the search embedder (decision 0018); unset stays CUDA, as before the setting existed."""
    return validate_search_device(_saved(config).get('search_device', 'cuda'))


def validate_search_threads(value, available=None):
    """None (automatic) or a thread count; a saved count above this machine's threads is capped where used."""
    if value is None or value == 'auto' or value == '':
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if available is None:
        from .engines import cpu_threads
        available = cpu_threads()
    if type(value) is not int or not 1 <= value <= available:
        raise ConfigError(f'Choose Automatic or 1 to {available} CPU threads for search in Settings → General')
    return value


def search_threads(config):
    """CPU threads for search data (decision 0022); unset is automatic: the speed test's choice."""
    value = _saved(config).get('search_threads')
    return value if type(value) is int and value >= 1 else None


def format_group(extension):
    return 'gltf' if extension == 'glb' else extension


def inspected_path(record):
    return record.get('primary_inspection_path') or (record.get('technical') or {}).get('inspected_path')


def processing_eligible(record, formats):
    from .asset_structure import asset_type
    if asset_type(record) == 'audio' or record.get('identity_version') == 'subasset-v1':
        return False  # Recognized content, without an implemented processing adapter.
    if asset_type(record) == 'image':
        # ``formats`` comes from used_formats: an image is processed when one of its formats is on.
        from .image_media import FORMATS
        return any(f['format'] in FORMATS and format_key(f['format']) in formats for f in record['files'])
    # Downstream work belongs to the source actually inspected, even when the
    # inventory also contains an enabled alternate. Settings never replace it.
    path = inspected_path(record) if record['processing'].get('inspection') != 'pending' else None
    files = [f for f in record['files'] if not path or f['path'] == path]
    return any(format_group(f['format']) in formats for f in files)


def format_off(record, formats):
    """Why a shown model is left out of processing: its previews came from a file whose format is off, while
    another of its formats is on (so it stays listed). ``{'file', 'format', 'reason'}``; None otherwise.

    Its results stay; descriptions and search by meaning skip it until that format is on (P5: no silent states).
    """
    from .asset_structure import asset_type
    if asset_type(record) != 'model_3d' or record['processing'].get('inspection') == 'pending':
        return None
    path = inspected_path(record)
    source = next((f for f in record['files'] if f['path'] == path), None)
    if source is None or format_group(source['format']) in formats:
        return None
    if not any(format_group(f['format']) in formats for f in record['files']):
        return None  # Every format it has is off: the asset is hidden, not shown with a reason.
    name, shown = path.rsplit('/', 1)[-1], format_group(source['format']).upper().replace('GLTF', 'glTF')
    return {'file': name, 'format': format_group(source['format']),
            'reason': f'Previews were made from {name}, and {shown} is off, so descriptions and search by meaning '
                      f'leave it out. Turn {shown} on to include it again; its results are kept.'}


def turn_format_on(config, extension, actor='user'):
    """Turn one 3D format on and keep every other saved setting (an asset's Turn FBX on)."""
    group = format_group(format_key(str(extension)))
    if group not in PROCESSING_FORMATS:
        raise ConfigError('Only a 3D model format can be turned on here')
    formats = processing_formats(config)
    if group not in formats:
        path = settings_path(config)
        value = read_json(path) if path.exists() else {'schema_version': 1}
        value['processing_formats'] = validate_formats(formats + [group])
        atomic_json(path, value)
        from .setup_core import note_set_by
        note_set_by(config, ['processing_formats'], actor)
        from .logs import kv
        logging.getLogger(__name__).info('General settings saved · %s', kv(by=actor, processing_formats=processing_formats(config)))
    return dict(general_settings(config), status='saved')


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
                'description_engine', 'description_server', 'search_device', 'search_threads', 'image_formats')


def general_settings(config):
    engine = description_engine_settings(config)
    return {'status': 'ready', 'storage_budget_gib': storage_budget(config)['total_allocated_bytes'] / GIB,
            'processing_formats': processing_formats(config), 'caption_batch_size': caption_batch_size(config),
            'descriptions_enabled': descriptions_enabled(config), 'description_engine': engine['engine'],
            'description_server': engine['server'], 'search_device': search_device(config),
            'search_threads': search_threads(config), 'image_formats': image_formats(config)}


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
                    descriptions_enabled=None, description_engine=None, description_server=None, search_device=None,
                    search_threads=None, image_formats=None):
    """Validated settings.json content; omitted values keep what is saved ("auto" clears search_threads). Writes nothing."""
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
    device = validate_search_device(search_device if search_device is not None else value.get('search_device', 'cuda'))
    threads = (value.get('search_threads') if search_threads is None else validate_search_threads(search_threads))
    value.update(schema_version=1, storage_budget_bytes=limit * GIB, processing_formats=formats,
                 caption_batch_size=batch, descriptions_enabled=enabled, description_engine=engine,
                 description_server=server, search_device=device, search_threads=threads,
                 image_formats=validate_image_formats(image_formats if image_formats is not None else
                                                     value.get('image_formats', list(IMAGE_FORMATS))))
    return value


def save_general_settings(config, storage_budget_gib, processing_formats=None, caption_batch_size=None,
                          descriptions_enabled=None, description_engine=None, description_server=None,
                          search_device=None, actor='user', search_threads=None, image_formats=None):
    value = checked_general(config, storage_budget_gib, processing_formats, caption_batch_size,
                            descriptions_enabled, description_engine, description_server, search_device, search_threads,
                            image_formats)
    path = settings_path(config)
    try:
        before = general_settings(config)
    except (ConfigError, OSError, ValueError, KeyError):
        before = {}  # Saving a valid value is how a damaged or missing saved setting gets fixed.
    atomic_json(path, value)
    after = general_settings(config)
    from .setup_core import note_set_by
    changed = [key for key in SETTING_KEYS if before.get(key) != after[key]]
    note_set_by(config, changed, actor)
    if changed:
        from .logs import kv
        logging.getLogger(__name__).info('General settings saved · %s', kv(by=actor, **{k: after[k] for k in changed}))
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
