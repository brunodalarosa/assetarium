"""Owner CLI: the desktop's source, processing, settings and collection actions from a terminal."""
import io
import json
from pathlib import Path

import pytest

from test_sources import managed, ready_source  # noqa: F401  (fixture and helper)
from local_asset_library import asset_collections as collections, owner_commands, source_operations, sources
from local_asset_library.membership import records


class Terminal(io.StringIO):
    def isatty(self):
        return True


def run(config, *argv):
    return owner_commands.main(list(argv), config=config)


def test_owner_commands_route_without_changing_existing_commands():
    wanted = owner_commands.wanted
    assert wanted(['sources', 'list']) and wanted(['--config', 'x.toml', 'settings', 'show'])
    assert wanted(['process', '--asset-source', 'k']) and wanted(['collections', 'delete', 'col_x'])
    # The stage-level maintenance command (library-batch.py) and read commands keep their parser.
    assert not wanted(['process', '--stage', 'inspection', '--limit', '5']) and not wanted(['process', '--dry-run'])
    assert not wanted(['search', 'chair']) and not wanted(['--config', 'sources', 'doctor']) and not wanted([])


def test_settings_round_trip_and_validation(managed, capsys):
    config = managed[0]
    membership = config.project_root / 'docs/library-membership.json'
    value = json.loads(membership.read_text())
    membership.write_text(json.dumps(dict(value, budget={'total_allocated_bytes': 8 * 1024 ** 3,
                                                         'peak_additional_allocated_bytes': 2 * 1024 ** 3})))
    assert run(config, 'settings', 'set', '--formats', 'obj, GLTF', '--batch-size', '4', '--budget-gib', '12') == 0
    capsys.readouterr()
    assert run(config, '--json', 'settings', 'show') == 0
    value = json.loads(capsys.readouterr().out)
    assert value['processing_formats'] == ['gltf', 'obj'] and value['caption_batch_size'] == 4 and value['storage_budget_gib'] == 12
    assert run(config, 'settings', 'set', '--budget-gib', '0') == 2
    assert 'whole number' in capsys.readouterr().err
    assert run(config, 'settings', 'set', '--formats', 'none') == 0
    assert 'none (processing paused)' in capsys.readouterr().out
    assert run(config, 'settings', 'set') == 2


def test_sources_list_enable_disable_images_and_failures(managed, monkeypatch, capsys):
    config, _, one, _ = managed
    started = []
    monkeypatch.setattr(source_operations, 'start', lambda c, op, key: started.append((op, key)) or {'status': 'started'})
    assert run(config, 'sources', 'list') == 0
    assert one['key'] in capsys.readouterr().out
    assert run(config, 'sources', 'disable', one['key']) == 0 and not sources.get_source(config, one['key'])['enabled']
    assert run(config, 'sources', 'enable', one['key']) in {0, 1} and sources.get_source(config, one['key'])['enabled']
    assert run(config, 'sources', 'images', one['key'], 'on') in {0, 1}
    assert started == [('scan', one['key'])] * 2  # Like the app: enabling and image changes rescan; disabling does not.
    capsys.readouterr()
    assert run(config, '--json', 'failures') == 0
    failures = json.loads(capsys.readouterr().out)
    assert failures['status'] == 'ready' and failures['assets'] == 0
    assert run(config, 'sources', 'enable', 'missing-key') == 2


def test_process_follows_progress_and_ctrl_c_cancels_once_then_detaches(managed, monkeypatch, capsys):
    config, _, one, _ = managed
    running = {'status': 'processing', 'phase': 'Inspecting assets and rendering previews', 'progress': .4,
               'completed': 2, 'total': 6, 'token': 't'}
    states, cancels, interrupts = [{'status': 'idle'}], [], iter([KeyboardInterrupt, KeyboardInterrupt])
    monkeypatch.setattr(source_operations, 'start', lambda *a: states.append(running) or {'status': 'started'})
    monkeypatch.setattr(source_operations, 'operation_status', lambda scoped: states[-1])
    monkeypatch.setattr(source_operations, 'cancel', lambda scoped: cancels.append(1) or {'status': 'cancelling'})
    def sleep(_):
        raise next(interrupts)
    monkeypatch.setattr(owner_commands.time, 'sleep', sleep)
    assert run(config, 'process', '--asset-source', one['key']) == 1  # Still processing: not a finished success.
    out = capsys.readouterr().out
    assert '[ 40%] Inspecting assets and rendering previews · 2/6' in out and cancels == [1]
    assert 'Cancelling' in out and 'Stopped watching' in out


