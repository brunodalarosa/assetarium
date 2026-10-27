"""Excluded folders and owner-confirmed duplicate export folders (decision 0019), with synthetic unrelated names."""
from argparse import Namespace

import pytest

from local_asset_library import sources
from local_asset_library.catalog import file_variants
from local_asset_library.config import ConfigError
from local_asset_library.incremental import inspection_input, working
from local_asset_library.mcp_assets import source_variants
from local_asset_library.retrieval import resolved_detail
from local_asset_library.sources import read_records
from test_sources import managed  # noqa: F401 (fixture)

NAMES = ('crate', 'barrel', 'lantern')


def kit(root, extra=None, copy='Engine Copy'):
    """Exports/FBX + Exports/gLTF (recognized) and a third copy whose subfolder is spelled differently."""
    for name in NAMES:
        for folder, sub, suffix, data in (('FBX', 'Props', '.fbx', b'fbx ' + name.encode()),
                                          ('gLTF', 'Props', '.gltf', b'{"asset":{"version":"2.0"}}'),
                                          (copy, 'Prop', '.fbx', b'engine fbx ' + name.encode())):
            path = root / 'Exports' / folder / sub / (name + suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    for relative in extra or ():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'extra')
    return root


@pytest.fixture
def source(managed, tmp_path):
    config = managed[0]
    added = sources.add(config, str(kit(tmp_path / 'kit')))
    sources.scan_source(config, added)
    return config, added


def state(config, source):
    work = working(sources.bound(config, source))
    return read_records(work), sources.source_status(config, source), work


def test_sibling_folders_with_the_same_model_names_are_suggested_not_grouped(source):
    config, added = source
    records, status, _ = state(config, added)
    assert len(records) == 6  # 3 recognized FBX+glTF groups plus 3 standalone copies.
    [suggestion] = status['export_suggestions']
    assert suggestion['anchor'] == 'Exports' and suggestion['folders'] == ['Engine Copy', 'FBX', 'gLTF']
    assert suggestion['grouped_folders'] == ['FBX', 'gLTF'] and suggestion['reference'] == 'FBX'
    assert suggestion['names'] == 3 and sorted(suggestion['sample_names']) == sorted(NAMES)  # Prop vs Props still match.


def test_grouping_keeps_reference_identities_and_finished_inspection_inputs(source):
    config, added = source
    records, status, work = state(config, added)
    grouped = {r['display_name']: r for r in records if len(r['files']) == 2}
    before = {name: inspection_input(work, r)[3] for name, r in grouped.items()}
    sources.decide_export(config, added['key'], status['export_suggestions'][0]['id'], 'group')
    sources.scan_source(config, added)
    records, status, work = state(config, added)
    assert len(records) == 3 and not status['export_suggestions']
    for record in records:
        assert record['asset_id'] == grouped[record['display_name']]['asset_id']
        assert len(record['files']) == 3 and record['grouping']['evidence'][0]['method'] == 'confirmed-sibling-export-v1'
        assert sorted(file_variants(record).values()) == ['Engine Copy', 'FBX', 'gLTF']
        # The rendered file and its inputs are unchanged, so finished previews and descriptions are reused.
        assert inspection_input(work, record)[3] == before[record['display_name']]
    crate = next(r for r in records if r['display_name'] == 'crate')
    assert {v['variant'] for v in source_variants(crate)['source_variants']} == {'Engine Copy', 'FBX', 'gLTF'}
    chosen = resolved_detail(work, crate['asset_id'], 'fbx', 'engine copy')['selected_source']
    assert chosen['variant'] == 'Engine Copy' and '/Engine Copy/' in chosen['path']
    assert resolved_detail(work, crate['asset_id'], 'fbx')['selected_source']['variant'] == 'FBX'
    with pytest.raises(ConfigError, match='Engine Copy, FBX, gLTF'):
        resolved_detail(work, crate['asset_id'], None, 'Godot')


def test_a_changed_folder_stops_grouping_until_its_names_match_again(source, tmp_path):
    config, added = source
    _, status, _ = state(config, added)
    sources.decide_export(config, added['key'], status['export_suggestions'][0]['id'], 'group')
    extra = tmp_path / 'kit/Exports/Engine Copy/Prop/torch.fbx'
    extra.write_bytes(b'new')
    sources.scan_source(config, added)
    records, status, _ = state(config, added)
    assert len(records) == 7 and not any(len(r['files']) == 3 for r in records)  # Never regrouped without the owner.
    extra.unlink()
    sources.scan_source(config, added)
    assert len(state(config, added)[0]) == 3  # The saved answer applies again to the same names.


