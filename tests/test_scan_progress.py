"""Scan measurements describe real file work without changing scan results or adding a counting pass."""
from pathlib import Path

from PIL import Image

from test_sources import managed  # noqa: F401
from local_asset_library import catalog, source_operations, sources


def test_scan_reports_discovery_known_image_total_and_finalization(managed):
    config, _, one, _ = managed
    icons = Path(one['path']) / 'Icons'
    icons.mkdir()
    for name in ('one.png', 'two.png'):
        Image.new('RGB', (8, 8), 'blue').save(icons / name)
    events = []
    result = sources.scan_source(config, one, progress=events.append)
    assert result['assets'] == 5
    checked = [e for e in events if e['phase'] == 'Checking files']
    verified = [e for e in events if e['phase'] == 'Verifying files']
    assert checked[-1]['completed'] == verified[-1]['completed'] == 5
    assert all(e['total'] is None for e in checked + verified)
    images = [e for e in events if e['phase'] == 'Classifying images']
    assert images[0]['completed'] == 0 and images[-1]['completed'] == images[-1]['total'] == 2
    assert events[-1]['phase'] == 'Saving catalog' and events[-1]['total'] is None
    again = []
    sources.scan_source(config, one, progress=again.append)
    assert [e for e in again if e['phase'] == 'Checking files'][-1]['reused'] == 5


def test_discovery_counts_faults_separately(managed, monkeypatch):
    config, _, one, _ = managed
    scoped = sources.bound(config, one)
    (Path(one['path']) / 'item1.obj').write_text('# Changed so its previously cached hash cannot mask the injected read fault\nv 7 8 9')
    original = catalog.file_hash
    def hashing(stream):
        if str(stream.name).endswith('item1.obj'):
            raise OSError('Synthetic unreadable file')
        return original(stream)
    monkeypatch.setattr(catalog, 'file_hash', hashing)
    events = []
    rows = catalog.walk_source(scoped, progress=events.append)
    assert len(rows) == 3 and sum(r['status'] == 'rejected' for r in rows) == 1
    assert events[-1]['completed'] == 3 and events[-1]['failed'] == 1


def test_progress_writes_are_throttled_and_phase_boundaries_are_kept(monkeypatch):
    writes = []
    monkeypatch.setattr(source_operations, 'state', lambda config, **value: writes.append(value))
    monkeypatch.setattr(source_operations.time, 'monotonic', lambda: 100)
    report = source_operations.scan_reporter(None)
    for number in range(100):
        report(dict(phase='Checking files', completed=number, total=None, unit='files'))
    report(dict(phase='Classifying images', completed=0, total=10, unit='images'))
    report(dict(phase='Classifying images', completed=10, total=10, unit='images'))
    assert len(writes) == 3 and writes[-1]['metrics']['completed'] == 10