def test_process_reports_the_finished_operation_and_optional_descriptions(managed, monkeypatch, capsys):
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    done = {'status': 'complete', 'phase': 'Up to date and published', 'progress': 1}
    monkeypatch.setattr(source_operations, 'start', lambda *a: {'status': 'started'})
    monkeypatch.setattr(source_operations, 'operation_status', lambda scoped: done)
    assert run(config, 'process', '--asset-source', one['key']) == 0
    assert 'complete' in capsys.readouterr().out
    assert run(config, 'process', '--asset-source', one['key'], '--follow') == 0  # Nothing running: says so.
    assert 'No operation is running' in capsys.readouterr().out


def test_deletions_need_an_interactive_owner(managed, monkeypatch, capsys):
    config, backend, one, two = managed
    ready_source(config, backend, one)
    identifier = collections.create(config, 'Shelf', '', [records(config)[0]['asset_id']])['collection_id']
    assert run(config, 'collections', 'delete', identifier) == 2  # Captured output is not a terminal.
    assert 'interactive terminal' in capsys.readouterr().err
    assert run(config, 'sources', 'remove', two['key']) == 2 and sources.get_source(config, two['key'])
    monkeypatch.setattr(owner_commands.sys, 'stdout', Terminal())
    monkeypatch.setattr(owner_commands.sys, 'stdin', Terminal('no\n'))
    assert run(config, 'collections', 'delete', identifier) == 0 and collections.detail(config, identifier)
    monkeypatch.setattr(owner_commands.sys, 'stdin', Terminal('yes\n'))
    assert run(config, 'collections', 'delete', identifier) == 0
    assert not collections.summaries(config)['collections']
    monkeypatch.setattr(owner_commands.sys, 'stdin', Terminal('yes\n'))
    assert run(config, 'sources', 'remove', two['key']) == 0
    assert two['key'] not in {s['key'] for s in sources.registry(config)['sources']}


def test_collection_exports_write_under_data_exports(managed, capsys):
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    identifier = collections.create(config, 'Crates: set/1', '', [r['asset_id'] for r in records(config)[:2]])['collection_id']
    for kind in ('json', 'md', 'png'):
        assert run(config, '--json', 'collections', 'export', identifier, '--format', kind) == 0
        result = json.loads(capsys.readouterr().out)
        path = Path(result['path'])
        assert path.is_file() and path.parent == config.output_path('data', 'exports/collections') and path.name.startswith('Crates set1')
    assert json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))['asset_count'] == 2
    outside = str(config.project_root.parent / 'elsewhere.json')
    assert run(config, 'collections', 'export', identifier, '--format', 'json', '--output', outside) == 2
    assert 'under data/exports' in capsys.readouterr().err
    assert run(config, 'collections', 'export', identifier, '--format', 'json') == 2  # Exists; no terminal to confirm.


def test_description_settings_and_setup_commands(managed, monkeypatch, capsys):
    from local_asset_library import setup_core
    config = managed[0]
    membership = config.project_root / 'docs/library-membership.json'
    value = json.loads(membership.read_text())
    membership.write_text(json.dumps(dict(value, budget={'total_allocated_bytes': 8 * 1024 ** 3,
                                                         'peak_additional_allocated_bytes': 2 * 1024 ** 3})))
    assert owner_commands.wanted(['setup']) and owner_commands.wanted(['setup', 'blender', 'check', 'x'])
    assert run(config, 'settings', 'set', '--descriptions', 'off') == 0
    assert 'Descriptions: off (existing descriptions are kept)' in capsys.readouterr().out
    assert run(config, 'settings', 'set', '--engine', 'local-server', '--server-url', 'http://192.168.0.2:8080/v1',
               '--server-model', 'm') == 2
    assert 'this computer' in capsys.readouterr().err
    assert run(config, 'settings', 'set', '--descriptions', 'on', '--engine', 'local-server', '--server-model', 'vision') == 0
    out = capsys.readouterr().out
    assert 'local-server (http://127.0.0.1:8080/v1, model vision)' in out and 'not used by a local server' in out
    assert run(config, 'setup', 'blender', 'check', str(config.project_root / 'not-blender.txt')) == 1
    assert 'must be named' in capsys.readouterr().out
    monkeypatch.setattr('sys.stdin', io.StringIO())  # No terminal: the guided setup refuses instead of hanging.
    assert run(config, 'setup') == 2
    assert 'interactive terminal' in capsys.readouterr().err
    assert run(config, 'setup', 'skip') == 0
    assert json.loads(setup_core.setup_path(config).read_text(encoding='utf-8'))['state'] == 'skipped'
    monkeypatch.setattr(setup_core, 'gpu_report', lambda run=None: {'status': 'none', 'nvidia': [], 'other': []})
    assert run(config, 'setup', 'status') == 0
    out = capsys.readouterr().out
    assert 'This computer:' in out and 'Engine builtin:' in out and '[miss] NVIDIA GPU with BF16' in out