def test_keep_separate_hides_the_suggestion_and_undo_brings_it_back(source):
    config, added = source
    suggestion = state(config, added)[1]['export_suggestions'][0]
    sources.decide_export(config, added['key'], suggestion['id'], 'separate')
    sources.scan_source(config, added)
    records, status, _ = state(config, added)
    assert len(records) == 6 and not status['export_suggestions']
    assert [d['decision'] for d in status['export_decisions']] == ['separate']
    sources.forget_export(config, added['key'], suggestion['id'])
    sources.scan_source(config, added)
    assert [s['id'] for s in state(config, added)[1]['export_suggestions']] == [suggestion['id']]
    with pytest.raises(ConfigError, match='no longer current'):
        sources.decide_export(config, added['key'], 'f' * 64, 'group')


def test_excluding_the_extra_folders_skips_them_and_restoring_brings_them_back(source):
    config, added = source
    suggestion = state(config, added)[1]['export_suggestions'][0]
    sources.decide_export(config, added['key'], suggestion['id'], 'exclude')
    sources.scan_source(config, added)
    records, status, _ = state(config, added)
    assert status['exclusions'] == ['Exports/Engine Copy'] and len(records) == 3
    assert status['excluded_folders'] == [{'path': 'Exports/Engine Copy', 'files': 3}] and not status['export_suggestions']
    sources.set_excluded_folders(config, added['key'], [])
    sources.scan_source(config, added)
    assert len(state(config, added)[0]) == 6


def test_exclusion_patterns_match_names_or_paths_and_reject_unsafe_values(source):
    config, added = source
    for pattern in ('engine*', 'Exports/Engine Copy', '*COPY'):
        sources.set_excluded_folders(config, added['key'], [pattern])
        sources.scan_source(config, added)
        assert len(state(config, added)[0]) == 3, pattern
    sources.set_excluded_folders(config, added['key'], ['Other/Engine Copy'])  # A path matches only that path.
    sources.scan_source(config, added)
    assert len(state(config, added)[0]) == 6
    for bad in ('', '..', 'a/../b', 'metadata-lal', 'C:/assets', 'x' * 201):
        with pytest.raises(ConfigError):
            sources.set_excluded_folders(config, added['key'], [bad])
    assert sources.validate_exclusion('\\Exports\\Engine Copy\\') == 'Exports/Engine Copy'


def test_small_or_ambiguous_folders_are_not_suggested(managed, tmp_path):
    config = managed[0]
    root = tmp_path / 'small'
    for folder in ('A', 'B'):
        for name in ('one', 'two'):  # Two names are not enough evidence.
            (root / 'Set' / folder).mkdir(parents=True, exist_ok=True)
            (root / 'Set' / folder / (name + '.obj')).write_text('v 0 0 0\n')
    for folder in ('C', 'D'):  # A repeated name inside a folder is ambiguous.
        for sub in ('x', 'y'):
            for name in ('rock', 'tree', 'bush') if sub == 'x' else ('rock',):
                path = root / 'Dup' / folder / sub / (name + '.obj')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('v 0 0 0\n')
    added = sources.add(config, str(root))
    sources.scan_source(config, added)
    assert state(config, added)[1]['export_suggestions'] == []


def test_the_source_worker_runs_a_reuse_only_pass_without_a_model(managed, monkeypatch):
    """After grouping, a stage's dry run finds nothing to compute but stages to mark complete: it must still run."""
    from local_asset_library import engines, incremental, source_operations as operations
    from test_sources import ready_source
    config, backend, one, _ = managed
    ready_source(config, backend, one)
    scoped = sources.bound(config, one)
    operations.state(scoped, operation='describe', status='processing', token='r1')
    calls = []
    def fake(scoped, stage, limit=40, backend=None, dry_run=False, asset_ids=None, **kw):
        calls.append((dry_run, backend))
        return {'pending': 0, 'restored': 0 if len(calls) > 2 else 2, 'outcomes': []}
    monkeypatch.setattr(incremental, 'process', fake)
    monkeypatch.setattr(engines, 'description_engine', lambda c: pytest.fail('Reuse alone must not start a model'))
    operations.worker_stage(config, one, 'caption', 'r1')
    assert calls == [(True, None), (False, None), (True, None)]


def test_the_owner_cli_lists_and_answers_suggestions(source, capsys):
    from local_asset_library.owner_commands import sources_command
    config, added = source
    args = Namespace(action='exports', key=added['key'], group=None, separate=None, exclude=None, undo=None, json=False, quiet=False)
    listed = sources_command(args, config)
    assert 'Engine Copy, FBX, gLTF have the same 3 model names' in capsys.readouterr().out
    assert listed['export_suggestions'][0]['reference'] == 'FBX'
