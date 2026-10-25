"""Retention keeps the active publication, recent history and launch audits (decision 0006)."""
import json
import os
import shutil

from test_sources import managed, ready_source  # noqa: F401  (fixtures)
from local_asset_library import retention, sources
from local_asset_library.publication import read_json


def generation_dirs(config):
    root = config.output_path('data', 'library/generations')
    return {p.name for p in root.iterdir() if retention.GENERATION.fullmatch(p.name)}


def test_publication_keeps_active_and_two_previous_generations(managed):
    config, backend, one, two = managed
    root = config.output_path('data', 'library/generations')
    projections = config.project_root / 'data/library/combined-publications'
    fake = []
    for index in range(4):
        name = 'v_' + f'{index:x}' * 32
        (root / name / 'embeddings').mkdir(parents=True)
        (root / name / 'catalog.sqlite').write_bytes(b'superseded %d' % index)
        (root / name / 'catalog.sqlite').chmod(0o444)  # Publications are read-only.
        os.utime(root / name, ns=(index * 10**9, index * 10**9))
        (projections / f'fake-{index}.json').write_text(json.dumps({'generation': name}), encoding='utf-8')
        fake.append(name)
    ready_source(config, backend, one)  # Publishing the source republishes the combined library.
    sources.aggregate(config)
    active = read_json(config.project_root / 'data/library/active.json')['generation']
    kept = generation_dirs(config)
    assert active in kept and len(kept) == 1 + retention.KEEP_GENERATIONS
    assert not set(fake[:3]) & kept  # Oldest superseded generations are removed.
    for path in projections.glob('*.json'):
        assert read_json(path)['generation'] in kept  # Stale shortcuts are dropped with them.
    receipts = list((config.project_root / 'data/maintenance').glob('generation-retention-*.json'))
    assert len(receipts) == 1 and not json.loads(receipts[0].read_text(encoding='utf-8'))['faults']
    # A retired combination is rebuilt instead of failing as an incomplete saved publication.
    sources.set_enabled(config, one['key'], False)
    assert sources.aggregate(config)['generation'] in generation_dirs(config)


def test_changed_file_is_retained_as_a_fault(tmp_path, monkeypatch):
    root = tmp_path / 'generations'
    old = root / ('v_' + '1' * 32)
    old.mkdir(parents=True)
    (old / 'catalog.sqlite').write_bytes(b'old')
    from local_asset_library import maintenance_files
    real = maintenance_files.remove_manifest
    def changed(base, rows, **options):
        (old / 'catalog.sqlite').write_bytes(b'changed after planning')
        return real(base, rows, **options)
    monkeypatch.setattr(retention, 'remove_manifest', changed)
    outcome = retention.retire(root, [old])
    assert outcome['faults'] and (old / 'catalog.sqlite').read_bytes() == b'changed after planning'


def test_launch_audits_keep_the_ten_newest(managed):
    config = managed[0]
    runs = config.output_path('data', 'gui/runs')
    for index in range(13):
        folder = runs / f'run-{index:02}'
        folder.mkdir(parents=True)
        (folder / 'desktop.jsonl').write_text('{}\n', encoding='utf-8')
        os.utime(folder, ns=(index * 10**9, index * 10**9))
    receipt = retention.retire_gui_runs(config)
    assert sorted(p.name for p in runs.iterdir()) == [f'run-{i:02}' for i in range(3, 13)]
    assert receipt['outcomes'][0]['targets'] == ['run-02', 'run-01', 'run-00']


def test_reused_pytest_basetemp_cleanup_does_not_follow_junctions(tmp_path, directory_link):
    """pytest clears a reused --basetemp with shutil.rmtree; it must never traverse links."""
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'keep.txt').write_text('kept', encoding='utf-8')
    base = tmp_path / 'basetemp'
    base.mkdir()
    link = base / 'linked'
    directory_link(link, outside)
    shutil.rmtree(base)
    assert not base.exists() and (outside / 'keep.txt').read_text(encoding='utf-8') == 'kept'
