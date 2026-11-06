"""Fast startup scans: parse results reused by content hash, one summary log line per scan (decision 0027)."""
import logging
from pathlib import Path

from PIL import Image

from test_sources import managed  # noqa: F401 -- fixture
from local_asset_library import catalog, parse_cache, sources
from local_asset_library.incremental import working
from local_asset_library.membership import records


def scan(config, source, caplog):
    caplog.clear()
    with caplog.at_level(logging.INFO, logger='local_asset_library.sources'):
        sources.scan_source(config, source)
    return next(r.getMessage() for r in caplog.records if r.getMessage().startswith('Scan finished'))


def named(config, source):
    return {r['display_name']: r for r in records(working(sources.bound(config, source)))}


def test_unchanged_scan_parses_nothing_and_a_new_texture_still_resolves(managed, caplog):
    config, _, one, _ = managed
    kit = Path(one['path']) / 'Kit' / 'gltf'
    kit.mkdir(parents=True)
    (kit / 'barrel.gltf').write_text('{"asset":{"version":"2.0"},"images":[{"uri":"paint.png"}]}')
    first = scan(config, one, caplog)
    assert 'reparsed=0' not in first and 'seconds=' in first and 'phases=checking-files:' in first
    assert 'reparsed=0' in scan(config, one, caplog)  # Every model's answer came from the cache.
    Image.new('RGB', (4, 4), 'blue').save(kit / 'paint.png')
    line = scan(config, one, caplog)
    assert 'reparsed=0' in line and 'changed=1' in line  # The glTF was not read again, yet its texture is found.
    paint = next(d for d in named(config, one)['barrel']['dependencies'] if d['reference'] == 'paint.png')
    assert paint['status'] == 'available'


def test_changed_fbx_bytes_are_read_again(managed, caplog):
    config, _, one, _ = managed
    root = Path(one['path']) / 'Kit_1.0' / 'fbx'
    root.mkdir(parents=True)
    for name in ('red', 'blue'):
        Image.new('RGB', (4, 4), name).save(root / f'{name}_diffuse.png')
    chest = root / 'chest.fbx'
    chest.write_bytes(b'Kaydara FBX Binary\x00\x00RelativeFilename\x00\x10red_diffuse.png\x00')
    scan(config, one, caplog)
    assert 'red_diffuse' not in named(config, one) and 'blue_diffuse' in named(config, one)
    chest.write_bytes(b'Kaydara FBX Binary\x00\x00RelativeFilename\x00\x11blue_diffuse.png\x00')
    assert 'reparsed=1' in scan(config, one, caplog)
    assert 'blue_diffuse' not in named(config, one) and 'red_diffuse' in named(config, one)


def test_cached_references_match_a_fresh_parse(managed):
    """The OBJ existing-file choice and a parse stopped by a bad mtllib line replay exactly from the cache."""
    config, _, one, _ = managed
    folder = Path(one['path']) / 'Objs'
    folder.mkdir()
    texts = {'spaces.obj': 'mtllib my mat.mtl\n', 'stopped.obj': 'mtllib "broken\nmtllib after.mtl\n',
             'maps.mtl': 'map_Kd -s 1 1 1 tex.png\nmap_Ka plain.png\n', 'bad.gltf': '{not json'}
    for name, text in texts.items():
        (folder / name).write_text(text)
    scoped = sources.bound(config, one)
    rows = catalog.walk_source(scoped)
    def answers(inventory):
        return {r['path']: catalog.dependencies(scoped, r, inventory)[:2] for r in rows if r['path'].endswith(tuple(texts))}
    fresh = answers({r['path']: r for r in rows})
    with parse_cache.session(scoped) as warm:
        answers({r['path']: r for r in rows})
    with parse_cache.session(scoped) as warm:
        assert answers({r['path']: r for r in rows}) == fresh and warm.misses == 0
    stopped = next(v for k, v in fresh.items() if k.endswith('stopped.obj'))
    assert stopped[0] == [] and stopped[1] == ['Dependency parse failed: No closing quotation']
    (folder / 'my mat.mtl').write_text('')  # Now the exact name exists: one reference, chosen at replay.
    rows = catalog.walk_source(scoped)
    with parse_cache.session(scoped):
        spaced = next(v for k, v in answers({r['path']: r for r in rows}).items() if k.endswith('spaces.obj'))
    assert [d['reference'] for d in spaced[0]] == ['my mat.mtl']


def test_read_failures_are_never_remembered(managed):
    config = managed[0]
    with parse_cache.session(config) as current:
        assert current.remember('references', 'f' * 64, lambda: (['x'], False)) == ['x']
        assert current.remember('references', 'f' * 64, lambda: (['y'], True)) == ['y']
        assert current.misses == 2


def test_license_evidence_keeps_ancestor_folders_only():
    record = {'files': [{'path': 'src/Pack/Kit/Models/a.fbx'}], 'license_evidence': [
        {'path': 'src/Pack/License.txt'}, {'path': 'src/Pack/Kit/License.txt'}, {'path': 'src/Pack/Other/License.txt'},
        {'path': 'src/Pack/Kit/Visit.url'}, {'path': 'src/README-licenses.txt', 'kind': 'collection_note'},
        {'path': 'src/Pack/Kit/Models/a/License.txt'}]}
    assert [e['path'] for e in catalog.relevant_license_evidence(record)] == [
        'src/Pack/License.txt', 'src/Pack/Kit/License.txt', 'src/README-licenses.txt']


def test_unchanged_scan_leaves_the_library_database_alone(managed):
    config, _, one, _ = managed
    from local_asset_library.source_operations import scan_all
    scan_all(config, 'a' * 32)
    path = config.library_store() / 'library.sqlite'
    before = path.stat().st_mtime_ns, path.stat().st_size
    scan_all(config, 'a' * 32)
    assert (path.stat().st_mtime_ns, path.stat().st_size) == before


def test_launch_check_is_quiet_and_reports_what_changed(managed, monkeypatch):
    from local_asset_library import source_operations
    config, _, one, _ = managed
    spawned = []
    class Process:
        pid = 4242
    monkeypatch.setattr(source_operations.subprocess, 'Popen', lambda *a, **k: spawned.append(a) or Process())
    assert source_operations.start(config, 'scan', quiet=True)['status'] == 'started'
    assert source_operations.operation_status(config)['quiet'] is True
    source_operations.state(config, status='complete')
    assert source_operations.start(config, 'scan', one['key'], quiet=True)['status'] == 'started'
    assert source_operations.operation_status(sources.bound(config, one))['quiet'] is False  # Only the all-folder check.
    source_operations.scan_all(config, 'b' * 32)
    source_operations.scan_all(config, 'b' * 32)
    assert source_operations.operation_status(config)['changes'] == {'new': 0, 'changed': 0, 'removed': 0}
    (Path(one['path']) / 'extra.obj').write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n')
    source_operations.scan_all(config, 'b' * 32)
    assert source_operations.operation_status(config)['changes'] == {'new': 1, 'changed': 0, 'removed': 0}
