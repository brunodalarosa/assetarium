"""Application-owned settings shared by the desktop and processing workers."""
import json

from .config import ConfigError
from .publication import atomic_json, read_json

GIB = 1024**3
MAX_BUDGET_GIB = 1048576


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
    return {'status': 'ready', 'storage_budget_gib': storage_budget(config)['total_allocated_bytes'] / GIB}


def save_general_settings(config, storage_budget_gib):
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
    value.update(schema_version=1, storage_budget_bytes=int(limit) * GIB)
    atomic_json(path, value)
    return dict(general_settings(config), status='saved')
