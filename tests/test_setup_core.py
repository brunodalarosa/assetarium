"""Setup rules (decision 0014): environment report, Blender checks and writer, first-run rule, setup record."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import tomllib

import pytest

from local_asset_library import setup_core
from local_asset_library.config import ConfigError, load_config
from local_asset_library.publication import atomic_json
from local_asset_library.settings import general_settings, save_general_settings, settings_path
from test_blender_integration import BLENDER
from test_sources import managed

ROOT = Path(__file__).resolve().parents[1]


def runner(*outputs):
    """Fake subprocess.run answering each call with the next (returncode, stdout)."""
    calls, answers = [], iter(outputs)
    def run(command, timeout):
        calls.append(command)
        code, out = next(answers)
        return SimpleNamespace(returncode=code, stdout=out, stderr='')
    run.calls = calls
    return run


@pytest.fixture
def no_other_adapters(monkeypatch):
    monkeypatch.setattr(setup_core, 'other_adapters', lambda run=None: [])


def test_nvidia_report_parses_present_old_driver_absent_and_malformed(monkeypatch, no_other_adapters):
    monkeypatch.setattr(setup_core.shutil, 'which', lambda name: '/usr/bin/nvidia-smi')
    report = setup_core.gpu_report(runner((0, 'Synthetic GPU 16G, 16384, 999.1, 8.9\n')))
    assert report['status'] == 'nvidia'
    assert report['nvidia'] == [{'name': 'Synthetic GPU 16G', 'vram_gib': 16.0, 'driver': '999.1', 'compute_capability': 8.9}]
    old = runner((6, 'Field "compute_cap" is not a valid field'), (0, 'Older GPU, 6144, 470.0\n'))
    report = setup_core.gpu_report(old)
    assert report['nvidia'][0]['compute_capability'] is None and len(old.calls) == 2
    assert setup_core.gpu_report(runner((0, 'only two, fields\n')))['status'] == 'faulty'
    monkeypatch.setattr(setup_core.shutil, 'which', lambda name: None)
    assert setup_core.gpu_report(runner()) == {'status': 'none', 'nvidia': [], 'other': []}


def test_batch_and_budget_recommendations_follow_their_tables():
    def batch(vram):
        return (setup_core.recommended_batch({'nvidia': [{'vram_gib': vram}]}) or {}).get('size')
    assert [batch(v) for v in (11.9, 10, 9.9, 8, 7.9, 4)] == [8, 8, 4, 4, 1, 1]
    assert setup_core.recommended_batch({'nvidia': [{'vram_gib': 4}]})['may_not_fit']
    assert setup_core.recommended_batch({'nvidia': []}) is None
    assert setup_core.recommended_budget(9.0, 500) == {'gib': 30, 'limited_by_free_space': False}
    assert setup_core.recommended_budget(9.0, 10) == {'gib': 17, 'limited_by_free_space': True}
    assert setup_core.recommended_budget(None, 100) is None
    assert {hint['id'] for hint in setup_core.ENGINE_HINTS if hint['formats'] == ['fbx', 'gltf', 'obj']} == {'unsure'}


def test_blender_checks_refuse_other_programs_without_running_them(tmp_path, monkeypatch):
    config = SimpleNamespace(project_root=tmp_path)
    monkeypatch.setattr(setup_core, '_probe', lambda *a: pytest.fail('nothing may run'))
    other = tmp_path / ('notepad.exe' if os.name == 'nt' else 'bash')
    other.write_bytes(b'x')
    for path, reason in ((str(other), 'must be named'), ('relative/blender', 'full path'),
                         (str(tmp_path / ('blender.exe' if os.name == 'nt' else 'blender')), 'No file')):
        result = setup_core.validate_blender(config, path)
        assert result['status'] == 'failed' and reason in result['checks'][0]['detail']


def test_blender_check_fails_a_program_that_is_not_blender(tmp_path):
    # A real executable under Blender's name that prints no Blender version.
    fake = tmp_path / ('blender.exe' if os.name == 'nt' else 'blender')
    shutil.copy2(sys.executable, fake)
    project = tmp_path / 'project'
    for area in ('data', 'cache', 'scratch'):
        (project / area).mkdir(parents=True)
    config = SimpleNamespace(project_root=project, output_path=lambda area, rel: project / area / rel)
    result = setup_core.validate_blender(config, str(fake))
    assert result['status'] == 'failed'
    assert [c['id'] for c in result['checks']] == ['file', 'version'] and result['checks'][1]['status'] == 'failed'
    assert setup_core._cached(fake) is None


def test_real_blender_passes_every_check(tmp_path, request):
    request.node.user_properties.append(('real_blender', str(BLENDER)))
    if not BLENDER.is_file():
        if os.environ.get('LAL_REQUIRE_BLENDER') == '1':
            pytest.fail(f'Real Blender unavailable ({BLENDER}) (LAL_REQUIRE_BLENDER=1)')
        pytest.skip(f'Real Blender unavailable ({BLENDER})')
    project = tmp_path / 'project'
    config = SimpleNamespace(project_root=project, output_path=lambda area, rel: project / area / rel)
    result = setup_core.validate_blender(config, str(BLENDER))
    assert result['status'] in {'passed', 'warning'}, result
    assert [c['id'] for c in result['checks']] == ['file', 'version', 'headless', 'importers']
    assert result['checks'][3]['status'] == 'passed'
    assert setup_core._cached(BLENDER)['version'] == result['version']


def test_cancel_stops_only_setup_probes(tmp_path):
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    with setup_core._lock:
        setup_core._running['synthetic'] = process
    try:
        assert setup_core.cancel_blender_checks()['stopped'] == 1
        assert process.wait(10) is not None
    finally:
        with setup_core._lock:
            setup_core._running.pop('synthetic', None)
            setup_core._cancelled.discard('synthetic')


EXAMPLE = '''schema_version = 2

[sources]
registry = "data/library/sources.json"

[storage]
data = "data"
models = "models"
cache = "cache"
logs = "logs"
scratch = "scratch"
environment = ".venv"

[tools]
# Unset: Blender is discovered.
#   blender = 'C:\\Program Files\\Blender\\blender.exe'
'''


def test_toml_edit_keeps_every_other_line_and_line_ending():
    edited = setup_core.with_blender(EXAMPLE, r'C:\Tools\Blender 5.2\blender.exe')
    assert edited.replace("blender = 'C:\\Tools\\Blender 5.2\\blender.exe'\n", '') == EXAMPLE
    assert tomllib.loads(edited)['tools']['blender'] == r'C:\Tools\Blender 5.2\blender.exe'
    again = setup_core.with_blender(edited, '/opt/blender-5.2/blender')
    assert sum(line.startswith('blender =') for line in again.splitlines()) == 1 and tomllib.loads(again)['tools']['blender'] == '/opt/blender-5.2/blender'
    crlf = setup_core.with_blender(EXAMPLE.replace('\n', '\r\n'), "/home/o'neil/blender")
    assert '\r\n' in crlf and '\n' not in crlf.replace('\r\n', '')
    assert tomllib.loads(crlf)['tools']['blender'] == "/home/o'neil/blender"
    appended = setup_core.with_blender(EXAMPLE.split('[tools]')[0].rstrip('\n'), '/usr/bin/blender')
    assert tomllib.loads(appended)['tools'] == {'blender': '/usr/bin/blender'}
    for unusual in ('tools.blender = "/x"\n', 'tools = { blender = "/x" }\n', "[tools]\nblender = '''/x'''\n"):
        with pytest.raises(ConfigError, match='by hand'):
            setup_core.with_blender(unusual, '/usr/bin/blender')


def project_with_example(tmp_path):
    root = tmp_path / 'fresh'
    root.mkdir()
    (root / 'config.example.toml').write_text(EXAMPLE, encoding='utf-8')
    return load_config(root / 'config.example.toml', root)


def test_blender_write_creates_local_config_from_the_example_atomically(tmp_path):
    config = project_with_example(tmp_path)
    blender = tmp_path / ('blender.exe' if os.name == 'nt' else 'blender')
    result = setup_core.write_blender(config, str(blender))
    assert result == {'status': 'saved', 'path': str(blender), 'file': 'config.local.toml', 'created': True}
    local = config.project_root / 'config.local.toml'
    assert load_config(local, config.project_root).blender == blender
    assert (config.project_root / 'config.example.toml').read_text(encoding='utf-8') == EXAMPLE
    assert not list(config.project_root.glob('.config.local.*'))
    local.write_text(EXAMPLE.replace('models = "models"', 'models = "elsewhere"'), encoding='utf-8')
    before = local.read_bytes()
    with pytest.raises(ConfigError):  # An edit that does not load is never written.
        setup_core.write_blender(config, str(blender))
    assert local.read_bytes() == before and not list(config.project_root.glob('.config.local.*'))


def test_choosing_what_is_already_used_writes_nothing(tmp_path, monkeypatch):
    config = project_with_example(tmp_path)
    found = tmp_path / ('blender.exe' if os.name == 'nt' else 'blender')
    found.write_bytes(b'x')
    monkeypatch.setattr('local_asset_library.inspection.blender_candidates', lambda c: [found] if not c.blender else [c.blender])
    assert setup_core.blender_change(config, str(found)) == 'unchanged'
    assert setup_core.blender_change(config, str(tmp_path / 'other' / found.name)) == 'write'
    setup_core.write_blender(config, str(found))
    assert setup_core.blender_change(config, str(found)) == 'unchanged'


def test_first_run_matrix(tmp_path):
    config = project_with_example(tmp_path)
    assert setup_core.first_run(config)['fresh'] and setup_core.setup_state(config)['auto_open']
    atomic_json(setup_core.setup_path(config), {'schema_version': 1, 'state': 'skipped'})
    assert not setup_core.first_run(config)['fresh']
    setup_core.setup_path(config).unlink()
    atomic_json(settings_path(config), {'schema_version': 1})
    assert setup_core.first_run(config)['existing']['settings'] and not setup_core.first_run(config)['fresh']
    settings_path(config).unlink()
    atomic_json(config.sources_registry, {'schema_version': 1, 'sources': [{'key': 'x'}]})
    assert setup_core.first_run(config)['existing']['sources'] and not setup_core.first_run(config)['fresh']


def test_existing_sources_are_never_ambushed(tmp_path):
    config, _, _, _ = managed.__wrapped__(tmp_path)
    state = setup_core.setup_state(config)
    assert not state['auto_open'] and state['first_run']['existing']['sources']


@pytest.fixture
def fresh(tmp_path):
    config = project_with_example(tmp_path)
    (config.project_root / 'docs').mkdir()
    (config.project_root / 'docs/library-membership.json').write_text(json.dumps(
        {'budget': {'total_allocated_bytes': 10 * 1024**3, 'peak_additional_allocated_bytes': 3 * 1024**3}}), encoding='utf-8')
    return config


def test_save_validates_everything_before_writing(fresh):
    for bad in ({'storage_budget_gib': 0}, {'processing_formats': ['blend']}, {'caption_batch_size': 3},
                {'descriptions_enabled': 'yes'}, {'description_engine': 'cloud'},
                {'description_engine': 'local-server', 'description_server': {'url': 'http://example.com/v1', 'model': 'm'}},
                {'blender_path': str(fresh.project_root / 'blender.exe')}):
        with pytest.raises(ConfigError):
            setup_core.save_setup(fresh, bad)
    assert not settings_path(fresh).exists() and not setup_core.setup_path(fresh).exists()


def test_save_records_choices_who_set_them_and_skipped_steps(fresh):
    result = setup_core.save_setup(fresh, {'storage_budget_gib': '30', 'processing_formats': ['gltf'], 'descriptions_enabled': False,
                                           'skipped_steps': ['blender', 'batch'], 'engine_hint': 'godot'})
    assert result['status'] == 'saved' and result['blender'] == {'status': 'unchanged'}
    current = general_settings(fresh)
    assert current['storage_budget_gib'] == 30 and current['processing_formats'] == ['gltf'] and not current['descriptions_enabled']
    assert current['caption_batch_size'] == 8  # A skipped step keeps its value.
    record = json.loads(setup_core.setup_path(fresh).read_text(encoding='utf-8'))
    assert record['state'] == 'completed' and record['by'] == 'user' and record['skipped_steps'] == ['blender', 'batch']
    assert {k: v['set_by'] for k, v in record['values'].items()} == {
        'storage_budget_gib': 'user', 'processing_formats': 'user', 'descriptions_enabled': 'user'}
    save_general_settings(fresh, 30, None, 4, actor='agent')
    record = json.loads(setup_core.setup_path(fresh).read_text(encoding='utf-8'))
    assert record['values']['caption_batch_size']['set_by'] == 'agent'
    assert record['values']['storage_budget_gib']['set_by'] == 'user'  # Unchanged values keep who set them.
    with pytest.raises(ConfigError, match='actor'):
        setup_core.save_setup(fresh, {}, actor='cloud')


def test_failed_blender_write_keeps_the_other_settings(fresh, monkeypatch):
    path = str(fresh.project_root / ('blender.exe' if os.name == 'nt' else 'blender'))
    Path(path).write_bytes(b'x')
    setup_core._validated[setup_core._identity(path)] = {'status': 'passed', 'version': '5.2.2'}
    monkeypatch.setattr(setup_core, 'blender_change', lambda config, chosen: 'write')
    monkeypatch.setattr(setup_core, 'processed_models', lambda config: 0)
    monkeypatch.setattr(setup_core, 'write_blender', lambda config, chosen: (_ for _ in ()).throw(OSError('disk is read only')))
    result = setup_core.save_setup(fresh, {'blender_path': path, 'storage_budget_gib': 40})
    assert result['status'] == 'partial' and 'disk is read only' in result['blender']['reason']
    assert general_settings(fresh)['storage_budget_gib'] == 40
    assert 'blender' not in json.loads(setup_core.setup_path(fresh).read_text(encoding='utf-8'))['values']


def test_unconfirmed_rerender_and_unchecked_paths_are_refused(fresh, monkeypatch):
    path = str(fresh.project_root / ('blender.exe' if os.name == 'nt' else 'blender'))
    Path(path).write_bytes(b'x')
    monkeypatch.setattr(setup_core, 'blender_change', lambda config, chosen: 'write')
    with pytest.raises(ConfigError, match='Check this Blender'):
        setup_core.save_setup(fresh, {'blender_path': path})
    setup_core._validated[setup_core._identity(path)] = {'status': 'warning', 'version': '4.4'}
    monkeypatch.setattr(setup_core, 'processed_models', lambda config: 12)
    with pytest.raises(ConfigError, match='rendered again'):
        setup_core.save_setup(fresh, {'blender_path': path})
    assert not settings_path(fresh).exists()
    monkeypatch.setattr(setup_core, 'write_blender', lambda config, chosen: {'status': 'saved', 'path': chosen, 'file': 'config.local.toml'})
    assert setup_core.save_setup(fresh, {'blender_path': path, 'confirm_rerender': True})['blender']['status'] == 'saved'


def test_skip_records_a_skip_and_saves_nothing_else(fresh):
    assert setup_core.skip_setup(fresh)['record']['state'] == 'skipped'
    assert not settings_path(fresh).exists()
    assert not setup_core.setup_state(fresh)['auto_open']


def test_damaged_setup_record_is_reported_and_kept(fresh):
    setup_core.setup_path(fresh).parent.mkdir(parents=True, exist_ok=True)
    setup_core.setup_path(fresh).write_text('{damaged', encoding='utf-8')
    state = setup_core.setup_state(fresh)
    assert 'kept for review' in state['record_fault'] and not state['auto_open']
    with pytest.raises(ConfigError, match='kept for review'):
        setup_core.skip_setup(fresh)
    assert setup_core.setup_path(fresh).read_text(encoding='utf-8') == '{damaged'


def test_environment_report_reads_readiness_without_running_models(fresh, monkeypatch, no_other_adapters):
    monkeypatch.setattr(setup_core.shutil, 'which', lambda name: None)
    report = setup_core.environment_report(fresh)
    builtin = {item['id']: item for item in report['engines']['builtin']['items']}
    assert not builtin['gpu']['ready'] and not builtin['caption_runtime']['ready']
    assert 'caption-runtime' in builtin['caption_runtime']['command'] and 'sync --locked' in builtin['caption_runtime']['command']
    assert 'prepare_caption_model.py' in builtin['caption_weights']['command']
    assert report['engines']['local-server']['items'][0]['ready'] is False
    assert report['recommended_batch'] is None and report['disk']['free_gib'] > 0
