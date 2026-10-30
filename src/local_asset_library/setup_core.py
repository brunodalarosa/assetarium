"""Setup rules shared by the desktop wizard, the CLI and later the MCP tools (decision 0014).

Plain functions returning JSON-able dicts; no GUI imports. Setup records and
validates choices only: it never downloads, installs, processes, renders or starts
a model. The one program it runs is Blender, and only when the user asks for a
check. ``data/library/setup.json`` records the outcome and who set each value.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import threading
import time
import uuid

from .config import ConfigError, load_config, load_project_config, project_config_path
from .publication import atomic_json, read_json

WIZARD_VERSION = 1
ACTORS = ('user', 'agent')
STEPS = ('welcome', 'blender', 'formats', 'storage', 'descriptions', 'batch', 'review')
TESTED_BLENDER = (5, 2)
BLENDER_URL = 'https://www.blender.org/download/'
# Suggestions shown by the Formats step (decision 0009: data, not per-engine code paths).
ENGINE_HINTS = (
    {'id': 'godot', 'label': 'Godot', 'formats': ['gltf'], 'reason': 'Godot’s recommended 3D format.'},
    {'id': 'unity', 'label': 'Unity', 'formats': ['fbx'],
     'reason': 'Unity’s usual interchange format; glTF needs an extra package.'},
    {'id': 'unreal', 'label': 'Unreal', 'formats': ['fbx'],
     'reason': 'Unreal’s standard import path; recent versions also import glTF.'},
    {'id': 'blender-web', 'label': 'Blender / web', 'formats': ['gltf'],
     'reason': 'Open, widely supported, keeps PBR materials.'},
    {'id': 'unsure', 'label': 'Not sure', 'formats': ['fbx', 'gltf', 'obj'], 'reason': 'Processes everything; narrow it later.'},
)
# Built-in engine, 20 assets on one RTX 5070 (12 GiB): data/evidence/caption-batch-benchmark/batching-2026-10-18a.
BATCH_BENCHMARK = ({'size': 1, 'seconds_per_asset': 9.24, 'peak_gib': 4.7}, {'size': 2, 'seconds_per_asset': 5.29, 'peak_gib': 5.3},
                   {'size': 4, 'seconds_per_asset': 3.0, 'peak_gib': 5.8}, {'size': 8, 'seconds_per_asset': 2.22, 'peak_gib': 7.1})
BATCH_BY_VRAM = ((10, 8), (8, 4), (0, 1))  # Measured peak plus about 1.5 GiB for the desktop and other apps.
PROBE = ("import bpy, json; ops = bpy.ops; print('LAL_SETUP_PROBE ' + json.dumps({'gltf': 'gltf' in dir(ops.import_scene), "
         "'fbx': 'fbx' in dir(ops.import_scene), 'obj': 'obj_import' in dir(ops.wm)}), flush=True)")
_validated, _running, _cancelled, _lock = {}, {}, set(), threading.Lock()


def utc():
    return datetime.now(timezone.utc).isoformat()


def setup_path(config):
    return config.storage_root('data') / 'library/setup.json'


def load_record(config):
    """The setup record, or None. A damaged record is reported and never reset."""
    path = setup_path(config)
    if not path.exists():
        return None, None
    try:
        value = read_json(path)
        if not isinstance(value, dict) or value.get('schema_version') != 1:
            raise ValueError('unsupported setup record')
        return value, None
    except (OSError, ValueError) as exc:
        return None, f'The setup record {path.name} could not be read ({exc}); it is kept for review'


def _change(config, update):
    from .gpu_queue import lease
    with lease(config, 'setup', resource='setup'):
        value, fault = load_record(config)
        if fault:
            raise ConfigError(fault)
        value = value or {'schema_version': 1, 'state': 'not_run', 'values': {}}
        update(value)
        value['updated_utc'] = utc()
        atomic_json(setup_path(config), value)
        return value


def checked_actor(actor):
    if actor not in ACTORS:
        raise ConfigError('Unknown setup actor')
    return actor


def note_set_by(config, keys, actor='user'):
    """Remember who last set each value (user or agent); no-op when nothing changed."""
    checked_actor(actor)
    if not keys:
        return None
    stamp = utc()
    return _change(config, lambda value: value.setdefault('values', {}).update(
        {key: {'set_by': actor, 'utc': stamp} for key in keys}))


# ------------------------------- environment -------------------------------

def _run(command, timeout):
    return subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)


def gpu_report(run=_run):
    """NVIDIA GPUs through nvidia-smi; other display adapters by name only. Absence is normal, not a fault."""
    result = {'status': 'none', 'nvidia': [], 'other': []}
    exe = shutil.which('nvidia-smi')
    if exe:
        try:
            fields = 'name,memory.total,driver_version,compute_cap'
            done = run([exe, '--query-gpu=' + fields, '--format=csv,noheader,nounits'], 10)
            if done.returncode:  # Older drivers lack compute_cap.
                fields = 'name,memory.total,driver_version'
                done = run([exe, '--query-gpu=' + fields, '--format=csv,noheader,nounits'], 10)
            if done.returncode:
                raise ValueError((done.stderr or done.stdout or 'nvidia-smi failed').strip()[:200])
            for line in filter(None, (row.strip() for row in done.stdout.splitlines())):
                parts = [part.strip() for part in line.split(',')]
                if len(parts) != len(fields.split(',')):
                    raise ValueError('unexpected nvidia-smi output')
                capability = parts[3] if len(parts) > 3 else None
                result['nvidia'].append({'name': parts[0], 'vram_gib': round(int(float(parts[1])) / 1024, 1),
                                         'driver': parts[2], 'compute_capability':
                                             float(capability) if capability and re.fullmatch(r'\d+(\.\d+)?', capability) else None})
            result['status'] = 'nvidia' if result['nvidia'] else 'none'
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result.update(status='faulty', reason='nvidia-smi could not be read: ' + str(exc))
    result['other'] = other_adapters(run)
    return result


def other_adapters(run=_run):
    """Non-NVIDIA display adapters by name (Windows; read only). Memory is not reported reliably, so it is omitted."""
    if os.name != 'nt':
        return []
    try:
        done = run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                    '(Get-CimInstance Win32_VideoController).Name'], 15)
    except (OSError, subprocess.SubprocessError):
        return []
    names = [line.strip() for line in done.stdout.splitlines() if line.strip()] if not done.returncode else []
    return [name for name in dict.fromkeys(names) if 'nvidia' not in name.lower()][:8]


def os_report():
    system = platform.system()
    if system == 'Windows':
        name = f'Windows {platform.release()}' + (f' {platform.win32_edition()}' if platform.win32_edition() else '')
        return {'system': system, 'name': name, 'version': platform.version()}
    try:
        name = platform.freedesktop_os_release().get('PRETTY_NAME') or system
    except OSError:
        name = system
    return {'system': system, 'name': name, 'version': platform.release()}


def disk_report(config):
    usage = shutil.disk_usage(config.project_root)
    return {'path': str(config.project_root), 'drive': Path(config.project_root).anchor or '/',
            'free_gib': round(usage.free / 1024**3, 1), 'total_gib': round(usage.total / 1024**3, 1)}


def environment_report(config, run=_run):
    """OS, GPUs, free disk and the readiness of every engine. Read only; runs no model."""
    from .engines import DESCRIPTION_ENGINES, SEARCH_DEVICES, gpu_bf16, readiness, search_readiness
    gpu = gpu_report(run)
    return {'status': 'ready', 'os': os_report(), 'gpu': gpu, 'disk': disk_report(config),
            'engines': {key: readiness(config, key, gpu) for key in DESCRIPTION_ENGINES},
            # Per device, so setup can show the checklist for the device being chosen before it is saved.
            'search_devices': {key: search_readiness(config, gpu, key) for key in SEARCH_DEVICES},
            'suggested_search_device': 'cuda' if gpu_bf16(gpu) else 'cpu',
            'recommended_batch': recommended_batch(gpu)}


def recommended_batch(gpu):
    devices = (gpu or {}).get('nvidia') or []
    if not devices:
        return None
    vram = devices[0]['vram_gib']
    return {'size': next(size for floor, size in BATCH_BY_VRAM if vram >= floor), 'vram_gib': vram,
            'may_not_fit': vram < 6}


# ---------------------------------- storage ---------------------------------

def storage_use(config, measure=False):
    """Current allocated use: measured now (read only, can take a while) or the newest processing receipt."""
    free = disk_report(config)['free_gib']
    if measure:
        from .source_storage import measure_all
        report = measure_all(config)
        use = round(report['totals']['allocated_bytes'] / 1024**3, 1)
        return {'status': 'measured', 'allocated_gib': use, 'measured_utc': utc(), 'faults': len(report['faults']),
                'free_gib': free, 'recommended': recommended_budget(use, free)}
    receipts = sorted((config.project_root / 'data/storage').glob('sources-*.json'), key=lambda p: p.stat().st_mtime)
    for path in reversed(receipts[-5:]):
        try:
            use = round(read_json(path)['totals']['allocated_bytes'] / 1024**3, 1)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        return {'status': 'receipt', 'allocated_gib': use, 'free_gib': free, 'recommended': recommended_budget(use, free),
                'measured_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
    return {'status': 'unknown', 'free_gib': free, 'recommended': None}


def recommended_budget(use_gib, free_gib):
    """Current use plus 20 GiB, rounded up to 5 GiB, within 80% of the free space."""
    if use_gib is None:
        return None
    value = math.ceil((use_gib + 20) / 5) * 5
    limit = math.floor(use_gib + 0.8 * free_gib)
    return {'gib': max(1, min(value, limit)), 'limited_by_free_space': value > limit}


# ---------------------------------- blender ---------------------------------

def configured_blender(config):
    """[tools].blender as saved on disk now (the running app's Config is frozen at launch)."""
    try:
        fresh = load_project_config(config.project_root)
    except ConfigError:
        fresh = config
    source = project_config_path(config.project_root)
    return fresh, (str(fresh.blender) if fresh.blender else None), source.name if source.exists() else None


def _same(a, b):
    return bool(a and b) and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def processed_models(config):
    """Finished 3D inspections that a Blender change would mark as pending again (fingerprint input)."""
    from .incremental import working
    from .sources import bound, read_records, registry
    count = 0
    if config.sources_registry:
        for source in registry(config)['sources']:
            count += sum(1 for record in read_records(working(bound(config, source)))
                         if record['processing'].get('inspection') == 'complete' and record.get('asset_type') != 'image')
    return count


def blender_report(config):
    """Configured and discovered executables. Nothing is run."""
    from .inspection import blender_candidates
    fresh, configured, source = configured_blender(config)
    found = blender_candidates(fresh)
    def origin(path):
        if configured and _same(path, configured):
            return 'configured in ' + (source or 'the configuration')
        if shutil.which('blender') and _same(path, shutil.which('blender')):
            return 'found on PATH'
        return 'found in Program Files' if os.name == 'nt' else 'found in a usual install location'
    candidates = [{'path': str(path), 'origin': origin(path), 'validated': _cached(path)} for path in found]
    return {'status': 'ready', 'configured': configured, 'configured_exists': bool(configured and Path(configured).is_file()),
            'config_file': source, 'used': candidates[0]['path'] if candidates else None, 'candidates': candidates,
            'processed_models': processed_models(config), 'download_url': BLENDER_URL,
            'tested_version': '.'.join(map(str, TESTED_BLENDER))}


def _identity(path):
    target = Path(path).resolve()
    info = target.stat()
    return os.path.normcase(str(target)), info.st_size, info.st_mtime_ns


def _cached(path):
    try:
        return _validated.get(_identity(path))
    except OSError:
        return None


def _probe(command, env, timeout, token):
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    with _lock:
        _running[token] = process
    try:
        output, _ = process.communicate(timeout=timeout)
        return process.returncode, output.decode('utf-8', errors='replace'), False
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate()
        return process.returncode, output.decode('utf-8', errors='replace'), True
    finally:
        with _lock:
            _running.pop(token, None)


def cancel_blender_checks():
    """Stops this setup's own Blender probe processes (never a processing worker)."""
    with _lock:
        processes = list(_running.values())
        _cancelled.update(_running)
    for process in processes:
        process.kill()
    return {'status': 'cancelled', 'stopped': len(processes)}


def validate_blender(config, path):
    """Pass/fail per check: executable, version, headless start with scripts disabled, importers."""
    from .inspection import blender_command, environment
    checks, version = [], None
    def check(identifier, label, status, detail=None):
        checks.append({'id': identifier, 'label': label, 'status': status, 'detail': detail})
        return status
    name = 'blender.exe' if os.name == 'nt' else 'blender'
    candidate = Path(path.strip().strip('"')) if isinstance(path, str) and path.strip() else None
    if candidate is None or not candidate.is_absolute():
        check('file', 'Executable', 'failed', 'Choose the full path of ' + name)
    elif (candidate.name.lower() if os.name == 'nt' else candidate.name) != name:
        check('file', 'Executable', 'failed', f'The file must be named {name}; “{candidate.name}” is not run')
    elif not candidate.resolve().is_file():
        check('file', 'Executable', 'failed', 'No file exists at this path')
    else:
        check('file', 'Executable', 'passed', str(candidate))
    if checks[-1]['status'] == 'failed':
        return {'status': 'failed', 'path': path, 'checks': checks, 'version': None}
    token = uuid.uuid4().hex
    env = environment(config)
    started = time.perf_counter()
    def stopped():
        with _lock:
            return token in _cancelled
    def end(status='failed'):
        cancelled = stopped()
        with _lock:
            _cancelled.discard(token)
        return {'status': 'cancelled' if cancelled else status, 'path': str(candidate), 'checks': checks,
                'version': version, 'elapsed_seconds': round(time.perf_counter() - started, 1)}
    code, output, timed_out = _probe([str(candidate), '--version'], env, 30, token)
    found = re.search(r'Blender (\d+)\.(\d+)(?:\.(\d+))?', output)
    if stopped():
        check('version', 'Version', 'failed', 'The check was cancelled')
        return end()
    if timed_out or code or not found:
        check('version', 'Version', 'failed', 'Did not answer within 30 s' if timed_out else
              f'No Blender version output (exit code {code})')
        return end()
    version = '.'.join(g for g in found.groups() if g)
    tested = tuple(int(g) for g in found.groups()[:2]) == TESTED_BLENDER
    check('version', 'Version', 'passed' if tested else 'warning',
          f'Blender {version}' + ('' if tested else f'; tested with {".".join(map(str, TESTED_BLENDER))}, this version may work'))
    code, output, timed_out = _probe(blender_command(candidate, '--python-exit-code', '5', '--python-expr', PROBE), env, 90, token)
    probe = next((line.split(' ', 1)[1] for line in output.splitlines() if line.startswith('LAL_SETUP_PROBE ')), None)
    importers = None
    try:
        importers = json.loads(probe) if probe else None
    except ValueError:
        pass
    if stopped() or timed_out or code or not isinstance(importers, dict):
        check('headless', 'Starts headless with scripts disabled', 'failed',
              'The check was cancelled' if stopped() else 'Did not finish within 90 s' if timed_out
              else f'Exited with code {code}' if code else 'No probe output')
        return end()
    check('headless', 'Starts headless with scripts disabled', 'passed')
    missing = [label for key, label in (('gltf', 'glTF'), ('fbx', 'FBX'), ('obj', 'OBJ')) if not importers.get(key)]
    check('importers', 'Importers: glTF · FBX · OBJ', 'failed' if missing else 'passed',
          ('Missing: ' + ', '.join(missing)) if missing else None)
    statuses = {c['status'] for c in checks}
    status = 'failed' if 'failed' in statuses else 'warning' if 'warning' in statuses else 'passed'
    result = end(status)
    if result['status'] in {'passed', 'warning'}:
        _validated[_identity(candidate)] = {'status': status, 'version': version}
    return result


def toml_string(value):
    if "'" not in value and not any(ord(c) < 32 for c in value):
        return "'" + value + "'"
    return json.dumps(value, ensure_ascii=False)  # JSON escapes are valid TOML basic-string escapes.


HEADER = re.compile(r'^\s*\[\s*([A-Za-z0-9_.-]+)\s*\]\s*(#.*)?$')


def with_blender(text, path):
    """``text`` with ``[tools].blender`` set; every other line is kept byte for byte."""
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.splitlines(keepends=True)
    if any(re.match(r'^\s*(tools\s*[.=]|\[\[)', line) for line in lines):
        raise ConfigError('This configuration defines [tools] in a form setup does not edit; add '
                          f'blender = {toml_string(path)} under [tools] in config.local.toml by hand')
    entry = 'blender = ' + toml_string(path) + newline
    headers = [(i, HEADER.match(line).group(1)) for i, line in enumerate(lines) if HEADER.match(line)]
    start = next((i for i, name in headers if name == 'tools'), None)
    if start is None:
        if lines and not lines[-1].endswith(('\n', '\r')):
            lines[-1] += newline
        return ''.join(lines) + newline + '[tools]' + newline + entry
    end = next((i for i, _ in headers if i > start), len(lines))
    for i in range(start + 1, end):
        if re.match(r'^\s*blender\s*=', lines[i]):
            if re.match(r'^\s*blender\s*=\s*("""|\'\'\')', lines[i]):
                raise ConfigError('The saved Blender path uses a multi-line string; edit config.local.toml by hand')
            lines[i] = entry
            return ''.join(lines)
    lines.insert(start + 1, entry)
    return ''.join(lines)


def write_blender(config, path):
    """Minimal, validated, atomic edit of ignored config.local.toml (decision 0001); created from the example."""
    target = config.project_root / 'config.local.toml'
    base = target if target.is_file() else config.project_root / 'config.example.toml'
    text = with_blender(base.read_bytes().decode('utf-8'), path)
    temporary = target.with_name('.config.local.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_bytes(text.encode('utf-8'))
        loaded = load_config(temporary, config.project_root)
        if str(loaded.blender) != path:
            raise ConfigError('The edited configuration does not read back the chosen Blender path')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return {'status': 'saved', 'path': path, 'file': target.name, 'created': base != target}


def blender_change(config, path):
    """'unchanged' only when the choice is the saved [tools].blender; else 'write'.

    A Blender that is only discovered is not saved: the speed test and render pool need the saved one.
    """
    _, configured, _ = configured_blender(config)
    return 'unchanged' if configured and _same(path, configured) else 'write'


def check_blender(config, path):
    """validate_blender plus what saving it would do ('unchanged' or 'write') and what that re-renders."""
    result = validate_blender(config, path)
    if result['status'] in {'passed', 'warning'}:
        change = blender_change(config, result['path'])
        result.update(change=change, rerender=processed_models(config) if change == 'write' else 0)
    return result


def blender_plan(config, path, confirm_rerender=False):
    """'unchanged' or 'write'; refuses an unchecked path or an unconfirmed re-render. Writes nothing."""
    if not isinstance(path, str) or not path.strip():
        raise ConfigError('Choose a Blender executable or skip the Blender step')
    change = blender_change(config, path)
    if change == 'write':
        if (_cached(path) or {}).get('status') not in {'passed', 'warning'}:
            raise ConfigError('Check this Blender executable before saving it')
        if confirm_rerender is not True and processed_models(config):
            raise ConfigError('Confirm that finished previews will be rendered again with the new Blender')
    return change


def set_blender(config, path, confirm_rerender=False, actor='user'):
    """Save a checked Blender path on its own (CLI, Settings, agent proposals); unchanged choices write nothing."""
    checked_actor(actor)
    if blender_plan(config, path, confirm_rerender) == 'unchanged':
        return {'status': 'unchanged', 'path': path}
    outcome = write_blender(config, path)
    note_set_by(config, ['blender'], actor)
    return outcome


# ----------------------------- state and saving -----------------------------

def first_run(config):
    """Open automatically only on a genuinely fresh install."""
    from .settings import settings_path
    reasons = {'setup_record': setup_path(config).exists(), 'settings': settings_path(config).exists(),
               'sources': bool(config.sources_registry
                               and _registered(config))}
    return {'fresh': not any(reasons.values()), 'existing': reasons}


def _registered(config):
    from .sources import registry
    try:
        value = registry(config)
    except (OSError, ValueError, KeyError, TypeError):
        return True  # A registry that exists but cannot be read is not a fresh install.
    from .library_migration import _legacy_registry
    return bool(value['sources'] or value.get('detached') or _legacy_registry(config))  # Or an install awaiting migration.


def setup_state(config):
    from .engines import DESCRIPTION_ENGINES, SEARCH_DEVICES
    from .settings import general_settings
    record, fault = load_record(config)
    try:
        current, settings_fault = general_settings(config), None
    except (ConfigError, OSError, ValueError, KeyError) as exc:
        current, settings_fault = None, 'Current settings could not be read: ' + str(exc)
    _, configured, source = configured_blender(config)
    run = first_run(config)
    return {'status': 'ready', 'wizard_version': WIZARD_VERSION, 'auto_open': run['fresh'], 'first_run': run,
            'record': record and {k: record.get(k) for k in ('state', 'completed_utc', 'skipped_utc', 'by', 'wizard_version')},
            'record_fault': fault, 'set_by': (record or {}).get('values', {}), 'settings': current,
            'settings_fault': settings_fault, 'blender': {'configured': configured, 'config_file': source},
            'engines': list(DESCRIPTION_ENGINES.values()), 'search_devices': list(SEARCH_DEVICES.values()),
            'hints': list(ENGINE_HINTS),
            'batch_benchmark': list(BATCH_BENCHMARK), 'steps': list(STEPS)}


def save_setup(config, choices, actor='user'):
    """Validate every choice first, then write settings, Blender and the setup record.

    A failed Blender write is reported on its own and keeps the other saved settings.
    """
    from .settings import SETTING_KEYS, checked_general, general_settings, save_general_settings
    checked_actor(actor)
    if not isinstance(choices, dict):
        raise ConfigError('Setup choices must be an object')
    skipped = [step for step in choices.get('skipped_steps') or [] if step in STEPS]
    current = general_settings(config)
    values = {key: choices.get(key, current[key]) for key in SETTING_KEYS}
    checked_general(config, values['storage_budget_gib'], values['processing_formats'], values['caption_batch_size'],
                    values['descriptions_enabled'], values['description_engine'], values['description_server'],
                    values['search_device'])
    blender = choices.get('blender_path')
    change = None
    if blender is not None and 'blender' not in skipped:
        change = blender_plan(config, blender, choices.get('confirm_rerender'))
    saved = save_general_settings(config, values['storage_budget_gib'], values['processing_formats'],
                                  values['caption_batch_size'], values['descriptions_enabled'],
                                  values['description_engine'], values['description_server'], values['search_device'],
                                  actor=actor)
    outcome = {'status': 'unchanged'} if change in {None, 'unchanged'} else None
    if outcome is None:
        try:
            outcome = write_blender(config, blender)
        except (OSError, ConfigError) as exc:
            outcome = {'status': 'faulty', 'reason': 'Blender was not saved: ' + str(exc)}
    stamp = utc()
    chosen = [key for key in SETTING_KEYS if key in choices]
    if outcome['status'] == 'saved':
        chosen.append('blender')
    def update(value):
        value.update(state='completed', completed_utc=stamp, by=actor, wizard_version=WIZARD_VERSION,
                     skipped_steps=skipped, engine_hint=choices.get('engine_hint') if isinstance(choices.get('engine_hint'), str) else None)
        value.setdefault('values', {}).update({key: {'set_by': actor, 'utc': stamp} for key in chosen})
    record = _change(config, update)
    return {'status': 'saved' if outcome['status'] != 'faulty' else 'partial', 'settings': saved, 'blender': outcome,
            'record': {k: record.get(k) for k in ('state', 'completed_utc', 'by', 'wizard_version')}}


def skip_setup(config, actor='user'):
    """Records a skip so setup does not reopen; nothing chosen in the wizard is saved."""
    checked_actor(actor)
    stamp = utc()
    record = _change(config, lambda value: value.update(state='skipped', skipped_utc=stamp, by=actor,
                                                        wizard_version=WIZARD_VERSION))
    return {'status': 'skipped', 'record': {k: record.get(k) for k in ('state', 'skipped_utc', 'by', 'wizard_version')}}


def check_server(config, url, model=''):
    from .engine_server import probe
    return probe(url, model)
